"""Doğal sesli okuma: Google Cloud Text-to-Speech (Chirp 3 HD).

Günlük karakter tavanı ayda 1M ücretsiz kotanın altında tutulur. Tavan dolarsa
ya da anahtar yoksa TTSUnavailable fırlatılır; arayüz tarayıcının sesine döner.
"""

import base64
from datetime import date

import requests
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app import config
from app.db import get_engine, tts_usage

MAX_CHARS = 1500


class TTSUnavailable(Exception):
    pass


def enabled() -> bool:
    return bool(config.GOOGLE_TTS_API_KEY)


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


def synthesize(text: str, subject: str) -> bytes:
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
        _undo(day, n)
        _undo(personal, n)
        raise TTSUnavailable(f"Google TTS'e ulaşılamadı: {e}") from e
    if r.status_code != 200:
        _undo(day, n)
        _undo(personal, n)
        raise TTSUnavailable(f"Google TTS {r.status_code}: {r.text[:200]}")
    return base64.b64decode(r.json().get("audioContent", ""))
