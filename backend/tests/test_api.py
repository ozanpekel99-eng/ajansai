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


def test_ideas_503_and_refund_when_no_ai(client):
    token = register(client)
    r = client.post("/api/content/ideas", json=IDEA_BODY, headers=auth(token))
    assert r.status_code == 503
    assert client.get("/api/plans/usage", headers=auth(token)).json()["ideas"]["used"] == 0


def test_trial_idea_quota(client, monkeypatch):
    monkeypatch.setattr(llm_service, "complete", lambda *a, **k: (json.dumps(IDEAS_JSON), "test"))
    from app.services import claude_service

    monkeypatch.setattr(claude_service, "complete", lambda *a, **k: (json.dumps(IDEAS_JSON), "test"))
    token = register(client)
    for _ in range(10):
        assert client.post("/api/content/ideas", json=IDEA_BODY, headers=auth(token)).status_code == 200
    r = client.post("/api/content/ideas", json=IDEA_BODY, headers=auth(token))
    assert r.status_code == 402


def test_unparseable_ai_answer_refunds(client, monkeypatch):
    from app.services import claude_service

    monkeypatch.setattr(claude_service, "complete", lambda *a, **k: ("üzgünüm, yapamam", "test"))
    token = register(client)
    r = client.post("/api/content/ideas", json=IDEA_BODY, headers=auth(token))
    assert r.json()["error"]
    assert client.get("/api/plans/usage", headers=auth(token)).json()["ideas"]["used"] == 0


# ---------------- Kota ----------------

def _set_plan(user_id, plan):
    with get_engine().begin() as conn:
        conn.execute(
            update(users).where(users.c.id == user_id).values(plan=plan, plan_expires_at=utcnow() + timedelta(days=30))
        )


def test_trial_cannot_make_images(client):
    token = register(client)
    r = client.post("/api/content/image", json={"concept": "kahve"}, headers=auth(token))
    assert r.status_code == 402
    assert "paketinde bulunmuyor" in r.json()["detail"]


def test_image_failure_refunds_quota(client):
    token = register(client)
    _set_plan(_user_id(client, token), "baslangic")
    # IDEOGRAM_API_KEY yok -> üretim başarısız -> kota iade
    r = client.post("/api/content/image", json={"concept": "kahve"}, headers=auth(token))
    assert r.status_code == 200 and r.json()["image_url"] is None
    assert client.get("/api/plans/usage", headers=auth(token)).json()["image"]["used"] == 0


def test_video_quota_and_failed_job_refund(client, monkeypatch):
    from app.routers import content

    token = register(client)
    uid = _user_id(client, token)
    _set_plan(uid, "baslangic")

    counter = {"n": 0}

    def fake_start(**kw):
        counter["n"] += 1
        return {"job_id": f"job-{counter['n']}", "error": None}

    monkeypatch.setattr(content, "start_video_generation", fake_start)
    monkeypatch.setattr(content, "get_video_status", lambda job_id: {"status": "FAILED", "video_url": None})

    for _ in range(10):
        assert client.post("/api/content/video", json={"concept": "x"}, headers=auth(token)).status_code == 200
    assert client.post("/api/content/video", json={"concept": "x"}, headers=auth(token)).status_code == 402

    # Başarısız job iki kez sorgulansa da kota yalnızca bir kez iade edilir
    client.get("/api/content/video/job-1", headers=auth(token))
    client.get("/api/content/video/job-1", headers=auth(token))
    assert client.get("/api/plans/usage", headers=auth(token)).json()["video"]["used"] == 9


def test_cannot_read_other_users_video(client, monkeypatch):
    from app.routers import content

    owner = register(client, "a@example.com")
    _set_plan(_user_id(client, owner), "baslangic")
    monkeypatch.setattr(content, "start_video_generation", lambda **kw: {"job_id": "job-x", "error": None})
    monkeypatch.setattr(content, "get_video_status", lambda job_id: {"status": "FAILED"})
    client.post("/api/content/video", json={"concept": "x"}, headers=auth(owner))

    other = register(client, "b@example.com")
    assert client.get("/api/content/video/job-x", headers=auth(other)).status_code == 404
    # Başkası sorgulayamadığı için sahibin kotası iade edilmemiş olmalı
    assert client.get("/api/plans/usage", headers=auth(owner)).json()["video"]["used"] == 1


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


def test_health(client):
    h = client.get("/health").json()
    assert h["status"] == "ok"
