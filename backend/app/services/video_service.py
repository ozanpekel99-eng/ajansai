import logging

import requests

from app import config

# MVP'de Runway ML kullanıyoruz. Video üretimi görselden farklı olarak
# ASENKRON çalışır: önce bir "job" (görev) başlatılır, sonra durumu
# ayrı bir endpoint'ten sorgulanır (üretim genelde 30sn - birkaç dakika sürer).
RUNWAY_BASE_URL = "https://api.dev.runwayml.com/v1"
RUNWAY_VERSION_HEADER = "2024-11-06"

logger = logging.getLogger("ajansai.video")


def _headers():
    return {
        "Authorization": f"Bearer {config.RUNWAY_API_KEY}",
        "X-Runway-Version": RUNWAY_VERSION_HEADER,
        "Content-Type": "application/json",
    }


def start_video_generation(prompt: str, image_url: str | None = None, duration: int = 5) -> dict:
    """Video üretim görevi başlatır. {"job_id", "error"} döndürür."""
    if not config.RUNWAY_API_KEY:
        return {"error": "Video üretimi henüz yapılandırılmadı (RUNWAY_API_KEY).", "job_id": None}

    payload = {
        "promptText": prompt,
        "duration": duration,
        "ratio": "768:1280",  # dikey format, reels/story için
    }
    if image_url:
        payload["promptImage"] = image_url

    endpoint = f"{RUNWAY_BASE_URL}/image_to_video" if image_url else f"{RUNWAY_BASE_URL}/text_to_video"

    try:
        response = requests.post(endpoint, json=payload, headers=_headers(), timeout=30)
        response.raise_for_status()
        job_id = response.json().get("id")
    except (requests.RequestException, ValueError) as e:
        logger.error("Runway başlatma hatası: %s", e)
        return {"error": "Video üretimi başlatılamadı, lütfen tekrar dene.", "job_id": None}

    if not job_id:
        return {"error": "Video üretimi başlatılamadı, lütfen tekrar dene.", "job_id": None}
    return {"job_id": job_id, "error": None}


def get_video_status(job_id: str) -> dict:
    """Durum: PENDING, RUNNING, SUCCEEDED, FAILED. SUCCEEDED olunca video_url dolu gelir."""
    if not config.RUNWAY_API_KEY:
        return {"error": "Video üretimi yapılandırılmadı.", "status": None}

    try:
        response = requests.get(f"{RUNWAY_BASE_URL}/tasks/{job_id}", headers=_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        # Geçici ağ hatası: job'ı başarısız sayıp kotayı iade etmiyoruz, istemci tekrar sorar.
        logger.warning("Runway durum sorgusu hatası: %s", e)
        return {"status": "UNKNOWN", "video_url": None, "error": None}

    video_url = None
    if data.get("status") == "SUCCEEDED":
        outputs = data.get("output") or []
        video_url = outputs[0] if outputs else None

    return {
        "status": data.get("status"),
        "video_url": video_url,
        "error": data.get("failure") if data.get("status") == "FAILED" else None,
    }
