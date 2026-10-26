"""@ajansai.tr Instagram DM'leri: Meta webhook'unu doğrular, mesajları kaydeder, konuşmaları listeler.

Akış (1. adım): Meta, hesaba gelen her DM için /api/meta/webhook'a `object: "instagram"` olayı gönderir →
imza (X-Hub-Signature-256, META_APP_SECRET ile HMAC-SHA256) doğrulanır → mesajlar `instagram_messages`
tablosuna yazılır (mid tekil, tekrar gelen olay ikinci kez kaydedilmez). Hesaptan gönderilen mesajlar
(`is_echo`, ör. Instagram uygulamasından elle verilen cevaplar) "out" olarak aynı konuşmaya eklenir.
Otomatik yanıt (Claude) sonraki adımda eklenecek; INSTAGRAM_DM_AUTO_REPLY kapalıyken hiçbir mesaj gönderilmez.
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

from app import config
from app.db import get_engine, instagram_messages, utcnow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- webhook doğrulama


def verify_subscription(mode: str | None, token: str | None, challenge: str | None) -> str | None:
    """Meta'nın abonelik doğrulaması (GET). Doğruysa geri gönderilecek challenge, değilse None."""
    expected = config.META_WEBHOOK_VERIFY_TOKEN
    if not expected or mode != "subscribe" or not token or challenge is None:
        return None
    if not hmac.compare_digest(token.encode(), expected.encode()):
        return None
    return challenge


def verify_signature(body: bytes, header: str | None, secret: str | None = None) -> bool:
    """X-Hub-Signature-256: `sha256=<hex HMAC-SHA256(body, app secret)>`."""
    secret = secret if secret is not None else (config.META_APP_SECRET or "").strip()
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header.removeprefix("sha256=").strip().lower(), expected)


# ---------------------------------------------------------------- olayları ayrıştırma


def _ts(ms) -> datetime:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError, OverflowError, OSError):
        return utcnow()


def parse_event(event: dict) -> list[dict]:
    """Webhook gövdesinden kaydedilecek mesajları çıkarır. Okundu, tepki, silinen mesaj vb. atlanır."""
    if not isinstance(event, dict) or event.get("object") != "instagram":
        return []
    out = []
    for entry in event.get("entry") or []:
        account = str((entry or {}).get("id") or "")
        for m in (entry or {}).get("messaging") or []:
            msg = (m or {}).get("message")
            if not isinstance(msg, dict) or not msg.get("mid") or msg.get("is_deleted"):
                continue
            sender = str(((m.get("sender") or {}).get("id")) or "")
            recipient = str(((m.get("recipient") or {}).get("id")) or "")
            echo = bool(msg.get("is_echo"))
            thread = recipient if echo else sender
            if not thread:
                continue
            attachments = [
                {"type": str(a.get("type") or ""), "url": str((a.get("payload") or {}).get("url") or "")}
                for a in msg.get("attachments") or [] if isinstance(a, dict)
            ]
            out.append({
                "id": str(msg["mid"])[:200],
                "thread": thread[:64],
                "ig_account": (account or (sender if echo else recipient))[:64],
                "direction": "out" if echo else "in",
                "text": str(msg.get("text") or "")[:4000],
                "attachments": attachments,
                "sent_at": _ts(m.get("timestamp")),
            })
    return out


def save_message(m: dict) -> bool:
    """Mesajı kaydeder. Aynı mid daha önce geldiyse False (yinelenen webhook)."""
    try:
        with get_engine().begin() as conn:
            conn.execute(insert(instagram_messages).values(
                id=m["id"], thread=m["thread"], ig_account=m["ig_account"], direction=m["direction"],
                text=m["text"], attachments=json.dumps(m["attachments"], ensure_ascii=False) if m["attachments"] else None,
                status="sent" if m["direction"] == "out" else "received", note=None,
                sent_at=m["sent_at"], created_at=utcnow(),
            ))
        return True
    except IntegrityError:
        return False


def handle_event(event: dict) -> dict:
    """Webhook olayını işler: yeni mesajları kaydeder. Otomatik yanıt sonraki adımda (bayrakla) eklenecek."""
    saved = duplicates = 0
    for m in parse_event(event):
        if save_message(m):
            saved += 1
        else:
            duplicates += 1
    return {"saved": saved, "duplicates": duplicates}


# ---------------------------------------------------------------- yönetici listesi


def _row(r) -> dict:
    return {
        "id": r.id, "direction": r.direction, "text": r.text,
        "attachments": json.loads(r.attachments) if r.attachments else [],
        "status": r.status, "note": r.note, "sent_at": r.sent_at.isoformat() + "Z",
    }


def list_conversations(limit: int = 50) -> list[dict]:
    """Son mesaja göre sıralı konuşmalar; son mesaj müşteriden geldiyse `awaiting_reply`."""
    t = instagram_messages
    with get_engine().connect() as conn:
        threads = conn.execute(
            select(t.c.thread, func.count().label("n"), func.max(t.c.sent_at).label("last"))
            .group_by(t.c.thread).order_by(func.max(t.c.sent_at).desc()).limit(limit)
        ).all()
        result = []
        for th in threads:
            last = conn.execute(
                select(t).where(t.c.thread == th.thread).order_by(t.c.sent_at.desc(), t.c.created_at.desc()).limit(1)
            ).first()
            result.append({
                "thread": th.thread,
                "messages": th.n,
                "last_at": th.last.isoformat() + "Z",
                "last": _row(last),
                "awaiting_reply": last.direction == "in",
            })
    return result


def thread_messages(thread: str, limit: int = 200) -> list[dict]:
    t = instagram_messages
    with get_engine().connect() as conn:
        rows = conn.execute(
            select(t).where(t.c.thread == thread).order_by(t.c.sent_at.desc(), t.c.created_at.desc()).limit(limit)
        ).all()
    return [_row(r) for r in reversed(rows)]


def status() -> dict:
    return {
        "receiving": bool(config.META_WEBHOOK_VERIFY_TOKEN and (config.META_APP_SECRET or "").strip()),
        "auto_reply": config.INSTAGRAM_DM_AUTO_REPLY,
    }
