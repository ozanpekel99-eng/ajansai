"""Sohbetten video üretimi ve görsel oranı."""

from app.services import assistant, free_tier, gateway_media

from .conftest import auth, register
from .test_api import _enable_media, register_paid


def test_split_video_request_and_image_aspect():
    text, req = free_tier.split_video_request("Hazırlıyorum.\n[[VIDEO: 16:9 | 10 | a drone shot over a beach at sunset]]")
    assert text == "Hazırlıyorum." and req == {"aspect": "16:9", "duration": 10, "prompt": "a drone shot over a beach at sunset"}
    assert free_tier.split_video_request("[[VIDEO: coffee pouring]]")[1] == {"aspect": "9:16", "duration": 5, "prompt": "coffee pouring"}
    assert free_tier.image_aspect("9:16 | a latte on a table") == ("9:16", "a latte on a table")
    assert free_tier.image_aspect("a latte") == ("1:1", "a latte")


def test_paid_chat_starts_video_job(client, monkeypatch):
    _enable_media(monkeypatch)
    monkeypatch.setattr(assistant, "chat_completion", lambda model, messages, max_tokens=0: "Videon geliyor.\n[[VIDEO: 9:16 | 5 | iced coffee pouring, slow motion]]")
    started = {}

    def fake_start(prompt, duration, resolution, image_url, end_image_url, audio, aspect):
        started.update(prompt=prompt, duration=duration, resolution=resolution, audio=audio, aspect=aspect)
        return {"model": "bytedance/seedance-v1.5-pro", "operation": {"id": "op1"}}

    monkeypatch.setattr(gateway_media, "start_video", fake_start)
    token = register_paid(client, plan="pro")
    r = client.post("/api/content/chat", json={"messages": [{"role": "user", "content": "Buzlu kahve videosu yap"}]}, headers=auth(token))
    data = r.json()
    assert r.status_code == 200, r.text
    assert data["reply"] == "Videon geliyor." and len(data["videos"]) == 1 and data["videos"][0]["job_id"]
    assert started == {"prompt": "iced coffee pouring, slow motion", "duration": 5, "resolution": "720p", "audio": True, "aspect": "9:16"}
    assert data["credits_spent"] == 1 + 24


def test_video_mode_requires_video_plan(client, monkeypatch):
    _enable_media(monkeypatch)
    token = register(client)  # ücretsiz paket
    r = client.post("/api/content/chat", json={"mode": "video", "messages": [{"role": "user", "content": "video"}]}, headers=auth(token))
    assert r.status_code == 402 and "Video" in r.json()["detail"]
