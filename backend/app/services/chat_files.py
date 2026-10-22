"""Sohbette istenen dosyayı oluşturup depoya kaydeder."""

import base64
import logging

from app.services import documents, storage
from app.services.llm_service import LLMError

logger = logging.getLogger("ajansai.chat_files")


def make(request: dict, conversation: list[dict], folder: str) -> tuple[dict | None, str | None]:
    """({"name","url","mime","size","title","format"} veya None, hata mesajı) döndürür."""
    try:
        data, mime, name, title = documents.create(request, conversation)
    except (documents.DocumentError, LLMError) as e:
        logger.error("Dosya oluşturulamadı: %s", e)
        return None, "Dosya oluşturulamadı, tekrar dener misin?"
    if storage.is_enabled():
        try:
            url = storage.save(data, mime, folder, filename=name)
        except storage.StorageError as e:
            logger.error("Dosya saklanamadı: %s", e)
            return None, "Dosya kaydedilemedi, tekrar dener misin?"
    else:
        url = f"data:{mime};base64,{base64.b64encode(data).decode()}"
    return {"name": name, "url": url, "mime": mime, "size": len(data), "title": title, "format": request["format"]}, None
