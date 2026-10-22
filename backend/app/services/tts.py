"""Doğal sesli okuma.

Sırayla denenir:
1. Gemini TTS (GEMINI_API_KEY, Google AI Studio): insan gibi, tonlamalı Türkçe; ücretsiz katman.
2. Google Cloud Text-to-Speech Chirp 3 HD (GOOGLE_TTS_API_KEY): ayda 1M karakter ücretsiz.

Günlük karakter tavanı aşılırsa ya da anahtar yoksa TTSUnavailable fırlatılır; arayüz
tarayıcının sesine döner.
"""

import base64
import logging
import struct
from datetime import date

import requests
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app import config
from app.db import get_engine, tts_usage

MAX_CHARS = 1500
logger = logging.getLogger("ajansai.tts")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta"


class TTSUnavailable(Exception):
    pass


def enabled() -> bool:
    return bool(config.GEMINI_API_KEY or config.GOOGLE_TTS_API_KEY)


def _add(key: str, chars: int, limit: int) -> bool:
    """Sayaç sınırı aşmayacaksa ekler; aşacaksa False döner (atomik)."""
    engine = get_engine()
    with engine.begin() as conn:
        if conn.execute(select(tts_usage.c.key).where(tts_usage.c.key == key)).first() is None:
            try:
                conn.execute(tts_usage.insert().values(key=key, chars=0))
            except IntegrityError:
                pass
    with engine.begin() as conn:
        changed = conn.execute(
            update(tts_usage)
            .where(tts_usage.c.key == key, tts_usage.c.chars + chars <= limit)
            .values(chars=tts_usage.c.chars + chars)
        ).rowcount
    return bool(changed)


def _undo(key: str, chars: int) -> None:
    with get_engine().begin() as conn:
        conn.execute(update(tts_usage).where(tts_usage.c.key == key).values(chars=tts_usage.c.chars - chars))


def _wav(pcm: bytes, rate: int = 24000) -> bytes:
    """Başlıksız 16-bit mono PCM'i WAV dosyasına sarar."""
    header = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack(
        "<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16
    ) + b"data" + struct.pack("<I", len(pcm))
    return header + pcm


def _find_audio(node) -> tuple[str, str] | None:
    """Yanıtın içinde base64 ses verisini arar: (veri, mime)."""
    if isinstance(node, dict):
        data = node.get("data")
        mime = node.get("mime_type") or node.get("mimeType") or ""
        if isinstance(data, str) and len(data) > 200 and (not mime or "audio" in mime):
            return data, mime
        for v in node.values():
            found = _find_audio(v)
            if found:
                return found
    elif isinstance(node, list):
        for v in node:
            found = _find_audio(v)
            if found:
                return found
    return None


def _decode(found: tuple[str, str]) -> tuple[bytes, str]:
    data, mime = found
    raw = base64.b64decode(data)
    if raw[:4] == b"RIFF":
        return raw, "audio/wav"
    if raw[:3] == b"ID3" or raw[:2] == b"\xff\xfb":
        return raw, "audio/mpeg"
    rate = 24000
    if "rate=" in mime:
        try:
            rate = int(mime.split("rate=")[1].split(";")[0])
        except ValueError:
            pass
    return _wav(raw, rate), "audio/wav"


def _gemini(text: str) -> tuple[bytes, str]:
    """Gemini TTS: önce Interactions API, olmazsa generateContent."""
    headers = {"x-goog-api-key": config.GEMINI_API_KEY, "Content-Type": "application/json"}
    style = config.TTS_STYLE
    errors = []
    try:
        r = requests.post(
            f"{GEMINI_URL}/interactions",
            headers=headers,
            json={
                "model": config.GEMINI_TTS_MODEL,
                "input": [{
                    "type": "user_input",
                    "content": [{
                        "type": "text",
                        "text": text,
                        "annotations": [{"type": "speech_metadata", "style": style}],
                    }],
                }],
                "response_format": {"type": "audio"},
                "generation_config": {"speech_config": [{"voice": config.GEMINI_TTS_VOICE}]},
            },
            timeout=45,
        )
        if r.status_code == 200:
            found = _find_audio(r.json())
            if found:
                return _decode(found)
            errors.append("interactions: ses yok")
        else:
            errors.append(f"interactions {r.status_code}: {r.text[:200]}")
    except requests.RequestException as e:
        errors.append(f"interactions: {e}")
    try:
        r = requests.post(
            f"{GEMINI_URL}/models/{config.GEMINI_TTS_MODEL}:generateContent",
            headers=headers,
            json={
                "contents": [{"parts": [{"text": f"{style.capitalize()} bir sesle oku: {text}"}]}],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": config.GEMINI_TTS_VOICE}}},
                },
            },
            timeout=45,
        )
        if r.status_code == 200:
            found = _find_audio(r.json())
            if found:
                return _decode(found)
            errors.append("generateContent: ses yok")
        else:
            errors.append(f"generateContent {r.status_code}: {r.text[:200]}")
    except requests.RequestException as e:
        errors.append(f"generateContent: {e}")
    raise TTSUnavailable("Gemini TTS: " + "; ".join(errors))


def _google_cloud(text: str) -> tuple[bytes, str]:
    try:
        r = requests.post(
            "https://texttospeech.googleapis.com/v1/text:synthesize",
            params={"key": config.GOOGLE_TTS_API_KEY},
            json={
                "input": {"text": text},
                "voice": {"languageCode": "tr-TR", "name": config.TTS_VOICE},
                "audioConfig": {"audioEncoding": "MP3"},
            },
            timeout=30,
        )
    except requests.RequestException as e:
        raise TTSUnavailable(f"Google TTS'e ulaşılamadı: {e}") from e
    if r.status_code != 200:
        raise TTSUnavailable(f"Google TTS {r.status_code}: {r.text[:200]}")
    return base64.b64decode(r.json().get("audioContent", "")), "audio/mpeg"


def synthesize(text: str, subject: str) -> tuple[bytes, str]:
    """(ses baytları, mime) döndürür."""
    if not enabled():
        raise TTSUnavailable("Doğal ses yapılandırılmadı.")
    text = text.strip()[:MAX_CHARS]
    if not text:
        raise TTSUnavailable("Boş metin.")
    n = len(text)
    day = date.today().isoformat()
    if not _add(day, n, config.TTS_DAILY_CHARS):
        raise TTSUnavailable("Günlük doğal ses kotası doldu.")
    personal = f"{day}:{subject}"
    if not _add(personal, n, config.TTS_CHARS_PER_DAY_SUBJECT):
        _undo(day, n)
        raise TTSUnavailable("Kişisel günlük doğal ses kotası doldu.")
    errors = []
    providers = ([_gemini] if config.GEMINI_API_KEY else []) + ([_google_cloud] if config.GOOGLE_TTS_API_KEY else [])
    for provider in providers:
        try:
            return provider(text)
        except TTSUnavailable as e:
            errors.append(str(e))
            logger.warning("Doğal ses sağlayıcısı olmadı: %s", e)
    _undo(day, n)
    _undo(personal, n)
    raise TTSUnavailable("; ".join(errors))
