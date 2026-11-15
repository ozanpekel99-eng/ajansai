import hashlib
import hmac
import json

import pytest

from app import config
from app.services import instagram_dm
from tests.conftest import auth, register

SECRET = "test-app-secret"
IG = "17841400000000001"
USER = "990000000000123"


def _sig(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _event(*messaging, account=IG) -> dict:
    return {"object": "instagram", "entry": [{"id": account, "time": 1761300000, "messaging": list(messaging)}]}


def _msg(mid, text="Merhaba", sender=USER, recipient=IG, ts=1761300000000, **extra):
    return {"sender": {"id": sender}, "recipient": {"id": recipient}, "timestamp": ts,
            "message": {"mid": mid, "text": text, **extra}}


@pytest.fixture
def meta(monkeypatch):
    monkeypatch.setattr(config, "META_APP_SECRET", SECRET)
    monkeypatch.setattr(config, "META_WEBHOOK_VERIFY_TOKEN", "dogrula-123")
    monkeypatch.setattr(config, "ADMIN_EMAILS", {"admin@example.com"})


def _post(client, event, secret=SECRET):
    body = json.dumps(event).encode()
    return client.post("/api/meta/webhook", content=body,
                       headers={"Content-Type": "application/json", "X-Hub-Signature-256": _sig(body, secret)})


def test_subscription_verify(client, meta):
    q = {"hub.mode": "subscribe", "hub.verify_token": "dogrula-123", "hub.challenge": "112233"}
    r = client.get("/api/meta/webhook", params=q)
    assert r.status_code == 200 and r.text == "112233"
    assert client.get("/api/meta/webhook", params={**q, "hub.verify_token": "yanlis"}).status_code == 403
    assert client.get("/api/meta/webhook", params={**q, "hub.mode": "unsubscribe"}).status_code == 403


def test_subscription_verify_without_token_configured(client, monkeypatch):
    monkeypatch.setattr(config, "META_WEBHOOK_VERIFY_TOKEN", None)
    q = {"hub.mode": "subscribe", "hub.verify_token": "", "hub.challenge": "1"}
    assert client.get("/api/meta/webhook", params=q).status_code == 403


def test_signature():
    body = b'{"object":"instagram"}'
    assert instagram_dm.verify_signature(body, _sig(body), SECRET)
    assert not instagram_dm.verify_signature(body + b" ", _sig(body), SECRET)
    assert not instagram_dm.verify_signature(body, _sig(body, "baska"), SECRET)
    assert not instagram_dm.verify_signature(body, None, SECRET)
    assert not instagram_dm.verify_signature(body, _sig(body), "")


def test_webhook_rejects_bad_signature(client, meta):
    assert _post(client, _event(_msg("m1")), secret="yanlis").status_code == 401
    r = client.post("/api/meta/webhook", content=b"{}", headers={"Content-Type": "application/json"})
    assert r.status_code == 401


def test_parse_event_filters():
    event = _event(
        _msg("m1", "Fiyatlar ne kadar?"),
        _msg("m2", "Merhaba! Paketlerimiz...", sender=IG, recipient=USER, is_echo=True),
        _msg("m3", "", attachments=[{"type": "image", "payload": {"url": "https://cdn.example/a.jpg"}}]),
        _msg("m4", "silindi", is_deleted=True),
        {"sender": {"id": USER}, "recipient": {"id": IG}, "timestamp": 1, "read": {"mid": "m1"}},
        {"sender": {"id": USER}, "recipient": {"id": IG}, "timestamp": 1, "reaction": {"mid": "m1", "action": "react"}},
    )
    msgs = instagram_dm.parse_event(event)
    assert [m["id"] for m in msgs] == ["m1", "m2", "m3"]
    assert msgs[0]["direction"] == "in" and msgs[0]["thread"] == USER
    assert msgs[1]["direction"] == "out" and msgs[1]["thread"] == USER  # yankı: konuşma müşteriye göre
    assert msgs[2]["attachments"] == [{"type": "image", "url": "https://cdn.example/a.jpg"}]
    assert instagram_dm.parse_event({"object": "page", "entry": [{"messaging": [_msg("x")]}]}) == []
    assert instagram_dm.parse_event({"object": "instagram", "entry": None}) == []


def test_webhook_saves_and_dedupes(client, meta):
    ev = _event(_msg("m1", "Ücretsiz paket var mı?", ts=1761300000000))
    r = _post(client, ev)
    assert r.status_code == 200 and r.json() == {"ok": True, "saved": 1, "duplicates": 0}
    r = _post(client, ev)  # Meta aynı olayı tekrar gönderebilir
    assert r.json() == {"ok": True, "saved": 0, "duplicates": 1}


def test_admin_conversations(client, meta):
    _post(client, _event(_msg("a1", "İlk soru", ts=1761300000000)))
    _post(client, _event(_msg("a2", "Cevap", sender=IG, recipient=USER, ts=1761300060000, is_echo=True)))
    _post(client, _event(_msg("b1", "Başka müşteri", sender="555", ts=1761300120000)))

    user = register(client, "musteri@example.com")
    assert client.get("/api/admin/instagram/dm", headers=auth(user)).status_code == 403

    admin = register(client, "admin@example.com")
    r = client.get("/api/admin/instagram/dm", headers=auth(admin))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["receiving"] is True and data["auto_reply"] is False
    convs = data["conversations"]
    assert [c["thread"] for c in convs] == ["555", USER]
    assert convs[0]["awaiting_reply"] is True and convs[0]["messages"] == 1
    assert convs[1]["awaiting_reply"] is False and convs[1]["last"]["text"] == "Cevap"

    r = client.get(f"/api/admin/instagram/dm/{USER}", headers=auth(admin)).json()
    assert [(m["direction"], m["text"], m["status"]) for m in r["messages"]] == [
        ("in", "İlk soru", "received"), ("out", "Cevap", "sent")]


def test_auto_reply_off_by_default():
    assert config.INSTAGRAM_DM_AUTO_REPLY is False
