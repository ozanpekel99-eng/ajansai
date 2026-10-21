"""Vercel AI Gateway üzerinden görsel ve video üretimi.

Ayrı bir sağlayıcı anahtarı gerekmez: Vercel'de proje kimliği (OIDC) ile
doğrulanır, maliyet Vercel faturasına yansır. İstek biçimi resmi
`@ai-sdk/gateway` paketiyle aynıdır (v4 protokolü):

- Görsel: POST /image-model  → {"images": [base64, ...]}
- Video:  POST /video-model/start → {"operation": {...}}
          POST /video-model/status {"operation"} → pending | completed | error
"""

import base64
import logging

import requests

from app import config
from app.services.llm_service import ai_gateway_token

logger = logging.getLogger("ajansai.media")

BASE_URL = "https://ai-gateway.vercel.sh/v4/ai"


class MediaError(Exception):
    pass


def is_enabled() -> bool:
    return config.AI_GATEWAY_ENABLED


def _headers(model: str, kind: str) -> dict:
    token = ai_gateway_token()
    if not token:
        raise MediaError("AI Gateway kimlik bilgisi yok (OIDC token veya AI_GATEWAY_API_KEY).")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "ai-gateway-protocol-version": "0.0.1",
        "ai-gateway-auth-method": "api-key" if config.AI_GATEWAY_API_KEY else "oidc",
        f"ai-{kind}-model-specification-version": "4",
        "ai-model-id": model,
    }


def _post(path: str, model: str, kind: str, body: dict, timeout: float) -> dict:
    try:
        response = requests.post(f"{BASE_URL}{path}", headers=_headers(model, kind), json=body, timeout=timeout)
    except requests.RequestException as e:
        raise MediaError(f"AI Gateway'e ulaşılamadı: {e}") from e
    if response.status_code >= 400:
        raise MediaError(f"AI Gateway {response.status_code}: {response.text[:400]}")
    try:
        return response.json()
    except ValueError as e:
        raise MediaError(f"AI Gateway beklenmeyen yanıt: {response.text[:200]}") from e


def _sniff_mime(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def generate_image(prompt: str, aspect_ratio: str) -> tuple[bytes, str]:
    """(görsel baytları, mime) döndürür. aspect_ratio örn. "9:16"."""
    data = _post(
        "/image-model",
        config.IMAGE_MODEL,
        "image",
        {"prompt": prompt, "n": 1, "aspectRatio": aspect_ratio},
        timeout=150,
    )
    images = data.get("images") or []
    if not images:
        raise MediaError(f"Görsel dönmedi: {str(data)[:300]}")
    raw = images[0]
    if raw.startswith("data:"):
        raw = raw.split(",", 1)[1]
    payload = base64.b64decode(raw)
    return payload, _sniff_mime(payload)


def start_video(prompt: str, duration: int, image_url: str | None = None) -> dict:
    """Video işini başlatır, durum sorgusu için gerekli `operation` nesnesini döndürür."""
    body = {
        "prompt": prompt,
        "n": 1,
        "aspectRatio": "9:16",
        "resolution": config.VIDEO_RESOLUTION,
        "duration": duration,
        "generateAudio": False,
    }
    if image_url:
        body["image"] = {"type": "url", "url": image_url}
    data = _post("/video-model/start", config.VIDEO_MODEL, "video", body, timeout=60)
    if data.get("operation") is None:
        raise MediaError(f"Video işi başlatılamadı: {str(data)[:300]}")
    return data["operation"]


def video_status(operation) -> dict:
    """{"status": pending|completed|error, "video": {"url"} veya {"data", "mediaType"}, "error"}."""
    data = _post("/video-model/status", config.VIDEO_MODEL, "video", {"operation": operation}, timeout=60)
    status = data.get("status")
    if status == "completed":
        videos = data.get("videos") or []
        if not videos:
            return {"status": "error", "error": "Video boş döndü."}
        return {"status": "completed", "video": videos[0]}
    if status in ("error", "cancelled"):
        return {"status": "error", "error": data.get("error") or "Video üretimi iptal edildi."}
    return {"status": "pending"}
