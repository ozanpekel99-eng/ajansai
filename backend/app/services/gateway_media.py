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


# GPT Image yalnızca üç boyut üretir; diğer oranlar en yakın boyuttan ortadan kırpılır.
OPENAI_SIZES = {"square": (1024, 1024), "portrait": (1024, 1536), "landscape": (1536, 1024)}


def _ratio(aspect: str) -> float:
    try:
        w, h = (float(x) for x in aspect.split(":"))
        return w / h
    except ValueError:
        return 1.0


def _crop_to(data: bytes, aspect: str) -> bytes:
    """Görseli ortadan istenen orana kırpar (oran zaten uyuyorsa dokunmaz)."""
    import io

    from PIL import Image

    try:
        img = Image.open(io.BytesIO(data))
        w, h = img.size
    except Exception:  # okunamazsa olduğu gibi kullan
        return data
    target = _ratio(aspect)
    if abs(w / h - target) < 0.01:
        return data
    if w / h > target:  # fazla geniş: yanlardan
        nw = round(h * target)
        box = ((w - nw) // 2, 0, (w - nw) // 2 + nw, h)
    else:  # fazla uzun: üstten ve alttan
        nh = round(w / target)
        box = (0, (h - nh) // 2, w, (h - nh) // 2 + nh)
    out = io.BytesIO()
    img.crop(box).save(out, "PNG")
    return out.getvalue()


def _openai_image(model: str, prompt: str, aspect_ratio: str, reference_urls: list[str] | None) -> bytes:
    """GPT Image (ChatGPT'nin görsel modeli). Ek görsel varsa ilk görsel düzenlenir / örnek alınır."""
    r = _ratio(aspect_ratio)
    kind = "square" if abs(r - 1) < 0.01 else ("portrait" if r < 1 else "landscape")
    w, h = OPENAI_SIZES[kind]
    if abs(w / h - r) > 0.01:
        prompt += (
            f"\n\nThe final image will be center-cropped to a {aspect_ratio} frame: keep all text, logos and key "
            "elements well inside the central area, away from the edges that will be cropped."
        )
    body = {"prompt": prompt, "n": 1, "size": f"{w}x{h}"}
    if reference_urls:
        body["files"] = [{"type": "url", "url": u} for u in reference_urls]
    data = _post("/image-model", model, "image", body, timeout=180)
    images = data.get("images") or []
    if not images:
        raise MediaError(f"Görsel dönmedi: {str(data)[:300]}")
    raw = images[0]
    if raw.startswith("data:"):
        raw = raw.split(",", 1)[1]
    return _crop_to(base64.b64decode(raw), aspect_ratio)


GEMINI_ASPECTS = {"1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"}


def _gemini_image(model: str, prompt: str, aspect_ratio: str, reference_urls: list[str] | None) -> bytes:
    """Gemini görsel modelleri (Nano Banana) sohbet API'si üzerinden görsel üretir/düzenler."""
    token = ai_gateway_token()
    if not token:
        raise MediaError("AI Gateway kimlik bilgisi yok.")
    content = [{"type": "text", "text": prompt}]
    content += [{"type": "image_url", "image_url": {"url": u}} for u in (reference_urls or [])]
    body = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "modalities": ["text", "image"],
    }
    if aspect_ratio in GEMINI_ASPECTS:
        body["providerOptions"] = {"google": {"imageConfig": {"aspectRatio": aspect_ratio}}}
    try:
        response = requests.post(
            f"{config.AI_GATEWAY_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
            timeout=120,
        )
    except requests.RequestException as e:
        raise MediaError(f"AI Gateway'e ulaşılamadı: {e}") from e
    if response.status_code >= 400:
        raise MediaError(f"AI Gateway {response.status_code}: {response.text[:400]}")
    try:
        message = response.json()["choices"][0]["message"]
    except (ValueError, KeyError, IndexError) as e:
        raise MediaError(f"Beklenmeyen yanıt: {response.text[:200]}") from e
    for image in message.get("images") or []:
        url = (image.get("image_url") or {}).get("url") or ""
        if url.startswith("data:"):
            return base64.b64decode(url.split(",", 1)[1])
    raise MediaError(f"Görsel dönmedi: {str(message.get('content'))[:200]}")


def _image_endpoint(model: str, prompt: str, aspect_ratio: str, reference_urls: list[str] | None) -> bytes:
    body = {"prompt": prompt, "n": 1, "aspectRatio": aspect_ratio}
    if reference_urls:
        body["files"] = [{"type": "url", "url": u} for u in reference_urls]
    data = _post("/image-model", model, "image", body, timeout=150)
    images = data.get("images") or []
    if not images:
        raise MediaError(f"Görsel dönmedi: {str(data)[:300]}")
    raw = images[0]
    if raw.startswith("data:"):
        raw = raw.split(",", 1)[1]
    return base64.b64decode(raw)


def generate_image(prompt: str, aspect_ratio: str, reference_urls: list[str] | None = None) -> tuple[bytes, str]:
    """(görsel baytları, mime) döndürür. aspect_ratio örn. "9:16".

    reference_urls verilirse model bu görselleri kullanır: düzenlemede ilk görsel düzenlenecek
    görseldir; ürün/stil örnekleri de aynı listede gelir.
    Sıra: GPT Image 2 (ChatGPT'nin modeli) → Gemini 3.1 Flash Image → Gemini 3 Pro Image.
    """
    errors = []
    for model in (config.IMAGE_MODEL, config.IMAGE_MODEL_FALLBACK, config.IMAGE_MODEL_LAST):
        if not model:
            continue
        try:
            if model.startswith("google/gemini"):
                payload = _gemini_image(model, prompt, aspect_ratio, reference_urls)
            elif model.startswith("openai/gpt-image"):
                payload = _openai_image(model, prompt, aspect_ratio, reference_urls)
            else:
                payload = _image_endpoint(model, prompt, aspect_ratio, reference_urls)
            return payload, _sniff_mime(payload)
        except MediaError as e:
            logger.warning("Görsel modeli %s başarısız: %s", model, e)
            errors.append(f"{model}: {e}")
    raise MediaError(" | ".join(errors)[:600])


def start_video(
    prompt: str,
    duration: int,
    resolution: str = "720p",
    image_url: str | None = None,
    end_image_url: str | None = None,
    audio: bool = False,
    aspect_ratio: str = "9:16",
) -> dict:
    """Video işini başlatır. Durum sorgusu için {"model", "operation"} döndürür.

    image_url başlangıç karesi (görselden video), end_image_url bitiş karesidir.
    """
    model, size = config.VIDEO_MODELS[resolution]
    body = {
        "prompt": prompt,
        "n": 1,
        "aspectRatio": aspect_ratio,
        "resolution": size,
        "duration": duration,
        "generateAudio": audio,
    }
    if image_url and end_image_url:
        body["frameImages"] = [
            {"image": {"type": "url", "url": image_url}, "frameType": "first_frame"},
            {"image": {"type": "url", "url": end_image_url}, "frameType": "last_frame"},
        ]
    elif image_url:
        body["image"] = {"type": "url", "url": image_url}
    data = _post("/video-model/start", model, "video", body, timeout=60)
    if data.get("operation") is None:
        raise MediaError(f"Video işi başlatılamadı: {str(data)[:300]}")
    return {"model": model, "operation": data["operation"]}


def video_status(job: dict) -> dict:
    """{"status": pending|completed|error, "video": {"url"} veya {"data", "mediaType"}, "error"}."""
    model = job.get("model") or config.VIDEO_MODELS["720p"][0]
    data = _post("/video-model/status", model, "video", {"operation": job.get("operation")}, timeout=60)
    status = data.get("status")
    if status == "completed":
        videos = data.get("videos") or []
        if not videos:
            return {"status": "error", "error": "Video boş döndü."}
        return {"status": "completed", "video": videos[0]}
    if status in ("error", "cancelled"):
        return {"status": "error", "error": data.get("error") or "Video üretimi iptal edildi."}
    return {"status": "pending"}
