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
from app.services import assistant, documents, web_search
from app.services.llm_service import LLMError, free_chat_completion

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


def reserve_upload(subject: str, per_day: int) -> str:
    return _reserve(subject, "upload", per_day, DAY, None, "Bugün çok fazla dosya yükledin, yarın tekrar dene.")


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

FREE_NOTE = (
    "\n- Yanıtları derli toplu tut.\n- Video üretimi yalnızca ücretli paketlerde var; kullanıcı video isterse bunu kısaca "
    "söyle ve paket seçebileceğini belirt."
)

# Sohbetten görsel üretimi (ChatGPT gibi): model görsel istendiğini bu satırla bildirir.
IMAGE_TOOL_NOTE = (
    "\n- Görsel üretebilirsin. Kullanıcı açıkça bir görsel, fotoğraf, afiş veya gönderi görseli üretmeni/çizmeni "
    "isterse (ör. 'bunun görselini üret', 'bir post görseli yap'), yanıtını kısa tut (1-2 cümle, gerekirse caption) ve "
    "en sona tek satır olarak şunu ekle: [[GORSEL: <oran> | <İngilizce, 40-90 kelimelik ayrıntılı görüntü istemi: konu, "
    "kompozisyon ve kamera açısı, ortam, ışık, renk paleti, atmosfer, stil (ör. photorealistic product photography, "
    "35mm, soft natural light)>]]. <oran> şunlardan biri: 1:1 (varsayılan, gönderi), 4:5, 9:16 (story/reels), 16:9 "
    "(yatay/kapak). Kullanıcı görsel eklediyse ve onu kullanmak/değiştirmek istiyorsa istemde 'the product in image 0' gibi "
    "ona atıf yap. Görsel istenmedikçe bu satırı ekleme. Görsel üretemeyeceğini asla söyleme; satırı eklemen yeterli, "
    "görseli sistem üretip mesajının altında gösterir. Satırda yazı/logo isteme; görselde metin olmasın."
)
IMAGE_TAG = re.compile(r"\[\[\s*G[ÖO]RSEL\s*:\s*(.+?)\]\]", re.IGNORECASE | re.DOTALL)
HISTORY_MESSAGES = 8
FREE_FILES_PER_DAY = 3
MESSAGE_CHARS = 3000


def split_image_request(text: str) -> tuple[str, str | None]:
    """Yanıttaki [[GORSEL: ...]] satırını ayırır: (görünen metin, görsel istemi)."""
    m = IMAGE_TAG.search(text)
    if not m:
        return text, None
    return IMAGE_TAG.sub("", text).strip(), m.group(1).strip()[:1500]


IMAGE_ASPECTS = {"1:1": (1024, 1024), "4:5": (896, 1120), "9:16": (768, 1360), "16:9": (1360, 768)}
ASPECT_PREFIX = re.compile(r"^\s*\(?\s*(1:1|4:5|9:16|16:9)\s*\)?\s*[|,;:-]?\s*")


def image_aspect(prompt: str) -> tuple[str, str]:
    """İstemin başındaki oranı ayırır: ("9:16", "a cup of coffee ...")."""
    m = ASPECT_PREFIX.match(prompt or "")
    if not m:
        return "1:1", (prompt or "").strip()
    return m.group(1), prompt[m.end():].strip()


# ---- Sohbette üretilen görsellerin hafızası ----
# Arayüz, önceki asistan mesajlarında üretilen görsellerin adreslerini "media" alanında gönderir.
# Her birine "görsel-N" etiketi verilir; model önceki bir görseli düzenlemek ya da videoya
# çevirmek isterse etiketin istemine ref=görsel-N yazar.
REF_TOKEN = re.compile(r"(?:^|[|,;\s])ref\s*=\s*(g[öo]rsel-\d+)\s*[|,;]?", re.IGNORECASE)
MEDIA_NOTE = (
    "\n- Bu sohbette daha önce ürettiğin görseller, ilgili yanıtının sonunda 'görsel-N' etiketiyle belirtilir. "
    "Kullanıcı önceki bir görseli düzenlemek, düzeltmek, benzerini yapmak veya videoya çevirmek isterse etiket satırına "
    "ref=görsel-N ekle; örn. [[GORSEL: 9:16 | ref=görsel-1 | the same iced latte, ...]] ya da "
    "[[VIDEO: 9:16 | 5 | ref=görsel-1 | milk slowly pours into the iced latte ...]]. Sistem o görseli kaynak olarak kullanır."
)


def label_media(history: list[dict], own_url) -> dict[str, str]:
    """Asistan mesajlarındaki üretilmiş görsellere etiket notu ekler; {etiket: adres} döndürür."""
    labels: dict[str, str] = {}
    for m in history:
        media = [u for u in (m.get("media") or []) if isinstance(u, str) and own_url(u)]
        if m.get("role") != "assistant" or not media:
            continue
        names = []
        for url in media[:4]:
            label = f"görsel-{len(labels) + 1}"
            labels[label] = url
            names.append(label)
        m["_note"] = f"\n[Sistem notu: bu yanıtta üretilen görsel: {', '.join(names)}]"
    return labels


def extract_ref(prompt: str, labels: dict[str, str]) -> tuple[str | None, str]:
    """İstemdeki ref=görsel-N'i ayırır: (adres veya None, temiz istem)."""
    m = REF_TOKEN.search(prompt or "")
    if not m:
        return None, prompt
    key = m.group(1).lower().replace("gorsel", "görsel")
    clean = (prompt[: m.start()] + " " + prompt[m.end():]).strip(" |,;")
    return labels.get(key), re.sub(r"\s{2,}", " ", clean)


# Sohbetten video üretimi (yalnızca ücretli paketler)
VIDEO_TOOL_NOTE = (
    "\n- Video da üretebilirsin. Kullanıcı açıkça bir video, reels veya animasyon üretmeni isterse yanıtını kısa tut "
    "(1-2 cümle) ve en sona tek satır ekle: [[VIDEO: <oran> | <süre> | <İngilizce, 40-80 kelimelik video istemi: sahne, "
    "özne ve hareketi, kamera hareketi, ışık, atmosfer, stil>]]. <oran>: 9:16 (varsayılan, reels/story), 1:1 veya 16:9. "
    "<süre>: 5 veya 10 (saniye, varsayılan 5). Kullanıcı görsel eklediyse video o görselden başlar. Video istenmedikçe "
    "bu satırı ekleme; video üretemeyeceğini söyleme, satırı eklemen yeterli."
)
FORCE_VIDEO_NOTE = "\n- Kullanıcı bu mesajda 'Video oluştur' seçeneğini kullandı: mutlaka en sona [[VIDEO: ...]] satırını ekle."
SYSTEM_NOTE = re.compile(r"\[Sistem notu:[^\]]*\]", re.IGNORECASE)
VIDEO_TAG = re.compile(r"\[\[\s*V[İI]DEO\s*:\s*(.+?)\]\]", re.IGNORECASE | re.DOTALL)


def split_video_request(text: str) -> tuple[str, dict | None]:
    """[[VIDEO: oran | süre | istem]] satırını ayırır."""
    m = VIDEO_TAG.search(text or "")
    if not m:
        return text, None
    parts = [p.strip() for p in m.group(1).split("|")]
    ref = next((p for p in parts if p.lower().startswith("ref=")), None)
    parts = [p for p in parts if p is not ref]
    aspect, duration = "9:16", 5
    while len(parts) > 1 and parts[0] in ("9:16", "1:1", "16:9", "5", "10", "7"):
        head = parts.pop(0)
        if ":" in head:
            aspect = head
        else:
            duration = int(head)
    if duration not in (5, 7, 10):
        duration = 5
    prompt = " ".join(parts).strip()[:1500]
    req = {"aspect": aspect, "duration": duration, "prompt": prompt, "ref": ref.split("=", 1)[1].strip().lower().replace("gorsel", "görsel") if ref else None}
    return VIDEO_TAG.sub("", text).strip(), (req if prompt else None)


FORCE_IMAGE_NOTE = (
    "\n- Kullanıcı bu mesajda 'Görsel oluştur' seçeneğini kullandı: mutlaka en sona [[GORSEL: ...]] satırını ekle."
)
MAX_VISION_IMAGES = 3


def _vision_part(data: bytes) -> dict:
    """Görseli küçültüp (en uzun kenar 1024) data URL olarak modele gönderir."""
    from PIL import Image, ImageOps

    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    img.thumbnail((1024, 1024))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85)
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()}}


def chat(
    subject: str,
    signed_in: bool,
    history: list[dict],
    attachments: list[dict] | None = None,
    force_image: bool = False,
    force_search: bool = False,
    force_file: bool = False,
) -> tuple[str, str | None, list[dict], dict | None, list[dict]]:
    """(yanıt metni, görsel istemi, web kaynakları, dosya isteği, model mesajları) döndürür.

    attachments: son mesajın ekleri; her biri {"kind", "name", "data"(bayt)}.
    Belgeler metne çevrilip mesaja eklenir; görseller görebilen ücretsiz modele (Qwen) gider.
    """
    lim = limits(signed_in)["chat_per_day"]
    msg = (
        f"Ücretsiz pakette günde {lim} mesaj hakkın var ve bugünkü hakkın doldu. "
        + ("Yarın devam edebilir ya da bir paket seçebilirsin." if signed_in else "Üye olursan günde daha fazla mesaj yazabilirsin.")
    )
    event_id = _reserve(subject, "chat", lim, DAY, config.FREE_CHAT_PER_DAY_TOTAL, msg)
    system = assistant.SYSTEM_PROMPT + web_search.today_line() + FREE_NOTE + (IMAGE_TOOL_NOTE + MEDIA_NOTE if image_enabled() else "")
    if web_search.enabled():
        system += web_search.SEARCH_NOTE
    if force_image and image_enabled():
        system += FORCE_IMAGE_NOTE
    system += documents.FILE_NOTE + (documents.FORCE_FILE_NOTE if force_file else "")
    messages = [{"role": "system", "content": system}]
    recent = history[-HISTORY_MESSAGES:]
    attachments = attachments or []
    images = [a for a in attachments if a["kind"] == "image"][:MAX_VISION_IMAGES]
    docs = [a for a in attachments if a["kind"] == "document"]
    for i, m in enumerate(recent):
        content = (m.get("content") or "")[:MESSAGE_CHARS] + (m.get("_note") or "")
        if i < len(recent) - 1 or m["role"] != "user":
            messages.append({"role": m["role"], "content": content or "(dosya)"})
            continue
        for d in docs:
            text = assistant.document_text(d["data"], d["content_type"])[: assistant.MAX_TEXT_CHARS // 2]
            content += f"\n\n--- Ek belge: {d['name']} ---\n{text}\n--- Belge sonu ---"
        if images:
            note = f"[Kullanıcı {len(images)} görsel ekledi: " + ", ".join(f"image {k}" for k in range(len(images))) + "]"
            parts = [{"type": "text", "text": f"{content}\n{note}".strip()}]
            try:
                parts += [_vision_part(a["data"]) for a in images]
            except Exception as e:
                release(event_id)
                raise FreeServiceError("Görsel okunamadı.") from e
            messages.append({"role": "user", "content": parts})
        else:
            messages.append({"role": "user", "content": content or "(dosya)"})
    try:
        if force_search and web_search.enabled():
            text = f"[[ARA: {(history[-1].get('content') or '')[:300]}]]"
        else:
            text, _ = free_chat_completion(messages, max_tokens=1500, vision=bool(images))
    except Exception:
        release(event_id)
        raise
    return (*finish_reply(text, messages), messages)


def finish_reply(text: str, messages: list[dict], paid: bool = False) -> tuple[str, str | None, list[dict], dict | None]:
    """Yanıttaki arama, görsel ve dosya isteklerini ayırır: (metin, görsel istemi, kaynaklar, dosya isteği)."""
    sources: list[dict] = []
    query = web_search.split_search_request(text)
    if query:
        try:
            text, sources = web_search.answer(messages, query, paid)
        except LLMError as e:
            logger.error("Web araması yapılamadı: %s", e)
            rest = web_search.SEARCH_TAG.sub("", text).strip()
            text = rest or "Şu an internette arama yapamadım. Biraz sonra tekrar dener misin?"
    text = SYSTEM_NOTE.sub("", VIDEO_TAG.sub("", text)).strip()
    text, file_request = documents.split_file_request(text)
    text, image_prompt = split_image_request(text)
    return text, image_prompt, sources, file_request


def reserve_file(subject: str) -> str:
    lim = FREE_FILES_PER_DAY
    return _reserve(subject, "file", lim, DAY, None, f"Ücretsiz pakette günde {lim} dosya oluşturabilirsin; bugünkü hakkın doldu.")


# ---------------- Ücretsiz AI görseli (Cloudflare Workers AI) ----------------

def image_enabled() -> bool:
    return bool(config.CLOUDFLARE_ACCOUNT_ID and config.CLOUDFLARE_AI_TOKEN)


ENHANCE_PROMPT = (
    "Rewrite this image idea as one vivid English image-generation prompt (40-80 words). Describe the subject, "
    "composition and camera angle, setting, lighting, colour palette, mood and style (e.g. photorealistic product "
    "photography, 35mm, soft natural light). Keep any reference to the uploaded/reference image or product (e.g. "
    "'the product from image 0'). No text, letters or logos in the image. Reply with the prompt only.\n\n"
)


def _english_prompt(concept: str) -> str:
    """FLUX İngilizce istemlerde daha iyi sonuç verir; ücretsiz zincirle kısa bir çeviri."""
    try:
        text, _ = free_chat_completion(
            [
                {
                    "role": "user",
                    "content": ENHANCE_PROMPT + concept,
                }
            ],
            max_tokens=300,
        )
        return text.strip() or concept
    except Exception as e:  # çeviri olmazsa özgün metinle devam
        logger.warning("İstem çevrilemedi: %s", e)
        return concept


def _cloudflare_image(prompt: str, model: str | None = None, size: tuple[int, int] = (1024, 1024)) -> bytes:
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{config.CLOUDFLARE_ACCOUNT_ID}"
        f"/ai/run/{model or config.FREE_IMAGE_MODEL}"
    )
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {config.CLOUDFLARE_AI_TOKEN}"},
            json={"prompt": prompt[:2048], "steps": 4, "width": size[0], "height": size[1]},
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


def _cloudflare_ref_image(prompt: str, references: list[bytes], model: str | None = None,
                          size: tuple[int, int] = (1024, 1024)) -> bytes:
    """FLUX.2 (çok parçalı istek). references boşsa metinden görsel üretir."""
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{config.CLOUDFLARE_ACCOUNT_ID}"
        f"/ai/run/{model or config.FREE_IMAGE_REF_MODEL}"
    )
    files = {f"input_image_{i}": (f"ref{i}.jpg", _small_reference(b), "image/jpeg") for i, b in enumerate(references[:4])}
    data = {"prompt": prompt[:2048], "width": str(size[0]), "height": str(size[1])}
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
    aspect, concept = image_aspect(concept)
    size = IMAGE_ASPECTS[aspect]
    prompt = _english_prompt(concept) if translate else concept
    if references:
        return _cloudflare_ref_image(prompt, references, size=size)
    if "flux-2" in (config.FREE_IMAGE_MODEL or ""):
        try:
            return _cloudflare_ref_image(prompt, [], config.FREE_IMAGE_MODEL, size)
        except FreeServiceError as e:
            logger.warning("FLUX.2 olmadı, FLUX.1 schnell deneniyor: %s", e)
            return _cloudflare_image(prompt, "@cf/black-forest-labs/flux-1-schnell", size)
    return _cloudflare_image(prompt, size=size)


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
