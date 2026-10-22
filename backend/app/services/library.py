"""Kullanıcının ürettiği görsel ve videoların kütüphanesi."""

import logging
import uuid

from sqlalchemy import and_, delete, select

from app.db import get_engine, media, utcnow

logger = logging.getLogger("ajansai.library")


def add(user_id: str | None, kind: str, url: str | None, prompt: str = "", source: str = "") -> None:
    """Kalıcı adresli (http) üretimleri kaydeder; hata üretimi bozmaz."""
    if not user_id or not url or not url.startswith("http"):
        return
    try:
        with get_engine().begin() as conn:
            conn.execute(media.insert().values(
                id=str(uuid.uuid4()), user_id=user_id, kind=kind, url=url,
                prompt=(prompt or "")[:500], source=source, created_at=utcnow(),
            ))
    except Exception as e:  # pragma: no cover
        logger.warning("Kütüphaneye eklenemedi: %s", e)


def items(user_id: str, kind: str | None = None, limit: int = 60, before: str | None = None) -> list[dict]:
    cond = [media.c.user_id == user_id]
    if kind:
        cond.append(media.c.kind == kind)
    q = select(media).where(and_(*cond)).order_by(media.c.created_at.desc()).limit(max(1, min(limit, 200)))
    with get_engine().connect() as conn:
        rows = conn.execute(q).all()
    return [
        {"id": r.id, "kind": r.kind, "url": r.url, "prompt": r.prompt, "source": r.source,
         "created_at": r.created_at.isoformat() + "Z"}
        for r in rows
    ]


def remove(user_id: str, item_id: str) -> None:
    with get_engine().begin() as conn:
        conn.execute(delete(media).where(and_(media.c.id == item_id, media.c.user_id == user_id)))
