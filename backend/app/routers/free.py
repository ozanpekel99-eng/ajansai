"""Ücretsiz araçlar: giriş yapmadan da kullanılabilir, kredi harcamaz."""

import base64
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.security import get_current_user, get_optional_user
from app.services import free_tier, storage
from app.services.llm_service import LLMError

router = APIRouter()
logger = logging.getLogger("ajansai.free")


def client_ip(request: Request) -> str:
    # Vercel gerçek istemci adresini x-forwarded-for'un başına yazar.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "0.0.0.0")


def _subject(request: Request, user: dict | None) -> str:
    return free_tier.subject_for(user, client_ip(request))


def _save_image(data: bytes, mime: str, folder: str) -> str:
    if storage.is_enabled():
        try:
            return storage.save(data, mime, folder)
        except storage.StorageError as e:
            logger.error("Ücretsiz görsel saklanamadı: %s", e)
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


@router.get("/status")
def status(request: Request, user: dict | None = Depends(get_optional_user)):
    """Ücretsiz haklar: bugünkü mesaj ve bu ayki görsel hakkı."""
    return free_tier.status(_subject(request, user), user is not None)


class FreeMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field("", max_length=20000)


class FreeChatRequest(BaseModel):
    messages: list[FreeMessage] = Field(..., min_length=1, max_length=40)


@router.post("/chat")
def chat(payload: FreeChatRequest, request: Request, user: dict | None = Depends(get_optional_user)):
    last = payload.messages[-1]
    if last.role != "user" or not last.content.strip():
        raise HTTPException(status_code=400, detail="Bir mesaj yaz.")
    subject = _subject(request, user)
    try:
        text = free_tier.chat(subject, user is not None, [m.model_dump() for m in payload.messages])
    except free_tier.FreeLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except LLMError as e:
        logger.error("Ücretsiz sohbet yanıtı alınamadı: %s", e)
        raise HTTPException(status_code=503, detail="Yapay zeka şu an yanıt veremedi, hakkın düşülmedi. Birazdan tekrar dene.")
    return {"reply": text, "free": free_tier.status(subject, user is not None)}


class FreeImageRequest(BaseModel):
    concept: str = Field(..., min_length=3, max_length=1500)


@router.post("/image")
def image(payload: FreeImageRequest, request: Request, user: dict | None = Depends(get_optional_user)):
    if not free_tier.image_enabled():
        raise HTTPException(status_code=503, detail="Ücretsiz görsel üretimi henüz açılmadı.")
    subject = _subject(request, user)
    try:
        event_id = free_tier.reserve_image(subject, user is not None)
    except free_tier.FreeLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    try:
        data = free_tier.generate_image(payload.concept)
    except free_tier.FreeServiceError as e:
        logger.error("Ücretsiz görsel üretilemedi: %s", e)
        free_tier.release(event_id)
        return {"image_url": None, "error": "Görsel üretilemedi, hakkın düşülmedi. Tekrar dene.", "free": free_tier.status(subject, user is not None)}
    folder = f"gorsel/{user['id']}" if user else "gorsel/ucretsiz"
    return {
        "image_url": _save_image(data, "image/jpeg", folder),
        "error": None,
        "free": free_tier.status(subject, user is not None),
    }


@router.get("/stock")
def stock(
    request: Request,
    q: str = Query(..., min_length=2, max_length=100),
    orientation: Literal["landscape", "portrait", "square"] | None = None,
    page: int = Query(1, ge=1, le=20),
    user: dict | None = Depends(get_optional_user),
):
    """Pexels'te telifsiz fotoğraf arar (ücretsiz, sınırsız indirme)."""
    if not free_tier.stock_enabled():
        raise HTTPException(status_code=503, detail="Stok fotoğraf kütüphanesi henüz açılmadı.")
    try:
        return free_tier.search_stock(_subject(request, user), q, orientation, page)
    except free_tier.FreeLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except free_tier.FreeServiceError as e:
        logger.error("Stok arama hatası: %s", e)
        raise HTTPException(status_code=503, detail="Fotoğraf kütüphanesine şu an ulaşılamıyor, birazdan tekrar dene.")


class StockSaveRequest(BaseModel):
    photo_id: int = Field(..., gt=0)


@router.post("/stock/save")
def stock_save(payload: StockSaveRequest, user: dict = Depends(get_current_user)):
    """Stok fotoğrafı kullanıcının dosyalarına kopyalar; böylece görsel/video örneği
    ya da reklam görseli olarak kullanılabilir."""
    if not free_tier.stock_enabled():
        raise HTTPException(status_code=503, detail="Stok fotoğraf kütüphanesi henüz açılmadı.")
    if not storage.is_enabled():
        raise HTTPException(status_code=503, detail="Dosya deposu bağlı değil.")
    try:
        data, photo = free_tier.stock_photo_bytes(payload.photo_id)
        url = storage.save(data, "image/jpeg", f"stok/{user['id']}")
    except (free_tier.FreeServiceError, storage.StorageError) as e:
        logger.error("Stok fotoğraf kaydedilemedi: %s", e)
        raise HTTPException(status_code=503, detail="Fotoğraf kaydedilemedi, tekrar dene.")
    return {"url": url, "photo": photo}
