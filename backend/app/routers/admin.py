"""Yönetici uçları: görsel/video modellerini aynı istekle karşılaştırma (süre, çıktı)."""

import base64
import json
import time

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import config
from app.security import get_current_user
from app.services import gateway_media, storage
from app.services.llm_service import ai_gateway_token

router = APIRouter()


def _admin(user: dict = Depends(get_current_user)) -> dict:
    if (user.get("email") or "").lower() not in config.ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Yalnızca yönetici.")
    return user


class ImageBench(BaseModel):
    model: str
    prompt: str = Field(..., max_length=4000)
    aspect: str = "1:1"
    refs: list[str] = Field(default_factory=list, max_length=4)
    via: str = "image"  # image | chat (Gemini görsel modelleri)
    extra: dict = Field(default_factory=dict)


def _chat_image(model: str, prompt: str, refs: list[str], extra: dict | None = None) -> bytes:
    token = ai_gateway_token()
    content = [{"type": "text", "text": prompt}] + [{"type": "image_url", "image_url": {"url": u}} for u in refs]
    r = requests.post(
        f"{config.AI_GATEWAY_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "user", "content": content}], "modalities": ["text", "image"], **(extra or {})},
        timeout=280,
    )
    if r.status_code != 200:
        raise gateway_media.MediaError(f"{r.status_code}: {r.text[:400]}")
    msg = r.json()["choices"][0]["message"]
    for img in msg.get("images") or []:
        url = (img.get("image_url") or {}).get("url") or ""
        if url.startswith("data:"):
            return base64.b64decode(url.split(",", 1)[1])
    raise gateway_media.MediaError("görsel yok: " + json.dumps(msg)[:300])


@router.post("/bench/image")
def bench_image(p: ImageBench, user: dict = Depends(_admin)):
    t = time.time()
    try:
        if p.via == "chat":
            data = _chat_image(p.model, p.prompt, p.refs, p.extra)
            mime = gateway_media._sniff_mime(data)
        else:
            body = {"prompt": p.prompt, "n": 1, "aspectRatio": p.aspect, **p.extra}
            if p.refs:
                body["files"] = [{"type": "url", "url": u} for u in p.refs]
            out = gateway_media._post("/image-model", p.model, "image", body, timeout=280)
            raw = (out.get("images") or [""])[0]
            if raw.startswith("data:"):
                raw = raw.split(",", 1)[1]
            data = base64.b64decode(raw)
            mime = gateway_media._sniff_mime(data)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "seconds": round(time.time() - t, 1), "error": str(e)[:500]}
    secs = round(time.time() - t, 1)
    url = storage.save(data, mime, f"bench/{user['id']}")
    try:
        from PIL import Image
        import io
        w, h = Image.open(io.BytesIO(data)).size
    except Exception:  # noqa: BLE001
        w = h = 0
    return {"ok": True, "seconds": secs, "url": url, "bytes": len(data), "size": f"{w}x{h}"}


class VideoBench(BaseModel):
    model: str
    prompt: str = Field(..., max_length=4000)
    image_url: str | None = None
    duration: int = 5
    size: str = "1280x720"
    aspect: str = "9:16"
    extra: dict = Field(default_factory=dict)


@router.post("/bench/video")
def bench_video(p: VideoBench, user: dict = Depends(_admin)):
    body = {"prompt": p.prompt, "n": 1, "aspectRatio": p.aspect, "resolution": p.size, "duration": p.duration,
            "generateAudio": False, **p.extra}
    if p.image_url:
        body["image"] = {"type": "url", "url": p.image_url}
    t = time.time()
    try:
        out = gateway_media._post("/video-model/start", p.model, "video", body, timeout=60)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:500]}
    return {"ok": True, "job": {"model": p.model, "operation": out.get("operation")}, "started": t}


class VideoPoll(BaseModel):
    job: dict


@router.post("/bench/video/status")
def bench_video_status(p: VideoPoll, user: dict = Depends(_admin)):
    try:
        res = gateway_media.video_status(p.job)
    except Exception as e:  # noqa: BLE001
        return {"status": "pending", "error": str(e)[:300]}
    if res["status"] == "completed":
        v = res["video"]
        if v.get("type") == "url":
            data = requests.get(v["url"], timeout=120).content
        else:
            data = base64.b64decode(v.get("data", ""))
        return {"status": "completed", "url": storage.save(data, "video/mp4", f"bench/{user['id']}")}
    return res


@router.get("/meta/get")
def meta_get(path: str, fields: str = "", page_token_for: str = "", user: dict = Depends(_admin)):
    """Yönetici teşhisi: kendi Meta jetonuyla salt okunur Graph GET (isteğe bağlı sayfa jetonuyla)."""
    from app.routers.ads import _get_token
    from app.services import meta_ads_service as meta

    token = _get_token(user["id"])
    try:
        if page_token_for:
            token = meta._graph("GET", page_token_for, token, fields="access_token").get("access_token") or token
        params = {"fields": fields} if fields else {}
        return meta._graph("GET", path, token, **params)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:500]}


class ChatBench(BaseModel):
    model: str  # "anthropic/claude-haiku-5.5" (AI Gateway) ya da "groq:openai/gpt-oss-120b", "cerebras:..."
    prompt: str = Field(..., max_length=8000)
    image_url: str | None = None


@router.post("/bench/chat")
def bench_chat(p: ChatBench, user: dict = Depends(_admin)):
    """Ücretsiz sohbetle aynı koşullar: aynı sistem istemi, aynı yanıt uzunluğu sınırı (1500 token)."""
    from app.services import free_tier
    from app.services.llm_service import FREE_PROVIDERS, LLMError, _free_provider_call, chat_completion

    system = (free_tier.assistant.SYSTEM_PROMPT + free_tier.web_search.today_line() + free_tier.FREE_NOTE
              + free_tier.IMAGE_TOOL_NOTE + free_tier.MEDIA_NOTE)
    content = p.prompt
    if p.image_url:
        content = [{"type": "text", "text": p.prompt + "\n[Kullanıcı 1 görsel ekledi: image 0]"},
                   {"type": "image_url", "image_url": {"url": p.image_url}}]
    messages = [{"role": "system", "content": system}, {"role": "user", "content": content}]
    t = time.time()
    provider, _, model = p.model.partition(":")
    try:
        if provider in FREE_PROVIDERS and model:
            text = _free_provider_call(provider, model, messages, 1500)
        else:
            text = chat_completion(p.model, messages, 1500)
    except LLMError as e:
        return {"model": p.model, "error": str(e)[:500], "seconds": round(time.time() - t, 1)}
    return {"model": p.model, "text": text, "seconds": round(time.time() - t, 1)}


class AssetUpload(BaseModel):
    content: str = Field(..., max_length=8_000_000)
    content_type: str = Field("image/svg+xml", pattern=r"^image/(svg\+xml|png|jpeg)$")


@router.post("/asset")
def upload_asset(p: AssetUpload, user: dict = Depends(_admin)):
    """Site varlığı (ör. iyzico logo bandı) yükler; kalıcı Blob adresini döndürür."""
    data = p.content.encode() if p.content_type == "image/svg+xml" else base64.b64decode(p.content)
    return {"url": storage.save(data, p.content_type, "site")}
