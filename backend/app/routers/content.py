import base64
import json
import logging
import uuid
from typing import Literal

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, select, update

from app import config
from app.db import get_engine, utcnow, video_tasks
from app.security import get_current_user
from app.services import assistant, chat_files, free_tier, gateway_media, library, media_planner, storage
from app.services.claude_service import generate_content_ideas
from app.services.llm_service import LLMError
from app.services.plans import CREDIT_COSTS, chat_cost, idea_cost, video_cost
from app.services.usage_service import QuotaExceededError, consume, get_usage, refund

router = APIRouter()
logger = logging.getLogger("ajansai.content")


def _charge(user_id: str, action: str, credits: int, detail: str) -> str:
    try:
        return consume(user_id, action, credits, detail)
    except QuotaExceededError as e:
        raise HTTPException(status_code=402, detail=str(e))


class ContentIdeaRequest(BaseModel):
    business_name: str = Field(..., max_length=200, examples=["Cafe Lorem"])
    sector: str = Field(..., max_length=200, examples=["Kafe / Restoran"])
    target_audience: str = Field(..., max_length=500, examples=["25-40 yaş, şehirde yaşayan genç profesyoneller"])
    tone: str = Field(..., max_length=200, examples=["Samimi ve eğlenceli"])
    topic: str = Field(..., max_length=1000, examples=["Yeni sezon soğuk kahve menüsü"])
    idea_count: int = Field(4, ge=1, le=8)


@router.post("/ideas")
def create_content_ideas(payload: ContentIdeaRequest, user: dict = Depends(get_current_user)):
    credits = idea_cost(payload.idea_count)
    event_id = _charge(user["id"], "idea", credits, f"{payload.idea_count} fikir: {payload.topic}")

    try:
        result = generate_content_ideas(
            business_name=payload.business_name,
            sector=payload.sector,
            target_audience=payload.target_audience,
            tone=payload.tone,
            topic=payload.topic,
            idea_count=payload.idea_count,
        )
    except LLMError:
        refund(event_id)
        raise HTTPException(status_code=503, detail="Yapay zeka servisine şu an ulaşılamıyor, birazdan tekrar dene.")

    if result.get("error"):
        refund(event_id)
        return result
    return {**result, "credits_spent": credits}


ASPECTS = {"ASPECT_1_1": "1:1", "ASPECT_9_16": "9:16", "ASPECT_3_4": "3:4", "ASPECT_4_5": "4:5", "ASPECT_16_9": "16:9", "ASPECT_4_3": "4:3"}


class ImageRequest(BaseModel):
    concept: str = Field(..., max_length=2000, examples=["Masada buğulanan bir buzlu kahve, sıcak yaz ışığı"])
    aspect_ratio: str = Field("ASPECT_1_1", pattern=r"^ASPECT_(1_1|9_16|3_4|4_5|16_9|4_3)$")
    reference_urls: list[str] = Field(default_factory=list, max_length=4, description="Örnek alınacak yüklenmiş görseller")
    # Revizyon: düzenlenecek önceki görsel ve onu üreten istem (yeniden sıfırdan üretmek yerine düzenlenir)
    base_url: str | None = Field(None, max_length=2000)
    previous_prompt: str | None = Field(None, max_length=4000)


def _own_urls(urls: list[str]) -> list[str]:
    bad = [u for u in urls if not storage.is_own_blob_url(u)]
    if bad:
        raise HTTPException(status_code=400, detail="Örnek dosyalar ajansAI'a yüklenmiş olmalı.")
    return urls


def _save_image(data: bytes, mime: str, user_id: str) -> str:
    if storage.is_enabled():
        try:
            return storage.save(data, mime, f"gorsel/{user_id}")
        except storage.StorageError as e:
            logger.error("Görsel saklanamadı: %s", e)
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


@router.post("/image")
def create_image(payload: ImageRequest, user: dict = Depends(get_current_user)):
    """Görsel üretir ya da (base_url verilirse) önceki görseli istenen yönde düzenler."""
    if not gateway_media.is_enabled():
        raise HTTPException(status_code=503, detail="Görsel üretimi henüz yapılandırılmadı.")
    refs = _own_urls(payload.reference_urls)
    base = _own_urls([payload.base_url])[0] if payload.base_url else None
    aspect = ASPECTS[payload.aspect_ratio]
    credits = CREDIT_COSTS["image"]
    event_id = _charge(user["id"], "image", credits, ("Revize: " if base else "") + payload.concept)

    if config.IMAGE_DIRECT:  # ChatGPT gibi: istek aynen modele gider
        plan = {"prompt": payload.concept, "note": None}
    else:
        plan = media_planner.plan_image(payload.concept, aspect, edit=bool(base), ref_count=len(refs),
                                        previous_prompt=payload.previous_prompt)
    try:
        data, mime = gateway_media.generate_image(plan["prompt"], aspect, ([base] if base else []) + refs or None)
    except gateway_media.MediaError as e:
        logger.error("Görsel üretilemedi: %s", e)
        refund(event_id)
        return {"image_url": None, "error": "Görsel üretilemedi, kredin iade edildi. Tekrar dene."}

    url = _save_image(data, mime, user["id"])
    library.add(user["id"], "image", url, payload.concept, "gorsel")
    return {"image_url": url, "error": None, "credits_spent": credits, "prompt": plan["prompt"], "note": plan["note"]}


class VideoRequest(BaseModel):
    concept: str = Field(..., max_length=2000, examples=["Buzlu kahvenin bardağa dökülüşü, ağır çekim"])
    image_url: str | None = Field(None, max_length=2000, description="Başlangıç karesi (görselden video)")
    end_image_url: str | None = Field(None, max_length=2000, description="Bitiş karesi (isteğe bağlı)")
    # Yüklenen görseller: 1 görsel → video ondan başlar; 2-4 görsel → görseller tek sahnede
    # birleştirilip (görsel kredisi) açılış karesi yapılır. Görsel yoksa açılış karesi üretilir.
    reference_urls: list[str] = Field(default_factory=list, max_length=4)
    duration: Literal[4, 6, 8] = 6
    resolution: Literal["720p", "1080p", "4k"] = "720p"
    aspect_ratio: Literal["9:16", "16:9"] = "9:16"
    audio: bool = False
    # Revizyon: önceki videonun iş kimliği; aynı açılış karesi ve istem korunup yalnızca istenen değişir
    revise_of: str | None = Field(None, max_length=36)


def _video_plan(user_id: str, job_id: str) -> dict:
    with get_engine().connect() as conn:
        row = conn.execute(
            select(video_tasks.c.plan).where(and_(video_tasks.c.id == job_id, video_tasks.c.user_id == user_id))
        ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Revize edilecek video bulunamadı.")
    try:
        return json.loads(row.plan or "{}")
    except ValueError:
        return {}


def _image_aspect_of(url: str) -> float | None:
    try:
        from io import BytesIO

        from PIL import Image

        w, h = Image.open(BytesIO(storage.fetch(url))).size
        return w / h if h else None
    except Exception:  # noqa: BLE001
        return None


def _fit_frame(user: dict, url: str, aspect: str) -> str:
    """Açılış karesi videonun oranında değilse (siyah bant olmasın diye) sahne o orana genişletilir."""
    target = {"9:16": 9 / 16, "16:9": 16 / 9}.get(aspect, 9 / 16)
    ratio = _image_aspect_of(url)
    if not ratio or abs(ratio - target) / target < 0.06:
        return url
    prompt = (f"Extend this exact photo to a {aspect} frame by naturally continuing the background and surface "
              "around it. Keep every product, food, person and object exactly as it is (same shape, colors, "
              "position relative to each other). No text, no borders, no new objects.")
    try:
        data, mime = gateway_media.generate_image(prompt, aspect, [url])
        return storage.save(data, mime, f"gorsel/{user['id']}")
    except (gateway_media.MediaError, storage.StorageError) as e:
        logger.warning("Açılış karesi orana uyarlanamadı: %s", e)
        return url


@router.post("/video")
def create_video(payload: VideoRequest, user: dict = Depends(get_current_user)):
    """Video üretimini başlatır. Yanıttaki job_id ile /video/{job_id} sorgulanmalı.

    Akış: istem yönetmen modeliyle netleştirilir → açılış karesi hazırlanır (yüklenen görsel,
    birleştirilmiş görseller veya üretilen kare; video oranına uyarlanır) → Veo ile görselden video.
    Revizyonda önceki açılış karesi ve istem korunur. Kredi iş başlamadan önce düşülür.
    """
    if not gateway_media.is_enabled():
        raise HTTPException(status_code=503, detail="Video üretimi henüz yapılandırılmadı.")
    need = video_cost(payload.duration, payload.resolution, payload.audio)
    previous = _video_plan(user["id"], payload.revise_of) if payload.revise_of else {}
    refs = _own_urls([u for u in payload.reference_urls if u])
    image_url = payload.image_url or (refs[0] if len(refs) == 1 else None) or previous.get("frame")
    end_image_url = payload.end_image_url if payload.image_url else None
    _own_urls([u for u in (image_url, end_image_url) if u])
    extra, extra_event = 0, None
    if len(refs) > 1:
        if get_usage(user["id"])["credits"]["remaining"] < need + CREDIT_COSTS["image"]:
            raise HTTPException(status_code=402, detail=f"Bu video için {need + CREDIT_COSTS['image']} kredi gerekiyor (görselleri birleştirme dahil).")
        image_url, extra, extra_event = _compose_frame(user, payload.concept, payload.aspect_ratio, refs)
        if not image_url:
            return {"job_id": None, "error": "Görseller birleştirilemedi, kredin iade edildi. Tekrar dene.", "credits_spent": 0}

    # Kredi baştan düşülür (açılış karesi ve planlama da bu işe dahil); başlatılamazsa iade edilir.
    label = ("4K" if payload.resolution == "4k" else payload.resolution) + (", sesli" if payload.audio else "")
    try:
        event_id = consume(user["id"], "video", need, f"{label}, {payload.duration} sn: {payload.concept[:300]}")
    except QuotaExceededError as e:
        if extra_event:
            refund(extra_event)
        raise HTTPException(status_code=402, detail=str(e))

    plan = media_planner.plan_video(payload.concept, payload.aspect_ratio, payload.duration,
                                    has_start_frame=bool(image_url), audio=payload.audio,
                                    previous_prompt=previous.get("prompt"))
    if not image_url or (payload.revise_of and plan.get("frame_prompt")):
        # Açılış karesi üretilir (revizyonda sahne değişikliği istendiyse önceki kareden düzenlenir)
        try:
            refs_for_frame = [previous["frame"]] if payload.revise_of and previous.get("frame") else None
            data, mime = gateway_media.generate_image(plan["frame_prompt"] or payload.concept, payload.aspect_ratio, refs_for_frame)
            image_url = storage.save(data, mime, f"gorsel/{user['id']}")
        except (gateway_media.MediaError, storage.StorageError) as e:
            logger.warning("Açılış karesi üretilemedi, metinden video: %s", e)
            image_url = None
    elif image_url and not end_image_url:
        image_url = _fit_frame(user, image_url, payload.aspect_ratio)

    plan_record = {"prompt": plan["prompt"], "frame": image_url, "request": payload.concept,
                   "aspect": payload.aspect_ratio, "duration": payload.duration,
                   "resolution": payload.resolution, "audio": payload.audio}
    job_id, error, credits = _start_video_job(
        user, payload.concept, payload.duration, payload.resolution, image_url, end_image_url, payload.audio,
        payload.aspect_ratio, model_prompt=plan["prompt"], plan=plan_record, event_id=event_id,
    )
    if not job_id and extra_event:
        refund(extra_event)  # video başlamadıysa açılış karesinin kredisi de iade edilir
        extra = 0
    return {"job_id": job_id, "error": error, "credits_spent": credits + extra, "start_frame": image_url,
            "note": plan.get("note") or ""}


def _compose_frame(user: dict, concept: str, aspect: str, refs: list[str]) -> tuple[str | None, int, str | None]:
    """Birden çok görseli tek açılış karesinde birleştirir. (adres, kredi, kredi kaydı)."""
    cost = CREDIT_COSTS["image"]
    event_id = _charge(user["id"], "image", cost, f"Video açılış karesi: {concept[:200]}")
    prompt = (
        f"Opening frame of a short social media video: {concept}. Combine the products, people and places "
        "from the reference images naturally into one coherent, photorealistic scene; keep the products exactly as "
        "they look. Cinematic lighting, no text or logos added."
    )
    try:
        data, mime = gateway_media.generate_image(prompt, aspect, refs)
        url = storage.save(data, mime, f"gorsel/{user['id']}")
        library.add(user["id"], "image", url, concept, "video")
    except (gateway_media.MediaError, storage.StorageError) as e:
        logger.error("Açılış karesi üretilemedi: %s", e)
        refund(event_id)
        return None, 0, None
    return url, cost, event_id


def _start_video_job(user: dict, concept: str, duration: int, resolution: str, image_url: str | None,
                     end_image_url: str | None, audio: bool, aspect_ratio: str, model_prompt: str | None = None,
                     plan: dict | None = None, event_id: str | None = None) -> tuple[str | None, str | None, int]:
    """Video işini başlatır (kredi düşülmediyse düşer). (iş kimliği, hata, harcanan kredi) döndürür."""
    credits = video_cost(duration, resolution, audio)
    if event_id is None:
        label = ("4K" if resolution == "4k" else resolution) + (", sesli" if audio else "")
        event_id = _charge(user["id"], "video", credits, f"{label}, {duration} sn: {concept[:300]}")

    try:
        operation = gateway_media.start_video(model_prompt or concept, duration, resolution, image_url, end_image_url,
                                              audio, aspect_ratio)
    except gateway_media.MediaError as e:
        logger.error("Video başlatılamadı: %s", e)
        refund(event_id)
        return None, "Video üretimi başlatılamadı, kredin iade edildi. Tekrar dene.", 0

    job_id = str(uuid.uuid4())
    with get_engine().begin() as conn:
        conn.execute(
            video_tasks.insert().values(
                id=job_id,
                user_id=user["id"],
                credit_event_id=event_id,
                operation=json.dumps(operation),
                status="pending",
                prompt=concept[:500],
                plan=json.dumps(plan or {"prompt": model_prompt or concept, "frame": image_url}),
                created_at=utcnow(),
            )
        )
    return job_id, None, credits


def _store_video(video: dict, user_id: str) -> str:
    """Bitmiş videoyu kalıcı depoya taşır; depo yoksa sağlayıcının süreli adresini döndürür."""
    if video.get("type") == "url":
        if not storage.is_enabled():
            return video["url"]
        data = requests.get(video["url"], timeout=120).content
    else:
        data = base64.b64decode(video.get("data", ""))
        if not storage.is_enabled():
            raise storage.StorageError("Blob deposu yok; video baytları saklanamıyor.")
    return storage.save(data, "video/mp4", f"video/{user_id}")


@router.get("/video/{job_id}")
def check_video(job_id: str, user: dict = Depends(get_current_user)):
    """Durum: PENDING, SUCCEEDED, FAILED. SUCCEEDED olunca video_url dolu gelir."""
    with get_engine().connect() as conn:
        task = conn.execute(
            select(video_tasks).where(and_(video_tasks.c.id == job_id, video_tasks.c.user_id == user["id"]))
        ).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Video bulunamadı.")

    if task.status == "completed":
        return {"status": "SUCCEEDED", "video_url": task.video_url, "error": None}
    if task.status == "failed":
        return {"status": "FAILED", "video_url": None, "error": task.error}

    try:
        result = gateway_media.video_status(json.loads(task.operation))
    except gateway_media.MediaError as e:
        # Geçici hata olabilir: işi başarısız saymıyoruz, istemci tekrar sorar.
        logger.warning("Video durumu alınamadı: %s", e)
        return {"status": "PENDING", "video_url": None, "error": None}

    if result["status"] == "pending":
        return {"status": "PENDING", "video_url": None, "error": None}

    if result["status"] == "completed":
        try:
            url = _store_video(result["video"], user["id"])
        except (requests.RequestException, storage.StorageError) as e:
            logger.error("Video saklanamadı: %s", e)
            return {"status": "PENDING", "video_url": None, "error": None}
        with get_engine().begin() as conn:
            conn.execute(
                update(video_tasks)
                .where(and_(video_tasks.c.id == job_id, video_tasks.c.status == "pending"))
                .values(status="completed", video_url=url)
            )
        library.add(user["id"], "video", url, task.prompt or "", "video")
        return {"status": "SUCCEEDED", "video_url": url, "error": None}

    error = str(result.get("error") or "Video üretilemedi.")[:500]
    with get_engine().begin() as conn:
        changed = conn.execute(
            update(video_tasks)
            .where(and_(video_tasks.c.id == job_id, video_tasks.c.status == "pending"))
            .values(status="failed", error=error)
        ).rowcount
    if changed:
        refund(task.credit_event_id)
    logger.error("Video başarısız (%s): %s", job_id, error)
    return {"status": "FAILED", "video_url": None, "error": "Video üretilemedi, kredin iade edildi."}


# ---------------- Fikir sohbeti ----------------

class Attachment(BaseModel):
    url: str = Field(..., max_length=2000)
    content_type: str = Field(..., max_length=120)
    name: str = Field("dosya", max_length=200)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field("", max_length=20000)
    attachments: list[Attachment] = Field(default_factory=list, max_length=5)
    # Asistan mesajında üretilmiş görsellerin adresleri (sohbet hafızası için)
    media: list[str] = Field(default_factory=list, max_length=4)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=40)
    mode: Literal["chat", "image", "search", "file"] = "chat"


@router.post("/chat")
def chat(payload: ChatRequest, user: dict = Depends(get_current_user)):
    """ChatGPT benzeri tek metin kutusu: son kullanıcı mesajı + ekleri yanıtlanır."""
    last = payload.messages[-1]
    if last.role != "user" or not (last.content.strip() or last.attachments):
        raise HTTPException(status_code=400, detail="Bir mesaj yaz veya dosya ekle.")
    for att in last.attachments:
        if storage.kind_of(att.content_type) is None:
            raise HTTPException(status_code=400, detail=f"{att.name}: bu dosya türü desteklenmiyor.")
    _own_urls([a.url for a in last.attachments])

    pages = []
    for att in last.attachments:
        if att.content_type == "application/pdf":
            try:
                n = assistant.pdf_pages(storage.fetch(att.url))
            except storage.StorageError as e:
                raise HTTPException(status_code=400, detail=f"{att.name}: {e}")
            if n > assistant.MAX_PDF_PAGES:
                raise HTTPException(
                    status_code=400,
                    detail=f"{att.name} {n} sayfa; en fazla {assistant.MAX_PDF_PAGES} sayfalık PDF ekleyebilirsin.",
                )
            pages.append(n)
    credits = chat_cost(len(last.attachments), pages)
    video_enabled = bool(get_usage(user["id"]).get("video_enabled"))
    event_id = _charge(user["id"], "chat", credits, last.content.strip()[:200] or "Dosya incelemesi")
    try:
        history = [m.model_dump() for m in payload.messages[-20:]]
        labels = free_tier.label_media(history, storage.is_own_blob_url)
        text, model, image_prompt, sources, file_request, model_messages, video_request = assistant.reply(
            history,
            force_image=payload.mode == "image",
            force_search=payload.mode == "search",
            force_file=payload.mode == "file",
            video_enabled=video_enabled,
        )
    except (LLMError, storage.StorageError) as e:
        logger.error("Sohbet yanıtı alınamadı: %s", e)
        refund(event_id)
        raise HTTPException(status_code=503, detail="Yapay zeka şu an yanıt veremedi, kredin iade edildi. Birazdan tekrar dene.")

    images, image_error = [], None
    if image_prompt:
        ref_url, image_prompt = free_tier.extract_ref(image_prompt, labels)
        refs = [a.url for a in last.attachments if storage.kind_of(a.content_type) == "image"][:4]
        if ref_url:
            refs = [ref_url] + refs[:3]
        image_prompt = free_tier.direct_image_prompt(image_prompt, last.content, editing=bool(ref_url))
        url, image_error, image_credits = _chat_image(user, image_prompt, refs)
        if url:
            images.append(url)
            if image_credits:  # ücretsiz FLUX yedeği kendi kaydını yapar
                library.add(user["id"], "image", url, last.content.strip() or image_prompt, "sohbet")
        credits += image_credits
    out_files, file_error = [], None
    if file_request:
        cost = CREDIT_COSTS["file"]
        try:
            file_event = consume(user["id"], "file", cost, f"Dosya: {file_request['brief'][:200]}")
        except QuotaExceededError as e:
            file_event, file_error = None, str(e)
        if file_event:
            conversation = model_messages + [{"role": "assistant", "content": text}]
            made, file_error = chat_files.make(file_request, conversation, f"dosya/{user['id']}", paid=True)
            if made:
                out_files.append(made)
                credits += cost
            else:
                refund(file_event)
    # Video sohbette üretilmez: Video sayfasını hazır dolduracak öneri döndürülür.
    video = None
    if video_request:
        start = next((a.url for a in last.attachments if storage.kind_of(a.content_type) == "image"), None)
        if video_request.get("ref") and labels.get(video_request["ref"]):
            start = labels[video_request["ref"]]
        if images and storage.is_own_blob_url(images[0]):
            start = images[0]
        video = {"concept": video_request["prompt"], "aspect": video_request["aspect"],
                 "duration": video_request["duration"], "image_url": start, "enabled": video_enabled}
    return {
        "reply": text or ("İşte görselin." if images else "Dosyan hazır." if out_files else ""),
        "model": model,
        "images": images,
        "image_error": image_error or file_error,
        "sources": sources,
        "files": out_files,
        "video": video,
        "credits_spent": credits,
    }


def _chat_image(user: dict, prompt: str, refs: list[str]) -> tuple[str | None, str | None, int]:
    """Sohbette istenen görsel: önce Seedream (4 kredi); olmazsa ücretsiz görsel hakkıyla FLUX.

    (adres, hata, harcanan kredi) döndürür.
    """
    if gateway_media.is_enabled():
        cost = CREDIT_COSTS["image"]
        try:
            event_id = consume(user["id"], "image", cost, f"Sohbetten görsel: {prompt}")
        except QuotaExceededError:
            event_id = None
        if event_id:
            try:
                aspect, clean = free_tier.image_aspect(prompt)
                data, mime = gateway_media.generate_image(clean, aspect, refs or None)
                if storage.is_enabled():
                    return storage.save(data, mime, f"gorsel/{user['id']}"), None, cost
                return f"data:{mime};base64,{base64.b64encode(data).decode()}", None, cost
            except (gateway_media.MediaError, storage.StorageError) as e:
                logger.warning("Seedream olmadı, ücretsiz görsele geçiliyor: %s", e)
                refund(event_id)
    from app.routers.free import make_free_image

    url, error, _ = make_free_image(f"u:{user['id']}", user, prompt, refs, translate=False)
    return url, error, 0


class DescribeRequest(BaseModel):
    attachment: Attachment
    target: Literal["image", "video"]
    note: str = Field("", max_length=500)


@router.post("/describe")
def describe(payload: DescribeRequest, user: dict = Depends(get_current_user)):
    """Yüklenen örnek görsel/videodan, aynı tarzda yeni üretim için konsept metni çıkarır."""
    if storage.kind_of(payload.attachment.content_type) not in ("image", "video"):
        raise HTTPException(status_code=400, detail="Örnek olarak görsel veya video yükleyebilirsin.")
    _own_urls([payload.attachment.url])
    credits = CREDIT_COSTS["describe"]
    event_id = _charge(user["id"], "describe", credits, f"Örnekten konsept: {payload.attachment.name}")
    try:
        concept = assistant.describe_for_generation(payload.attachment.model_dump(), payload.target, payload.note)
    except (LLMError, storage.StorageError) as e:
        logger.error("Örnek incelenemedi: %s", e)
        refund(event_id)
        raise HTTPException(status_code=503, detail="Örnek incelenemedi, kredin iade edildi. Tekrar dene.")
    return {"concept": concept, "credits_spent": credits}


# ---------------- Kütüphane ----------------

@router.get("/library")
def get_library(kind: Literal["image", "video"] | None = None, limit: int = 60, user: dict = Depends(get_current_user)):
    """Üretilen görsel ve videolar (en yeni önce)."""
    return {"items": library.items(user["id"], kind, limit)}


@router.delete("/library/{item_id}", status_code=204)
def delete_library_item(item_id: str, user: dict = Depends(get_current_user)):
    library.remove(user["id"], item_id)
    from fastapi import Response

    return Response(status_code=204)
