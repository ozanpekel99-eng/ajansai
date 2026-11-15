"""Meta webhook'u (@ajansai.tr Instagram DM'leri) ve yönetici konuşma listesi."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.routers.admin import _admin
from app.services import instagram_dm

logger = logging.getLogger(__name__)
router = APIRouter()
admin_router = APIRouter()


@router.get("/webhook")
def verify(request: Request):
    q = request.query_params
    challenge = instagram_dm.verify_subscription(q.get("hub.mode"), q.get("hub.verify_token"), q.get("hub.challenge"))
    if challenge is None:
        raise HTTPException(status_code=403, detail="Doğrulama başarısız.")
    return PlainTextResponse(challenge)


@router.post("/webhook")
async def receive(request: Request):
    body = await request.body()
    if not instagram_dm.verify_signature(body, request.headers.get("x-hub-signature-256")):
        raise HTTPException(status_code=401, detail="İmza doğrulanamadı.")
    try:
        event = json.loads(body)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz JSON.")
    try:
        return {"ok": True, **instagram_dm.handle_event(event)}
    except Exception as e:  # noqa: BLE001
        # 200 dönülür: Meta başarısız teslimatları tekrar dener, sürekli hata uygulamayı devre dışı bırakabilir.
        logger.exception("Instagram webhook olayı işlenemedi")
        return {"ok": False, "error": str(e)[:200]}


@admin_router.get("/dm")
def conversations(limit: int = 50, user: dict = Depends(_admin)):
    return {**instagram_dm.status(), "conversations": instagram_dm.list_conversations(min(max(limit, 1), 200))}


@admin_router.get("/dm/{thread}")
def thread(thread: str, user: dict = Depends(_admin)):
    return {"thread": thread, "messages": instagram_dm.thread_messages(thread)}
