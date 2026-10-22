"""Kullanıcının ürettiği görsel ve videoların kütüphanesi."""

import logging
import uuid

from sqlalchemy import and_, delete, select

from app.db import get_engine, media, utcnow, video_tasks

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
        old_videos = []
        if kind in (None, "video"):
            # Kütüphane öncesi üretilen videolar (ve revizyon için iş kimlikleri)
            old_videos = conn.execute(
                select(video_tasks).where(and_(video_tasks.c.user_id == user_id, video_tasks.c.status == "completed"))
            ).all()
    job_of = {v.video_url: v.id for v in old_videos if v.video_url}
    out = [
        {"id": r.id, "kind": r.kind, "url": r.url, "prompt": r.prompt, "source": r.source, "job_id": job_of.get(r.url),
         "created_at": r.created_at.isoformat() + "Z"}
        for r in rows
    ]
    known = {i["url"] for i in out}
    for v in old_videos:
        if v.video_url and v.video_url not in known:
            out.append({"id": f"v-{v.id}", "kind": "video", "url": v.video_url, "prompt": v.prompt or "Video",
                        "source": "video", "job_id": v.id, "created_at": v.created_at.isoformat() + "Z"})
    out.sort(key=lambda i: i["created_at"], reverse=True)
    return out[:limit]


def remove(user_id: str, item_id: str) -> None:
    with get_engine().begin() as conn:
        if item_id.startswith("v-"):
            from sqlalchemy import update

            conn.execute(update(video_tasks).where(and_(video_tasks.c.id == item_id[2:], video_tasks.c.user_id == user_id))
                         .values(status="hidden"))
            return
        conn.execute(delete(media).where(and_(media.c.id == item_id, media.c.user_id == user_id)))
