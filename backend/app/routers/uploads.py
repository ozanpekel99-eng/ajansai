import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.security import get_optional_user
from app.services import free_tier, storage
from app.services.plans import FREE_PLAN

router = APIRouter()


class UploadRequest(BaseModel):
    filename: str = Field(..., max_length=200)
    content_type: str = Field(..., max_length=120)
    size: int = Field(..., gt=0)


GUEST_UPLOADS_PER_DAY = 30
GUEST_MAX_SIZE = 10 * 1024 * 1024


@router.post("/token")
def upload_token(payload: UploadRequest, request: Request, user: dict | None = Depends(get_optional_user)):
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
    paid = bool(user) and user["plan"] != FREE_PLAN
    if not paid:
        # Ücretsiz kullanım ve ziyaretçi: görsel ve belge, günlük sınırla
        if kind == "video":
            raise HTTPException(status_code=403, detail="Video eklemek ücretli paketlerde açık.")
        max_size = min(max_size, GUEST_MAX_SIZE)
        from app.routers.free import client_ip

        subject = free_tier.subject_for(user, client_ip(request))
        try:
            free_tier.reserve_upload(subject, GUEST_UPLOADS_PER_DAY)
        except free_tier.FreeLimitError as e:
            raise HTTPException(status_code=429, detail=str(e))
    if payload.size > max_size:
        raise HTTPException(status_code=413, detail=f"Dosya en fazla {max_size // (1024 * 1024)} MB olabilir.")

    ext = re.sub(r"[^a-z0-9]", "", payload.filename.rsplit(".", 1)[-1].lower())[:6] if "." in payload.filename else "bin"
    owner = user["id"] if user else "misafir"
    pathname = f"yuklemeler/{owner}/{uuid.uuid4().hex}.{ext or 'bin'}"
    return {
        "client_token": storage.client_upload_token(pathname, payload.content_type, max_size),
        "pathname": pathname,
        "kind": kind,
    }
