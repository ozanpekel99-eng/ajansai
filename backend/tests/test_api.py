import base64
import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal

import pytest
import requests

from app import config
from app.db import get_engine, users, utcnow
from app.services import iyzico_service, llm_service
from app.services.usage_service import get_usage
from sqlalchemy import select, update

from .conftest import auth, register

IDEAS_JSON = {
    "ideas": [
        {
            "platform": "instagram",
            "format": "reels",
            "title": "Soğuk kahve",
            "concept": "Buzlu kahve hazırlanışı",
            "caption": "Yaz geldi!",
            "hashtags": ["#kahve"],
        }
    ]
}

IDEA_BODY = {
    "business_name": "Cafe Lorem",
    "sector": "Kafe",
    "target_audience": "Gençler",
    "tone": "Samimi",
    "topic": "Soğuk kahve",
}


class FakeResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data
        self.text = json.dumps(data)
        self.content = self.text.encode()

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


def _user_id(client, token):
    return client.get("/api/auth/me", headers=auth(token)).json()["user"]["id"]


def register_paid(client, plan="baslangic", **kw):
    token = register(client, **kw)
    with get_engine().begin() as conn:
        conn.execute(
            update(users)
            .where(users.c.id == _user_id(client, token))
            .values(plan=plan, plan_expires_at=utcnow() + timedelta(days=30))
        )
    return token


# ---------------- Kimlik doğrulama ----------------

def test_register_login_me(client):
    token = register(client)
    me = client.get("/api/auth/me", headers=auth(token)).json()
    assert me["user"]["email"] == "ozan@example.com"
    assert me["usage"]["plan"] == "deneme"

    r = client.post("/api/auth/login", json={"email": "OZAN@example.com", "password": "gizlisifre123"})
    assert r.status_code == 200
    assert client.post("/api/auth/login", json={"email": "ozan@example.com", "password": "yanlis1234"}).status_code == 401


def test_duplicate_email_rejected(client):
    register(client)
    r = client.post("/api/auth/register", json={"email": "ozan@example.com", "password": "baskasifre1"})
    assert r.status_code == 409


def test_endpoints_require_login(client):
    assert client.post("/api/content/ideas", json=IDEA_BODY).status_code == 401
    assert client.get("/api/plans/usage").status_code == 401
    assert client.post("/api/content/image", json={"concept": "x"}).status_code == 401
    assert client.get("/api/plans/usage", headers=auth("sahte.token.degeri")).status_code == 401
    # Eski MVP'deki ücretsiz paket değiştirme kapısı kapalı olmalı
    assert client.post("/api/plans/select", json={"plan_id": "ajans"}).status_code in (404, 405)


def test_public_plan_list_hides_trial(client):
    plans = client.get("/api/plans/").json()["plans"]
    assert set(plans) == {"baslangic", "pro", "ajans"}


# ---------------- Yapay zeka (OmniRoute + yedek) ----------------

def test_ideas_via_omniroute(client, monkeypatch):
    config.OMNIROUTE_BASE_URL = "http://omniroute.test/v1"
    config.OMNIROUTE_API_KEY = "or-key"
    calls = {}

    def fake_post(url, headers=None, json=None, timeout=None, **kw):
        calls["url"], calls["headers"], calls["body"] = url, headers, json
        text = "İşte fikirler:\n```json\n" + __import__("json").dumps(IDEAS_JSON, ensure_ascii=False) + "\n```"
        return FakeResponse(200, {"choices": [{"message": {"content": text}}]})

    monkeypatch.setattr(llm_service.requests, "post", fake_post)
    token = register_paid(client)
    r = client.post("/api/content/ideas", json=IDEA_BODY, headers=auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["provider"] == "omniroute"
    assert r.json()["ideas"][0]["title"] == "Soğuk kahve"
    assert calls["url"] == "http://omniroute.test/v1/chat/completions"
    assert calls["headers"]["Authorization"] == "Bearer or-key"
    assert calls["body"]["model"] == config.OMNIROUTE_MODEL
    assert calls["body"]["messages"][0]["role"] == "system"


def test_ideas_fall_back_to_anthropic_when_omniroute_down(client, monkeypatch):
    config.OMNIROUTE_BASE_URL = "http://omniroute.test/v1"
    config.ANTHROPIC_API_KEY = "sk-test"

    def broken_post(*a, **kw):
        raise requests.ConnectionError("bağlantı yok")

    monkeypatch.setattr(llm_service.requests, "post", broken_post)
    monkeypatch.setattr(llm_service, "_call_anthropic", lambda s, u, m: json.dumps(IDEAS_JSON))

    token = register_paid(client)
    r = client.post("/api/content/ideas", json=IDEA_BODY, headers=auth(token))
    assert r.status_code == 200
    assert r.json()["provider"] == "anthropic"


def _credits(client, token):
    return client.get("/api/plans/usage", headers=auth(token)).json()["credits"]


def test_ideas_503_and_refund_when_no_ai(client):
    token = register_paid(client)
    r = client.post("/api/content/ideas", json=IDEA_BODY, headers=auth(token))
    assert r.status_code == 503
    assert _credits(client, token)["used"] == 0


def _fake_ideas(monkeypatch):
    from app.services import claude_service

    monkeypatch.setattr(claude_service, "complete", lambda *a, **k: (json.dumps(IDEAS_JSON), "test"))


def test_idea_cost_is_one_credit_per_two_ideas(client, monkeypatch):
    _fake_ideas(monkeypatch)
    token = register_paid(client)
    r = client.post("/api/content/ideas", json={**IDEA_BODY, "idea_count": 6}, headers=auth(token))
    assert r.status_code == 200 and r.json()["credits_spent"] == 3
    r = client.post("/api/content/ideas", json={**IDEA_BODY, "idea_count": 1}, headers=auth(token))
    assert r.json()["credits_spent"] == 1
    c = _credits(client, token)
    assert c == {"total": 200, "used": 4, "remaining": 196, "period_remaining": 196, "extra": 0}
    events = client.get("/api/plans/history", headers=auth(token)).json()["events"]
    assert [e["credits"] for e in events] == [1, 3] and events[0]["label"] == "İçerik fikri"


def test_free_plan_has_no_credits(client, monkeypatch):
    _fake_ideas(monkeypatch)
    token = register(client)
    assert _credits(client, token) == {"total": 0, "used": 0, "remaining": 0, "period_remaining": 0, "extra": 0}
    r = client.post("/api/content/ideas", json=IDEA_BODY, headers=auth(token))
    assert r.status_code == 402 and "Kredin yetmiyor" in r.json()["detail"]


def test_unparseable_ai_answer_refunds(client, monkeypatch):
    from app.services import claude_service

    monkeypatch.setattr(claude_service, "complete", lambda *a, **k: ("üzgünüm, yapamam", "test"))
    token = register_paid(client)
    r = client.post("/api/content/ideas", json=IDEA_BODY, headers=auth(token))
    assert r.json()["error"]
    assert _credits(client, token)["used"] == 0
    assert client.get("/api/plans/history", headers=auth(token)).json()["events"][0]["refunded"] is True


# ---------------- Kredi / görsel / video ----------------

def _set_plan(user_id, plan):
    with get_engine().begin() as conn:
        conn.execute(
            update(users).where(users.c.id == user_id).values(plan=plan, plan_expires_at=utcnow() + timedelta(days=30))
        )


BLOB_TOKEN = "vercel_blob_rw_StoreAbc123_gizli"
BLOB_URL = "https://storeabc123.public.blob.vercel-storage.com/yuklemeler/u/"


def _enable_media(monkeypatch):
    from app.routers import content

    config.AI_GATEWAY_ENABLED = True
    monkeypatch.setattr(config, "BLOB_READ_WRITE_TOKEN", BLOB_TOKEN)
    # Planlayıcı (LLM) testte çağrılmaz: istek olduğu gibi kullanılır
    monkeypatch.setattr(content.media_planner, "plan_image",
                        lambda req, aspect, edit=False, ref_count=0, previous_prompt=None: {"prompt": req, "note": ""})
    monkeypatch.setattr(content.media_planner, "plan_video",
                        lambda req, aspect, duration, has_start_frame, audio, previous_prompt=None:
                        {"prompt": req, "frame_prompt": "" if has_start_frame else req, "note": ""})

    def no_frame(*a, **k):
        raise content.gateway_media.MediaError("testte görsel yok")

    monkeypatch.setattr(content.gateway_media, "generate_image", no_frame)
    monkeypatch.setattr(content, "_image_aspect_of", lambda url: None)
    return content


def test_paid_plan_makes_images_and_pays_four_credits(client, monkeypatch):
    content = _enable_media(monkeypatch)
    calls = {}

    def fake_image(prompt, aspect, refs=None):
        calls["aspect"] = aspect
        return b"\x89PNG\r\n\x1a\nveri", "image/png"

    monkeypatch.setattr(content.gateway_media, "generate_image", fake_image)
    monkeypatch.setattr(config, "BLOB_READ_WRITE_TOKEN", None)  # depo yoksa data URL döner
    token = register_paid(client)
    r = client.post("/api/content/image", json={"concept": "kahve", "aspect_ratio": "ASPECT_9_16"}, headers=auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["image_url"].startswith("data:image/png;base64,")
    assert r.json()["credits_spent"] == 4 and calls["aspect"] == "9:16"
    assert _credits(client, token)["used"] == 4


def test_image_saved_to_blob_when_configured(client, monkeypatch):
    content = _enable_media(monkeypatch)
    monkeypatch.setattr(content.gateway_media, "generate_image", lambda p, a, r=None: (b"\xff\xd8\xffjpg", "image/jpeg"))
    sent = {}

    def fake_put(url, params=None, data=None, headers=None, timeout=None):
        sent.update(url=url, params=params, headers=headers)
        return FakeResponse(200, {"url": "https://store.public.blob.vercel-storage.com/" + params["pathname"]})

    from app.services import storage

    monkeypatch.setattr(storage.requests, "put", fake_put)
    token = register_paid(client)
    r = client.post("/api/content/image", json={"concept": "kahve"}, headers=auth(token))
    assert r.json()["image_url"].startswith("https://store.public.blob.vercel-storage.com/gorsel/")
    assert sent["params"]["pathname"].endswith(".jpg")
    assert sent["headers"]["x-vercel-blob-access"] == "public"


def test_image_failure_refunds_credits(client, monkeypatch):
    content = _enable_media(monkeypatch)

    def broken(prompt, aspect, refs=None):
        raise content.gateway_media.MediaError("kapalı")

    monkeypatch.setattr(content.gateway_media, "generate_image", broken)
    token = register_paid(client)
    r = client.post("/api/content/image", json={"concept": "kahve"}, headers=auth(token))
    assert r.status_code == 200 and r.json()["image_url"] is None
    assert _credits(client, token)["used"] == 0


def test_trial_cannot_make_videos(client, monkeypatch):
    _enable_media(monkeypatch)
    token = register(client)
    r = client.post("/api/content/video", json={"concept": "x"}, headers=auth(token))
    assert r.status_code == 402 and "paketinde bulunmuyor" in r.json()["detail"]
    assert _credits(client, token)["used"] == 0


def test_video_costs_and_failed_job_refunded_once(client, monkeypatch):
    content = _enable_media(monkeypatch)
    token = register(client)
    _set_plan(_user_id(client, token), "baslangic")
    started = []
    monkeypatch.setattr(content.gateway_media, "start_video", lambda p, d, r="720p", i=None, e=None, a=False, ar="9:16": started.append((d, r, i, e, a, ar)) or {"model": "m", "operation": {"id": "op"}})
    monkeypatch.setattr(content.gateway_media, "video_status", lambda op: {"status": "error", "error": "model hatası"})

    r5 = client.post("/api/content/video", json={"concept": "x"}, headers=auth(token)).json()
    r10 = client.post(
        "/api/content/video",
        json={
            "concept": "x",
            "duration": 8,
            "resolution": "1080p",
            "image_url": BLOB_URL + "a.png",
            "end_image_url": BLOB_URL + "b.png",
            "aspect_ratio": "16:9",
        },
        headers=auth(token),
    ).json()
    assert (r5["credits_spent"], r10["credits_spent"]) == (12, 48)
    assert started == [(6, "720p", None, None, False, "9:16"), (8, "1080p", BLOB_URL + "a.png", BLOB_URL + "b.png", False, "16:9")]
    assert _credits(client, token)["used"] == 60
    # Desteklenmeyen süre/çözünürlük reddedilir
    assert client.post("/api/content/video", json={"concept": "x", "duration": 5}, headers=auth(token)).status_code == 422
    assert client.post("/api/content/video", json={"concept": "x", "resolution": "8k"}, headers=auth(token)).status_code == 422
    # 4K, Başlangıç paketinin 200 kredisine sığmaz
    r4k = client.post("/api/content/video", json={"concept": "x", "resolution": "4k", "duration": 8, "audio": True}, headers=auth(token))
    assert r4k.status_code == 402 and "168" in r4k.json()["detail"]

    # Başarısız iş iki kez sorgulansa da kredi bir kez iade edilir
    for _ in range(2):
        st = client.get(f"/api/content/video/{r5['job_id']}", headers=auth(token)).json()
        assert st["status"] == "FAILED"
    assert _credits(client, token)["used"] == 48


def test_video_completes_and_is_cached(client, monkeypatch):
    content = _enable_media(monkeypatch)
    token = register(client)
    _set_plan(_user_id(client, token), "pro")
    monkeypatch.setattr(content.gateway_media, "start_video", lambda *a, **k: {"model": "m", "operation": {"id": "op"}})
    monkeypatch.setattr(config, "BLOB_READ_WRITE_TOKEN", None)  # depo yoksa sağlayıcının adresi döner
    states = iter([{"status": "pending"}, {"status": "completed", "video": {"type": "url", "url": "https://cdn/v.mp4"}}])
    monkeypatch.setattr(content.gateway_media, "video_status", lambda op: next(states))

    job = client.post("/api/content/video", json={"concept": "x"}, headers=auth(token)).json()["job_id"]
    assert client.get(f"/api/content/video/{job}", headers=auth(token)).json()["status"] == "PENDING"
    done = client.get(f"/api/content/video/{job}", headers=auth(token)).json()
    assert done == {"status": "SUCCEEDED", "video_url": "https://cdn/v.mp4", "error": None}
    # Üçüncü sorgu sağlayıcıya gitmez (iterator bitti, gitseydi hata verirdi)
    assert client.get(f"/api/content/video/{job}", headers=auth(token)).json()["status"] == "SUCCEEDED"


def test_cannot_read_other_users_video(client, monkeypatch):
    content = _enable_media(monkeypatch)
    owner = register(client, "a@example.com")
    _set_plan(_user_id(client, owner), "baslangic")
    monkeypatch.setattr(content.gateway_media, "start_video", lambda *a, **k: {"model": "m", "operation": {"id": "op"}})
    monkeypatch.setattr(content.gateway_media, "video_status", lambda op: {"status": "error"})
    job = client.post("/api/content/video", json={"concept": "x"}, headers=auth(owner)).json()["job_id"]

    other = register(client, "b@example.com")
    assert client.get(f"/api/content/video/{job}", headers=auth(other)).status_code == 404
    # Başkası sorgulayamadığı için sahibin kredisi iade edilmemiş olmalı
    assert _credits(client, owner)["used"] == 12


def test_video_audio_costs_more_and_foreign_urls_rejected(client, monkeypatch):
    content = _enable_media(monkeypatch)
    token = register(client)
    _set_plan(_user_id(client, token), "pro")
    monkeypatch.setattr(content.gateway_media, "start_video", lambda *a, **k: {"model": "m", "operation": {}})
    r = client.post("/api/content/video", json={"concept": "x", "resolution": "1080p", "audio": True}, headers=auth(token))
    assert r.json()["credits_spent"] == 54
    bad = client.post("/api/content/video", json={"concept": "x", "image_url": "https://kotu.site/a.png"}, headers=auth(token))
    assert bad.status_code == 400
    assert _credits(client, token)["used"] == 54


def test_image_with_reference_images(client, monkeypatch):
    content = _enable_media(monkeypatch)
    seen = {}
    monkeypatch.setattr(content.gateway_media, "generate_image", lambda p, a, r=None: seen.update(refs=r) or (b"\x89PNG\r\n\x1a\n", "image/png"))
    monkeypatch.setattr(content.storage, "save", lambda d, m, f: "https://storeabc123.public.blob.vercel-storage.com/gorsel/x.png")
    token = register_paid(client)
    r = client.post("/api/content/image", json={"concept": "aynı ürün, beyaz fon", "reference_urls": [BLOB_URL + "urun.jpg"]}, headers=auth(token))
    assert r.status_code == 200 and seen["refs"] == [BLOB_URL + "urun.jpg"]
    assert client.post("/api/content/image", json={"concept": "x", "reference_urls": ["https://baska.com/a.jpg"]}, headers=auth(token)).status_code == 400


def test_upload_token_rules(client, monkeypatch):
    _enable_media(monkeypatch)
    token = register_paid(client)
    ok = client.post("/api/uploads/token", json={"filename": "urun.JPG", "content_type": "image/jpeg", "size": 1000}, headers=auth(token))
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["kind"] == "image" and body["pathname"].endswith(".jpg")
    assert body["client_token"].startswith("vercel_blob_client_StoreAbc123_")
    signature, payload = base64.b64decode(body["client_token"].split("_", 4)[4]).decode().split(".", 1)
    assert hmac.new(BLOB_TOKEN.encode(), payload.encode(), hashlib.sha256).hexdigest() == signature
    claims = json.loads(base64.b64decode(payload))
    assert claims["pathname"] == body["pathname"] and claims["allowedContentTypes"] == ["image/jpeg"]

    too_big = client.post("/api/uploads/token", json={"filename": "v.mp4", "content_type": "video/mp4", "size": 60 * 1024 * 1024}, headers=auth(token))
    assert too_big.status_code == 413
    wrong = client.post("/api/uploads/token", json={"filename": "a.exe", "content_type": "application/x-msdownload", "size": 10}, headers=auth(token))
    assert wrong.status_code == 400

    # Ziyaretçi: görsel ve belge yükleyebilir, video yükleyemez, 10 MB sınırı
    guest = client.post("/api/uploads/token", json={"filename": "a.pdf", "content_type": "application/pdf", "size": 1000})
    assert guest.status_code == 200 and "/misafir/" in guest.json()["pathname"]
    assert client.post("/api/uploads/token", json={"filename": "v.mp4", "content_type": "video/mp4", "size": 10}).status_code == 403
    assert client.post("/api/uploads/token", json={"filename": "b.png", "content_type": "image/png", "size": 11 * 1024 * 1024}).status_code == 413


def test_chat_with_attachments(client, monkeypatch):
    _enable_media(monkeypatch)
    from app.services import assistant

    sent = {}
    monkeypatch.setattr(assistant.storage, "fetch", lambda url, max_bytes=0: b"video-bytes" if url.endswith(".mp4") else b"%PDF-1.4")
    monkeypatch.setattr(assistant, "chat_completion", lambda model, messages, max_tokens=0: sent.update(model=model, messages=messages) or "Harika bir video!")
    token = register_paid(client)
    r = client.post(
        "/api/content/chat",
        json={
            "messages": [
                {"role": "user", "content": "Merhaba"},
                {"role": "assistant", "content": "Selam, nasıl yardımcı olayım?"},
                {
                    "role": "user",
                    "content": "Bu videoya benzer 3 Reels fikri",
                    "attachments": [
                        {"url": BLOB_URL + "ornek.mp4", "content_type": "video/mp4", "name": "ornek.mp4"},
                        {"url": BLOB_URL + "katalog.pdf", "content_type": "application/pdf", "name": "katalog.pdf"},
                    ],
                },
            ]
        },
        headers=auth(token),
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"reply": "Harika bir video!", "model": config.CHAT_VIDEO_MODEL, "images": [], "image_error": None, "sources": [], "files": [], "video": None, "credits_spent": 3}
    last = sent["messages"][-1]["content"]
    assert last[1]["type"] == "file" and last[1]["file"]["file_data"].startswith("data:video/mp4;base64,")
    assert last[2]["file"]["filename"] == "katalog.pdf"
    assert sent["messages"][0]["role"] == "system"
    events = client.get("/api/plans/history", headers=auth(token)).json()["events"]
    assert events[0]["label"] == "Sohbet" and events[0]["credits"] == 3


def test_chat_text_only_uses_claude_and_refunds_on_error(client, monkeypatch):
    _enable_media(monkeypatch)
    from app.services import assistant
    from app.services.llm_service import LLMError

    monkeypatch.setattr(assistant, "chat_completion", lambda model, messages, max_tokens=0: (_ for _ in ()).throw(LLMError("kapalı")))
    token = register_paid(client)
    r = client.post("/api/content/chat", json={"messages": [{"role": "user", "content": "Fikir ver"}]}, headers=auth(token))
    assert r.status_code == 503
    assert _credits(client, token)["used"] == 0
    assert client.post("/api/content/chat", json={"messages": [{"role": "user", "content": "  "}]}, headers=auth(token)).status_code == 400


def test_describe_sample_for_video(client, monkeypatch):
    _enable_media(monkeypatch)
    from app.services import assistant

    monkeypatch.setattr(assistant.storage, "fetch", lambda url, max_bytes=0: b"\xff\xd8\xff")
    monkeypatch.setattr(assistant, "chat_completion", lambda model, messages, max_tokens=0: " Buzdolabı kapağı açılıyor. ")
    token = register_paid(client)
    r = client.post(
        "/api/content/describe",
        json={"attachment": {"url": BLOB_URL + "a.jpg", "content_type": "image/jpeg", "name": "a.jpg"}, "target": "video"},
        headers=auth(token),
    )
    assert r.json() == {"concept": "Buzdolabı kapağı açılıyor.", "credits_spent": 1}


def test_plans_endpoint_shows_credit_examples(client):
    data = client.get("/api/plans/").json()
    assert data["costs"]["image"] == 4
    assert data["costs"]["video"]["720p"] == {"4": 8, "6": 12, "8": 16}
    assert data["costs"]["video"]["4k"]["8"] == 144
    pro = data["plans"]["pro"]
    assert pro["credits"] == 500 and pro["examples"]["images"] == 125 and pro["price"] == 20 and pro["price_yearly"] == 192
    assert pro["examples"]["videos"] == {"720p": 41, "1080p": 13, "4k": 4}
    assert data["plans"]["ajans"]["name"] == "Advanced" and data["plans"]["ajans"]["credits"] == 900 and data["plans"]["ajans"]["price_yearly"] == 288
    assert data["trial"]["examples"]["videos"]["720p"] == 0


def test_gateway_media_request_format(monkeypatch):
    from app.services import gateway_media, llm_service as ls

    config.AI_GATEWAY_API_KEY = "gw-key"
    sent = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        sent.update(url=url, headers=headers, body=json)
        if url.endswith("/image-model"):
            return FakeResponse(200, {"images": [base64.b64encode(b"\xff\xd8\xffx").decode()]})
        return FakeResponse(200, {"operation": {"gatewayJobId": "job_1"}})

    monkeypatch.setattr(gateway_media.requests, "post", fake_post)
    # Gemini (sohbet API'si) yanıt vermezse sıradaki modele geçilir; en son Seedream (görsel API'si)
    def fake_chat_post(url, headers=None, json=None, timeout=None):
        if url.endswith("/chat/completions"):
            sent.setdefault("chat", []).append(json)
            return FakeResponse(200, {"choices": [{"message": {"content": "", "images": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\nxx").decode()}}]}}]})
        return fake_post(url, headers, json, timeout)

    monkeypatch.setattr(gateway_media.requests, "post", fake_chat_post)
    data, mime = gateway_media.generate_image("kahve", "9:16", ["https://x/ref.png"])
    assert mime == "image/png"
    body = sent["chat"][0]
    assert body["model"] == config.IMAGE_MODEL and body["modalities"] == ["text", "image"]
    assert body["providerOptions"]["google"]["imageConfig"]["aspectRatio"] == "9:16"
    assert body["messages"][0]["content"][1] == {"type": "image_url", "image_url": {"url": "https://x/ref.png"}}

    monkeypatch.setattr(gateway_media.requests, "post", fake_post)
    monkeypatch.setattr(gateway_media, "_gemini_image", lambda *a: (_ for _ in ()).throw(gateway_media.MediaError("yok")))
    data, mime = gateway_media.generate_image("kahve", "1:1")
    assert mime == "image/jpeg" and sent["url"].endswith("/v4/ai/image-model")
    assert sent["headers"]["ai-model-id"] == config.IMAGE_MODEL_LAST
    assert sent["headers"]["ai-image-model-specification-version"] == "4"
    assert sent["headers"]["Authorization"] == "Bearer gw-key"

    job = gateway_media.start_video("dalga", 8, "4k", "https://x/a.png")
    assert job == {"model": config.VIDEO_MODELS["4k"][0], "operation": {"gatewayJobId": "job_1"}}
    assert sent["url"].endswith("/video-model/start") and sent["headers"]["ai-model-id"] == config.VIDEO_MODELS["4k"][0]
    assert sent["body"]["image"] == {"type": "url", "url": "https://x/a.png"}
    assert sent["body"]["aspectRatio"] == "9:16" and sent["body"]["duration"] == 8
    assert sent["body"]["resolution"] == "3840x2160"


def test_expired_plan_falls_back_to_trial(client):
    token = register(client)
    uid = _user_id(client, token)
    with get_engine().begin() as conn:
        conn.execute(
            update(users).where(users.c.id == uid).values(plan="pro", plan_expires_at=utcnow() - timedelta(minutes=1))
        )
    assert get_usage(uid)["plan"] == "deneme"


def test_ads_locked_on_trial(client):
    token = register(client)
    assert client.get("/api/ads/meta/connect", headers=auth(token)).status_code == 403


# ---------------- iyzico ----------------

def test_iyzico_signature_matches_documented_formula():
    config.IYZICO_API_KEY = "apikey"
    config.IYZICO_SECRET_KEY = "secret"
    body = '{"locale":"tr","conversationId":"1"}'
    headers = iyzico_service.build_auth_headers("/payment/test", body, random_key="123456789")

    expected_sig = hmac.new(b"secret", b"123456789/payment/test" + body.encode(), hashlib.sha256).hexdigest()
    decoded = base64.b64decode(headers["Authorization"].removeprefix("IYZWSv2 ")).decode()
    assert decoded == f"apiKey:apikey&randomKey:123456789&signature:{expected_sig}"
    assert headers["x-iyzi-rnd"] == "123456789"


def _enable_iyzico(monkeypatch, retrieve_result):
    config.IYZICO_API_KEY = "k"
    config.IYZICO_SECRET_KEY = "s"
    sent = []

    def fake_post(path, payload, raise_on_failure=True):
        sent.append((path, payload))
        if path == iyzico_service.INIT_PATH:
            return {"status": "success", "token": "tok-1", "paymentPageUrl": "https://sandbox.iyzi/pay/tok-1"}
        result = dict(retrieve_result)
        result.setdefault("basketId", payload["conversationId"])
        return result

    monkeypatch.setattr(iyzico_service, "_post", fake_post)
    return sent


BILLING = {"name": "Ozan", "surname": "Pekel", "phone": "0535 000 00 00", "city": "Tekirdağ", "address": "Çorlu Merkez"}


def test_payment_success_activates_plan_once(client, monkeypatch):
    sent = _enable_iyzico(
        monkeypatch, {"status": "success", "paymentStatus": "SUCCESS", "paidPrice": "24.00", "currency": "USD", "paymentId": "p1"}
    )
    token = register(client)

    r = client.post("/api/payments/checkout", json={"plan_id": "pro", "billing": BILLING}, headers=auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["payment_page_url"].endswith("tok-1")
    init_payload = sent[0][1]
    assert init_payload["price"] == "24.00" and init_payload["paidPrice"] == "24.00"  # $20 + %20 KDV
    assert init_payload["currency"] == "USD"
    assert init_payload["buyer"]["gsmNumber"] == "+905350000000"
    assert init_payload["callbackUrl"].endswith("/api/payments/iyzico/callback")

    # Ödeme bitmeden paket açılmamalı
    assert client.get("/api/plans/usage", headers=auth(token)).json()["plan"] == "deneme"

    cb = client.post("/api/payments/iyzico/callback", data={"token": "tok-1"}, follow_redirects=False)
    assert cb.status_code == 303 and "status=success" in cb.headers["location"]
    usage = client.get("/api/plans/usage", headers=auth(token)).json()
    assert usage["plan"] == "pro" and usage["plan_expires_at"]

    # Aynı callback tekrar gelirse iyzico'ya tekrar sorulmaz, paket uzatılmaz
    before = usage["plan_expires_at"]
    n = len(sent)
    cb2 = client.post("/api/payments/iyzico/callback", data={"token": "tok-1"}, follow_redirects=False)
    assert "status=success" in cb2.headers["location"]
    assert len(sent) == n
    assert client.get("/api/plans/usage", headers=auth(token)).json()["plan_expires_at"] == before


@pytest.mark.parametrize(
    "result",
    [
        {"status": "success", "paymentStatus": "FAILURE", "paidPrice": "24.00", "currency": "USD"},
        {"status": "failure", "errorMessage": "Kart reddedildi"},
        {"status": "success", "paymentStatus": "SUCCESS", "paidPrice": "1.00", "currency": "USD"},  # eksik tutar
        {"status": "success", "paymentStatus": "SUCCESS", "paidPrice": "25.00", "currency": "TRY"},  # yanlış para birimi
        {"status": "success", "paymentStatus": "SUCCESS", "paidPrice": "24.00", "currency": "USD", "basketId": "baska-sepet"},
    ],
)
def test_payment_failure_does_not_activate(client, monkeypatch, result):
    _enable_iyzico(monkeypatch, result)
    token = register(client)
    client.post("/api/payments/checkout", json={"plan_id": "pro", "billing": BILLING}, headers=auth(token))
    cb = client.post("/api/payments/iyzico/callback", data={"token": "tok-1"}, follow_redirects=False)
    assert "status=failure" in cb.headers["location"]
    assert client.get("/api/plans/usage", headers=auth(token)).json()["plan"] == "deneme"


def test_unknown_token_callback(client):
    cb = client.post("/api/payments/iyzico/callback", data={"token": "yok"}, follow_redirects=False)
    assert cb.status_code == 303 and "status=failure" in cb.headers["location"]


def test_checkout_rejects_trial_and_unknown_plans(client, monkeypatch):
    _enable_iyzico(monkeypatch, {})
    token = register(client)
    for plan in ("deneme", "bedava"):
        r = client.post("/api/payments/checkout", json={"plan_id": plan, "billing": BILLING}, headers=auth(token))
        assert r.status_code == 400


def test_payment_status_only_visible_to_owner(client, monkeypatch):
    _enable_iyzico(monkeypatch, {"status": "failure"})
    a = register(client, "a@example.com")
    pid = client.post("/api/payments/checkout", json={"plan_id": "pro", "billing": BILLING}, headers=auth(a)).json()["payment_id"]
    b = register(client, "b@example.com")
    assert client.get(f"/api/payments/{pid}", headers=auth(b)).status_code == 404
    st = client.get(f"/api/payments/{pid}", headers=auth(a)).json()
    assert st["status"] == "pending"  # kullanıcı ödeme sayfasını bitirmedi


def test_payment_list_shows_only_own_payments(client, monkeypatch):
    _enable_iyzico(monkeypatch, {"status": "failure"})
    a = register(client, "a@example.com")
    client.post("/api/payments/checkout", json={"plan_id": "pro", "billing": BILLING}, headers=auth(a))
    b = register(client, "b@example.com")
    assert client.get("/api/payments/", headers=auth(b)).json()["payments"] == []
    items = client.get("/api/payments/", headers=auth(a)).json()["payments"]
    assert len(items) == 1
    assert items[0]["plan_name"] == "Pro" and items[0]["amount"] == 24 and items[0]["currency"] == "USD"
    assert items[0]["status"] == "pending"


def test_image_rejects_unknown_aspect_ratio(client):
    config.AI_GATEWAY_ENABLED = True
    token = register(client)
    r = client.post("/api/content/image", json={"concept": "kahve", "aspect_ratio": "ASPECT_99"}, headers=auth(token))
    assert r.status_code == 422


def test_health(client):
    h = client.get("/health").json()
    assert h["status"] == "ok"


def test_jwt_secret_generated_and_stored_when_not_configured(client, monkeypatch):
    from app import security
    from app.db import app_settings

    monkeypatch.setattr(config, "JWT_SECRET", None)
    monkeypatch.setattr(security, "_cached_secret", None)

    token = register(client)
    with get_engine().connect() as conn:
        stored = conn.execute(select(app_settings.c.value).where(app_settings.c.key == "jwt_secret")).scalar()
    assert stored and len(stored) > 40

    # Yeni bir sunucu örneği gibi önbelleği temizle: aynı anahtar veritabanından okunmalı
    monkeypatch.setattr(security, "_cached_secret", None)
    assert client.get("/api/auth/me", headers=auth(token)).status_code == 200


def test_ideas_via_vercel_ai_gateway_with_oidc_header(client, monkeypatch):
    """Vercel'de API key olmadan: istekle gelen OIDC token AI Gateway'e iletilir."""
    config.AI_GATEWAY_ENABLED = True
    monkeypatch.delenv("VERCEL_OIDC_TOKEN", raising=False)
    calls = {}

    def fake_post(url, headers=None, json=None, timeout=None, **kw):
        calls["url"], calls["auth"], calls["model"] = url, headers.get("Authorization"), json["model"]
        return FakeResponse(200, {"choices": [{"message": {"content": __import__("json").dumps(IDEAS_JSON)}}]})

    monkeypatch.setattr(llm_service.requests, "post", fake_post)
    token = register_paid(client)
    headers = {**auth(token), "x-vercel-oidc-token": "oidc-123"}
    r = client.post("/api/content/ideas", json=IDEA_BODY, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["provider"] == "ai_gateway"
    assert calls["url"] == "https://ai-gateway.vercel.sh/v1/chat/completions"
    assert calls["auth"] == "Bearer oidc-123"
    assert calls["model"] == config.AI_GATEWAY_MODEL


def test_omniroute_failure_falls_back_to_ai_gateway(client, monkeypatch):
    config.OMNIROUTE_BASE_URL = "http://omniroute.test/v1"
    config.AI_GATEWAY_ENABLED = True
    config.AI_GATEWAY_API_KEY = "gw-key"

    def fake_post(url, headers=None, json=None, timeout=None, **kw):
        if "omniroute" in url:
            raise requests.ConnectionError("kapalı")
        return FakeResponse(200, {"choices": [{"message": {"content": __import__("json").dumps(IDEAS_JSON)}}]})

    monkeypatch.setattr(llm_service.requests, "post", fake_post)
    token = register_paid(client)
    r = client.post("/api/content/ideas", json=IDEA_BODY, headers=auth(token))
    assert r.json()["provider"] == "ai_gateway"


def test_meta_oauth_url_uses_business_login_config(monkeypatch):
    from app.services import meta_ads_service

    monkeypatch.setattr(config, "META_APP_ID", "1640836891080236")
    monkeypatch.setattr(config, "META_CONFIG_ID", "1641489131038900")
    url = meta_ads_service.get_oauth_url("https://www.ajansai.tr/ads/callback", "imzali-state")
    assert url.startswith("https://www.facebook.com/v26.0/dialog/oauth?")
    assert "config_id=1641489131038900" in url and "scope=" not in url
    assert "redirect_uri=https%3A%2F%2Fwww.ajansai.tr%2Fads%2Fcallback" in url

    monkeypatch.setattr(config, "META_CONFIG_ID", None)
    assert "scope=ads_management" in meta_ads_service.get_oauth_url("https://x/cb", "s")


def _meta_ready(client, monkeypatch, plan="pro"):
    from app.db import meta_connections

    _enable_media(monkeypatch)
    monkeypatch.setattr(config, "META_APP_ID", "app")
    monkeypatch.setattr(config, "META_APP_SECRET", "secret")
    token = register(client)
    uid = _user_id(client, token)
    _set_plan(uid, plan)
    with get_engine().begin() as conn:
        conn.execute(meta_connections.insert().values(user_id=uid, access_token="meta-token", updated_at=utcnow()))
    return token


AD_BODY = {
    "ad_account_id": "act_123",
    "page_id": "page1",
    "instagram_user_id": "ig1",
    "name": "Kasım buzdolabı",
    "objective": "traffic",
    "daily_budget": 250,
    "currency": "TRY",
    "locations": [{"key": "2520", "name": "Çorlu", "type": "city"}],
    "age_min": 25,
    "age_max": 45,
    "gender": "all",
    "media": {"url": BLOB_URL + "urun.jpg", "kind": "image"},
    "primary_text": "Peşin fiyatına 6 taksit!",
    "headline": "No-Frost fırsatı",
    "link": "basakarcelik.com",
    "call_to_action": "SHOP_NOW",
}


def test_create_instagram_only_ad(client, monkeypatch):
    from app.services import meta_ads_service as meta

    token = _meta_ready(client, monkeypatch)
    calls = []

    def fake_graph(method, path, tok, **data):
        calls.append((method, path, data))
        if path.endswith("/campaigns"):
            return {"id": "c1"}
        if path.endswith("/adsets"):
            return {"id": "s1"}
        if path.endswith("/adimages"):
            return {"images": {"x": {"hash": "h1"}}}
        if path.endswith("/adcreatives"):
            return {"id": "cr1"}
        if path.endswith("/ads"):
            return {"id": "a1"}
        if path == "c1":
            return {"effective_status": "PAUSED"}
        return {"data": []}

    monkeypatch.setattr(meta, "_graph", fake_graph)
    from app.routers import ads as ads_router

    monkeypatch.setattr(ads_router.storage, "fetch", lambda url, max_bytes=0: b"jpg")
    r = client.post("/api/ads/meta/ads", json=AD_BODY, headers=auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["campaign_id"] == "c1" and r.json()["status"] == "ACTIVE"
    # Oluşturma bittikten sonra hemen yayına alınır (reklam → set → kampanya)
    assert [(p, d["status"]) for m, p, d in calls if d.get("status") == "ACTIVE"] == [("a1", "ACTIVE"), ("s1", "ACTIVE"), ("c1", "ACTIVE")]

    adset = next(d for m, p, d in calls if p.endswith("/adsets"))
    t = adset["targeting"]
    assert t["publisher_platforms"] == ["instagram"]
    assert set(t["instagram_positions"]) == {"stream", "story", "reels"}
    assert t["geo_locations"] == {"cities": [{"key": "2520", "radius": 10, "distance_unit": "kilometer"}]}
    assert adset["daily_budget"] == 25000 and adset["status"] == "PAUSED" and adset["optimization_goal"] == "LINK_CLICKS"
    creative = next(d for m, p, d in calls if p.endswith("/adcreatives"))
    link_data = creative["object_story_spec"]["link_data"]
    assert link_data["link"] == "https://basakarcelik.com" and link_data["call_to_action"]["type"] == "SHOP_NOW"
    assert creative["object_story_spec"]["instagram_user_id"] == "ig1"

    # Yayına alma: reklam, reklam seti ve kampanya aktifleşir
    ad_id = client.get("/api/ads/meta/ads", headers=auth(token)).json()["ads"][0]["id"]
    calls.clear()
    assert client.post(f"/api/ads/meta/ads/{ad_id}/publish", headers=auth(token)).json() == {"status": "ACTIVE"}
    assert [(p, d["status"]) for m, p, d in calls] == [("a1", "ACTIVE"), ("s1", "ACTIVE"), ("c1", "ACTIVE")]

    # Başka kullanıcı bu reklamı yönetemez
    other = register(client, "baska@example.com")
    _set_plan(_user_id(client, other), "pro")
    from app.db import meta_connections

    with get_engine().begin() as conn:
        conn.execute(meta_connections.insert().values(user_id=_user_id(client, other), access_token="t2", updated_at=utcnow()))
    assert client.post(f"/api/ads/meta/ads/{ad_id}/publish", headers=auth(other)).status_code == 404


def test_failed_ad_creation_deletes_campaign(client, monkeypatch):
    from app.services import meta_ads_service as meta

    token = _meta_ready(client, monkeypatch)
    calls = []

    def fake_graph(method, path, tok, **data):
        calls.append((method, path))
        if path.endswith("/campaigns"):
            return {"id": "c9"}
        if path.endswith("/adsets"):
            raise meta.MetaError("Bütçe çok düşük.")
        return {}

    monkeypatch.setattr(meta, "_graph", fake_graph)
    r = client.post("/api/ads/meta/ads", json=AD_BODY, headers=auth(token))
    assert r.status_code == 502 and r.json()["detail"] == "Bütçe çok düşük."
    assert ("DELETE", "c9") in calls


def test_ad_requires_link_and_own_media(client, monkeypatch):
    token = _meta_ready(client, monkeypatch)
    r = client.post("/api/ads/meta/ads", json={**AD_BODY, "link": None}, headers=auth(token))
    assert r.status_code == 400
    r = client.post("/api/ads/meta/ads", json={**AD_BODY, "media": {"url": "https://baska.site/a.jpg", "kind": "image"}}, headers=auth(token))
    assert r.status_code == 400


def test_yearly_checkout_charges_discount_plus_vat_and_opens_365_days(client, monkeypatch):
    from app.routers import payments as pr

    q = client.get("/api/payments/quote", params={"plan_id": "ajans", "cycle": "yearly"}).json()
    assert q == {"plan_id": "ajans", "cycle": "yearly", "net": 288.0, "vat": 57.6, "vat_rate": 20, "total": 345.6, "currency": "USD"}
    monkeypatch.setattr(config, "IYZICO_API_KEY", "k")
    monkeypatch.setattr(config, "IYZICO_SECRET_KEY", "s")
    sent = {}

    def fake_init(**kw):
        sent.update(kw)
        return {"token": "tok-y", "payment_page_url": "https://iyzico/pay"}

    monkeypatch.setattr(pr.iyzico_service, "initialize_checkout", fake_init)
    token = register(client)
    billing = {"name": "Ozan", "surname": "P", "phone": "05350000000", "city": "Tekirdağ", "address": "Çorlu merkez 1"}
    r = client.post("/api/payments/checkout", json={"plan_id": "ajans", "cycle": "yearly", "billing": billing}, headers=auth(token))
    assert r.status_code == 200, r.text
    assert str(sent["amount"]) == "345.6" and "yıllık" in sent["plan_name"]
    monkeypatch.setattr(pr.iyzico_service, "retrieve_checkout", lambda t, c: {"status": "success", "paymentStatus": "SUCCESS", "paidPrice": "345.60", "currency": "USD", "basketId": c, "paymentId": "y1"})
    monkeypatch.setattr(pr.iyzico_service, "is_successful_payment", lambda result, **kw: True)
    client.post("/api/payments/iyzico/callback", data={"token": "tok-y"}, follow_redirects=False)
    usage = client.get("/api/plans/usage", headers=auth(token)).json()
    assert usage["plan"] == "ajans" and usage["credits"]["total"] == 10800 and usage["cycle"] == "yearly"  # 12 aylık kredi tek seferde
    from datetime import datetime

    days = (datetime.fromisoformat(usage["plan_expires_at"].rstrip("Z")) - datetime.utcnow()).days
    assert 363 <= days <= 365


def test_image_revision_edits_previous_image(client, monkeypatch):
    content = _enable_media(monkeypatch)
    calls = []
    monkeypatch.setattr(content.media_planner, "plan_image",
                        lambda req, aspect, edit=False, ref_count=0, previous_prompt=None:
                        {"prompt": f"{'EDIT' if edit else 'NEW'}:{req}:{previous_prompt}", "note": "düzelttim"})
    monkeypatch.setattr(content.gateway_media, "generate_image",
                        lambda prompt, aspect, refs=None: calls.append((prompt, aspect, refs)) or (b"\x89PNG\r\n\x1a\nx", "image/png"))
    monkeypatch.setattr(content.storage, "save", lambda data, mime, prefix: BLOB_URL + "v.png")
    token = register_paid(client)
    r = client.post("/api/content/image", json={"concept": "kahve", "aspect_ratio": "ASPECT_4_5"}, headers=auth(token)).json()
    assert r["prompt"] == "NEW:kahve:None" and r["note"] == "düzelttim" and calls[0][1] == "4:5"
    r2 = client.post("/api/content/image", json={"concept": "yazıyı büyüt", "base_url": BLOB_URL + "v.png",
                                                  "previous_prompt": r["prompt"]}, headers=auth(token)).json()
    assert r2["prompt"].startswith("EDIT:yazıyı büyüt:NEW:kahve")
    assert calls[1][2] == [BLOB_URL + "v.png"]  # düzenlenecek görsel ilk referans
    bad = client.post("/api/content/image", json={"concept": "x", "base_url": "https://kotu.site/a.png"}, headers=auth(token))
    assert bad.status_code == 400


def test_video_revision_reuses_start_frame_and_prompt(client, monkeypatch):
    content = _enable_media(monkeypatch)
    token = register(client)
    _set_plan(_user_id(client, token), "pro")
    started = []
    monkeypatch.setattr(content.gateway_media, "start_video",
                        lambda p, d, r="720p", i=None, e=None, a=False, ar="9:16": started.append((p, i)) or {"model": "m", "operation": {"id": "op"}})
    seen = []
    monkeypatch.setattr(content.media_planner, "plan_video",
                        lambda req, aspect, duration, has_start_frame, audio, previous_prompt=None:
                        seen.append(previous_prompt) or {"prompt": f"P[{req}]", "frame_prompt": "", "note": ""})
    first = client.post("/api/content/video", json={"concept": "tatlı", "image_url": BLOB_URL + "f.png"}, headers=auth(token)).json()
    again = client.post("/api/content/video", json={"concept": "daha yavaş", "revise_of": first["job_id"]}, headers=auth(token)).json()
    assert again["job_id"] and seen == [None, "P[tatlı]"]
    assert started[1] == ("P[daha yavaş]", BLOB_URL + "f.png")  # aynı açılış karesi
    other = register(client, "z@example.com")
    _set_plan(_user_id(client, other), "pro")
    assert client.post("/api/content/video", json={"concept": "x", "revise_of": first["job_id"]}, headers=auth(other)).status_code == 404


def _fake_meta(monkeypatch):
    from app.routers import ads as ads_router
    from app.services import meta_ads_service as meta

    calls = []

    def fake_graph(method, path, tok, **data):
        calls.append((method, path, data))
        if path.endswith("/campaigns"):
            return {"id": "c1"}
        if path.endswith("/adsets"):
            return {"id": "s1"}
        if path.endswith("/adimages"):
            return {"images": {"x": {"hash": f"h{len(calls)}"}}}
        if path.endswith("/adcreatives"):
            return {"id": "cr1"}
        if path.endswith("/ads"):
            return {"id": "a1"}
        return {"data": []}

    monkeypatch.setattr(meta, "_graph", fake_graph)
    monkeypatch.setattr(ads_router.storage, "fetch", lambda url, max_bytes=0: b"jpg")
    return calls


def test_ad_from_existing_instagram_post_and_carousel(client, monkeypatch):
    token = _meta_ready(client, monkeypatch)
    calls = _fake_meta(monkeypatch)
    body = {**AD_BODY, "media": None, "primary_text": "", "placements": ["instagram_feed", "facebook_feed"],
            "source_post": {"platform": "instagram", "id": "17900", "thumbnail": "https://cdn/x.jpg"}}
    r = client.post("/api/ads/meta/ads", json=body, headers=auth(token))
    assert r.status_code == 200, r.text
    creative = next(d for m, p, d in calls if p.endswith("/adcreatives"))
    assert creative["source_instagram_media_id"] == "17900" and creative["instagram_user_id"] == "ig1"
    adset = next(d for m, p, d in calls if p.endswith("/adsets"))
    assert adset["targeting"]["publisher_platforms"] == ["instagram"]  # Instagram gönderisi yalnızca Instagram'da

    calls.clear()
    cards = [{"media": {"url": BLOB_URL + f"{i}.jpg", "kind": "image"}, "headline": f"Ürün {i}"} for i in range(3)]
    r = client.post("/api/ads/meta/ads", json={**AD_BODY, "media": None, "carousel": cards}, headers=auth(token))
    assert r.status_code == 200, r.text
    creative = next(d for m, p, d in calls if p.endswith("/adcreatives"))
    children = creative["object_story_spec"]["link_data"]["child_attachments"]
    assert len(children) == 3 and children[1]["name"] == "Ürün 1" and children[0]["image_hash"]

    # İçerik seçilmezse veya tek kartlık karusel reddedilir
    assert client.post("/api/ads/meta/ads", json={**AD_BODY, "media": None}, headers=auth(token)).status_code == 400
    assert client.post("/api/ads/meta/ads", json={**AD_BODY, "media": None, "carousel": cards[:1]}, headers=auth(token)).status_code == 400


def test_lifetime_budget_and_draft(client, monkeypatch):
    token = _meta_ready(client, monkeypatch)
    calls = _fake_meta(monkeypatch)
    r = client.post("/api/ads/meta/ads", json={**AD_BODY, "budget_type": "lifetime"}, headers=auth(token))
    assert r.status_code == 400  # toplam bütçe bitiş tarihi ister
    body = {**AD_BODY, "budget_type": "lifetime", "daily_budget": 3000, "start_date": "2030-01-01", "end_date": "2030-01-10", "publish": False}
    r = client.post("/api/ads/meta/ads", json=body, headers=auth(token))
    assert r.status_code == 200 and r.json()["status"] == "PAUSED"
    adset = next(d for m, p, d in calls if p.endswith("/adsets"))
    assert adset["lifetime_budget"] == 300000 and "daily_budget" not in adset
    assert not [d for m, p, d in calls if d.get("status") == "ACTIVE"]
