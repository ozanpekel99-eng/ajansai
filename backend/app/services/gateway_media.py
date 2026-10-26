"""Vercel AI Gateway üzerinden görsel ve video üretimi.

Ayrı bir sağlayıcı anahtarı gerekmez: Vercel'de proje kimliği (OIDC) ile
doğrulanır, maliyet Vercel faturasına yansır. İstek biçimi resmi
`@ai-sdk/gateway` paketiyle aynıdır (v4 protokolü):

- Görsel: POST /image-model  → {"images": [base64, ...]}
- Video:  POST /video-model/start → {"operation": {...}}
          POST /video-model/status {"operation"} → pending | completed | error
"""

import base64
import json
import logging
import re

import requests

from app import config
from app.services import vertex_video
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


# GPT Image 2 istenen boyutu doğrudan üretir (kırpma yok: alttaki/üstteki yazılar kesilmez).
OPENAI_SIZES = {
    "1:1": (1024, 1024), "4:5": (1024, 1280), "3:4": (1056, 1408), "2:3": (1024, 1536),
    "9:16": (1008, 1792), "16:9": (1792, 1008), "4:3": (1408, 1056), "3:2": (1536, 1024),
}


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
    w, h = OPENAI_SIZES.get(aspect_ratio, (1024, 1024))
    # GPT Image istenmeyen rozet/marka/vaat ("ücretsiz kurulum", "2 yıl garanti", yanlış marka) uydurabiliyor.
    body = {"prompt": prompt, "n": 1, "size": f"{w}x{h}"}
    if reference_urls:
        body["files"] = [{"type": "url", "url": u} for u in reference_urls]
        # Yüklenen ürün fotoğrafları (logo, yazı, renk, biçim) olabildiğince aynen korunur
        body["providerOptions"] = {"openai": {"input_fidelity": "high"}}
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


def _video_body(prompt: str, duration: int, size: str, image_url: str | None, end_image_url: str | None,
                audio: bool, aspect_ratio: str) -> dict:
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
    return body


def _start(model: str, body: dict) -> dict:
    data = _post("/video-model/start", model, "video", body, timeout=60)
    if data.get("operation") is None:
        raise MediaError(f"Video işi başlatılamadı: {str(data)[:300]}")
    return {"model": model, "operation": data["operation"]}


def _oriented(size: str, aspect_ratio: str) -> str:
    """"1920x1080" gibi kademe adını videonun yönüne göre gerçek piksel boyutuna çevirir (9:16 → 1080x1920)."""
    w, h = (int(x) for x in size.split("x"))
    if aspect_ratio == "9:16" and w > h:
        w, h = h, w
    return f"{w}x{h}"


def is_too_large(data: dict) -> bool:
    """Gateway videoyu üretip boyut sınırı yüzünden geri vermediyse True."""
    job = ((data.get("providerMetadata") or {}).get("gateway") or {}).get("asyncJob") or {}
    return bool((job.get("result") or {}).get("inlineTooLarge"))


def fallback_video_model(has_image: bool, audio: bool) -> str:
    if audio:
        return config.VIDEO_FALLBACK_AUDIO_I2V if has_image else config.VIDEO_FALLBACK_AUDIO_T2V
    return config.VIDEO_FALLBACK_I2V if has_image else config.VIDEO_FALLBACK_T2V


def start_fallback_video(
    prompt: str,
    duration: int,
    resolution: str = "720p",
    image_url: str | None = None,
    audio: bool = False,
    aspect_ratio: str = "9:16",
) -> dict:
    """Yedek modelle (Kling) aynı istem ve açılış karesinden video başlatır."""
    model = fallback_video_model(bool(image_url), audio)
    size = "1280x720" if resolution == "720p" else "1920x1080"
    body = _video_body(prompt, 5 if duration <= 6 else 10, size, image_url, None, audio, aspect_ratio)
    # "pro" modu: aynı fiyata 1080p (varsayılan mod 720p üretiyor). Sesli istekte Kling 2.6 sesi açar.
    body["providerOptions"] = {"klingai": {"mode": "pro", **({"sound": "on"} if audio else {})}}
    job = _start(model, body)
    job["fallback"] = True
    return job


def start_video(
    prompt: str,
    duration: int,
    resolution: str = "720p",
    image_url: str | None = None,
    end_image_url: str | None = None,
    audio: bool = False,
    aspect_ratio: str = "9:16",
    allow_fallback: bool = True,
    tier: str = "fast",
    max_size: str | None = None,
) -> dict:
    """Video işini başlatır. Durum sorgusu için {"model", "operation"} döndürür.

    image_url başlangıç karesi (görselden video), end_image_url bitiş karesidir. Ana model (Veo)
    başlatılamazsa yedek modelle (Kling) denenir; dönen işte "fallback": True olur.
    """
    model, size = config.VIDEO_MODELS[resolution]
    if tier == "lite" and resolution != "4k":  # Lite 4K desteklemiyor
        model = config.VIDEO_MODEL_LITE
    target = _oriented(size, aspect_ratio)
    if vertex_video.handles(model) and not max_size:
        # Vertex: istenen çözünürlükte, boyut sınırı yok
        try:
            return vertex_video.start(model, prompt, duration, resolution, image_url, end_image_url, audio, aspect_ratio)
        except vertex_video.VertexError as e:
            logger.warning("Vertex'te başlatılamadı, AI Gateway'e geçiliyor: %s", e)
    if max_size:
        size = max_size
    elif config.VIDEO_UPSCALE:
        size = config.VIDEO_GATEWAY_SIZES.get(resolution, size)
    try:
        job = _start(model, _video_body(prompt, duration, size, image_url, end_image_url, audio, aspect_ratio))
        if size != config.VIDEO_MODELS[resolution][1]:
            job["upscale_to"] = target
        job["size"] = size
        return job
    except MediaError as e:
        if not (config.VIDEO_FALLBACK and allow_fallback):
            raise
        logger.warning("Video modeli %s başlatılamadı, yedeğe geçiliyor: %s", model, e)
        try:
            return start_fallback_video(prompt, duration, resolution, image_url, audio, aspect_ratio)
        except MediaError as e2:
            raise MediaError(f"{model}: {e} | yedek: {e2}") from e2


def _filter_reason(data) -> str:
    """Yanıtta güvenlik filtresi / uyarı nedeni varsa kısa metin olarak döndürür."""
    found: list[str] = []

    def walk(node, key=""):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, list):
            for v in node:
                walk(v, key)
        elif isinstance(node, (str, int)) and re.search(r"filter|reason|warning|error|rai|safety", key, re.I):
            found.append(f"{key}={node}")

    walk(data)
    return "; ".join(found)[:400]


def fetch_video(video: dict) -> bytes:
    """Sağlayıcının döndürdüğü videonun baytları (adres, gcs ya da gömülü veri)."""
    if video.get("type") == "gcs":
        try:
            return vertex_video.download_gcs(video["uri"])
        except vertex_video.VertexError as e:
            raise MediaError(str(e)) from e
    if video.get("type") == "url":
        response = requests.get(video["url"], timeout=120)
        response.raise_for_status()
        return response.content
    return base64.b64decode(video.get("data", ""))


def video_status(job: dict) -> dict:
    """{"status": pending|completed|error, "video": {"url"} veya {"data", "mediaType"}, "error"}."""
    if job.get("provider") == "vertex":
        try:
            return vertex_video.status(job)
        except vertex_video.VertexError as e:
            raise MediaError(str(e)) from e
    model = job.get("model") or config.VIDEO_MODELS["720p"][0]
    data = _post("/video-model/status", model, "video", {"operation": job.get("operation")}, timeout=60)
    status = data.get("status")
    if status == "completed":
        videos = data.get("videos") or []
        if not videos:
            # Veo güvenlik filtresine takılan işler "tamamlandı" ama videosuz döner; nedeni kaybolmasın.
            logger.warning("Video boş döndü, sağlayıcı yanıtı: %s", json.dumps(data, ensure_ascii=False)[:1500])
            if is_too_large(data):
                return {"status": "error", "too_large": True,
                        "error": "Video gateway boyut sınırını (~16 MiB) aştığı için geri verilmedi."}
            reason = _filter_reason(data)
            return {"status": "error", "error": "Video boş döndü." + (f" Neden: {reason}" if reason else "")}
        return {"status": "completed", "video": videos[0]}
    if status in ("error", "cancelled"):
        return {"status": "error", "error": data.get("error") or "Video üretimi iptal edildi."}
    return {"status": "pending"}
