import json
import logging
import re
import uuid
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select

from app import config
from app.db import get_engine, meta_ads, meta_connections, utcnow
from app.security import create_token, decode_token, get_current_user
from app.services.plans import CREDIT_COSTS
from app.services.usage_service import QuotaExceededError, consume, refund
from app.services import meta_ads_service as meta
from app.services import storage
from app.services.meta_ads_service import (
    MetaError,
    create_campaign_draft,
    exchange_code_for_token,
    get_oauth_url,
    list_ad_accounts,
)
from app.services.usage_service import AdsNotAvailableError, check_ads_access

router = APIRouter()
logger = logging.getLogger("ajansai.ads")


def _require_ads(user: dict, needs_meta: bool = True) -> None:
    try:
        check_ads_access(user["id"])
    except AdsNotAvailableError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if needs_meta and not (config.META_APP_ID and config.META_APP_SECRET):
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
    return {"connected": row is not None, "mode": config.ADS_MODE}


@router.get("/meta/connect")
def meta_connect(publishing: bool = False, user: dict = Depends(get_current_user)):
    """Kullanıcının Meta hesabını bağlaması için yönlendirme URL'si döndürür.

    publishing=1 yalnızca yöneticiler içindir: ajansAI'nin kendi Instagram hesabına paylaşım,
    DM ve yorum izinlerini de isteyen yapılandırmayla bağlanır (uygulamada rolü olan hesaplar için
    Meta'nın standart erişimi yeterlidir).
    """
    _require_ads(user)
    admin = (user.get("email") or "").lower() in config.ADMIN_EMAILS
    if publishing and not admin:
        raise HTTPException(status_code=403, detail="Bu bağlantı yalnızca yöneticiler içindir.")
    state = create_token(user["id"], purpose="meta_oauth", expires=timedelta(minutes=15))
    cfg = config.META_ADMIN_CONFIG_ID if publishing else None
    return {"oauth_url": get_oauth_url(config.META_REDIRECT_URI, state, cfg)}


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


def _meta_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except MetaError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/meta/setup")
def meta_setup(user: dict = Depends(get_current_user)):
    """Reklam öncesi hazırlık listesi: eksik adımlar ve tek tıklık çözüm bağlantıları."""
    _require_ads(user)
    return _meta_call(meta.setup_status, _get_token(user["id"]))


@router.get("/meta/whatsapp")
def meta_whatsapp(page_id: str, user: dict = Depends(get_current_user)):
    """Seçilen sayfaya bağlı WhatsApp numarası."""
    _require_ads(user)
    return _meta_call(meta.page_whatsapp, _get_token(user["id"]), page_id)


@router.get("/meta/posts")
def meta_posts(page_id: str, instagram_user_id: str | None = None, user: dict = Depends(get_current_user)):
    """Reklamda kullanılabilecek son Instagram ve Facebook gönderileri."""
    _require_ads(user)
    return {"posts": _meta_call(meta.recent_posts, _get_token(user["id"]), page_id, instagram_user_id)}


@router.get("/meta/pages")
def meta_pages(ad_account_id: str | None = None, fresh: bool = False, user: dict = Depends(get_current_user)):
    _require_ads(user)
    return {"pages": _meta_call(meta.list_pages, _get_token(user["id"]), ad_account_id, fresh)}


@router.get("/meta/page-instagram")
def meta_page_instagram(page_id: str, user: dict = Depends(get_current_user)):
    """Seçilen sayfaya bağlı Instagram hesabı (listede görünmediyse)."""
    _require_ads(user)
    return {"instagram": meta.page_instagram(_get_token(user["id"]), page_id)}


@router.get("/meta/instagram-accounts")
def meta_instagram_accounts(ad_account_id: str, user: dict = Depends(get_current_user)):
    _require_ads(user)
    return {"accounts": _meta_call(meta.list_instagram_accounts, ad_account_id, _get_token(user["id"]))}


@router.get("/meta/locations")
def meta_locations(q: str, user: dict = Depends(get_current_user)):
    _require_ads(user)
    if len(q.strip()) < 2:
        return {"locations": []}
    return {"locations": _meta_call(meta.search_locations, q.strip()[:60], _get_token(user["id"]))}


class Location(BaseModel):
    key: str = Field(..., max_length=40)
    name: str = Field("", max_length=120)
    type: Literal["country", "region", "city"]
    country_code: str | None = None


class AdMedia(BaseModel):
    url: str = Field(..., max_length=2000)
    kind: Literal["image", "video"]


class SourcePost(BaseModel):
    platform: Literal["instagram", "facebook"]
    id: str = Field(..., max_length=100)
    thumbnail: str | None = Field(None, max_length=3000)


class CarouselCard(BaseModel):
    media: AdMedia
    headline: str = Field("", max_length=80)
    link: str | None = Field(None, max_length=1000)


CTA_TYPES = ("LEARN_MORE", "SHOP_NOW", "ORDER_NOW", "BOOK_NOW", "CONTACT_US", "SIGN_UP", "GET_OFFER")


class CreateAdRequest(BaseModel):
    ad_account_id: str = Field(..., max_length=50)
    page_id: str = Field(..., max_length=50)
    instagram_user_id: str | None = Field(None, max_length=50)
    name: str = Field(..., min_length=2, max_length=150)
    objective: Literal["profile", "traffic", "whatsapp", "instagram_dm", "awareness"]
    daily_budget: float = Field(..., gt=0, le=10_000_000)  # günlük ya da toplam tutar (budget_type)
    budget_type: Literal["daily", "lifetime"] = "daily"
    publish: bool = True  # False: duraklatılmış taslak
    currency: str = Field("TRY", max_length=3)
    start_date: date | None = None
    end_date: date | None = None
    locations: list[Location] = Field(default_factory=list, max_length=25)
    age_min: int = Field(18, ge=18, le=65)
    age_max: int = Field(65, ge=18, le=65)
    gender: Literal["all", "male", "female"] = "all"
    # Reklam içeriği: yeni görsel/video (media), karusel (2-10 kart) ya da mevcut gönderi
    media: AdMedia | None = None
    carousel: list[CarouselCard] = Field(default_factory=list, max_length=10)
    source_post: SourcePost | None = None
    # Hikâye ve Reels için dikey (9:16) görsel/video; verilmezse ana medya her yerde kullanılır
    story_media: AdMedia | None = None
    placements: list[str] = Field(default_factory=lambda: list(meta.DEFAULT_PLACEMENTS), max_length=10)
    primary_text: str = Field("", max_length=2000)
    headline: str = Field("", max_length=120)
    link: str | None = Field(None, max_length=1000)
    call_to_action: str = "LEARN_MORE"

    @field_validator("link")
    @classmethod
    def _https(cls, v):
        if v and not re.match(r"^https?://", v):
            return "https://" + v
        return v


@router.post("/meta/ads")
def meta_create_ad(payload: CreateAdRequest, user: dict = Depends(get_current_user)):
    """Instagram'a özel reklamı (kampanya + reklam seti + kreatif + reklam) duraklatılmış oluşturur."""
    _require_ads(user)
    if payload.age_min > payload.age_max:
        raise HTTPException(status_code=400, detail="Minimum yaş, maksimum yaştan büyük olamaz.")
    if payload.objective in ("traffic", "awareness") and not payload.link:
        raise HTTPException(status_code=400, detail="Bu reklam amacı için bir web sitesi bağlantısı gerekli.")
    if payload.objective in ("profile", "instagram_dm") and not payload.instagram_user_id:
        raise HTTPException(status_code=400, detail="Bu reklam için bir Instagram hesabı seçmelisin.")
    if payload.call_to_action not in CTA_TYPES:
        raise HTTPException(status_code=400, detail="Geçersiz buton türü.")
    payload.placements = [p for p in payload.placements if p != "instagram_explore"]  # eski arayüzlerden gelebilir
    bad = [p for p in payload.placements if p not in meta.PLACEMENTS]
    if bad or not payload.placements:
        raise HTTPException(status_code=400, detail="En az bir geçerli reklam alanı seç.")
    modes = [bool(payload.media), bool(payload.carousel), bool(payload.source_post)]
    if sum(modes) != 1:
        raise HTTPException(status_code=400, detail="Reklam için bir görsel/video, karusel ya da mevcut bir gönderi seç.")
    if payload.carousel and not 2 <= len(payload.carousel) <= 10:
        raise HTTPException(status_code=400, detail="Karusel 2 ile 10 kart arasında olmalı.")
    own = [m.url for m in [payload.media, payload.story_media] if m] + [c.media.url for c in payload.carousel]
    if any(not storage.is_own_blob_url(u) for u in own):
        raise HTTPException(status_code=400, detail="Reklam görselleri ajansAI'a yüklenmiş olmalı.")
    if payload.source_post and payload.source_post.platform == "instagram" and not payload.instagram_user_id:
        raise HTTPException(status_code=400, detail="Instagram gönderisi için Instagram hesabı seçmelisin.")
    if not payload.source_post and not payload.primary_text.strip():
        raise HTTPException(status_code=400, detail="Reklam metnini yaz.")
    placements = payload.placements
    if payload.source_post:
        # Mevcut gönderi yalnızca kendi platformunun alanlarında yayınlanır
        own_platform = [p for p in placements if p.startswith(payload.source_post.platform)]
        defaults = (["instagram_feed", "instagram_story", "instagram_reels"]
                    if payload.source_post.platform == "instagram" else ["facebook_feed"])
        placements = own_platform or defaults
    if payload.budget_type == "lifetime" and not payload.end_date:
        raise HTTPException(status_code=400, detail="Toplam bütçede bitiş tarihi seçmelisin.")
    if payload.end_date and payload.start_date and payload.end_date <= payload.start_date:
        raise HTTPException(status_code=400, detail="Bitiş tarihi başlangıçtan sonra olmalı.")

    start = f"{payload.start_date.isoformat()}T00:00:00+0300" if payload.start_date else None
    end = f"{payload.end_date.isoformat()}T23:59:00+0300" if payload.end_date else None
    ids = _meta_call(
        meta.create_instagram_ad,
        token=_get_token(user["id"]),
        ad_account_id=payload.ad_account_id,
        page_id=payload.page_id,
        instagram_user_id=payload.instagram_user_id,
        name=payload.name,
        objective=payload.objective,
        daily_budget=payload.daily_budget,
        start_time=start,
        end_time=end,
        locations=[loc.model_dump() for loc in payload.locations],
        age_min=payload.age_min,
        age_max=payload.age_max,
        gender=payload.gender,
        media=payload.media.model_dump() if payload.media else None,
        primary_text=payload.primary_text,
        headline=payload.headline,
        link=payload.link,
        call_to_action=payload.call_to_action,
        fetch_bytes=storage.fetch,
        placements=placements,
        story_media=payload.story_media.model_dump() if payload.story_media else None,
        source_post=payload.source_post.model_dump() if payload.source_post else None,
        carousel=[c.model_dump() for c in payload.carousel] or None,
        budget_type=payload.budget_type,
        publish=payload.publish,
    )
    record_id = str(uuid.uuid4())
    with get_engine().begin() as conn:
        conn.execute(
            meta_ads.insert().values(
                id=record_id,
                user_id=user["id"],
                ad_account_id=payload.ad_account_id.removeprefix("act_"),
                campaign_id=ids["campaign_id"],
                adset_id=ids["adset_id"],
                ad_id=ids["ad_id"],
                name=payload.name,
                objective=payload.objective,
                daily_budget=payload.daily_budget,
                currency=payload.currency[:3].upper(),
                budget_type=payload.budget_type,
                media_url=(payload.media.url if payload.media else payload.carousel[0].media.url if payload.carousel
                           else (payload.source_post.thumbnail or "")),
                created_at=utcnow(),
            )
        )
    consume(user["id"], "ads_draft", CREDIT_COSTS["ads_draft"], payload.name)
    return {"id": record_id, **ids}


def _own_ad(user_id: str, record_id: str):
    with get_engine().connect() as conn:
        row = conn.execute(
            select(meta_ads).where(meta_ads.c.id == record_id, meta_ads.c.user_id == user_id)
        ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Reklam bulunamadı.")
    return row


@router.get("/meta/ads")
def meta_list_ads(range: str = "maximum", user: dict = Depends(get_current_user)):
    """Kullanıcının ajansAI'dan oluşturduğu reklamlar; durum, inceleme ve metrikler Meta'dan canlı.

    range: today | yesterday | last_7d | last_30d | maximum
    """
    _require_ads(user)
    token = _get_token(user["id"])
    with get_engine().connect() as conn:
        rows = conn.execute(
            select(meta_ads).where(meta_ads.c.user_id == user["id"]).order_by(meta_ads.c.created_at.desc()).limit(30)
        ).all()
    ads = []
    for r in rows:
        item = {
            "id": r.id,
            "name": r.name,
            "objective": r.objective,
            "daily_budget": float(r.daily_budget),
            "budget_type": r.budget_type or "daily",
            "currency": r.currency,
            "media_url": r.media_url,
            "campaign_id": r.campaign_id,
            "ad_account_id": r.ad_account_id,
            "created_at": r.created_at.isoformat() + "Z",
        }
        try:
            delivery = meta.ad_delivery(token, r.campaign_id, r.ad_id)
            item["status"], item["review"] = delivery["status"], delivery["review"]
            item["insights"] = meta.campaign_insights(token, r.campaign_id, r.objective, range)
        except MetaError as e:
            item["status"] = item.get("status") or "UNKNOWN"
            item["insights"] = None
            item["error"] = str(e)
        ads.append(item)
    return {"ads": ads, "range": range}


@router.post("/meta/ads/{record_id}/publish")
def meta_publish_ad(record_id: str, user: dict = Depends(get_current_user)):
    """Reklamı yayına alır (bütçe harcanmaya başlar)."""
    _require_ads(user)
    row = _own_ad(user["id"], record_id)
    _meta_call(meta.set_status, _get_token(user["id"]), [row.ad_id, row.adset_id, row.campaign_id], "ACTIVE")
    return {"status": "ACTIVE"}


@router.post("/meta/ads/{record_id}/pause")
def meta_pause_ad(record_id: str, user: dict = Depends(get_current_user)):
    _require_ads(user)
    row = _own_ad(user["id"], record_id)
    _meta_call(meta.set_status, _get_token(user["id"]), [row.campaign_id], "PAUSED")
    return {"status": "PAUSED"}


class AdCopyRequest(BaseModel):
    brief: str = Field(..., min_length=3, max_length=1500)
    objective: Literal["profile", "traffic", "whatsapp", "instagram_dm", "awareness"] = "traffic"


@router.post("/meta/ad-copy")
def meta_ad_copy(payload: AdCopyRequest, user: dict = Depends(get_current_user)):
    """Yapay zeka ile Instagram reklam metni (ana metin + başlık) yazar. 1 kredi."""
    from app.services.llm_service import LLMError, chat_completion

    _require_ads(user, needs_meta=False)
    try:
        event_id = consume(user["id"], "describe", CREDIT_COSTS["describe"], f"Reklam metni: {payload.brief[:150]}")
    except QuotaExceededError as e:
        raise HTTPException(status_code=402, detail=str(e))
    goal = _GOAL_TEXT[payload.objective]
    prompt = (
        "Türkçe bir Instagram reklamı için metin yaz. Amaç: " + goal + ".\n"
        "Ürün/işletme bilgisi: " + payload.brief + "\n"
        'Sadece şu JSON\'u döndür: {"primary_text": "en fazla 300 karakter, emoji kullanabilir, harekete geçiren", '
        '"headline": "en fazla 40 karakter"}'
    )
    try:
        text = chat_completion(config.CHAT_MODEL, [{"role": "user", "content": prompt}], max_tokens=500)
        match = re.search(r"\{.*\}", text, re.S)
        data = json.loads(match.group(0)) if match else {}
        if not data.get("primary_text"):
            raise ValueError("boş")
    except (LLMError, ValueError) as e:
        logger.error("Reklam metni yazılamadı: %s", e)
        refund(event_id)
        raise HTTPException(status_code=503, detail="Reklam metni yazılamadı, kredin iade edildi. Tekrar dene.")
    return {"primary_text": data["primary_text"][:2000], "headline": (data.get("headline") or "")[:120]}



_GOAL_TEXT = {
    "profile": "Instagram profilini ziyaret etme",
    "traffic": "web sitesine tıklama",
    "whatsapp": "WhatsApp'tan mesaj atma",
    "instagram_dm": "Instagram'dan DM atma",
    "awareness": "markayı tanıma",
}


class AdPackageRequest(BaseModel):
    brief: str = Field(..., min_length=3, max_length=1500)
    objective: Literal["profile", "traffic", "whatsapp", "instagram_dm", "awareness"] = "profile"
    location: str = Field("Türkiye", max_length=200)
    age_min: int = Field(18, ge=18, le=65)
    age_max: int = Field(65, ge=18, le=65)
    daily_budget: int = Field(150, ge=30, le=100000)
    days: int = Field(7, ge=1, le=60)


@router.post("/package")
def ad_package(payload: AdPackageRequest, user: dict = Depends(get_current_user)):
    """Reklam paketi: metin, başlık, buton ve hedef kitle önerisi (Meta API'siz mod). 1 kredi."""
    from app.services.llm_service import LLMError, chat_completion

    _require_ads(user, needs_meta=False)
    try:
        event_id = consume(user["id"], "describe", CREDIT_COSTS["describe"], f"Reklam paketi: {payload.brief[:150]}")
    except QuotaExceededError as e:
        raise HTTPException(status_code=402, detail=str(e))
    prompt = (
        "Türkiye'deki küçük bir işletme için Instagram reklamı hazırlıyorsun. Amaç: " + _GOAL_TEXT[payload.objective] + ".\n"
        "İşletme/ürün/kampanya: " + payload.brief + "\n"
        "Konum: " + payload.location + f", yaş {payload.age_min}-{payload.age_max}.\n"
        "Sadece şu JSON'u döndür (Türkçe, sade, abartısız, fiyat/indirim gibi bilgileri yalnızca verildiyse kullan): "
        '{"primary_text": "reklam ana metni, en fazla 300 karakter, 1-2 emoji olabilir, harekete geçiren", '
        '"headline": "en fazla 40 karakter", '
        '"interests": ["Instagram reklam hedeflemesinde aranabilecek 4-6 ilgi alanı, Türkçe, kısa"], '
        '"audience_note": "bu kitleyi neden seçtiğimizi anlatan tek cümle"}'
    )
    try:
        text = chat_completion(config.CHAT_MODEL, [{"role": "user", "content": prompt}], max_tokens=700)
        match = re.search(r"\{.*\}", text, re.S)
        data = json.loads(match.group(0)) if match else {}
        if not data.get("primary_text"):
            raise ValueError("boş")
    except (LLMError, ValueError) as e:
        logger.error("Reklam paketi hazırlanamadı: %s", e)
        refund(event_id)
        raise HTTPException(status_code=503, detail="Reklam paketi hazırlanamadı, kredin iade edildi. Tekrar dene.")
    cta = {"profile": "Profili ziyaret et", "traffic": "Daha fazla bilgi", "whatsapp": "WhatsApp'tan mesaj gönder",
           "instagram_dm": "Mesaj gönder", "awareness": "Daha fazla bilgi"}[payload.objective]
    interests = [str(i)[:60] for i in (data.get("interests") or []) if str(i).strip()][:6]
    return {
        "primary_text": str(data["primary_text"])[:2000],
        "headline": str(data.get("headline") or "")[:120],
        "cta": cta,
        "interests": interests,
        "audience_note": str(data.get("audience_note") or "")[:300],
        "location": payload.location,
        "age_min": min(payload.age_min, payload.age_max),
        "age_max": max(payload.age_min, payload.age_max),
        "daily_budget": payload.daily_budget,
        "days": payload.days,
        "total_budget": payload.daily_budget * payload.days,
    }
