"""Aynı yazının görselde iki kez çıkması (05.11 ve 09.11 kalite denetimleri).

İstem yazarı her ifadenin afişte yalnızca bir kez geçmesini istemeli; görsel denetimi de
tekrarlanan ifadeyi kusur saymalı (müşteri isteğinde tekrar yoksa)."""

from app.services import media_planner, media_qa


def _capture(monkeypatch, module, reply):
    seen = {}

    def fake_chat(model, messages, max_tokens=0):
        seen["system"] = messages[0]["content"]
        return reply

    monkeypatch.setattr(module.llm_service, "chat_completion", fake_chat)
    return seen


def test_ad_director_forbids_repeated_phrases(monkeypatch):
    seen = _capture(monkeypatch, media_planner, "PROMPT")
    assert media_planner.direct_ad_prompt("kafe yeni sezon kampanyası", "4:5") == "PROMPT"
    system = seen["system"]
    assert "Each phrase appears only once on the poster" in system
    assert "must not repeat words of the offer line" in system
    # Kural, metin kurallarının sonundaki zorunlu kapanış cümlesini bozmamalı
    assert system.rstrip().endswith("Output ONLY the prompt text, no preamble.")


def test_qa_flags_same_phrase_twice(monkeypatch):
    monkeypatch.setattr(media_qa.config, "IMAGE_QA", True)
    seen = _capture(monkeypatch, media_qa,
                    '{"ok": false, "problems": ["\\"YENİ SEZON\\" rendered twice"]}')
    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, "PNG")
    problems = media_qa.check_image(buf.getvalue(), "Kafe, YENİ SEZON fiyatı 120 TL")
    assert problems == ['"YENİ SEZON" rendered twice']
    assert "7. The same phrase rendered twice" in seen["system"]
    assert "unless the" in seen["system"] and "request itself repeats it" in seen["system"]
