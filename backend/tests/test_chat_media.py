"""Sohbetten video üretimi ve görsel oranı."""

from app.services import assistant, free_tier, gateway_media

from .conftest import auth, register
from .test_api import _enable_media, register_paid


def test_split_video_request_and_image_aspect():
    text, req = free_tier.split_video_request("Hazırlıyorum.\n[[VIDEO: 16:9 | 10 | a drone shot over a beach at sunset]]")
    assert text == "Hazırlıyorum." and req == {"aspect": "16:9", "duration": 10, "prompt": "a drone shot over a beach at sunset", "ref": None}
    assert free_tier.split_video_request("[[VIDEO: coffee pouring]]")[1] == {"aspect": "9:16", "duration": 5, "prompt": "coffee pouring", "ref": None}
    assert free_tier.split_video_request("[[VIDEO: 9:16 | 5 | ref=görsel-2 | milk pours]]")[1]["ref"] == "görsel-2"
    assert free_tier.image_aspect("9:16 | a latte on a table") == ("9:16", "a latte on a table")
    assert free_tier.image_aspect("a latte") == ("1:1", "a latte")


def test_paid_chat_suggests_video_page_instead_of_generating(client, monkeypatch):
    _enable_media(monkeypatch)
    monkeypatch.setattr(assistant, "chat_completion", lambda model, messages, max_tokens=0: "Video sayfasında oluşturabilirsin.\n[[VIDEO: 9:16 | 5 | iced coffee pouring, slow motion]]")
    monkeypatch.setattr(gateway_media, "start_video", lambda *a, **k: (_ for _ in ()).throw(AssertionError("sohbette video başlamamalı")))
    token = register_paid(client, plan="pro")
    r = client.post("/api/content/chat", json={"messages": [{"role": "user", "content": "Buzlu kahve videosu yap"}]}, headers=auth(token))
    data = r.json()
    assert r.status_code == 200, r.text
    assert data["reply"] == "Video sayfasında oluşturabilirsin." and data["credits_spent"] == 1
    assert data["video"] == {"concept": "iced coffee pouring, slow motion", "aspect": "9:16", "duration": 5, "image_url": None, "enabled": True}


def test_paid_chat_remembers_generated_image_for_video(client, monkeypatch):
    from app.services import storage
    from .test_api import BLOB_URL

    _enable_media(monkeypatch)
    seen = {}

    def fake_chat(model, messages, max_tokens=0):
        seen["messages"] = messages
        return "Tamam.\n[[VIDEO: 9:16 | 5 | ref=görsel-1 | milk slowly pours into the iced latte]]"

    monkeypatch.setattr(assistant, "chat_completion", fake_chat)
    token = register_paid(client, plan="pro")
    old = BLOB_URL + "latte.png"
    body = {"messages": [
        {"role": "user", "content": "latte görseli"},
        {"role": "assistant", "content": "İşte görselin.", "media": [old, "https://baska.com/x.png"]},
        {"role": "user", "content": "yukarıdaki görselden video yap"},
    ]}
    r = client.post("/api/content/chat", json=body, headers=auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["video"]["image_url"] == old and r.json()["video"]["concept"] == "milk slowly pours into the iced latte"
    assert "görsel-1" in seen["messages"][2]["content"] and "baska.com" not in str(seen["messages"])
    assert "ref=görsel-N" in seen["messages"][0]["content"]


def test_extract_ref_for_image_edit():
    url, prompt = free_tier.extract_ref("9:16 | ref=görsel-1 | the same latte, brighter", {"görsel-1": "u1"})
    assert url == "u1" and "ref" not in prompt and prompt.startswith("9:16")
    assert free_tier.image_aspect(prompt) == ("9:16", "the same latte, brighter")


def test_video_with_multiple_images_composes_start_frame(client, monkeypatch):
    from app.services import storage
    from .test_api import BLOB_URL

    _enable_media(monkeypatch)
    calls = {}
    monkeypatch.setattr(gateway_media, "generate_image", lambda prompt, aspect, refs: calls.update(refs=refs, aspect=aspect) or (b"\x89PNG\r\n\x1a\nx", "image/png"))
    monkeypatch.setattr(storage, "save", lambda data, mime, folder, filename=None: BLOB_URL + "kare.png")
    monkeypatch.setattr(gateway_media, "start_video", lambda prompt, d, r, image_url, e, a, asp: calls.update(start=image_url) or {"model": "m", "operation": {}})
    token = register_paid(client, plan="pro")
    refs = [BLOB_URL + "urun.png", BLOB_URL + "mekan.png"]
    r = client.post("/api/content/video", json={"concept": "ürün masada dönüyor", "reference_urls": refs}, headers=auth(token))
    assert r.status_code == 200, r.text
    assert calls["refs"] == refs and calls["aspect"] == "9:16" and calls["start"] == BLOB_URL + "kare.png"
    assert r.json()["credits_spent"] == 12 + 4 and r.json()["start_frame"] == BLOB_URL + "kare.png"

    # Tek görsel: doğrudan başlangıç karesi, birleştirme yok
    calls.clear()
    r = client.post("/api/content/video", json={"concept": "x", "reference_urls": refs[:1]}, headers=auth(token))
    assert calls == {"start": refs[0]} and r.json()["credits_spent"] == 12


def test_generated_media_appear_in_library(client, monkeypatch):
    from app.services import storage
    from .test_api import BLOB_URL

    _enable_media(monkeypatch)
    monkeypatch.setattr(gateway_media, "generate_image", lambda prompt, aspect, refs=None: (b"\x89PNG\r\n\x1a\nx", "image/png"))
    monkeypatch.setattr(storage, "save", lambda data, mime, folder, filename=None: BLOB_URL + "g.png")
    token = register_paid(client, plan="pro")
    r = client.post("/api/content/image", json={"concept": "kahve"}, headers=auth(token))
    assert r.status_code == 200
    items = client.get("/api/content/library", params={"kind": "image"}, headers=auth(token)).json()["items"]
    assert len(items) == 1 and items[0]["url"] == BLOB_URL + "g.png" and items[0]["prompt"] == "kahve"
    assert client.get("/api/content/library", params={"kind": "video"}, headers=auth(token)).json()["items"] == []
    assert client.delete(f"/api/content/library/{items[0]['id']}", headers=auth(token)).status_code == 204
    assert client.get("/api/content/library", headers=auth(token)).json()["items"] == []
