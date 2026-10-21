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
    token = register(client)
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

    token = register(client)
    r = client.post("/api/content/ideas", json=IDEA_BODY, headers=auth(token))
    assert r.status_code == 200
    assert r.json()["provider"] == "anthropic"


def _credits(client, token):
    return client.get("/api/plans/usage", headers=auth(token)).json()["credits"]


def test_ideas_503_and_refund_when_no_ai(client):
    token = register(client)
    r = client.post("/api/content/ideas", json=IDEA_BODY, headers=auth(token))
    assert r.status_code == 503
    assert _credits(client, token)["used"] == 0


def _fake_ideas(monkeypatch):
    from app.services import claude_service

    monkeypatch.setattr(claude_service, "complete", lambda *a, **k: (json.dumps(IDEAS_JSON), "test"))


def test_idea_cost_is_one_credit_per_two_ideas(client, monkeypatch):
    _fake_ideas(monkeypatch)
    token = register(client)
    r = client.post("/api/content/ideas", json={**IDEA_BODY, "idea_count": 6}, headers=auth(token))
    assert r.status_code == 200 and r.json()["credits_spent"] == 3
    r = client.post("/api/content/ideas", json={**IDEA_BODY, "idea_count": 1}, headers=auth(token))
    assert r.json()["credits_spent"] == 1
    c = _credits(client, token)
    assert c == {"total": 20, "used": 4, "remaining": 16}
    events = client.get("/api/plans/history", headers=auth(token)).json()["events"]
    assert [e["credits"] for e in events] == [1, 3] and events[0]["label"] == "İçerik fikri"


def test_trial_credits_run_out(client, monkeypatch):
    _fake_ideas(monkeypatch)
    token = register(client)
    for _ in range(10):  # 10 x 2 kredi = 20
        assert client.post("/api/content/ideas", json=IDEA_BODY, headers=auth(token)).status_code == 200
    r = client.post("/api/content/ideas", json=IDEA_BODY, headers=auth(token))
    assert r.status_code == 402 and "Kredin yetmiyor" in r.json()["detail"]


def test_unparseable_ai_answer_refunds(client, monkeypatch):
    from app.services import claude_service

    monkeypatch.setattr(claude_service, "complete", lambda *a, **k: ("üzgünüm, yapamam", "test"))
    token = register(client)
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


def _enable_media(monkeypatch):
    from app.routers import content

    config.AI_GATEWAY_ENABLED = True
    return content


def test_trial_can_make_images_and_pays_four_credits(client, monkeypatch):
    content = _enable_media(monkeypatch)
    calls = {}

    def fake_image(prompt, aspect):
        calls["aspect"] = aspect
        return b"\x89PNG\r\n\x1a\nveri", "image/png"

    monkeypatch.setattr(content.gateway_media, "generate_image", fake_image)
    token = register(client)
    r = client.post("/api/content/image", json={"concept": "kahve", "aspect_ratio": "ASPECT_9_16"}, headers=auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["image_url"].startswith("data:image/png;base64,")
    assert r.json()["credits_spent"] == 4 and calls["aspect"] == "9:16"
    assert _credits(client, token)["used"] == 4


def test_image_saved_to_blob_when_configured(client, monkeypatch):
    content = _enable_media(monkeypatch)
    monkeypatch.setattr(content.gateway_media, "generate_image", lambda p, a: (b"\xff\xd8\xffjpg", "image/jpeg"))
    config.BLOB_READ_WRITE_TOKEN = "vercel_blob_rw_store_x"
    sent = {}

    def fake_put(url, params=None, data=None, headers=None, timeout=None):
        sent.update(url=url, params=params, headers=headers)
        return FakeResponse(200, {"url": "https://store.public.blob.vercel-storage.com/" + params["pathname"]})

    from app.services import storage

    monkeypatch.setattr(storage.requests, "put", fake_put)
    try:
        token = register(client)
        r = client.post("/api/content/image", json={"concept": "kahve"}, headers=auth(token))
    finally:
        config.BLOB_READ_WRITE_TOKEN = None
    assert r.json()["image_url"].startswith("https://store.public.blob.vercel-storage.com/gorsel/")
    assert sent["params"]["pathname"].endswith(".jpg")
    assert sent["headers"]["x-vercel-blob-access"] == "public"


def test_image_failure_refunds_credits(client, monkeypatch):
    content = _enable_media(monkeypatch)

    def broken(prompt, aspect):
        raise content.gateway_media.MediaError("kapalı")

    monkeypatch.setattr(content.gateway_media, "generate_image", broken)
    token = register(client)
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
    monkeypatch.setattr(content.gateway_media, "start_video", lambda p, d, i=None: started.append((d, i)) or {"id": "op"})
    monkeypatch.setattr(content.gateway_media, "video_status", lambda op: {"status": "error", "error": "model hatası"})

    r5 = client.post("/api/content/video", json={"concept": "x"}, headers=auth(token)).json()
    r10 = client.post(
        "/api/content/video",
        json={"concept": "x", "duration": 10, "image_url": "https://blob.example/a.png"},
        headers=auth(token),
    ).json()
    assert (r5["credits_spent"], r10["credits_spent"]) == (12, 24)
    assert started == [(5, None), (10, "https://blob.example/a.png")]
    assert _credits(client, token)["used"] == 36

    # Başarısız iş iki kez sorgulansa da kredi bir kez iade edilir
    for _ in range(2):
        st = client.get(f"/api/content/video/{r5['job_id']}", headers=auth(token)).json()
        assert st["status"] == "FAILED"
    assert _credits(client, token)["used"] == 24


def test_video_completes_and_is_cached(client, monkeypatch):
    content = _enable_media(monkeypatch)
    token = register(client)
    _set_plan(_user_id(client, token), "pro")
    monkeypatch.setattr(content.gateway_media, "start_video", lambda p, d, i=None: {"id": "op"})
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
    monkeypatch.setattr(content.gateway_media, "start_video", lambda p, d, i=None: {"id": "op"})
    monkeypatch.setattr(content.gateway_media, "video_status", lambda op: {"status": "error"})
    job = client.post("/api/content/video", json={"concept": "x"}, headers=auth(owner)).json()["job_id"]

    other = register(client, "b@example.com")
    assert client.get(f"/api/content/video/{job}", headers=auth(other)).status_code == 404
    # Başkası sorgulayamadığı için sahibin kredisi iade edilmemiş olmalı
    assert _credits(client, owner)["used"] == 12


def test_plans_endpoint_shows_credit_examples(client):
    data = client.get("/api/plans/").json()
    assert data["costs"]["image"] == 4 and data["costs"]["video_5"] == 12
    pro = data["plans"]["pro"]
    assert pro["credits"] == 800 and pro["examples"]["images"] == 200 and pro["examples"]["videos_5"] == 66
    assert data["trial"]["examples"]["videos_5"] == 0


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

    op = gateway_media.start_video("dalga", 5, "https://x/a.png")
    assert op == {"gatewayJobId": "job_1"} and sent["url"].endswith("/video-model/start")
    assert sent["body"]["image"] == {"type": "url", "url": "https://x/a.png"}
    assert sent["body"]["aspectRatio"] == "9:16" and sent["body"]["duration"] == 5


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
        monkeypatch, {"status": "success", "paymentStatus": "SUCCESS", "paidPrice": "1249.00", "currency": "TRY", "paymentId": "p1"}
    )
    token = register(client)

    r = client.post("/api/payments/checkout", json={"plan_id": "pro", "billing": BILLING}, headers=auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["payment_page_url"].endswith("tok-1")
    init_payload = sent[0][1]
    assert init_payload["price"] == "1249.00" and init_payload["paidPrice"] == "1249.00"
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
        {"status": "success", "paymentStatus": "FAILURE", "paidPrice": "1249.00"},
        {"status": "failure", "errorMessage": "Kart reddedildi"},
        {"status": "success", "paymentStatus": "SUCCESS", "paidPrice": "1.00"},  # eksik tutar
        {"status": "success", "paymentStatus": "SUCCESS", "paidPrice": "1249.00", "basketId": "baska-sepet"},
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
    assert items[0]["plan_name"] == "Pro" and items[0]["amount_try"] == 1249 and items[0]["status"] == "pending"


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
    token = register(client)
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
    token = register(client)
    r = client.post("/api/content/ideas", json=IDEA_BODY, headers=auth(token))
    assert r.json()["provider"] == "ai_gateway"
