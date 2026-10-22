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
    assert c == {"total": 200, "used": 4, "remaining": 196}
    events = client.get("/api/plans/history", headers=auth(token)).json()["events"]
    assert [e["credits"] for e in events] == [1, 3] and events[0]["label"] == "İçerik fikri"


def test_free_plan_has_no_credits(client, monkeypatch):
    _fake_ideas(monkeypatch)
    token = register(client)
    assert _credits(client, token) == {"total": 0, "used": 0, "remaining": 0}
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
            "duration": 7,
            "resolution": "1080p",
            "image_url": BLOB_URL + "a.png",
            "end_image_url": BLOB_URL + "b.png",
            "aspect_ratio": "16:9",
        },
        headers=auth(token),
    ).json()
    assert (r5["credits_spent"], r10["credits_spent"]) == (12, 37)
    assert started == [(5, "720p", None, None, False, "9:16"), (7, "1080p", BLOB_URL + "a.png", BLOB_URL + "b.png", False, "16:9")]
    assert _credits(client, token)["used"] == 49
    # Desteklenmeyen süre/çözünürlük reddedilir
    assert client.post("/api/content/video", json={"concept": "x", "duration": 6}, headers=auth(token)).status_code == 422
    assert client.post("/api/content/video", json={"concept": "x", "resolution": "8k"}, headers=auth(token)).status_code == 422
    # 4K, Başlangıç paketinin 200 kredisine sığmaz
    r4k = client.post("/api/content/video", json={"concept": "x", "resolution": "4k"}, headers=auth(token))
    assert r4k.status_code == 402 and "355 kredi" in r4k.json()["detail"]

    # Başarısız iş iki kez sorgulansa da kredi bir kez iade edilir
    for _ in range(2):
        st = client.get(f"/api/content/video/{r5['job_id']}", headers=auth(token)).json()
        assert st["status"] == "FAILED"
    assert _credits(client, token)["used"] == 37


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
    assert r.json()["credits_spent"] == 53
    bad = client.post("/api/content/video", json={"concept": "x", "image_url": "https://kotu.site/a.png"}, headers=auth(token))
    assert bad.status_code == 400
    assert _credits(client, token)["used"] == 53


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
    token = register(client)
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
    assert r.json() == {"reply": "Harika bir video!", "model": config.CHAT_VIDEO_MODEL, "credits_spent": 3}
    last = sent["messages"][-1]["content"]
    assert last[1]["type"] == "file" and last[1]["file"]["file_data"].startswith("data:video/mp4;base64,")
    assert last[2]["file"]["filename"] == "katalog.pdf"
    assert sent["messages"][0]["role"] == "system"
    events = client.get("/api/plans/history", headers=auth(token)).json()["events"]
    assert events[0]["label"] == "Fikir sohbeti" and events[0]["credits"] == 3


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
    assert data["costs"]["video"]["720p"] == {"5": 12, "7": 17, "10": 24}
    assert data["costs"]["video"]["4k"]["10"] == 710
    pro = data["plans"]["pro"]
    assert pro["credits"] == 530 and pro["examples"]["images"] == 132
    assert pro["examples"]["videos"] == {"720p": 44, "1080p": 19, "4k": 1}
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
    data, mime = gateway_media.generate_image("kahve", "1:1")
    assert mime == "image/jpeg" and sent["url"].endswith("/v4/ai/image-model")
    assert sent["headers"]["ai-model-id"] == config.IMAGE_MODEL
    assert sent["headers"]["ai-image-model-specification-version"] == "4"
    assert sent["headers"]["Authorization"] == "Bearer gw-key"

    job = gateway_media.start_video("dalga", 7, "4k", "https://x/a.png")
    assert job == {"model": "bytedance/seedance-2.0", "operation": {"gatewayJobId": "job_1"}}
    assert sent["url"].endswith("/video-model/start") and sent["headers"]["ai-model-id"] == "bytedance/seedance-2.0"
    assert sent["body"]["image"] == {"type": "url", "url": "https://x/a.png"}
    assert sent["body"]["aspectRatio"] == "9:16" and sent["body"]["duration"] == 7
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
        monkeypatch, {"status": "success", "paymentStatus": "SUCCESS", "paidPrice": "25.00", "currency": "USD", "paymentId": "p1"}
    )
    token = register(client)

    r = client.post("/api/payments/checkout", json={"plan_id": "pro", "billing": BILLING}, headers=auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["payment_page_url"].endswith("tok-1")
    init_payload = sent[0][1]
    assert init_payload["price"] == "25.00" and init_payload["paidPrice"] == "25.00"
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
        {"status": "success", "paymentStatus": "FAILURE", "paidPrice": "25.00", "currency": "USD"},
        {"status": "failure", "errorMessage": "Kart reddedildi"},
        {"status": "success", "paymentStatus": "SUCCESS", "paidPrice": "1.00", "currency": "USD"},  # eksik tutar
        {"status": "success", "paymentStatus": "SUCCESS", "paidPrice": "25.00", "currency": "TRY"},  # yanlış para birimi
        {"status": "success", "paymentStatus": "SUCCESS", "paidPrice": "25.00", "currency": "USD", "basketId": "baska-sepet"},
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
    assert items[0]["plan_name"] == "Pro" and items[0]["amount"] == 25 and items[0]["currency"] == "USD"
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
    assert r.json()["campaign_id"] == "c1" and r.json()["status"] == "PAUSED"

    adset = next(d for m, p, d in calls if p.endswith("/adsets"))
    t = adset["targeting"]
    assert t["publisher_platforms"] == ["instagram"]
    assert set(t["instagram_positions"]) == {"stream", "story", "reels", "explore"}
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
