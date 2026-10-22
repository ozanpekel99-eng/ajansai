import base64

from app import config
from app.services import tts

from .test_api import FakeResponse


def test_speak_disabled_without_key(client):
    assert client.post("/api/voice/speak", json={"text": "Merhaba"}).status_code == 503
    assert client.get("/api/voice/status").json() == {"natural_voice": False}


def test_speak_returns_mp3_and_respects_daily_caps(client, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_TTS_API_KEY", "k")
    monkeypatch.setattr(config, "TTS_DAILY_CHARS", 20)
    monkeypatch.setattr(config, "TTS_CHARS_PER_DAY_SUBJECT", 15)
    sent = {}

    def fake_post(url, params=None, json=None, timeout=None):
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
