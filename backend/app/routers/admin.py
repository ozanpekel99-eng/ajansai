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


def _chat_image(model: str, prompt: str, refs: list[str]) -> bytes:
    token = ai_gateway_token()
    content = [{"type": "text", "text": prompt}] + [{"type": "image_url", "image_url": {"url": u}} for u in refs]
    r = requests.post(
        f"{config.AI_GATEWAY_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "user", "content": content}], "modalities": ["text", "image"]},
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
            data = _chat_image(p.model, p.prompt, p.refs)
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
    return {"ok": True, "seconds": secs, "url": url, "bytes": len(data)}


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
