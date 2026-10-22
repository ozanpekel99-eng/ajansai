"""Ücretsiz paket: kredi harcamadan fikir sohbeti, ücretsiz AI görseli ve stok fotoğraf.

Maliyet sıfıra yakın tutulur:
- Sohbet Groq / Cerebras ücretsiz katmanlarıyla ($0), kotalar dolarsa Claude Haiku 5.5 ile
  (mesaj başı ~$0,0007); yalnızca metin, kısa geçmiş.
- Görsel Cloudflare Workers AI'ın günlük ücretsiz kotasıyla (FLUX.1 schnell); site geneli
  günlük tavan ücretsiz kotanın altında tutulur, aşılırsa üretim ertesi güne kalır.
- Stok fotoğraflar Pexels'ten (ücretsiz, ticari kullanım serbest).

Giriş yapmamış ziyaretçiler IP adresinin özetiyle sayılır (IP'nin kendisi saklanmaz).
"""

import base64
import io
import hashlib
import json
import logging
import re
import uuid
from datetime import timedelta
from urllib.parse import urlparse

import requests
from sqlalchemy import and_, delete, func, select

from app import config
from app.db import free_events, get_engine, stock_cache, utcnow
from app.services import assistant
from app.services.llm_service import free_chat_completion

logger = logging.getLogger("ajansai.free")

DAY = timedelta(days=1)
MONTH = timedelta(days=30)
STOCK_PER_DAY = 200  # kişi başı arama sınırı (sonuçlar önbellekten de gelir)
STOCK_CACHE_TTL = timedelta(hours=24)
PEXELS_HOSTS = {"images.pexels.com"}
PIXABAY_HOSTS = {"pixabay.com", "cdn.pixabay.com"}
PIXABAY_ORIENTATION = {"landscape": "horizontal", "portrait": "vertical"}


class FreeLimitError(Exception):
    pass


class FreeServiceError(Exception):
    pass


# ---------------- Kimlik ve sınırlar ----------------

def subject_for(user: dict | None, ip: str) -> str:
    if user:
        return f"u:{user['id']}"
    from app.security import _jwt_secret

    salt = _jwt_secret()
    return "ip:" + hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()[:40]


def limits(signed_in: bool) -> dict:
    return {
        "chat_per_day": config.FREE_CHAT_PER_DAY_USER if signed_in else config.FREE_CHAT_PER_DAY_ANON,
        "images_per_month": config.FREE_IMAGES_PER_MONTH,
    }


def _count(conn, kind: str, since, subject: str | None = None) -> int:
    cond = [free_events.c.kind == kind, free_events.c.created_at >= since]
    if subject:
        cond.append(free_events.c.subject == subject)
    return conn.execute(select(func.count()).select_from(free_events).where(and_(*cond))).scalar_one()


def _reserve(subject: str, kind: str, limit: int, window: timedelta, total_limit: int | None, message: str) -> str:
    """Sınır içindeyse bir kullanım kaydı ekler ve id'sini döndürür.

    Önce yazıp sonra sayar; aynı anda gelen istekler sınırı aşarsa fazlası geri alınır.
    """
    event_id = str(uuid.uuid4())
    now = utcnow()
    with get_engine().begin() as conn:
        conn.execute(free_events.insert().values(id=event_id, subject=subject, kind=kind, created_at=now))
    with get_engine().connect() as conn:
        mine = _count(conn, kind, now - window, subject)
        total = 0
        if total_limit:
            total = _count(conn, kind, now - DAY)
            if kind == "image":  # örnekli üretim iki kat kota harcar
                total += _count(conn, "image_extra", now - DAY)
    if mine > limit:
        release(event_id)
        raise FreeLimitError(message)
    if total_limit and total > total_limit:
        release(event_id)
        raise FreeLimitError("Bugünkü ücretsiz kullanım kotası doldu. Yarın tekrar dene ya da bir paket seç.")
    return event_id


def release(event_id: str) -> None:
    """Başarısız işlemde kullanım hakkını geri verir (virgülle birden çok kayıt olabilir)."""
    with get_engine().begin() as conn:
        conn.execute(delete(free_events).where(free_events.c.id.in_(event_id.split(","))))


def status(subject: str, signed_in: bool) -> dict:
    now = utcnow()
    lim = limits(signed_in)
    with get_engine().connect() as conn:
        chat_used = _count(conn, "chat", now - DAY, subject)
        images_used = _count(conn, "image", now - MONTH, subject)
    return {
        "signed_in": signed_in,
        "chat": {"used": chat_used, "limit": lim["chat_per_day"], "remaining": max(lim["chat_per_day"] - chat_used, 0)},
        "images": {
            "used": images_used,
            "limit": lim["images_per_month"],
            "remaining": max(lim["images_per_month"] - images_used, 0),
        },
        "ai_image_enabled": image_enabled(),
        "stock_enabled": stock_enabled(),
    }


# ---------------- Sohbet ----------------

FREE_NOTE = "\n- Yanıtları derli toplu tut."

# Sohbetten görsel üretimi (ChatGPT gibi): model görsel istendiğini bu satırla bildirir.
IMAGE_TOOL_NOTE = (
    "\n- Görsel üretebilirsin. Kullanıcı açıkça bir görsel, fotoğraf, afiş veya gönderi görseli üretmeni/çizmeni "
    "isterse (ör. 'bunun görselini üret', 'bir post görseli yap'), yanıtını kısa tut (1-2 cümle, gerekirse caption) ve "
    "en sona tek satır olarak şunu ekle: [[GORSEL: <İngilizce, en fazla 60 kelimelik görüntü istemi: konu, ortam, ışık, "
    "stil>]]. Kullanıcı görsel eklediyse ve onu kullanmak/değiştirmek istiyorsa istemde 'the product in image 0' gibi "
    "ona atıf yap. Görsel istenmedikçe bu satırı ekleme. Görsel üretemeyeceğini asla söyleme; satırı eklemen yeterli, "
    "görseli sistem üretip mesajının altında gösterir. Satırda yazı/logo isteme; görselde metin olmasın."
)
IMAGE_TAG = re.compile(r"\[\[\s*G[ÖO]RSEL\s*:\s*(.+?)\]\]", re.IGNORECASE | re.DOTALL)
HISTORY_MESSAGES = 8
MESSAGE_CHARS = 3000


def split_image_request(text: str) -> tuple[str, str | None]:
    """Yanıttaki [[GORSEL: ...]] satırını ayırır: (görünen metin, görsel istemi)."""
    m = IMAGE_TAG.search(text)
    if not m:
        return text, None
    return IMAGE_TAG.sub("", text).strip(), m.group(1).strip()[:1500]


def chat(subject: str, signed_in: bool, history: list[dict]) -> tuple[str, str | None]:
    """(yanıt metni, görsel istemi veya None) döndürür."""
    lim = limits(signed_in)["chat_per_day"]
    msg = (
        f"Ücretsiz pakette günde {lim} mesaj hakkın var ve bugünkü hakkın doldu. "
        + ("Yarın devam edebilir ya da bir paket seçebilirsin." if signed_in else "Ücretsiz üye olursan günde daha fazla mesaj yazabilirsin.")
    )
    event_id = _reserve(subject, "chat", lim, DAY, config.FREE_CHAT_PER_DAY_TOTAL, msg)
    system = assistant.SYSTEM_PROMPT + FREE_NOTE + (IMAGE_TOOL_NOTE if image_enabled() else "")
    messages = [{"role": "system", "content": system}]
    for m in history[-HISTORY_MESSAGES:]:
        content = (m.get("content") or "")[:MESSAGE_CHARS]
        n = len(m.get("attachments") or [])
        if n:
            content = f"{content}\n[Kullanıcı bu mesaja {n} görsel ekledi: image 0{', image 1' if n > 1 else ''}]".strip()
        messages.append({"role": m["role"], "content": content or "(boş mesaj)"})
    try:
        text, _ = free_chat_completion(messages, max_tokens=1200)
    except Exception:
        release(event_id)
        raise
    return split_image_request(text)


# ---------------- Ücretsiz AI görseli (Cloudflare Workers AI) ----------------

def image_enabled() -> bool:
    return bool(config.CLOUDFLARE_ACCOUNT_ID and config.CLOUDFLARE_AI_TOKEN)


def _english_prompt(concept: str) -> str:
    """FLUX İngilizce istemlerde daha iyi sonuç verir; ücretsiz zincirle kısa bir çeviri."""
    try:
        text, _ = free_chat_completion(
            [
                {
                    "role": "user",
                    "content": "Translate this social media image idea into one concise English image-generation "
                    "prompt (max 60 words, describe subject, setting, light, style). If it mentions the uploaded/reference "
                    "image or product, keep that reference (e.g. 'the product from image 0'). Reply with the prompt only.\n\n"
                    + concept,
                }
            ],
            max_tokens=300,
        )
        return text.strip() or concept
    except Exception as e:  # çeviri olmazsa özgün metinle devam
        logger.warning("İstem çevrilemedi: %s", e)
        return concept


def _cloudflare_image(prompt: str) -> bytes:
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{config.CLOUDFLARE_ACCOUNT_ID}"
        f"/ai/run/{config.FREE_IMAGE_MODEL}"
    )
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {config.CLOUDFLARE_AI_TOKEN}"},
            json={"prompt": prompt[:2048], "steps": 4},
            timeout=90,
        )
    except requests.RequestException as e:
        raise FreeServiceError(f"Cloudflare'e ulaşılamadı: {e}") from e
    if r.status_code >= 400:
        raise FreeServiceError(f"Cloudflare {r.status_code}: {r.text[:300]}")
    image = ((r.json() or {}).get("result") or {}).get("image")
    if not image:
        raise FreeServiceError(f"Cloudflare yanıtında görsel yok: {r.text[:200]}")
    return base64.b64decode(image)


def reserve_image(subject: str, signed_in: bool, with_reference: bool = False) -> str:
    lim = limits(signed_in)["images_per_month"]
    msg = (
        f"Ücretsiz pakette 30 günde {lim} görsel üretebilirsin ve bu hakkın doldu. "
        "Stok kütüphanesinden fotoğraf seçmeye devam edebilir ya da bir paketle sınırsız üretebilirsin."
    )
    extra = None
    if with_reference:
        extra = str(uuid.uuid4())
        with get_engine().begin() as conn:
            conn.execute(free_events.insert().values(id=extra, subject=subject, kind="image_extra", created_at=utcnow()))
    try:
        event_id = _reserve(subject, "image", lim, MONTH, config.FREE_IMAGES_PER_DAY_TOTAL, msg)
    except FreeLimitError:
        if extra:
            release(extra)
        raise
    return f"{event_id},{extra}" if extra else event_id


def _small_reference(data: bytes) -> bytes:
    """FLUX.2 klein örnek görselleri 512x512'den küçük ister."""
    from PIL import Image, ImageOps

    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except Exception as e:
        raise FreeServiceError("Örnek görsel okunamadı.") from e
    img.thumbnail((508, 508))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=90)
    return out.getvalue()


def _cloudflare_ref_image(prompt: str, references: list[bytes]) -> bytes:
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{config.CLOUDFLARE_ACCOUNT_ID}"
        f"/ai/run/{config.FREE_IMAGE_REF_MODEL}"
    )
    files = {f"input_image_{i}": (f"ref{i}.jpg", _small_reference(b), "image/jpeg") for i, b in enumerate(references[:4])}
    data = {"prompt": prompt[:2048], "width": "1024", "height": "1024"}
    try:
        r = requests.post(url, headers={"Authorization": f"Bearer {config.CLOUDFLARE_AI_TOKEN}"}, data=data, files=files, timeout=120)
    except requests.RequestException as e:
        raise FreeServiceError(f"Cloudflare'e ulaşılamadı: {e}") from e
    if r.status_code >= 400:
        raise FreeServiceError(f"Cloudflare {r.status_code}: {r.text[:300]}")
    image = ((r.json() or {}).get("result") or {}).get("image")
    if not image:
        raise FreeServiceError(f"Cloudflare yanıtında görsel yok: {r.text[:200]}")
    return base64.b64decode(image)


def generate_image(concept: str, references: list[bytes] | None = None, translate: bool = True) -> bytes:
    prompt = _english_prompt(concept) if translate else concept
    if references:
        return _cloudflare_ref_image(prompt, references)
    return _cloudflare_image(prompt)


# ---------------- Stok fotoğraf (Pixabay veya Pexels) ----------------

def stock_provider() -> str | None:
    if config.PIXABAY_API_KEY:
        return "pixabay"
    if config.PEXELS_API_KEY:
        return "pexels"
    return None


def stock_enabled() -> bool:
    return stock_provider() is not None


def _pixabay(params: dict) -> dict:
    try:
        r = requests.get(
            "https://pixabay.com/api/",
            params={"key": config.PIXABAY_API_KEY, "image_type": "photo", "safesearch": "true", **params},
            timeout=20,
        )
    except requests.RequestException as e:
        raise FreeServiceError(f"Pixabay'e ulaşılamadı: {e}") from e
    if r.status_code >= 400:
        raise FreeServiceError(f"Pixabay {r.status_code}: {r.text[:200]}")
    return r.json()


def _pixabay_photo(h: dict) -> dict:
    user = h.get("user") or ""
    return {
        "id": h["id"],
        "alt": h.get("tags") or "",
        "width": h.get("imageWidth"),
        "height": h.get("imageHeight"),
        "color": None,
        "photographer": user,
        "photographer_url": f"https://pixabay.com/users/{user}-{h.get('user_id')}/" if user else "https://pixabay.com",
        "page_url": h.get("pageURL") or "",
        "thumb": h.get("webformatURL") or h.get("previewURL"),
        "preview": h.get("largeImageURL") or h.get("webformatURL"),
        "download": h.get("largeImageURL") or h.get("webformatURL"),
    }


def _pexels(path: str, params: dict | None = None) -> dict:
    try:
        r = requests.get(
            f"https://api.pexels.com/v1/{path}",
            headers={"Authorization": config.PEXELS_API_KEY},
            params=params,
            timeout=20,
        )
    except requests.RequestException as e:
        raise FreeServiceError(f"Pexels'e ulaşılamadı: {e}") from e
    if r.status_code == 404:
        raise FreeServiceError("Fotoğraf bulunamadı.")
    if r.status_code >= 400:
        raise FreeServiceError(f"Pexels {r.status_code}: {r.text[:200]}")
    return r.json()


def _photo(p: dict) -> dict:
    src = p.get("src") or {}
    return {
        "id": p["id"],
        "alt": p.get("alt") or "",
        "width": p.get("width"),
        "height": p.get("height"),
        "color": p.get("avg_color"),
        "photographer": p.get("photographer") or "",
        "photographer_url": p.get("photographer_url") or "",
        "page_url": p.get("url") or "",
        "thumb": src.get("medium") or src.get("small"),
        "preview": src.get("large") or src.get("medium"),
        "download": src.get("large2x") or src.get("original"),
    }


def search_stock(subject: str, query: str, orientation: str | None, page: int) -> dict:
    provider = stock_provider()
    key = json.dumps([provider, query.strip().lower(), orientation or "", page])
    now = utcnow()
    with get_engine().connect() as conn:
        row = conn.execute(select(stock_cache).where(stock_cache.c.key == key)).first()
    if row and now - row.created_at < STOCK_CACHE_TTL:
        return json.loads(row.data)

    _reserve(subject, "stock", STOCK_PER_DAY, DAY, None, "Bugün çok fazla arama yaptın, yarın tekrar dene.")
    if provider == "pixabay":
        params = {"q": query.strip()[:100], "lang": "tr", "per_page": 24, "page": page}
        if orientation in PIXABAY_ORIENTATION:
            params["orientation"] = PIXABAY_ORIENTATION[orientation]
        data = _pixabay(params)
        hits = data.get("hits", [])
        if orientation == "square":  # Pixabay'de kare filtresi yok; oranı yakın olanları al
            hits = [h for h in hits if h.get("imageHeight") and 0.8 <= h["imageWidth"] / h["imageHeight"] <= 1.25] or hits
        result = {
            "photos": [_pixabay_photo(h) for h in hits],
            "page": page,
            "has_more": page * 24 < min(int(data.get("totalHits") or 0), 500),
            "source": "Pixabay",
        }
    else:
        params = {"query": query, "per_page": 24, "page": page, "locale": "tr-TR"}
        if orientation:
            params["orientation"] = orientation
        data = _pexels("search", params)
        result = {
            "photos": [_photo(p) for p in data.get("photos", [])],
            "page": page,
            "has_more": bool(data.get("next_page")),
            "source": "Pexels",
        }
    with get_engine().begin() as conn:
        conn.execute(delete(stock_cache).where(stock_cache.c.key == key))
        conn.execute(stock_cache.insert().values(key=key, data=json.dumps(result), created_at=now))
    return result


def stock_photo_bytes(photo_id: int) -> tuple[bytes, dict]:
    """Seçilen stok fotoğrafı indirir (yalnızca kütüphanenin kendi görsel sunucusundan)."""
    if stock_provider() == "pixabay":
        hits = _pixabay({"id": int(photo_id)}).get("hits") or []
        if not hits:
            raise FreeServiceError("Fotoğraf bulunamadı.")
        photo, hosts = _pixabay_photo(hits[0]), PIXABAY_HOSTS
    else:
        photo, hosts = _photo(_pexels(f"photos/{int(photo_id)}")), PEXELS_HOSTS
    url = photo["download"] or ""
    if urlparse(url).hostname not in hosts:
        raise FreeServiceError("Beklenmeyen fotoğraf adresi.")
    try:
        r = requests.get(url, timeout=60)
    except requests.RequestException as e:
        raise FreeServiceError(f"Fotoğraf indirilemedi: {e}") from e
    if r.status_code != 200 or len(r.content) > 20 * 1024 * 1024:
        raise FreeServiceError("Fotoğraf indirilemedi.")
    return r.content, photo
