"""@ajansai.tr sosyal medya yayın kuyruğu (1. adım: içe aktarma ve onay).

`marketing/<hafta>/plan.json` satırları kuyruğa alınır. Her satır bekleyen (pending) olarak başlar;
yönetici onaylar, düzenler ya da atlar. Instagram'a paylaşım ayrı adımda (Vercel Cron) yapılacak.

Saatler İstanbul saatidir (UTC+3, yaz saati uygulaması yok); veritabanına naive UTC yazılır.
"""

import json
import re
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import and_, select

from app.db import get_engine, social_posts, utcnow

ISTANBUL_OFFSET = timedelta(hours=3)

MONTHS = {
    "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "mayis": 5, "haziran": 6,
    "temmuz": 7, "ağustos": 8, "agustos": 8, "eylül": 9, "eylul": 9, "ekim": 10, "kasım": 11,
    "kasim": 11, "aralık": 12, "aralik": 12,
}

# Instagram sınırları (Graph API içerik yayınlama)
CAPTION_MAX = 2200
HASHTAG_MAX = 30
CAROUSEL_MIN, CAROUSEL_MAX = 2, 10

IMAGE_EXT = (".png", ".jpg", ".jpeg")
VIDEO_EXT = (".mp4", ".mov")

# Bu durumlardaki gönderiye yeniden içe aktarma veya düzenleme dokunmaz.
LOCKED = ("published",)


class QueueError(ValueError):
    """Kullanıcıya (yöneticiye) gösterilecek Türkçe hata."""


def parse_week(week: str) -> date:
    try:
        d = date.fromisoformat(week)
    except ValueError as e:
        raise QueueError("Hafta YYYY-AA-GG biçiminde olmalı.") from e
    return d


WEEKDAYS = ["pazartesi", "salı", "çarşamba", "perşembe", "cuma", "cumartesi", "pazar"]


def _tr_lower(s: str) -> str:
    return s.replace("İ", "i").replace("I", "ı").lower()


def weekday_warning(day: str, utc: datetime) -> str | None:
    """Plandaki gün adı tarihle uyuşmuyorsa uyarı (tarih esas alınır)."""
    local = to_istanbul(utc)
    actual = WEEKDAYS[local.weekday()]
    words = re.findall(r"[^\W\d_]+", _tr_lower(day))
    named = next((w for w in words if w in WEEKDAYS), None)
    if named and named != actual:
        return f"'{day}': {local.day}.{local.month:02d}.{local.year} aslında {actual}; paylaşım tarihe göre planlandı."
    return None


def schedule_utc(week: str, day: str, hhmm: str) -> datetime:
    """'Salı 27 Ekim' + '12:30' (İstanbul) → naive UTC. Yıl, haftanın tarihinden alınır."""
    start = parse_week(week)
    m = re.search(r"(\d{1,2})\s+([^\s\d]+)", day or "")
    if not m:
        raise QueueError(f"Gün okunamadı: {day!r}")
    month = MONTHS.get(_tr_lower(m.group(2)))
    if not month:
        raise QueueError(f"Ay adı okunamadı: {day!r}")
    t = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", hhmm or "")
    if not t or int(t.group(1)) > 23 or int(t.group(2)) > 59:
        raise QueueError(f"Saat okunamadı: {hhmm!r}")
    # Aralık sonundaki haftada ocak günleri bir sonraki yıla düşer.
    year = start.year + 1 if month < start.month else start.year
    try:
        d = date(year, month, int(m.group(1)))
    except ValueError as e:
        raise QueueError(f"Geçersiz tarih: {day!r}") from e
    if not (start <= d <= start + timedelta(days=6)):
        raise QueueError(f"{day} bu haftaya ({week}) ait değil.")
    local = datetime(d.year, d.month, d.day, int(t.group(1)), int(t.group(2)))
    return local - ISTANBUL_OFFSET


def to_istanbul(utc: datetime) -> datetime:
    return utc + ISTANBUL_OFFSET


def kind_of(type_label: str, files: list[str]) -> str:
    label = (type_label or "").lower()
    if "reels" in label or (len(files) == 1 and files[0].lower().endswith(VIDEO_EXT)):
        return "reels"
    if "carousel" in label or len(files) > 1:
        return "carousel"
    return "image"


def media_urls(files: list[str], media_base: str | None) -> list[str]:
    out = []
    for f in files:
        f = str(f).strip()
        if f.startswith("https://"):
            out.append(f)
        elif media_base:
            out.append(media_base.rstrip("/") + "/" + f.lstrip("/"))
        else:
            raise QueueError(f"'{f}' için herkese açık adres yok (media_base verin ya da tam https adresi yazın).")
    return out


def problems(kind: str, caption: str, media: list[str]) -> list[str]:
    """Instagram'ın reddedeceği durumlar. Boş liste = paylaşılabilir."""
    out = []
    if not caption.strip():
        out.append("Açıklama boş.")
    if len(caption) > CAPTION_MAX:
        out.append(f"Açıklama {CAPTION_MAX} karakteri aşıyor ({len(caption)}).")
    tags = len(re.findall(r"#\w+", caption))
    if tags > HASHTAG_MAX:
        out.append(f"En fazla {HASHTAG_MAX} etiket olabilir ({tags}).")
    if any(not u.startswith("https://") for u in media):
        out.append("Dosya adresleri https ile başlamalı.")
    lower = [u.lower().split("?")[0] for u in media]
    if kind == "image":
        if len(media) != 1 or not lower[0].endswith(IMAGE_EXT):
            out.append("Gönderi tek bir görsel (png/jpg) olmalı.")
    elif kind == "reels":
        if len(media) != 1 or not lower[0].endswith(VIDEO_EXT):
            out.append("Reels tek bir video (mp4/mov) olmalı.")
    elif kind == "carousel":
        if not (CAROUSEL_MIN <= len(media) <= CAROUSEL_MAX):
            out.append(f"Carousel {CAROUSEL_MIN}-{CAROUSEL_MAX} dosya içermeli ({len(media)}).")
        if any(not u.endswith(IMAGE_EXT + VIDEO_EXT) for u in lower):
            out.append("Carousel dosyaları görsel ya da video olmalı.")
    else:
        out.append(f"Bilinmeyen tür: {kind}")
    return out


def _row(r) -> dict:
    media = json.loads(r.media)
    return {
        "id": r.id, "week": r.week, "idx": r.idx, "kind": r.kind, "title": r.title, "target": r.target,
        "caption": r.caption, "media": media,
        "scheduled_at": r.scheduled_at.isoformat() + "Z",
        "scheduled_local": to_istanbul(r.scheduled_at).strftime("%Y-%m-%d %H:%M"),
        "status": r.status, "ig_media_id": r.ig_media_id, "error": r.error, "approved_by": r.approved_by,
        "problems": problems(r.kind, r.caption, media),
    }


def import_week(week: str, posts: list[dict], media_base: str | None = None) -> dict:
    """plan.json satırlarını kuyruğa alır. Aynı hafta yeniden aktarılırsa bekleyen satırlar güncellenir;
    onaylanmış/atlanmış/paylaşılmış satırlara dokunulmaz (yöneticinin kararı korunur)."""
    start = parse_week(week)
    warnings = []
    if start.weekday() != 0:
        warnings.append(f"{week} pazartesi değil ({WEEKDAYS[start.weekday()]}).")
    prepared = []
    for i, p in enumerate(posts):
        files = [str(f) for f in (p.get("files") or [])]
        try:
            prepared.append({
                "idx": i,
                "kind": kind_of(str(p.get("type") or ""), files),
                "title": str(p.get("title") or "")[:300],
                "target": str(p.get("target") or "")[:120],
                "caption": str(p.get("caption") or ""),
                "media": json.dumps(media_urls(files, media_base), ensure_ascii=False),
                "scheduled_at": schedule_utc(week, str(p.get("day") or ""), str(p.get("time") or "")),
            })
        except QueueError as e:
            raise QueueError(f"{i + 1}. satır: {e}") from e
        w = weekday_warning(str(p.get("day") or ""), prepared[-1]["scheduled_at"])
        if w:
            warnings.append(w)

    created = updated = kept = 0
    now = utcnow()
    with get_engine().begin() as conn:
        existing = {r.idx: r for r in conn.execute(select(social_posts).where(social_posts.c.week == week)).all()}
        for p in prepared:
            old = existing.get(p["idx"])
            if old is None:
                conn.execute(social_posts.insert().values(
                    id=str(uuid.uuid4()), week=week, status="pending", created_at=now, updated_at=now, **p))
                created += 1
            elif old.status == "pending":
                conn.execute(social_posts.update().where(social_posts.c.id == old.id).values(updated_at=now, **p))
                updated += 1
            else:
                kept += 1
    return {"week": week, "created": created, "updated": updated, "kept": kept, "warnings": warnings}


def list_posts(week: str | None = None) -> list[dict]:
    q = select(social_posts).order_by(social_posts.c.scheduled_at, social_posts.c.idx)
    if week:
        q = q.where(social_posts.c.week == week)
    with get_engine().connect() as conn:
        return [_row(r) for r in conn.execute(q).all()]


def get(post_id: str) -> dict | None:
    with get_engine().connect() as conn:
        r = conn.execute(select(social_posts).where(social_posts.c.id == post_id)).first()
    return _row(r) if r else None


def _require(post_id: str) -> dict:
    p = get(post_id)
    if not p:
        raise KeyError(post_id)
    if p["status"] in LOCKED:
        raise QueueError("Bu gönderi paylaşıldı; değiştirilemez.")
    return p


def _set(post_id: str, **values) -> dict:
    with get_engine().begin() as conn:
        conn.execute(social_posts.update().where(social_posts.c.id == post_id).values(updated_at=utcnow(), **values))
    return get(post_id)


def approve(post_id: str, by: str) -> dict:
    p = _require(post_id)
    if p["problems"]:
        raise QueueError("Onaylanamaz: " + " ".join(p["problems"]))
    return _set(post_id, status="approved", approved_by=by, error=None)


def skip(post_id: str) -> dict:
    _require(post_id)
    return _set(post_id, status="skipped")


def edit(post_id: str, caption: str | None = None, scheduled_local: str | None = None) -> dict:
    """Açıklamayı ve/veya İstanbul saatiyle paylaşım zamanını değiştirir. Onaylı gönderi yeniden
    onay beklemeye döner: yönetici son halini görmeden paylaşılmasın."""
    p = _require(post_id)
    values: dict = {}
    if caption is not None:
        values["caption"] = caption
    if scheduled_local is not None:
        try:
            local = datetime.strptime(scheduled_local.strip(), "%Y-%m-%d %H:%M")
        except ValueError as e:
            raise QueueError("Zaman 'YYYY-AA-GG SS:DD' biçiminde olmalı.") from e
        values["scheduled_at"] = local - ISTANBUL_OFFSET
    if not values:
        return p
    if p["status"] == "approved":
        values["status"] = "pending"
        values["approved_by"] = None
    return _set(post_id, **values)


def due(now: datetime | None = None) -> list[dict]:
    """Paylaşım zamanı gelmiş onaylı gönderiler (cron adımında kullanılacak)."""
    now = now or utcnow()
    q = (select(social_posts)
         .where(and_(social_posts.c.status == "approved", social_posts.c.scheduled_at <= now))
         .order_by(social_posts.c.scheduled_at))
    with get_engine().connect() as conn:
        return [_row(r) for r in conn.execute(q).all()]
