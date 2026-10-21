"""Paket, kota ve kullanım takibi.

Kota düşürme işlemleri tek bir koşullu UPDATE ile yapılır
(`... WHERE used < quota`). Böylece aynı anda gelen iki istek kotayı aşamaz.
"""

from datetime import timedelta

from sqlalchemy import and_, select, update

from app.db import get_engine, users, utcnow, video_jobs
from app.services.plans import FREE_PLAN, PLAN_DURATION_DAYS, get_plan

PERIOD_DAYS = 30

_KINDS = {
    "video": ("video_used", "video_quota", "Video"),
    "image": ("image_used", "image_quota", "Görsel"),
    "idea": ("idea_used", "idea_quota", "Fikir"),
}


class QuotaExceededError(Exception):
    pass


class AdsNotAvailableError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


def _refresh_period(conn, row) -> None:
    """Süresi biten paketi deneme paketine düşürür, dolan dönemin kotasını sıfırlar."""
    now = utcnow()
    values = {}

    if row.plan != FREE_PLAN and row.plan_expires_at is not None and row.plan_expires_at <= now:
        values = {
            "plan": FREE_PLAN,
            "plan_expires_at": None,
            "period_start": now,
            "video_used": 0,
            "image_used": 0,
            "idea_used": 0,
        }
    elif now - row.period_start > timedelta(days=PERIOD_DAYS):
        values = {"period_start": now, "video_used": 0, "image_used": 0, "idea_used": 0}

    if values:
        conn.execute(update(users).where(users.c.id == row.id).values(**values))


def get_user(user_id: str) -> dict:
    engine = get_engine()
    with engine.begin() as conn:
        row = conn.execute(select(users).where(users.c.id == user_id)).first()
        if row is None:
            raise UserNotFoundError(user_id)
        _refresh_period(conn, row)
        row = conn.execute(select(users).where(users.c.id == user_id)).first()
    return dict(row._mapping)


def get_usage(user_id: str) -> dict:
    user = get_user(user_id)
    plan = get_plan(user["plan"])
    return {
        "plan": user["plan"],
        "plan_name": plan["name"],
        "plan_expires_at": user["plan_expires_at"].isoformat() + "Z" if user["plan_expires_at"] else None,
        "video": {"used": user["video_used"], "quota": plan["video_quota"]},
        "image": {"used": user["image_used"], "quota": plan["image_quota"]},
        "ideas": {"used": user["idea_used"], "quota": plan["idea_quota"]},
        "ideas_unlimited": plan["ideas_unlimited"],
        "ads_enabled": plan["ads_enabled"],
    }


def consume(user_id: str, kind: str) -> None:
    """Kotadan 1 birim düşer. Kota doluysa QuotaExceededError fırlatır."""
    used_col_name, quota_key, label = _KINDS[kind]
    user = get_user(user_id)  # dönem/paket süresi kontrolü
    plan = get_plan(user["plan"])
    quota = plan[quota_key]
    used_col = users.c[used_col_name]

    condition = users.c.id == user_id
    if quota is not None:
        condition = and_(condition, used_col < quota)

    with get_engine().begin() as conn:
        result = conn.execute(update(users).where(condition).values({used_col_name: used_col + 1}))

    if result.rowcount == 0:
        if quota == 0:
            raise QuotaExceededError(
                f"{label} üretimi '{plan['name']}' paketinde bulunmuyor. Bir paket seçerek açabilirsin."
            )
        raise QuotaExceededError(
            f"{label} kotan doldu ({quota}/{quota}). "
            "Daha yüksek bir pakete geçebilir veya bir sonraki döneme kadar bekleyebilirsin."
        )


def refund(user_id: str, kind: str) -> None:
    """Sağlayıcı hatası yüzünden üretim başarısız olduysa düşülen kotayı geri verir."""
    used_col_name = _KINDS[kind][0]
    used_col = users.c[used_col_name]
    with get_engine().begin() as conn:
        conn.execute(
            update(users)
            .where(and_(users.c.id == user_id, used_col > 0))
            .values({used_col_name: used_col - 1})
        )


def activate_plan(user_id: str, plan_id: str) -> None:
    """Başarılı ödemeden sonra çağrılır: paketi 30 gün için açar, kotayı sıfırlar.

    Aynı paketi süresi bitmeden yenileyen kullanıcının kalan günleri korunur.
    """
    user = get_user(user_id)
    now = utcnow()
    start = now
    if user["plan"] == plan_id and user["plan_expires_at"] and user["plan_expires_at"] > now:
        start = user["plan_expires_at"]

    with get_engine().begin() as conn:
        conn.execute(
            update(users)
            .where(users.c.id == user_id)
            .values(
                plan=plan_id,
                plan_expires_at=start + timedelta(days=PLAN_DURATION_DAYS),
                period_start=now,
                video_used=0,
                image_used=0,
                idea_used=0,
            )
        )


def record_video_job(user_id: str, job_id: str) -> None:
    """Runway job'ı başlatıldıktan sonra, başarısız olursa iade edilebilmesi için kaydedilir."""
    with get_engine().begin() as conn:
        conn.execute(
            video_jobs.insert().values(job_id=job_id, user_id=user_id, released=0, created_at=utcnow())
        )


def get_video_job_owner(job_id: str) -> str | None:
    with get_engine().connect() as conn:
        row = conn.execute(select(video_jobs.c.user_id).where(video_jobs.c.job_id == job_id)).first()
    return row.user_id if row else None


def release_video_if_failed(job_id: str) -> None:
    """Video üretimi başarısız olduysa kotayı geri yükler.

    İdempotent: `released` bayrağı koşullu UPDATE ile çevrildiği için aynı job
    için kaç kez çağrılırsa çağrılsın kota yalnızca bir kez iade edilir.
    """
    with get_engine().begin() as conn:
        result = conn.execute(
            update(video_jobs)
            .where(and_(video_jobs.c.job_id == job_id, video_jobs.c.released == 0))
            .values(released=1)
        )
        if result.rowcount == 0:
            return
        owner = conn.execute(select(video_jobs.c.user_id).where(video_jobs.c.job_id == job_id)).scalar_one()
        conn.execute(
            update(users)
            .where(and_(users.c.id == owner, users.c.video_used > 0))
            .values(video_used=users.c.video_used - 1)
        )


def check_ads_access(user_id: str) -> None:
    user = get_user(user_id)
    plan = get_plan(user["plan"])
    if not plan["ads_enabled"]:
        raise AdsNotAvailableError(
            f"Reklam entegrasyonu '{plan['name']}' paketinde bulunmuyor. "
            "Bu özellik Pro ve üzeri paketlerde kullanılabilir."
        )
