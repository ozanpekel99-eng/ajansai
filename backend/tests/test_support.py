import base64
import hashlib
import hmac
import json
import time

import pytest

from app import config
from app.services import support


SECRET = "whsec_" + base64.b64encode(b"test-secret-key-123").decode()


def _sign(body: bytes, ts=None, mid="msg_1"):
    ts = str(ts or int(time.time()))
    sig = base64.b64encode(hmac.new(b"test-secret-key-123", f"{mid}.{ts}.".encode() + body, hashlib.sha256).digest()).decode()
    return {"svix-id": mid, "svix-timestamp": ts, "svix-signature": f"v1,{sig}"}


def test_signature_ok_and_tampered():
    body = b'{"type":"email.received"}'
    h = _sign(body)
    assert support.verify_signature(h, body, SECRET)
    assert not support.verify_signature(h, body + b" ", SECRET)
    assert not support.verify_signature(_sign(body, ts=int(time.time()) - 3600), body, SECRET)


def test_strip_quoted_and_html():
    text = "Merhaba, kredim neden bitti?\n\n12 Eki 2026 tarihinde ajansAI şunu yazdı:\n> eski"
    assert support.strip_quoted(text) == "Merhaba, kredim neden bitti?"
    assert "Selam" in support.message_text({"html": "<p>Selam<br>nasılsın</p><style>x{}</style>"})
    data = "data:text/html;base64," + base64.b64encode("<b>Merhaba</b>".encode()).decode()
    assert support.message_text({"html": data}) == "Merhaba"


@pytest.mark.parametrize("email,reason", [
    ({"from": "noreply@x.com"}, "otomatik gönderici"),
    ({"from": "Ali <ali@x.com>", "headers": {"Auto-Submitted": "auto-replied"}}, "otomatik e-posta (Auto-Submitted)"),
    ({"from": "ali@x.com", "headers": {"List-Unsubscribe": "<mailto:u@x.com>"}}, "liste/otomatik yanıt e-postası"),
    ({"from": "support@ajansai.tr"}, "kendi alan adımızdan"),
    ({"from": "Ali <ali@x.com>"}, None),
])
def test_skip_reason(email, reason):
    assert support.skip_reason(email) == reason


def test_parse_reply():
    d = support.parse_reply('Tamam: {"reply": "Merhaba", "escalate": false, "spam": false, "reason": "sss"}')
    assert d["reply"] == "Merhaba" and not d["escalate"]
    assert support.parse_reply("bozuk")["escalate"]


def test_handle_inbound_flow(monkeypatch):
    sent = []
    monkeypatch.setattr(config, "SUPPORT_FORWARD_TO", "owner@gmail.com")
    monkeypatch.setattr(support, "fetch_email", lambda i: {
        "from": "Ayşe <ayse@firma.com>", "subject": "Kredi", "text": "Yıllık pakette krediler ne zaman yüklenir?",
        "message_id": "<abc@firma.com>", "headers": {},
    })
    monkeypatch.setattr(support, "draft_reply", lambda s, b, f: {"reply": "Merhaba Ayşe, tek seferde yüklenir.", "escalate": False, "spam": False, "reason": "sss"})
    monkeypatch.setattr(support, "send_email", lambda to, subject, text, reply_to=None, headers=None: sent.append((to, subject, reply_to, headers)) or {})
    out = support.handle_inbound("em_1")
    assert out["status"] == "replied"
    assert sent[0][0] == ["ayse@firma.com"] and sent[0][1] == "Re: Kredi" and sent[0][3]["In-Reply-To"] == "<abc@firma.com>"
    assert sent[1][0] == ["owner@gmail.com"] and sent[1][2] == "ayse@firma.com"
    assert support.handle_inbound("em_1")["status"] == "duplicate"
    assert len(sent) == 2


def test_inbound_endpoint_rejects_bad_signature(client, monkeypatch):
    monkeypatch.setattr(config, "RESEND_WEBHOOK_SECRET", SECRET)
    body = json.dumps({"type": "email.received", "data": {"email_id": "x"}}).encode()
    r = client.post("/api/support/inbound", content=body, headers={"svix-id": "a", "svix-timestamp": "1", "svix-signature": "v1,zz"})
    assert r.status_code == 401


def test_platform_emails_are_not_auto_replied():
    from app.services import support

    assert support.skip_reason({"from": "Meta <security@facebookmail.com>"}) == "platform bildirimi"
    assert support.skip_reason({"from": "x@business.facebook.com"}) == "platform bildirimi"


def test_send_email_merges_headers(monkeypatch):
    """Idempotency-Key başlığı Authorization ile birleşmeli (önceden TypeError veriyordu)."""
    seen = {}

    class R:
        status_code = 200
        content = b'{"id":"x"}'

        def json(self):
            return {"id": "x"}

    def fake_request(method, url, headers=None, timeout=None, **kw):
        seen.update(headers=headers, json=kw.get("json"))
        return R()

    monkeypatch.setattr(support.config, "RESEND_API_KEY", "re_test")
    monkeypatch.setattr(support.requests, "request", fake_request)
    assert support.send_email(["a@b.com"], "Konu", "Merhaba", headers={"In-Reply-To": "<m>"}) == {"id": "x"}
    assert seen["headers"]["Authorization"] == "Bearer re_test"
    assert "Idempotency-Key" in seen["headers"]
    assert seen["json"]["headers"] == {"In-Reply-To": "<m>"}
