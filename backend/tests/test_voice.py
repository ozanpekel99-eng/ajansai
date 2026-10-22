import base64

from app import config
from app.services import tts

from .conftest import auth
from .test_api import FakeResponse, register_paid


def test_speak_disabled_without_key(client):
    assert client.post("/api/voice/speak", json={"text": "Merhaba"}).status_code == 503
    assert client.get("/api/voice/status").json() == {"natural_voice": False, "streaming": False}


def test_speak_returns_mp3_and_respects_daily_caps(client, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_TTS_API_KEY", "k")
    monkeypatch.setattr(config, "TTS_DAILY_CHARS", 20)
    monkeypatch.setattr(config, "TTS_CHARS_PER_DAY_SUBJECT", 15)
    sent = {}

    def fake_post(url, params=None, json=None, timeout=None, headers=None):
        sent.update(url=url, params=params, json=json)
        return FakeResponse(200, {"audioContent": base64.b64encode(b"ID3mp3").decode()})

    monkeypatch.setattr(tts.requests, "post", fake_post)
    ip = {"x-forwarded-for": "1.2.3.4"}
    r = client.post("/api/voice/speak", json={"text": "Merhaba dünya"}, headers=ip)  # 13 karakter
    assert r.status_code == 200 and r.content == b"ID3mp3" and r.headers["content-type"] == "audio/mpeg"
    assert sent["json"]["voice"] == {"languageCode": "tr-TR", "name": "tr-TR-Chirp3-HD-Achernar"}
    assert sent["params"] == {"key": "k"}
    # Kişisel tavan (15) aşılır
    assert client.post("/api/voice/speak", json={"text": "Selam"}, headers=ip).status_code == 503
    # Başka kişi: site tavanı (20) aşılır
    assert client.post("/api/voice/speak", json={"text": "Merhaba dünya"}, headers={"x-forwarded-for": "5.6.7.8"}).status_code == 503
    # Kısa metin sığar
    assert client.post("/api/voice/speak", json={"text": "Evet"}, headers={"x-forwarded-for": "5.6.7.8"}).status_code == 200


def test_speak_failure_does_not_consume_quota(client, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_TTS_API_KEY", "k")
    monkeypatch.setattr(config, "TTS_DAILY_CHARS", 10)
    monkeypatch.setattr(tts.requests, "post", lambda *a, **k: FakeResponse(500, {}))
    assert client.post("/api/voice/speak", json={"text": "Merhaba"}).status_code == 503
    monkeypatch.setattr(tts.requests, "post", lambda *a, **k: FakeResponse(200, {"audioContent": base64.b64encode(b"x").decode()}))
    assert client.post("/api/voice/speak", json={"text": "Merhaba"}).status_code == 200


def test_gemini_voice_preferred_and_pcm_wrapped_as_wav(client, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "gk")
    monkeypatch.setattr(config, "GOOGLE_TTS_API_KEY", "k")
    pcm = b"\x01\x00" * 400
    calls = []

    def fake_post(url, headers=None, json=None, params=None, timeout=None):
        calls.append(url)
        if url.endswith("/interactions"):
            return FakeResponse(404, {})
        return FakeResponse(200, {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/L16;codec=pcm;rate=24000", "data": base64.b64encode(pcm).decode()}}]}}]})

    monkeypatch.setattr(tts.requests, "post", fake_post)
    r = client.post("/api/voice/speak", json={"text": "Merhaba"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    assert r.content[:4] == b"RIFF" and r.content.endswith(pcm)
    assert calls[1].endswith(":generateContent") and "texttospeech" not in "".join(calls)



class _Stream:
    status_code = 200
    text = ""

    def __init__(self, chunks):
        self.chunks = chunks

    def iter_lines(self, decode_unicode=False):
        import json

        for c in self.chunks:
            yield "data: " + json.dumps({"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/L16;rate=24000", "data": base64.b64encode(c).decode()}}]}}]})
            yield ""


def test_stream_returns_pcm_and_paid_users_pay_per_1000_chars(client, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "gk")
    a, b = b"\x01\x00" * 300, b"\x02\x00" * 300
    monkeypatch.setattr(tts.requests, "post", lambda *x, **k: _Stream([a, b]))
    r = client.post("/api/voice/stream", json={"text": "Merhaba"})  # misafir: kredisiz
    assert r.status_code == 200 and r.content == a + b and r.headers["content-type"].startswith("audio/L16")

    token = register_paid(client, plan="pro")
    used = lambda: client.get("/api/plans/usage", headers=auth(token)).json()["credits"]["used"]
    for _ in range(3):  # 3 x 400 = 1200 karakter → 2 kredi (500 karakter = 1 kredi)
        assert client.post("/api/voice/stream", json={"text": "a" * 400}, headers=auth(token)).status_code == 200
    assert used() == 2


def test_stream_failure_refunds(client, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "gk")
    monkeypatch.setattr(config, "TTS_CHARS_PER_CREDIT", 10)
    monkeypatch.setattr(tts.requests, "post", lambda *x, **k: FakeResponse(429, {}))
    token = register_paid(client, plan="pro")
    assert client.post("/api/voice/stream", json={"text": "a" * 50}, headers=auth(token)).status_code == 503
    assert client.get("/api/plans/usage", headers=auth(token)).json()["credits"]["used"] == 0


def test_stream_prefers_vercel_gateway(client, monkeypatch):
    from app.services import llm_service

    monkeypatch.setattr(llm_service, "gateway_ready", lambda: True)
    monkeypatch.setattr(config, "AI_GATEWAY_API_KEY", "vk")
    pcm = b"\x05\x00" * 2400
    sent = {}

    def fake_post(url, headers=None, json=None, timeout=None, **k):
        sent.update(url=url, headers=headers, json=json)
        return FakeResponse(200, {"audio": base64.b64encode(pcm).decode()})

    monkeypatch.setattr(tts.requests, "post", fake_post)
    r = client.post("/api/voice/stream", json={"text": "Merhaba"})
    assert r.status_code == 200 and r.content == pcm
    assert sent["url"].endswith("/v4/ai/speech-model") and sent["headers"]["ai-model-id"] == "google/gemini-3.8-flash-tts"
    assert sent["headers"]["ai-speech-model-specification-version"] == "4"
    assert sent["json"]["outputFormat"] == "pcm" and sent["json"]["voice"] == "Sulafat"
    assert llm_service.spent_today() > 0
