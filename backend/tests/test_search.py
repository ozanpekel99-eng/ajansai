from app import config
from app.services import free_tier, web_search

from .test_api import FakeResponse, _enable_media, register_paid
from .conftest import auth

IP = {"x-forwarded-for": "9.9.9.9"}


def _groq_ok(calls):
    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "json": json})
        return FakeResponse(
            200,
            {
                "choices": [
                    {
                        "message": {
                            "content": "Bugün dolar 41,2 TL【1†L3-L5】.",
                            "executed_tools": [
                                {"search_results": {"results": [{"title": "Döviz", "url": "https://ornek.com/doviz"}, {"title": "Döviz", "url": "https://ornek.com/doviz"}]}}
                            ],
                        }
                    }
                ]
            },
        )

    return fake_post


def test_free_chat_searches_web_when_model_asks(client, monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "gk")
    seen = {}

    def first(messages, max_tokens=0, vision=False):
        seen["system"] = messages[0]["content"]
        return "[[ARA: dolar kuru bugün]]", "groq:x"

    monkeypatch.setattr(free_tier, "free_chat_completion", first)
    calls = []
    monkeypatch.setattr(web_search.requests, "post", _groq_ok(calls))
    r = client.post("/api/free/chat", json={"messages": [{"role": "user", "content": "Dolar kaç TL?"}]}, headers=IP)
    data = r.json()
    assert r.status_code == 200, r.text
    assert data["reply"] == "Bugün dolar 41,2 TL." and data["sources"] == [{"title": "Döviz", "url": "https://ornek.com/doviz"}]
    assert calls[0]["json"]["tools"] == [{"type": "browser_search"}] and calls[0]["json"]["model"] == "openai/gpt-oss-120b"
    assert "Bugünün tarihi" in seen["system"] and "[[ARA:" in seen["system"]


def test_search_mode_skips_first_call_and_uses_tavily(client, monkeypatch):
    monkeypatch.setattr(config, "TAVILY_API_KEY", "tv")
    monkeypatch.setattr(config, "GROQ_API_KEY", None)
    monkeypatch.setattr(free_tier, "free_chat_completion", lambda *a, **k: (_ for _ in ()).throw(AssertionError("çağrılmamalı")))
    monkeypatch.setattr(web_search, "smart_chat_completion", lambda *a, **k: ("Sonuç: maç 2-1 bitti [1].", "groq:x"))

    def fake_post(url, headers=None, json=None, timeout=None):
        assert url == "https://api.tavily.com/search" and json["query"] == "Galatasaray maç sonucu"
        return FakeResponse(200, {"results": [{"title": "Maç", "url": "https://spor.com/mac", "content": "2-1"}]})

    monkeypatch.setattr(web_search.requests, "post", fake_post)
    r = client.post("/api/free/chat", json={"mode": "search", "messages": [{"role": "user", "content": "Galatasaray maç sonucu"}]}, headers=IP)
    assert r.json()["reply"] == "Sonuç: maç 2-1 bitti [1]." and r.json()["sources"][0]["url"] == "https://spor.com/mac"


def test_search_failure_returns_friendly_message(client, monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "gk")
    monkeypatch.setattr(free_tier, "free_chat_completion", lambda *a, **k: ("[[ARA: haber]]", "groq:x"))
    monkeypatch.setattr(web_search.requests, "post", lambda *a, **k: FakeResponse(500, {}))
    r = client.post("/api/free/chat", json={"messages": [{"role": "user", "content": "Bugün ne oldu?"}]}, headers=IP)
    assert r.status_code == 200 and "arama yapamadım" in r.json()["reply"] and r.json()["sources"] == []


def test_paid_chat_searches_web(client, monkeypatch):
    _enable_media(monkeypatch)
    monkeypatch.setattr(config, "GROQ_API_KEY", "gk")
    from app.services import assistant

    monkeypatch.setattr(assistant, "chat_completion", lambda model, messages, max_tokens=0: "[[ARA: altın fiyatı]]")
    calls = []
    monkeypatch.setattr(web_search.requests, "post", _groq_ok(calls))
    token = register_paid(client)
    r = client.post("/api/content/chat", json={"messages": [{"role": "user", "content": "Gram altın kaç TL?"}]}, headers=auth(token))
    assert r.status_code == 200 and r.json()["model"] == "web" and r.json()["sources"]


def test_search_answer_prompt_has_no_search_instruction():
    msgs = [{"role": "system", "content": "Asistan." + web_search.SEARCH_NOTE}, {"role": "user", "content": "dolar?"}]
    out = web_search._text_messages(msgs)
    assert "[[ARA" not in out[0]["content"] and out[1]["content"] == "dolar?"
