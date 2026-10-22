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


def reserve(n: int, subject: str, paid: bool) -> list[tuple[str, int]]:
    """Karakter kotasını ayırır; başarısız işlemde geri almak için kayıtları döndürür.

    Ücretsiz/misafir: site geneli günlük tavan + kişi başı günlük tavan.
    Ücretli: kişi başı yüksek güvenlik tavanı (asıl sınır kredidir).
    """
    day = date.today().isoformat()
    taken: list[tuple[str, int]] = []
    checks = (
        [(f"{day}:{subject}:p", config.TTS_PAID_CHARS_PER_DAY)]
        if paid
        else [(day, config.TTS_DAILY_CHARS), (f"{day}:{subject}", config.TTS_CHARS_PER_DAY_SUBJECT)]
    )
    for key, limit in checks:
        if not _add(key, n, limit):
            release(taken)
            raise TTSUnavailable("Günlük doğal ses hakkı doldu.")
        taken.append((key, n))
    return taken


def release(taken: list[tuple[str, int]]) -> None:
    for key, n in taken:
        _undo(key, n)


def paid_chars_today(subject: str) -> int:
    day = date.today().isoformat()
    with get_engine().connect() as conn:
        row = conn.execute(select(tts_usage.c.chars).where(tts_usage.c.key == f"{day}:{subject}:p")).first()
    return row[0] if row else 0


def stream_pcm(text: str):
    """Gemini TTS akışı: 24 kHz, 16-bit mono PCM parçaları üretir (ilk ses ~1 sn'de gelir)."""
    r = requests.post(
        f"{GEMINI_URL}/models/{config.GEMINI_TTS_MODEL}:streamGenerateContent",
        params={"alt": "sse"},
        headers={"x-goog-api-key": config.GEMINI_API_KEY, "Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": f"{config.TTS_STYLE.capitalize()} bir sesle oku: {text}"}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": config.GEMINI_TTS_VOICE}}},
            },
        },
        stream=True,
        timeout=45,
    )
    if r.status_code != 200:
        raise TTSUnavailable(f"Gemini akış {r.status_code}: {r.text[:200]}")
    got = False
    for line in r.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        try:
            import json

            found = _find_audio(json.loads(line[5:].strip()))
        except ValueError:
            continue
        if not found:
            continue
        raw = base64.b64decode(found[0])
        if raw[:4] == b"RIFF":
            raw = raw[44:]
        if raw:
            got = True
            yield raw
    if not got:
        raise TTSUnavailable("Gemini akışında ses yok")


def synthesize_raw(text: str) -> tuple[bytes, str]:
    """Kota ayırmadan sesi üretir (kotayı çağıran yönetir)."""
    errors = []
    providers = ([_gemini] if config.GEMINI_API_KEY else []) + ([_google_cloud] if config.GOOGLE_TTS_API_KEY else [])
    for provider in providers:
        try:
            return provider(text)
        except TTSUnavailable as e:
            errors.append(str(e))
            logger.warning("Doğal ses sağlayıcısı olmadı: %s", e)
    raise TTSUnavailable("; ".join(errors) or "Doğal ses yapılandırılmadı.")


def synthesize(text: str, subject: str, paid: bool = False) -> tuple[bytes, str]:
    """(ses baytları, mime) döndürür."""
    if not enabled():
        raise TTSUnavailable("Doğal ses yapılandırılmadı.")
    text = text.strip()[:MAX_CHARS]
    if not text:
        raise TTSUnavailable("Boş metin.")
    taken = reserve(len(text), subject, paid)
    errors = []
    providers = ([_gemini] if config.GEMINI_API_KEY else []) + ([_google_cloud] if config.GOOGLE_TTS_API_KEY else [])
    for provider in providers:
        try:
            return provider(text)
        except TTSUnavailable as e:
            errors.append(str(e))
            logger.warning("Doğal ses sağlayıcısı olmadı: %s", e)
    release(taken)
    raise TTSUnavailable("; ".join(errors))
