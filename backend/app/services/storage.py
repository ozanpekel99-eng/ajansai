"""Üretilen görsel ve videoların kalıcı olarak saklanması (Vercel Blob).

BLOB_READ_WRITE_TOKEN, Vercel'de projeye bir Blob deposu bağlanınca otomatik
tanımlanır. Tanımlı değilse dosya saklanamaz; çağıran taraf geçici bir adres
(görsel için data URL, video için sağlayıcının süreli bağlantısı) kullanır.
"""

import base64 as _b64
import hashlib
import hmac
import json as _json
import logging
import time
import uuid
from urllib.parse import urlparse

import requests

from app import config

logger = logging.getLogger("ajansai.storage")

BLOB_API_URL = "https://vercel.com/api/blob"
EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "video/mp4": "mp4"}


class StorageError(Exception):
    pass


def is_enabled() -> bool:
    return bool(config.BLOB_READ_WRITE_TOKEN)


def save(data: bytes, mime: str, folder: str) -> str:
    """Dosyayı herkese açık Blob deposuna yükler ve kalıcı URL'sini döndürür."""
    if not is_enabled():
        raise StorageError("Blob deposu bağlı değil (BLOB_READ_WRITE_TOKEN).")
    pathname = f"{folder}/{uuid.uuid4().hex}.{EXTENSIONS.get(mime, 'bin')}"
    try:
        response = requests.put(
            f"{BLOB_API_URL}/",
            params={"pathname": pathname},
            data=data,
            headers={
                "authorization": f"Bearer {config.BLOB_READ_WRITE_TOKEN}",
                "x-api-version": "13",
                "x-vercel-blob-access": "public",
                "x-content-type": mime,
                "x-add-random-suffix": "0",
            },
            timeout=120,
        )
    except requests.RequestException as e:
        raise StorageError(f"Blob'a yüklenemedi: {e}") from e
    if response.status_code >= 400:
        raise StorageError(f"Blob {response.status_code}: {response.text[:300]}")
    url = response.json().get("url")
    if not url:
        raise StorageError(f"Blob yanıtında URL yok: {response.text[:200]}")
    return url


# ---------------- Tarayıcıdan doğrudan yükleme ----------------
# Vercel fonksiyonları 4,5 MB'tan büyük istek gövdesi kabul etmez. Bu yüzden
# kullanıcı dosyaları tarayıcıdan doğrudan Blob'a yüklenir; backend yalnızca
# kısa ömürlü, tek dosyalık bir "istemci token'ı" imzalar (@vercel/blob'daki
# generateClientTokenFromReadWriteToken ile aynı biçim).

UPLOAD_RULES = {
    # tür → (izin verilen MIME türleri, en büyük boyut)
    "image": ({"image/jpeg", "image/png", "image/webp"}, 20 * 1024 * 1024),
    "video": ({"video/mp4", "video/quicktime", "video/webm"}, 50 * 1024 * 1024),
    "document": (
        {
            "application/pdf",
            "text/plain",
            "text/csv",
            "text/markdown",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
        20 * 1024 * 1024,
    ),
}


def kind_of(content_type: str) -> str | None:
    for kind, (types, _) in UPLOAD_RULES.items():
        if content_type in types:
            return kind
    return None


def _store_id() -> str:
    parts = (config.BLOB_READ_WRITE_TOKEN or "").split("_")
    return parts[3] if len(parts) > 3 else ""


def client_upload_token(pathname: str, content_type: str, max_size: int, valid_seconds: int = 600) -> str:
    """Tarayıcının yalnızca bu yola, bu türde ve bu boyuta kadar dosya yükleyebileceği token."""
    if not is_enabled():
        raise StorageError("Blob deposu bağlı değil (BLOB_READ_WRITE_TOKEN).")
    payload = _b64.b64encode(
        _json.dumps(
            {
                "pathname": pathname,
                "allowedContentTypes": [content_type],
                "maximumSizeInBytes": max_size,
                "addRandomSuffix": True,
                "validUntil": int((time.time() + valid_seconds) * 1000),
            },
            separators=(",", ":"),
        ).encode()
    ).decode()
    signature = hmac.new(config.BLOB_READ_WRITE_TOKEN.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"vercel_blob_client_{_store_id()}_" + _b64.b64encode(f"{signature}.{payload}".encode()).decode()


def is_own_blob_url(url: str) -> bool:
    """Yalnızca kendi Blob depomuzdaki dosyalar işlenir (başka adreslere istek atılmaz)."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    store = _store_id().lower()
    return (
        parsed.scheme == "https"
        and bool(store)
        and parsed.hostname == f"{store}.public.blob.vercel-storage.com"
    )


def fetch(url: str, max_bytes: int = 50 * 1024 * 1024) -> bytes:
    if not is_own_blob_url(url):
        raise StorageError("Bu dosya ajansAI'a yüklenmemiş.")
    response = requests.get(url, timeout=60, stream=True)
    if response.status_code != 200:
        raise StorageError(f"Dosya okunamadı ({response.status_code}).")
    data = b""
    for chunk in response.iter_content(1024 * 256):
        data += chunk
        if len(data) > max_bytes:
            raise StorageError("Dosya çok büyük.")
    return data
