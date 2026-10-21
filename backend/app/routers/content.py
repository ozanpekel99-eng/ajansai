import base64
import json
import logging
import uuid
from typing import Literal

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, select, update

from app.db import get_engine, utcnow, video_tasks
from app.security import get_current_user
from app.services import assistant, gateway_media, storage
from app.services.claude_service import generate_content_ideas
from app.services.llm_service import LLMError
from app.services.plans import CREDIT_COSTS, chat_cost, idea_cost, video_cost
from app.services.usage_service import QuotaExceededError, consume, refund

router = APIRouter()
logger = logging.getLogger("ajansai.content")


def _charge(user_id: str, action: str, credits: int, detail: str) -> str:
    try:
        return consume(user_id, action, credits, detail)
    except QuotaExceededError as e:
        raise HTTPException(status_code=402, detail=str(e))


class ContentIdeaRequest(BaseModel):
    business_name: str = Field(..., max_length=200, examples=["Cafe Lorem"])
    sector: str = Field(..., max_length=200, examples=["Kafe / Restoran"])
    target_audience: str = Field(..., max_length=500, examples=["25-40 yaş, şehirde yaşayan genç profesyoneller"])
    tone: str = Field(..., max_length=200, examples=["Samimi ve eğlenceli"])
    topic: str = Field(..., max_length=1000, examples=["Yeni sezon soğuk kahve menüsü"])
    idea_count: int = Field(4, ge=1, le=8)


@router.post("/ideas")
def create_content_ideas(payload: ContentIdeaRequest, user: dict = Depends(get_current_user)):
    credits = idea_cost(payload.idea_count)
    event_id = _charge(user["id"], "idea", credits, f"{payload.idea_count} fikir: {payload.topic}")

    try:
        result = generate_content_ideas(
            business_name=payload.business_name,
            sector=payload.sector,
            target_audience=payload.target_audience,
            tone=payload.tone,
            topic=payload.topic,
            idea_count=payload.idea_count,
        )
    except LLMError:
        refund(event_id)
        raise HTTPException(status_code=503, detail="Yapay zeka servisine şu an ulaşılamıyor, birazdan tekrar dene.")

    if result.get("error"):
        refund(event_id)
        return result
    return {**result, "credits_spent": credits}


ASPECTS = {"ASPECT_1_1": "1:1", "ASPECT_9_16": "9:16", "ASPECT_3_4": "3:4", "ASPECT_16_9": "16:9", "ASPECT_4_3": "4:3"}


class ImageRequest(BaseModel):
    concept: str = Field(..., max_length=2000, examples=["Masada buğulanan bir buzlu kahve, sıcak yaz ışığı"])
    aspect_ratio: str = Field("ASPECT_1_1", pattern=r"^ASPECT_(1_1|9_16|3_4|16_9|4_3)$")
    reference_urls: list[str] = Field(default_factory=list, max_length=4, description="Örnek alınacak yüklenmiş görseller")


def _own_urls(urls: list[str]) -> list[str]:
    bad = [u for u in urls if not storage.is_own_blob_url(u)]
    if bad:
        raise HTTPException(status_code=400, detail="Örnek dosyalar ajansAI'a yüklenmiş olmalı.")
    return urls


@router.post("/image")
def create_image(payload: ImageRequest, user: dict = Depends(get_current_user)):
    if not gateway_media.is_enabled():
        raise HTTPException(status_code=503, detail="Görsel üretimi henüz yapılandırılmadı.")
    refs = _own_urls(payload.reference_urls)
    credits = CREDIT_COSTS["image"]
    event_id = _charge(user["id"], "image", credits, payload.concept)

    try:
        data, mime = gateway_media.generate_image(payload.concept, ASPECTS[payload.aspect_ratio], refs or None)
    except gateway_media.MediaError as e:
        logger.error("Görsel üretilemedi: %s", e)
        refund(event_id)
        return {"image_url": None, "error": "Görsel üretilemedi, kredin iade edildi. Tekrar dene."}

    if storage.is_enabled():
        try:
            url = storage.save(data, mime, f"gorsel/{user['id']}")
        except storage.StorageError as e:
            logger.error("Görsel saklanamadı: %s", e)
            url = f"data:{mime};base64,{base64.b64encode(data).decode()}"
    else:
        url = f"data:{mime};base64,{base64.b64encode(data).decode()}"
    return {"image_url": url, "error": None, "credits_spent": credits}


class VideoRequest(BaseModel):
    concept: str = Field(..., max_length=2000, examples=["Buzlu kahvenin bardağa dökülüşü, ağır çekim"])
    image_url: str | None = Field(None, max_length=2000, description="Başlangıç karesi (görselden video)")
    end_image_url: str | None = Field(None, max_length=2000, description="Bitiş karesi (isteğe bağlı)")
    duration: Literal[5, 7, 10] = 5
    resolution: Literal["720p", "1080p", "4k"] = "720p"
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = "9:16"
    audio: bool = False


@router.post("/video")
def create_video(payload: VideoRequest, user: dict = Depends(get_current_user)):
    """Video üretimini başlatır. Yanıttaki job_id ile /video/{job_id} sorgulanmalı.

    Kredi iş başlamadan önce atomik olarak düşülür. İş başlatılamazsa hemen,
    üretim başarısız olursa sorgulandığında iade edilir.
    """
    if not gateway_media.is_enabled():
        raise HTTPException(status_code=503, detail="Video üretimi henüz yapılandırılmadı.")
    image_url = payload.image_url or None
    end_image_url = payload.end_image_url if image_url else None
    _own_urls([u for u in (image_url, end_image_url) if u])
    duration, resolution = payload.duration, payload.resolution
    credits = video_cost(duration, resolution, payload.audio)
    label = ("4K" if resolution == "4k" else resolution) + (", sesli" if payload.audio else "")
    event_id = _charge(user["id"], "video", credits, f"{label}, {duration} sn: {payload.concept}")

    try:
        operation = gateway_media.start_video(
            payload.concept, duration, resolution, image_url, end_image_url, payload.audio, payload.aspect_ratio
        )
    except gateway_media.MediaError as e:
        logger.error("Video başlatılamadı: %s", e)
        refund(event_id)
        return {"job_id": None, "error": "Video üretimi başlatılamadı, kredin iade edildi. Tekrar dene."}

    job_id = str(uuid.uuid4())
    with get_engine().begin() as conn:
        conn.execute(
            video_tasks.insert().values(
                id=job_id,
                user_id=user["id"],
                credit_event_id=event_id,
                operation=json.dumps(operation),
                status="pending",
                created_at=utcnow(),
            )
        )
    return {"job_id": job_id, "error": None, "credits_spent": credits}


def _store_video(video: dict, user_id: str) -> str:
    """Bitmiş videoyu kalıcı depoya taşır; depo yoksa sağlayıcının süreli adresini döndürür."""
    if video.get("type") == "url":
        if not storage.is_enabled():
            return video["url"]
        data = requests.get(video["url"], timeout=120).content
    else:
        data = base64.b64decode(video.get("data", ""))
        if not storage.is_enabled():
            raise storage.StorageError("Blob deposu yok; video baytları saklanamıyor.")
    return storage.save(data, "video/mp4", f"video/{user_id}")


@router.get("/video/{job_id}")
def check_video(job_id: str, user: dict = Depends(get_current_user)):
    """Durum: PENDING, SUCCEEDED, FAILED. SUCCEEDED olunca video_url dolu gelir."""
    with get_engine().connect() as conn:
        task = conn.execute(
            select(video_tasks).where(and_(video_tasks.c.id == job_id, video_tasks.c.user_id == user["id"]))
        ).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Video bulunamadı.")

    if task.status == "completed":
        return {"status": "SUCCEEDED", "video_url": task.video_url, "error": None}
    if task.status == "failed":
        return {"status": "FAILED", "video_url": None, "error": task.error}

    try:
        result = gateway_media.video_status(json.loads(task.operation))
    except gateway_media.MediaError as e:
        # Geçici hata olabilir: işi başarısız saymıyoruz, istemci tekrar sorar.
        logger.warning("Video durumu alınamadı: %s", e)
        return {"status": "PENDING", "video_url": None, "error": None}

    if result["status"] == "pending":
        return {"status": "PENDING", "video_url": None, "error": None}

    if result["status"] == "completed":
        try:
            url = _store_video(result["video"], user["id"])
        except (requests.RequestException, storage.StorageError) as e:
            logger.error("Video saklanamadı: %s", e)
            return {"status": "PENDING", "video_url": None, "error": None}
        with get_engine().begin() as conn:
            conn.execute(
                update(video_tasks)
                .where(and_(video_tasks.c.id == job_id, video_tasks.c.status == "pending"))
                .values(status="completed", video_url=url)
            )
        return {"status": "SUCCEEDED", "video_url": url, "error": None}

    error = str(result.get("error") or "Video üretilemedi.")[:500]
    with get_engine().begin() as conn:
        changed = conn.execute(
            update(video_tasks)
            .where(and_(video_tasks.c.id == job_id, video_tasks.c.status == "pending"))
            .values(status="failed", error=error)
        ).rowcount
    if changed:
        refund(task.credit_event_id)
    logger.error("Video başarısız (%s): %s", job_id, error)
    return {"status": "FAILED", "video_url": None, "error": "Video üretilemedi, kredin iade edildi."}


# ---------------- Fikir sohbeti ----------------

class Attachment(BaseModel):
    url: str = Field(..., max_length=2000)
    content_type: str = Field(..., max_length=120)
    name: str = Field("dosya", max_length=200)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field("", max_length=20000)
    attachments: list[Attachment] = Field(default_factory=list, max_length=5)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=40)


@router.post("/chat")
def chat(payload: ChatRequest, user: dict = Depends(get_current_user)):
    """ChatGPT benzeri tek metin kutusu: son kullanıcı mesajı + ekleri yanıtlanır."""
    last = payload.messages[-1]
    if last.role != "user" or not (last.content.strip() or last.attachments):
        raise HTTPException(status_code=400, detail="Bir mesaj yaz veya dosya ekle.")
    for att in last.attachments:
        if storage.kind_of(att.content_type) is None:
            raise HTTPException(status_code=400, detail=f"{att.name}: bu dosya türü desteklenmiyor.")
    _own_urls([a.url for a in last.attachments])

    credits = chat_cost(len(last.attachments))
    event_id = _charge(user["id"], "chat", credits, last.content.strip()[:200] or "Dosya incelemesi")
    try:
        text, model = assistant.reply([m.model_dump() for m in payload.messages[-20:]])
    except (LLMError, storage.StorageError) as e:
        logger.error("Sohbet yanıtı alınamadı: %s", e)
        refund(event_id)
        raise HTTPException(status_code=503, detail="Yapay zeka şu an yanıt veremedi, kredin iade edildi. Birazdan tekrar dene.")
    return {"reply": text, "model": model, "credits_spent": credits}


class DescribeRequest(BaseModel):
    attachment: Attachment
    target: Literal["image", "video"]
    note: str = Field("", max_length=500)


@router.post("/describe")
def describe(payload: DescribeRequest, user: dict = Depends(get_current_user)):
    """Yüklenen örnek görsel/videodan, aynı tarzda yeni üretim için konsept metni çıkarır."""
    if storage.kind_of(payload.attachment.content_type) not in ("image", "video"):
        raise HTTPException(status_code=400, detail="Örnek olarak görsel veya video yükleyebilirsin.")
    _own_urls([payload.attachment.url])
    credits = CREDIT_COSTS["describe"]
    event_id = _charge(user["id"], "describe", credits, f"Örnekten konsept: {payload.attachment.name}")
    try:
        concept = assistant.describe_for_generation(payload.attachment.model_dump(), payload.target, payload.note)
    except (LLMError, storage.StorageError) as e:
        logger.error("Örnek incelenemedi: %s", e)
        refund(event_id)
        raise HTTPException(status_code=503, detail="Örnek incelenemedi, kredin iade edildi. Tekrar dene.")
    return {"concept": concept, "credits_spent": credits}
