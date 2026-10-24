"""Ücretsiz kullanıcı dosyalarının saklama süresi.

Misafirlerin ve hiç ödeme yapmamış ücretsiz üyelerin ürettiği/yüklediği dosyalar
FREE_RETENTION_DAYS (varsayılan 7) gün sonra Blob'dan silinir, kütüphane kayıtları da kaldırılır.
Bir kez başarılı ödeme yapmış (paketi bitmiş olsa bile) kullanıcıların ve yöneticilerin
dosyalarına dokunulmaz. Kalite testi (qa/) ve karşılaştırma (bench/) klasörleri kapsam dışıdır.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, select

from app import config
from app.db import get_engine, media, payments, users
from app.services import storage

logger = logging.getLogger("ajansai.retention")

# Kullanıcıya ait dosya klasörleri: <klasör>/<sahip>/...
PREFIXES = ("gorsel/", "video/", "dosya/", "yuklemeler/", "stok/")
GUEST_OWNERS = {"ucretsiz", "misafir"}


def protected_user_ids() -> set[str]:
    with get_engine().connect() as conn:
        paid = {r[0] for r in conn.execute(
            select(payments.c.user_id).where(and_(payments.c.status == "success", payments.c.sandbox.is_(False)))
        )}
        rows = conn.execute(select(users.c.id, users.c.email, users.c.plan)).all()
    admins = {r.id for r in rows if (r.email or "").lower() in config.ADMIN_EMAILS}
    on_paid_plan = {r.id for r in rows if r.plan != "deneme"}
    return paid | admins | on_paid_plan


def _uploaded_at(b: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(str(b.get("uploadedAt", "")).replace("Z", "+00:00"))
    except ValueError:
        return None


def expired_free_blobs(now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=config.FREE_RETENTION_DAYS)
    keep = protected_user_ids()
    out = []
    for prefix in PREFIXES:
        for b in storage.list_blobs(prefix):
            parts = str(b.get("pathname", "")).split("/")
            if len(parts) < 3:
                continue  # sahibi belli olmayan dosyaya dokunma
            owner = parts[1]
            if owner in keep or (owner not in GUEST_OWNERS and len(owner) != 36):
                continue
            ts = _uploaded_at(b)
            if ts and ts < cutoff:
                out.append(b)
    return out


def run(dry_run: bool = False) -> dict:
    blobs = expired_free_blobs()
    urls = [b["url"] for b in blobs]
    size = sum(int(b.get("size") or 0) for b in blobs)
    if not dry_run and urls:
        storage.delete(urls)
        with get_engine().begin() as conn:
            for i in range(0, len(urls), 500):
                conn.execute(delete(media).where(media.c.url.in_(urls[i : i + 500])))
    logger.info("Saklama temizliği: %s dosya, %.1f MB%s", len(urls), size / 1e6, " (deneme)" if dry_run else "")
    return {"deleted": 0 if dry_run else len(urls), "candidates": len(urls), "mb": round(size / 1e6, 1), "dry_run": dry_run}
