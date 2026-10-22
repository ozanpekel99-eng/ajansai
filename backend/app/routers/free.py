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


class FreeAttachment(BaseModel):
    url: str = Field(..., max_length=2000)
    content_type: str = Field(..., max_length=120)
    name: str = Field("görsel", max_length=200)


class FreeMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field("", max_length=20000)
    attachments: list[FreeAttachment] = Field(default_factory=list, max_length=5)


class FreeChatRequest(BaseModel):
    messages: list[FreeMessage] = Field(..., min_length=1, max_length=40)
    # "image": kullanıcı + menüsünden "Görsel oluştur"u seçti
    mode: Literal["chat", "image", "search"] = "chat"


def make_free_image(subject: str, user: dict | None, prompt: str, refs: list[str], translate: bool) -> tuple[str | None, str | None, bool]:
    """Ücretsiz görsel üretir. (görsel adresi, hata mesajı, sınıra takıldı_mı) döndürür."""
    if not free_tier.image_enabled():
        return None, "Ücretsiz görsel üretimi henüz açılmadı.", False
    try:
        event_id = free_tier.reserve_image(subject, user is not None, with_reference=bool(refs))
    except free_tier.FreeLimitError as e:
        return None, str(e), True
    try:
        ref_bytes = [storage.fetch(u, max_bytes=20 * 1024 * 1024) for u in refs]
        data = free_tier.generate_image(prompt, ref_bytes, translate=translate)
    except (free_tier.FreeServiceError, storage.StorageError) as e:
        logger.error("Ücretsiz görsel üretilemedi: %s", e)
        free_tier.release(event_id)
        return None, "Görsel üretilemedi, hakkın düşülmedi. Tekrar dene.", False
    folder = f"gorsel/{user['id']}" if user else "gorsel/ucretsiz"
    return _save_image(data, "image/jpeg", folder), None, False


def _load_attachments(attachments: list[FreeAttachment]) -> list[dict]:
    """Ücretsiz sohbette görsel ve belge eklenebilir (video ücretli paketlerde)."""
    out = []
    for a in attachments:
        kind = storage.kind_of(a.content_type)
        if kind not in ("image", "document"):
            raise HTTPException(status_code=400, detail=f"{a.name}: video eklemek ücretli paketlerde açık.")
        if not storage.is_own_blob_url(a.url):
            raise HTTPException(status_code=400, detail="Dosyalar ajansAI'a yüklenmiş olmalı.")
        try:
            data = storage.fetch(a.url, max_bytes=20 * 1024 * 1024)
        except storage.StorageError as e:
            raise HTTPException(status_code=400, detail=f"{a.name}: {e}")
        out.append({"kind": kind, "name": a.name, "content_type": a.content_type, "url": a.url, "data": data})
    return out


@router.post("/chat")
def chat(payload: FreeChatRequest, request: Request, user: dict | None = Depends(get_optional_user)):
    """ChatGPT gibi: metin yanıtı; görsel istendiyse görseli de üretip döndürür."""
    last = payload.messages[-1]
    if last.role != "user" or not (last.content.strip() or last.attachments):
        raise HTTPException(status_code=400, detail="Bir mesaj yaz.")
    files = _load_attachments(last.attachments)
    refs = [f["url"] for f in files if f["kind"] == "image"][:2]
    subject = _subject(request, user)
    history = [m.model_dump() for m in payload.messages]
    for m in history[:-1]:
        m["attachments"] = []  # eski eklerin yalnızca son mesajdaki hali kullanılır
    try:
        text, image_prompt, sources = free_tier.chat(
            subject, user is not None, history, files, force_image=payload.mode == "image", force_search=payload.mode == "search"
        )
    except free_tier.FreeLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except free_tier.FreeServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LLMError as e:
        logger.error("Ücretsiz sohbet yanıtı alınamadı: %s", e)
        raise HTTPException(status_code=503, detail="Yapay zeka şu an yanıt veremedi, hakkın düşülmedi. Birazdan tekrar dene.")

    images, image_error = [], None
    if image_prompt:
        url, image_error, _ = make_free_image(subject, user, image_prompt, refs, translate=False)
        if url:
            images.append(url)
    return {
        "reply": text or ("İşte görselin." if images else ""),
        "images": images,
        "image_prompt": image_prompt,
        "image_error": image_error,
        "sources": sources,
        "free": free_tier.status(subject, user is not None),
    }


class FreeImageRequest(BaseModel):
    concept: str = Field(..., min_length=3, max_length=1500)
    reference_urls: list[str] = Field(default_factory=list, max_length=2, description="Örnek görseller (üyelere)")


@router.post("/image")
def image(payload: FreeImageRequest, request: Request, user: dict | None = Depends(get_optional_user)):
    if not free_tier.image_enabled():
        raise HTTPException(status_code=503, detail="Ücretsiz görsel üretimi henüz açılmadı.")
    subject = _subject(request, user)
    refs = payload.reference_urls
    if refs and user is None:
        raise HTTPException(status_code=401, detail="Görselden görsel üretmek için ücretsiz üye ol.")
    if any(not storage.is_own_blob_url(u) for u in refs):
        raise HTTPException(status_code=400, detail="Örnek görseller ajansAI'a yüklenmiş olmalı.")
    url, error, limited = make_free_image(subject, user, payload.concept, refs, translate=True)
    if limited:
        raise HTTPException(status_code=429, detail=error)
    return {"image_url": url, "error": error, "free": free_tier.status(subject, user is not None)}


@router.get("/stock")
def stock(
    request: Request,
    q: str = Query(..., min_length=2, max_length=100),
    orientation: Literal["landscape", "portrait", "square"] | None = None,
    page: int = Query(1, ge=1, le=20),
    user: dict | None = Depends(get_optional_user),
):
    """Pixabay'de (yoksa Pexels'te) telifsiz fotoğraf arar (ücretsiz, sınırsız indirme)."""
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
