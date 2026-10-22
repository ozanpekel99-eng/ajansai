"""Sesli sohbet: doğal sesli okuma (TTS).

Ücretsiz paket ve misafir: günlük karakter hakkı (kredisiz).
Ücretli paketler: her TTS_CHARS_PER_CREDIT karakter (~1 dk ses) 1 kredi.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app import config
from app.routers.free import client_ip
from app.security import get_optional_user
from app.services import free_tier, tts
from app.services.usage_service import QuotaExceededError, consume, get_usage, refund

router = APIRouter()
logger = logging.getLogger("ajansai.voice")


@router.get("/status")
def status():
    return {"natural_voice": tts.enabled(), "streaming": bool(config.GEMINI_API_KEY)}


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=tts.MAX_CHARS)


def _start(text: str, request: Request, user: dict | None):
    """Kotayı ayırır ve gerekiyorsa krediyi düşer. (kota kayıtları, kredi kaydı) döndürür."""
    subject = free_tier.subject_for(user, client_ip(request))
    paid = bool(user) and get_usage(user["id"]).get("plan") != "deneme"
    n = len(text)
    before = tts.paid_chars_today(subject) if paid else 0
    try:
        taken = tts.reserve(n, subject, paid)
    except tts.TTSUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    event = None
    if paid:
        k = max(config.TTS_CHARS_PER_CREDIT, 1)
        credits = (before + n) // k - before // k
        if credits:
            try:
                event = consume(user["id"], "voice", credits, f"Sesli okuma ({credits * k} karakter)")
            except QuotaExceededError as e:
                tts.release(taken)
                raise HTTPException(status_code=402, detail=str(e))
    return taken, event


def _undo(taken, event):
    tts.release(taken)
    if event:
        refund(event)


@router.post("/speak")
def speak(payload: SpeakRequest, request: Request, user: dict | None = Depends(get_optional_user)):
    """Metni doğal Türkçe sesle tek dosya (WAV/MP3) olarak döndürür. Kullanılamazsa 503 (arayüz tarayıcı sesine döner)."""
    if not tts.enabled():
        raise HTTPException(status_code=503, detail="Doğal ses şu an kullanılamıyor.")
    text = payload.text.strip()[: tts.MAX_CHARS]
    taken, event = _start(text, request, user)
    try:
        audio, mime = tts.synthesize_raw(text)
    except tts.TTSUnavailable as e:
        _undo(taken, event)
        logger.info("Doğal ses kullanılamadı: %s", e)
        raise HTTPException(status_code=503, detail="Doğal ses şu an kullanılamıyor.")
    return Response(content=audio, media_type=mime, headers={"Cache-Control": "no-store"})


@router.post("/stream")
def stream(payload: SpeakRequest, request: Request, user: dict | None = Depends(get_optional_user)):
    """Akışlı doğal ses: 24 kHz 16-bit mono PCM (audio/L16). İlk ses ~1 sn'de gelir."""
    if not config.GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="Akışlı ses kullanılamıyor.")
    text = payload.text.strip()[: tts.MAX_CHARS]
    taken, event = _start(text, request, user)
    gen = tts.stream_pcm(text)
    try:
        first = next(gen)  # ilk parça gelmeden yanıt başlatılmaz; hata olursa 503
    except (tts.TTSUnavailable, StopIteration, Exception) as e:  # noqa: BLE001
        _undo(taken, event)
        logger.info("Akışlı ses kullanılamadı: %s", e)
        raise HTTPException(status_code=503, detail="Doğal ses şu an kullanılamıyor.")

    def body():
        yield first
        try:
            yield from gen
        except Exception as e:  # noqa: BLE001
            logger.warning("Ses akışı yarıda kesildi: %s", e)

    return StreamingResponse(body(), media_type="audio/L16;rate=24000", headers={"Cache-Control": "no-store"})
