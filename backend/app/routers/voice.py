"""Sesli sohbet: doğal sesli okuma (TTS)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.routers.free import client_ip
from app.security import get_optional_user
from app.services import free_tier, tts

router = APIRouter()
logger = logging.getLogger("ajansai.voice")


@router.get("/status")
def status():
    return {"natural_voice": tts.enabled()}


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=tts.MAX_CHARS)


@router.post("/speak")
def speak(payload: SpeakRequest, request: Request, user: dict | None = Depends(get_optional_user)):
    """Metni doğal Türkçe sesle ses dosyası (WAV/MP3) olarak döndürür. Kullanılamazsa 503 (arayüz tarayıcı sesine döner)."""
    subject = free_tier.subject_for(user, client_ip(request))
    try:
        audio, mime = tts.synthesize(payload.text, subject)
    except tts.TTSUnavailable as e:
        logger.info("Doğal ses kullanılamadı: %s", e)
        raise HTTPException(status_code=503, detail="Doğal ses şu an kullanılamıyor.")
    return Response(content=audio, media_type=mime, headers={"Cache-Control": "no-store"})
