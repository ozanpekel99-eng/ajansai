"""Veo'yu doğrudan Google Cloud Vertex AI üzerinden çağırır (AI Gateway'in ~16 MiB sınırı olmadan).

Kimlik: servis hesabı anahtarı (JSON) GOOGLE_VERTEX_CREDENTIALS ortam değişkeninde (düz JSON ya da
base64). Erişim jetonu JWT ile alınır ve ~55 dk önbellekte tutulur; ek kütüphane gerekmez (PyJWT).

- Başlat: POST .../publishers/google/models/{model}:predictLongRunning → {"name": operasyon}
- Durum:  POST .../publishers/google/models/{model}:fetchPredictOperation {"operationName"}
          → {"done": true, "response": {"videos": [{"bytesBase64Encoded" | "gcsUri", "mimeType"}],
                                        "raiMediaFilteredCount", "raiMediaFilteredReasons"}}
VERTEX_VIDEO_BUCKET verilirse videolar gs://<bucket>/ altına yazılır ve oradan indirilir
(yanıtta büyük gömülü veri taşınmaz).
"""

import base64
import json
import logging
import threading
import time
from urllib.parse import quote

import jwt
import requests

from app import config

logger = logging.getLogger("ajansai.vertex")

TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/cloud-platform"

# Gateway model adı → Vertex model adı
MODEL_MAP = {
    "google/veo-3.1-fast-generate-001": "veo-3.1-fast-generate-001",
    "google/veo-3.1-lite-generate-001": "veo-3.1-lite-generate-001",
    "google/veo-3.1-generate-001": "veo-3.1-generate-001",
}
RESOLUTIONS = {"720p": "720p", "1080p": "1080p", "4k": "4k"}

_lock = threading.Lock()
_token: dict = {}


class VertexError(Exception):
    pass


def _credentials() -> dict | None:
    raw = (config.GOOGLE_VERTEX_CREDENTIALS or "").strip()
    if not raw:
        return None
    try:
        if not raw.startswith("{"):
            raw = base64.b64decode(raw).decode()
        creds = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as e:
        logger.error("GOOGLE_VERTEX_CREDENTIALS okunamadı: %s", e)
        return None
    if not creds.get("private_key") or not creds.get("client_email"):
        return None
    return creds


def is_enabled() -> bool:
    return config.VERTEX_VIDEO and _credentials() is not None and bool(project())


def project() -> str:
    creds = _credentials() or {}
    return config.VERTEX_PROJECT or creds.get("project_id") or ""


def handles(model: str) -> bool:
    return is_enabled() and model in MODEL_MAP


def _access_token() -> str:
    with _lock:
        if _token.get("value") and _token.get("exp", 0) > time.time() + 60:
            return _token["value"]
        creds = _credentials()
        if not creds:
            raise VertexError("Vertex kimliği tanımlı değil.")
        now = int(time.time())
        assertion = jwt.encode(
            {"iss": creds["client_email"], "scope": SCOPE, "aud": TOKEN_URL, "iat": now, "exp": now + 3600},
            creds["private_key"], algorithm="RS256",
        )
        try:
            r = requests.post(TOKEN_URL, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                               "assertion": assertion}, timeout=30)
        except requests.RequestException as e:
            raise VertexError(f"Google jetonu alınamadı: {e}") from e
        if r.status_code >= 400:
            raise VertexError(f"Google jetonu alınamadı ({r.status_code}): {r.text[:300]}")
        data = r.json()
        _token.update(value=data["access_token"], exp=now + int(data.get("expires_in", 3600)))
        return _token["value"]


def _model_url(model: str, method: str) -> str:
    loc = config.VERTEX_LOCATION
    host = "aiplatform.googleapis.com" if loc == "global" else f"{loc}-aiplatform.googleapis.com"
    return (f"https://{host}/v1/projects/{project()}/locations/{loc}/publishers/google/models/"
            f"{MODEL_MAP.get(model, model)}:{method}")


def _post(url: str, body: dict, timeout: float) -> dict:
    try:
        r = requests.post(url, json=body, timeout=timeout,
                          headers={"Authorization": f"Bearer {_access_token()}"})
    except requests.RequestException as e:
        raise VertexError(f"Vertex'e ulaşılamadı: {e}") from e
    if r.status_code >= 400:
        raise VertexError(f"Vertex {r.status_code}: {r.text[:400]}")
    try:
        return r.json()
    except ValueError as e:
        raise VertexError(f"Vertex beklenmeyen yanıt: {r.text[:200]}") from e


def _image(url: str) -> dict:
    from app.services import storage

    data = storage.fetch(url)
    mime = "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else (
        "image/webp" if data[:4] == b"RIFF" and data[8:12] == b"WEBP" else "image/jpeg")
    return {"bytesBase64Encoded": base64.b64encode(data).decode(), "mimeType": mime}


def start(model: str, prompt: str, duration: int, resolution: str, image_url: str | None,
          end_image_url: str | None, audio: bool, aspect_ratio: str) -> dict:
    instance: dict = {"prompt": prompt}
    if image_url:
        instance["image"] = _image(image_url)
        if end_image_url:
            instance["lastFrame"] = _image(end_image_url)
    parameters: dict = {
        "aspectRatio": aspect_ratio,
        "durationSeconds": duration,
        "resolution": RESOLUTIONS.get(resolution, "1080p"),
        "generateAudio": bool(audio),
        "sampleCount": 1,
    }
    if config.VERTEX_VIDEO_BUCKET:
        parameters["storageUri"] = f"gs://{config.VERTEX_VIDEO_BUCKET.strip('/')}/video/"
    data = _post(_model_url(model, "predictLongRunning"), {"instances": [instance], "parameters": parameters}, 60)
    name = data.get("name")
    if not name:
        raise VertexError(f"Vertex işi başlatılamadı: {str(data)[:300]}")
    return {"provider": "vertex", "model": model, "operation": name}


def status(job: dict) -> dict:
    """gateway_media.video_status ile aynı biçim: pending | completed (video) | error."""
    data = _post(_model_url(job["model"], "fetchPredictOperation"), {"operationName": job["operation"]}, 120)
    if not data.get("done"):
        return {"status": "pending"}
    if data.get("error"):
        return {"status": "error", "error": f"Vertex: {str(data['error'])[:400]}"}
    response = data.get("response") or {}
    videos = response.get("videos") or []
    if not videos:
        reasons = response.get("raiMediaFilteredReasons") or []
        logger.warning("Vertex videosuz döndü: %s", json.dumps(response, ensure_ascii=False)[:1000])
        return {"status": "error", "filtered": bool(reasons),
                "error": "Video boş döndü." + (f" Neden: {'; '.join(map(str, reasons))[:300]}" if reasons else "")}
    video = videos[0]
    if video.get("gcsUri"):
        return {"status": "completed", "video": {"type": "gcs", "uri": video["gcsUri"]}}
    return {"status": "completed", "video": {"type": "base64", "data": video.get("bytesBase64Encoded", ""),
                                             "mediaType": video.get("mimeType", "video/mp4")}}


def download_gcs(uri: str) -> bytes:
    if not uri.startswith("gs://"):
        raise VertexError(f"Geçersiz gcs adresi: {uri}")
    bucket, _, name = uri[5:].partition("/")
    url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{quote(name, safe='')}?alt=media"
    try:
        r = requests.get(url, headers={"Authorization": f"Bearer {_access_token()}"}, timeout=120)
    except requests.RequestException as e:
        raise VertexError(f"Video indirilemedi: {e}") from e
    if r.status_code >= 400:
        raise VertexError(f"Video indirilemedi ({r.status_code}): {r.text[:200]}")
    return r.content
