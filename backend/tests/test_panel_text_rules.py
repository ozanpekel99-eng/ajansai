"""Ürün panellerinde sahte yazı/logo kuralları (05.11 kalite denetimi).

Referans fotoğrafı yokken istem yazarı temiz, markasız ürün ve yazısız panel istemeli;
görsel denetimi de paneldeki sahte etiketleri ve sahte logoları kusur saymalı."""

from app import config
from app.services import media_planner, media_qa


def _capture(monkeypatch, reply="PROMPT"):
    seen = {}

    def fake_chat(model, messages, max_tokens=0):
        seen["system"] = messages[0]["content"]
        seen["user"] = messages[1]["content"]
        return reply

    monkeypatch.setattr(media_planner.llm_service, "chat_completion", fake_chat)
    return seen


def _user_text(user):
    return user if isinstance(user, str) else user[0]["text"]


def test_ad_director_without_photos_asks_for_clean_panels(monkeypatch):
    seen = _capture(monkeypatch)
    assert media_planner.direct_ad_prompt("beyaz eşya kampanyası", "4:5") == "PROMPT"
    assert media_planner.NO_PRODUCT_PHOTOS in _user_text(seen["user"])
    system = seen["system"]
    assert "No product photos attached" in system
    assert "unbranded" in system and "blank dark" in system


def test_ad_director_with_photos_keeps_real_panel_text(monkeypatch):
    seen = _capture(monkeypatch)
    media_planner.direct_ad_prompt("buzdolabı kampanyası", "4:5", ref_count=2,
                                   image_urls=["data:image/png;base64,AA", "data:image/png;base64,BB"])
    text = _user_text(seen["user"])
    assert "2 product photo(s) attached" in text
    assert media_planner.NO_PRODUCT_PHOTOS not in text
    # Gerçek ürün fotoğrafındaki panel yazısı ve logo korunur (kural yalnızca fotoğrafsız ürünler için)
    assert "panel text and logos" in seen["system"]


def test_ad_director_edit_without_photos_still_marks_no_photos(monkeypatch):
    seen = _capture(monkeypatch)
    media_planner.direct_ad_prompt("başlığı büyüt", "1:1", edit=True, ref_count=0,
                                   image_urls=["data:image/png;base64,AA"])
    assert media_planner.NO_PRODUCT_PHOTOS in _user_text(seen["user"])


def test_image_planner_rule_mentions_unbranded_panels():
    assert "Products without reference photos" in media_planner.IMAGE_SYSTEM
    assert "no small printed labels" in media_planner.IMAGE_SYSTEM


def test_qa_flags_fake_panel_labels_and_pseudo_logos(monkeypatch):
    assert "fake labels" in media_qa.QA_SYSTEM
    assert "pseudo-logos" in media_qa.QA_SYSTEM
    monkeypatch.setattr(config, "IMAGE_QA", True)
    monkeypatch.setattr(media_qa, "_data_url", lambda data, max_side=1024: "data:image/jpeg;base64,AA")
    sent = {}

    def fake_chat(model, messages, max_tokens=0):
        sent["system"] = messages[0]["content"]
        return '{"ok": false, "problems": ["gibberish labels on the washing machine control panel"]}'

    monkeypatch.setattr(media_qa.llm_service, "chat_completion", fake_chat)
    problems = media_qa.check_image(b"img", "beyaz eşya kampanyası")
    assert problems == ["gibberish labels on the washing machine control panel"]
    assert sent["system"] == media_qa.QA_SYSTEM
