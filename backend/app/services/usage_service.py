"""Paket, kredi ve kullanım takibi.

Kredi düşme tek bir koşullu UPDATE ile yapılır
(`... WHERE credits_used + n <= kredi`). Böylece aynı anda gelen iki istek
bakiyeyi aşamaz. Her harcama `credit_events` tablosuna yazılır; başarısız
üretimde o satır iade edilir (iade idempotent: bir kez yapılır).
"""

import uuid
from datetime import timedelta

from sqlalchemy import and_, select, update

from app.db import credit_events, get_engine, users, utcnow
from app.services.plans import CREDIT_COSTS, FREE_PLAN, PLAN_DURATION_DAYS, get_plan, public_plan

PERIOD_DAYS = 30

ACTION_LABELS = {"idea": "İçerik fikri", "image": "Görsel", "video": "Video", "ads_draft": "Reklam taslağı"}


class QuotaExceededError(Exception):
    pass


class FeatureNotInPlanError(QuotaExceededError):
    pass


class AdsNotAvailableError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


def _reset_values(now) -> dict:
    return {"period_start": now, "credits_used": 0, "video_used": 0, "image_used": 0, "idea_used": 0}


def _refresh_period(conn, row) -> None:
    """Süresi biten paketi deneme paketine düşürür, dolan dönemin kredisini yeniler."""
    now = utcnow()
    values = {}
    if row.plan != FREE_PLAN and row.plan_expires_at is not None and row.plan_expires_at <= now:
        values = {"plan": FREE_PLAN, "plan_expires_at": None, **_reset_values(now)}
    elif now - row.period_start > timedelta(days=PERIOD_DAYS):
        values = _reset_values(now)
    if values:
        conn.execute(update(users).where(users.c.id == row.id).values(**values))


def get_user(user_id: str) -> dict:
    with get_engine().begin() as conn:
        row = conn.execute(select(users).where(users.c.id == user_id)).first()
        if row is None:
            raise UserNotFoundError(user_id)
        _refresh_period(conn, row)
        row = conn.execute(select(users).where(users.c.id == user_id)).first()
    return dict(row._mapping)


def _period_end(user: dict):
    if user["plan_expires_at"]:
        return user["plan_expires_at"]
    return user["period_start"] + timedelta(days=PERIOD_DAYS)


def get_usage(user_id: str) -> dict:
    user = get_user(user_id)
    plan = get_plan(user["plan"])
    total = plan["credits"]
    used = min(user["credits_used"], total)

    with get_engine().connect() as conn:
        counts = {}
        for r in conn.execute(
            select(credit_events.c.action, credit_events.c.detail).where(
                and_(
                    credit_events.c.user_id == user_id,
                    credit_events.c.refunded == 0,
                    credit_events.c.created_at >= user["period_start"],
                )
            )
        ):
            counts[r.action] = counts.get(r.action, 0) + 1

    return {
        "plan": user["plan"],
        "plan_name": plan["name"],
        "plan_expires_at": user["plan_expires_at"].isoformat() + "Z" if user["plan_expires_at"] else None,
        "period_start": user["period_start"].isoformat() + "Z",
        "period_end": _period_end(user).isoformat() + "Z",
        "credits": {"total": total, "used": used, "remaining": total - used},
        "video_enabled": plan["video_enabled"],
        "ads_enabled": plan["ads_enabled"],
        "costs": CREDIT_COSTS,
        "counts": {
            "idea": counts.get("idea", 0),
            "image": counts.get("image", 0),
            "video": counts.get("video", 0),
            "ads_draft": counts.get("ads_draft", 0),
        },
        "plan_details": public_plan(user["plan"]),
    }


def consume(user_id: str, action: str, credits: int, detail: str = "") -> str:
    """Bakiye yetiyorsa `credits` kadar kredi düşer ve harcama kaydının id'sini döndürür."""
    user = get_user(user_id)  # dönem/paket süresi kontrolü
    plan = get_plan(user["plan"])
    label = ACTION_LABELS.get(action, action)

    if action == "video" and not plan["video_enabled"]:
        raise FeatureNotInPlanError(
            f"Video üretimi '{plan['name']}' paketinde bulunmuyor. Başlangıç veya üzeri bir paket seçerek açabilirsin."
        )

    event_id = str(uuid.uuid4())
    with get_engine().begin() as conn:
        result = conn.execute(
            update(users)
            .where(and_(users.c.id == user_id, users.c.credits_used + credits <= plan["credits"]))
            .values(credits_used=users.c.credits_used + credits)
        )
        if result.rowcount == 0:
            remaining = max(plan["credits"] - user["credits_used"], 0)
            raise QuotaExceededError(
                f"Kredin yetmiyor: {label} için {credits} kredi gerekiyor, {remaining} kredin kaldı. "
                "Paketini yükseltebilir veya yenileyebilirsin."
            )
        conn.execute(
            credit_events.insert().values(
                id=event_id,
                user_id=user_id,
                action=action,
                credits=credits,
                detail=detail[:300],
                refunded=0,
                created_at=utcnow(),
            )
        )
    return event_id


def refund(event_id: str) -> None:
    """Sağlayıcı hatası yüzünden üretim başarısız olduysa krediyi geri verir (bir kez)."""
    with get_engine().begin() as conn:
        changed = conn.execute(
            update(credit_events)
            .where(and_(credit_events.c.id == event_id, credit_events.c.refunded == 0))
            .values(refunded=1)
        ).rowcount
        if not changed:
            return
        ev = conn.execute(select(credit_events).where(credit_events.c.id == event_id)).first()
        conn.execute(
            update(users)
            .where(and_(users.c.id == ev.user_id, users.c.credits_used >= ev.credits))
            .values(credits_used=users.c.credits_used - ev.credits)
        )


def list_events(user_id: str, limit: int = 50) -> list[dict]:
    with get_engine().connect() as conn:
        rows = conn.execute(
            select(credit_events)
            .where(credit_events.c.user_id == user_id)
            .order_by(credit_events.c.created_at.desc())
            .limit(limit)
        ).all()
    return [
        {
            "id": r.id,
            "action": r.action,
            "label": ACTION_LABELS.get(r.action, r.action),
            "credits": r.credits,
            "detail": r.detail,
            "refunded": bool(r.refunded),
            "created_at": r.created_at.isoformat() + "Z",
        }
        for r in rows
    ]


def activate_plan(user_id: str, plan_id: str) -> None:
    """Başarılı ödemeden sonra çağrılır: paketi 30 gün için açar, krediyi yeniler.

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
            .values(plan=plan_id, plan_expires_at=start + timedelta(days=PLAN_DURATION_DAYS), **_reset_values(now))
        )


def check_ads_access(user_id: str) -> None:
    user = get_user(user_id)
    plan = get_plan(user["plan"])
    if not plan["ads_enabled"]:
        raise AdsNotAvailableError(
            f"Reklam entegrasyonu '{plan['name']}' paketinde bulunmuyor. "
            "Bu özellik Pro ve üzeri paketlerde kullanılabilir."
        )
