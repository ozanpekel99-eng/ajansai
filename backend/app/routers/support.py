"""support@ajansai.tr gelen e-posta webhook'u (Resend)."""

import json
import logging

from fastapi import APIRouter, HTTPException, Request

from app import config
from app.services import support

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/inbound")
async def inbound(request: Request):
    body = await request.body()
    if not support.verify_signature(dict(request.headers), body):
        raise HTTPException(status_code=401, detail="İmza doğrulanamadı.")
    try:
        event = json.loads(body)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz JSON.")
    if event.get("type") != "email.received":
        return {"ok": True, "ignored": event.get("type")}
    email_id = (event.get("data") or {}).get("email_id")
    if not email_id:
        raise HTTPException(status_code=400, detail="email_id yok.")
    to = [a.lower() for a in (event.get("data") or {}).get("to") or []]
    if to and not any(config.SUPPORT_ADDRESS.lower() in a for a in to):
        # Alan adındaki başka adreslere gelenler yalnızca iletilir, otomatik yanıtlanmaz
        logger.info("Destek dışı adrese e-posta: %s", to)
    try:
        return {"ok": True, **support.handle_inbound(email_id)}
    except support.SupportError as e:
        logger.error("Destek e-postası işlenemedi: %s", e)
        # 200 dönülür: Resend'in tekrar denemesi aynı hatayı üretir; kayıt "error" olarak tutulur.
        return {"ok": False, "error": str(e)[:200]}


@router.get("/status")
def status():
    return {
        "receiving": bool(config.RESEND_API_KEY and config.RESEND_WEBHOOK_SECRET),
        "auto_reply": config.SUPPORT_AUTO_REPLY,
        "forward": bool(config.SUPPORT_FORWARD_TO),
    }
