"""Paket "+" rozeti ve örnek başlık (12.11 kalite denetimi).

"+" rozeti kırmızı daire içinde beyaz haç (ilk yardım işareti) gibi çizilmemeli; istem yazarına
verilen örnek başlık da teklif satırıyla kelime paylaşmamalı (aynı kelimenin afişte üç kez
geçmesine yol açıyordu: "İKİLİ" kurdele + "İKİ GÜÇLÜSÜ" başlık + fiyat etiketi)."""

import re

from app.services import media_planner


def _system(monkeypatch):
    seen = {}

    def fake_chat(model, messages, max_tokens=0):
        seen["system"] = messages[0]["content"]
        return "PROMPT"

    monkeypatch.setattr(media_planner.llm_service, "chat_completion", fake_chat)
    assert media_planner.direct_ad_prompt("buzdolabı + çamaşır makinesi ikili alım", "4:5") == "PROMPT"
    return seen["system"]


def test_plus_badge_is_not_a_red_cross(monkeypatch):
    system = _system(monkeypatch)
    assert "never a white cross on a red circle" in system
    assert "gold or" in system and "brand-colored plus sign" in system


def test_example_headline_shares_no_words_with_offer(monkeypatch):
    system = _system(monkeypatch)
    assert "EVİNİZİN İKİ GÜÇLÜSÜ" not in system
    assert "shares no words with the offer line" in system
    m = re.search(r'sold as "([^"]+)": "([^"]+)"', system)
    assert m, "örnek teklif satırı ve başlık bulunamadı"
    offer, headline = (set(re.findall(r"\w+", t)) for t in m.groups())
    # "İKİ" / "İKİLİ" gibi kök paylaşımı da olmasın
    assert not any(h.startswith(o[:3]) or o.startswith(h[:3]) for h in headline for o in offer)
    assert system.rstrip().endswith("Output ONLY the prompt text, no preamble.")
