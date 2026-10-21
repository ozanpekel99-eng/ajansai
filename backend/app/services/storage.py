"""Üretilen görsel ve videoların kalıcı olarak saklanması (Vercel Blob).

BLOB_READ_WRITE_TOKEN, Vercel'de projeye bir Blob deposu bağlanınca otomatik
tanımlanır. Tanımlı değilse dosya saklanamaz; çağıran taraf geçici bir adres
(görsel için data URL, video için sağlayıcının süreli bağlantısı) kullanır.
"""

import logging
import uuid

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
