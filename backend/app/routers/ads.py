from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from app import config
from app.db import get_engine, meta_connections, utcnow
from app.security import create_token, decode_token, get_current_user
from app.services.plans import CREDIT_COSTS
from app.services.usage_service import consume
from app.services.meta_ads_service import (
    MetaError,
    create_campaign_draft,
    exchange_code_for_token,
    get_oauth_url,
    list_ad_accounts,
)
from app.services.usage_service import AdsNotAvailableError, check_ads_access

router = APIRouter()


def _require_ads(user: dict) -> None:
    try:
        check_ads_access(user["id"])
    except AdsNotAvailableError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not (config.META_APP_ID and config.META_APP_SECRET):
        raise HTTPException(status_code=503, detail="Meta entegrasyonu henüz yapılandırılmadı.")


def _get_token(user_id: str) -> str:
    with get_engine().connect() as conn:
        row = conn.execute(
            select(meta_connections.c.access_token).where(meta_connections.c.user_id == user_id)
        ).first()
    if row is None:
        raise HTTPException(status_code=409, detail="Önce Meta hesabını bağlamalısın.")
    return row.access_token


@router.get("/meta/status")
def meta_status(user: dict = Depends(get_current_user)):
    with get_engine().connect() as conn:
        row = conn.execute(
            select(meta_connections.c.updated_at).where(meta_connections.c.user_id == user["id"])
        ).first()
    return {"connected": row is not None}


@router.get("/meta/connect")
def meta_connect(user: dict = Depends(get_current_user)):
    """Kullanıcının Meta hesabını bağlaması için yönlendirme URL'si döndürür."""
    _require_ads(user)
    state = create_token(user["id"], purpose="meta_oauth", expires=timedelta(minutes=15))
    return {"oauth_url": get_oauth_url(config.META_REDIRECT_URI, state)}


class MetaCallbackRequest(BaseModel):
    code: str
    state: str


@router.post("/meta/callback")
def meta_callback(payload: MetaCallbackRequest, user: dict = Depends(get_current_user)):
    """Meta'dan dönen kodu token'a çevirir ve sunucuda saklar (istemciye gönderilmez)."""
    _require_ads(user)
    try:
        state_user = decode_token(payload.state, purpose="meta_oauth")
    except ValueError:
        raise HTTPException(status_code=400, detail="Bağlantı isteği geçersiz veya süresi dolmuş, tekrar dene.")
    if state_user != user["id"]:
        raise HTTPException(status_code=400, detail="Bağlantı isteği bu hesaba ait değil.")

    try:
        token = exchange_code_for_token(payload.code, config.META_REDIRECT_URI)
    except MetaError as e:
        raise HTTPException(status_code=502, detail=str(e))

    with get_engine().begin() as conn:
        conn.execute(delete(meta_connections).where(meta_connections.c.user_id == user["id"]))
        conn.execute(meta_connections.insert().values(user_id=user["id"], access_token=token, updated_at=utcnow()))
    return {"connected": True}


@router.delete("/meta/connection")
def meta_disconnect(user: dict = Depends(get_current_user)):
    with get_engine().begin() as conn:
        conn.execute(delete(meta_connections).where(meta_connections.c.user_id == user["id"]))
    return {"connected": False}


@router.get("/meta/ad-accounts")
def meta_ad_accounts(user: dict = Depends(get_current_user)):
    _require_ads(user)
    try:
        return {"ad_accounts": list_ad_accounts(_get_token(user["id"]))}
    except MetaError as e:
        raise HTTPException(status_code=502, detail=str(e))


class CampaignDraftRequest(BaseModel):
    ad_account_id: str = Field(..., max_length=50)
    campaign_name: str = Field(..., max_length=200, examples=["Yaz Kahve Kampanyası"])


@router.post("/meta/campaign-draft")
def meta_campaign_draft(payload: CampaignDraftRequest, user: dict = Depends(get_current_user)):
    """PAUSED durumda bir kampanya taslağı oluşturur; yayına alma kullanıcıya bırakılır."""
    _require_ads(user)
    try:
        result = create_campaign_draft(
            ad_account_id=payload.ad_account_id,
            access_token=_get_token(user["id"]),
            campaign_name=payload.campaign_name,
        )
    except MetaError as e:
        raise HTTPException(status_code=502, detail=str(e))
    # Kredi düşmez; kullanım geçmişinde görünsün diye 0 kredilik kayıt.
    consume(user["id"], "ads_draft", CREDIT_COSTS["ads_draft"], payload.campaign_name)
    return result
