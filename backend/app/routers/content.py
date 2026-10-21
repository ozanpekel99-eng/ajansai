from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.security import get_current_user
from app.services.claude_service import generate_content_ideas
from app.services.image_service import generate_image
from app.services.llm_service import LLMError
from app.services.usage_service import (
    QuotaExceededError,
    consume,
    get_video_job_owner,
    record_video_job,
    refund,
    release_video_if_failed,
)
from app.services.video_service import get_video_status, start_video_generation

router = APIRouter()


class ContentIdeaRequest(BaseModel):
    business_name: str = Field(..., max_length=200, examples=["Cafe Lorem"])
    sector: str = Field(..., max_length=200, examples=["Kafe / Restoran"])
    target_audience: str = Field(..., max_length=500, examples=["25-40 yaş, şehirde yaşayan genç profesyoneller"])
    tone: str = Field(..., max_length=200, examples=["Samimi ve eğlenceli"])
    topic: str = Field(..., max_length=1000, examples=["Yeni sezon soğuk kahve menüsü"])
    idea_count: int = Field(4, ge=1, le=8)


@router.post("/ideas")
def create_content_ideas(payload: ContentIdeaRequest, user: dict = Depends(get_current_user)):
    try:
        consume(user["id"], "idea")
    except QuotaExceededError as e:
        raise HTTPException(status_code=402, detail=str(e))

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
        refund(user["id"], "idea")
        raise HTTPException(status_code=503, detail="Yapay zeka servisine şu an ulaşılamıyor, birazdan tekrar dene.")

    if result.get("error"):
        refund(user["id"], "idea")
    return result


class ImageRequest(BaseModel):
    concept: str = Field(..., max_length=2000, examples=["Masada buğulanan bir buzlu kahve, sıcak yaz ışığı"])
    aspect_ratio: str = "ASPECT_1_1"


@router.post("/image")
def create_image(payload: ImageRequest, user: dict = Depends(get_current_user)):
    try:
        consume(user["id"], "image")
    except QuotaExceededError as e:
        raise HTTPException(status_code=402, detail=str(e))

    result = generate_image(prompt=payload.concept, aspect_ratio=payload.aspect_ratio)
    if not result.get("image_url"):
        refund(user["id"], "image")
    return result


class VideoRequest(BaseModel):
    concept: str = Field(..., max_length=2000, examples=["Buzlu kahvenin bardağa dökülüşü, ağır çekim"])
    image_url: str | None = Field(
        None, description="Varsa, önce /image ile üretilmiş görselin URL'si (image-to-video)"
    )
    duration: int = Field(5, ge=5, le=10)


@router.post("/video")
def create_video(payload: VideoRequest, user: dict = Depends(get_current_user)):
    """Video üretimini başlatır. Yanıttaki job_id ile /video/{job_id} sorgulanmalı.

    Kota job başlamadan önce atomik olarak düşülür. Job başlatılamazsa hemen,
    Runway job'ı FAILED dönerse sorgulandığında iade edilir.
    """
    try:
        consume(user["id"], "video")
    except QuotaExceededError as e:
        raise HTTPException(status_code=402, detail=str(e))

    result = start_video_generation(
        prompt=payload.concept, image_url=payload.image_url, duration=payload.duration
    )

    if result.get("error") or not result.get("job_id"):
        refund(user["id"], "video")
        return result

    record_video_job(user["id"], result["job_id"])
    return result


@router.get("/video/{job_id}")
def check_video(job_id: str, user: dict = Depends(get_current_user)):
    """Video üretim görevinin durumunu ve tamamlandıysa video_url'ini döndürür."""
    if get_video_job_owner(job_id) != user["id"]:
        raise HTTPException(status_code=404, detail="Video bulunamadı.")

    status = get_video_status(job_id)
    if status.get("status") == "FAILED":
        release_video_if_failed(job_id)
    return status
