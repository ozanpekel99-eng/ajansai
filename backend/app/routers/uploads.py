import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.security import get_current_user
from app.services import storage

router = APIRouter()


class UploadRequest(BaseModel):
    filename: str = Field(..., max_length=200)
    content_type: str = Field(..., max_length=120)
    size: int = Field(..., gt=0)


@router.post("/token")
def upload_token(payload: UploadRequest, user: dict = Depends(get_current_user)):
    """Görsel, video veya belgeyi tarayıcıdan doğrudan depoya yüklemek için tek kullanımlık izin."""
    if not storage.is_enabled():
        raise HTTPException(status_code=503, detail="Dosya yükleme henüz yapılandırılmadı.")
    kind = storage.kind_of(payload.content_type)
    if kind is None:
        raise HTTPException(
            status_code=400,
            detail="Bu dosya türü desteklenmiyor. Görsel (JPG, PNG, WEBP), video (MP4, MOV, WEBM) "
            "veya belge (PDF, DOCX, TXT, CSV) yükleyebilirsin.",
        )
    max_size = storage.UPLOAD_RULES[kind][1]
    if payload.size > max_size:
        raise HTTPException(status_code=413, detail=f"Dosya en fazla {max_size // (1024 * 1024)} MB olabilir.")

    ext = re.sub(r"[^a-z0-9]", "", payload.filename.rsplit(".", 1)[-1].lower())[:6] if "." in payload.filename else "bin"
    pathname = f"yuklemeler/{user['id']}/{uuid.uuid4().hex}.{ext or 'bin'}"
    return {
        "client_token": storage.client_upload_token(pathname, payload.content_type, max_size),
        "pathname": pathname,
        "kind": kind,
    }
