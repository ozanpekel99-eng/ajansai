import base64

from app import config
from app.services import assistant, free_tier, storage
from app.services.llm_service import LLMError

from .conftest import auth, register
from .test_api import BLOB_TOKEN, BLOB_URL, FakeResponse, _enable_media, register_paid

IP_A = {"x-forwarded-for": "85.100.1.1, 10.0.0.1"}
IP_B = {"x-forwarded-for": "85.100.1.2"}


def _fake_chat(monkeypatch, seen=None):
    def fake(messages, max_tokens=0, vision=False):
        if seen is not None:
            seen.append({"messages": messages, "max_tokens": max_tokens})
        return "Ücretsiz fikir", "groq:test"

    monkeypatch.setattr(free_tier, "free_chat_completion", fake)


def _msg(text="Kafem için fikir"):
    return {"messages": [{"role": "user", "content": text}]}


def test_guest_chat_uses_haiku_and_daily_limit_per_ip(client, monkeypatch):
    seen = []
    _fake_chat(monkeypatch, seen)
    monkeypatch.setattr(config, "FREE_CHAT_PER_DAY_ANON", 2)
    for _ in range(2):
        r = client.post("/api/free/chat", json=_msg(), headers=IP_A)
        assert r.status_code == 200, r.text
    assert r.json()["reply"] == "Ücretsiz fikir"
    assert r.json()["free"]["chat"] == {"used": 2, "limit": 2, "remaining": 0}
    assert seen[0]["max_tokens"] <= 1500

    r = client.post("/api/free/chat", json=_msg(), headers=IP_A)
    assert r.status_code == 429 and "Üye olursan" in r.json()["detail"]
    # Başka bir IP etkilenmez
    assert client.post("/api/free/chat", json=_msg(), headers=IP_B).status_code == 200


def test_signed_in_free_user_has_own_limit(client, monkeypatch):
    _fake_chat(monkeypatch)
    monkeypatch.setattr(config, "FREE_CHAT_PER_DAY_ANON", 1)
    monkeypatch.setattr(config, "FREE_CHAT_PER_DAY_USER", 3)
    token = register(client)
    for _ in range(3):
        assert client.post("/api/free/chat", json=_msg(), headers={**IP_A, **auth(token)}).status_code == 200
    assert client.post("/api/free/chat", json=_msg(), headers={**IP_A, **auth(token)}).status_code == 429
    # Kullanıcı hakkı ziyaretçi hakkından ayrı sayılır
    assert client.post("/api/free/chat", json=_msg(), headers=IP_A).status_code == 200
    status = client.get("/api/free/status", headers=auth(token)).json()
    assert status["signed_in"] is True and status["chat"]["remaining"] == 0


def test_free_chat_failure_does_not_use_quota_and_is_text_only(client, monkeypatch):
    def broken(*a, **k):
        raise LLMError("kapalı")

    monkeypatch.setattr(free_tier, "free_chat_completion", broken)
    r = client.post("/api/free/chat", json=_msg(), headers=IP_A)
    assert r.status_code == 503
    assert client.get("/api/free/status", headers=IP_A).json()["chat"]["used"] == 0
    assert client.post("/api/free/chat", json=_msg("  "), headers=IP_A).status_code == 400


def test_free_chat_sends_short_history(client, monkeypatch):
    seen = []
    _fake_chat(monkeypatch, seen)
    history = []
    for i in range(15):
        history += [{"role": "user", "content": f"soru {i} " + "x" * 5000}, {"role": "assistant", "content": f"cevap {i}"}]
    history.append({"role": "user", "content": "son soru"})
    assert client.post("/api/free/chat", json={"messages": history}, headers=IP_A).status_code == 200
    sent = seen[0]["messages"]
    assert sent[0]["role"] == "system" and len(sent) == 1 + free_tier.HISTORY_MESSAGES
    assert all(len(m["content"]) <= free_tier.MESSAGE_CHARS for m in sent[1:])
    assert sent[-1]["content"] == "son soru"


def _enable_free_images(monkeypatch, calls):
    monkeypatch.setattr(config, "CLOUDFLARE_ACCOUNT_ID", "acc123")
    monkeypatch.setattr(config, "CLOUDFLARE_AI_TOKEN", "cf-token")
    monkeypatch.setattr(free_tier, "free_chat_completion", lambda messages, max_tokens=0, vision=False, premium=True: ("a fridge in a white kitchen", "groq:x"))

    def fake_post(url, headers=None, json=None, data=None, files=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json or data, "files": files})
        return FakeResponse(200, {"success": True, "result": {"image": base64.b64encode(b"\xff\xd8\xffjpg").decode()}})

    monkeypatch.setattr(free_tier.requests, "post", fake_post)


def test_free_images_monthly_limit_and_cloudflare_request(client, monkeypatch):
    calls = []
    _enable_free_images(monkeypatch, calls)
    monkeypatch.setattr(config, "FREE_IMAGES_PER_MONTH", 2)
    for _ in range(2):
        r = client.post("/api/free/image", json={"concept": "beyaz mutfakta buzdolabı"}, headers=IP_A)
        assert r.status_code == 200, r.text
        assert r.json()["image_url"].startswith("data:image/jpeg;base64,")
    assert r.json()["free"]["images"]["remaining"] == 0
    assert calls[0]["url"].endswith("/accounts/acc123/ai/run/@cf/black-forest-labs/flux-2-klein-4b")
    assert calls[0]["json"]["width"] == "1024" and calls[0]["files"] == {}
    assert calls[0]["headers"]["Authorization"] == "Bearer cf-token"
    assert calls[0]["json"]["prompt"] == "a fridge in a white kitchen"  # İngilizceye çevrilmiş istem

    r = client.post("/api/free/image", json={"concept": "beyaz mutfakta buzdolabı"}, headers=IP_A)
    assert r.status_code == 429 and "Stok kütüphanesinden" in r.json()["detail"]
    assert len(calls) == 2


def test_free_images_use_paid_model_then_flux_after_daily_cap(client, monkeypatch):
    from app.services import gateway_media, media_planner

    calls = []
    _enable_free_images(monkeypatch, calls)
    gemini = []
    monkeypatch.setattr(gateway_media, "is_enabled", lambda: True)
    monkeypatch.setattr(media_planner, "plan_image", lambda req, aspect, **k: {"prompt": "planned " + req, "note": None})

    def fake_generate(prompt, aspect, refs=None):
        gemini.append((prompt, aspect))
        return b"\x89PNGgemini", "image/png"

    monkeypatch.setattr(gateway_media, "generate_image", fake_generate)
    monkeypatch.setattr(config, "FREE_PREMIUM_IMAGES_PER_DAY", 1)
    r = client.post("/api/free/image", json={"concept": "kahve fincanı"}, headers=IP_A)
    assert r.status_code == 200 and r.json()["image_url"].startswith("data:image/png;base64,")
    assert gemini == [("planned kahve fincanı", "1:1")] and calls == []
    # Günlük Gemini tavanı doldu: aynı hak FLUX yedeğiyle üretilir
    r = client.post("/api/free/image", json={"concept": "kahve fincanı"}, headers=IP_B)
    assert r.status_code == 200 and r.json()["image_url"].startswith("data:image/jpeg;base64,")
    assert len(gemini) == 1 and len(calls) == 1


def test_free_images_site_wide_daily_cap(client, monkeypatch):
    _enable_free_images(monkeypatch, [])
    monkeypatch.setattr(config, "FREE_IMAGES_PER_DAY_TOTAL", 1)
    assert client.post("/api/free/image", json={"concept": "kahve fincanı"}, headers=IP_A).status_code == 200
    r = client.post("/api/free/image", json={"concept": "kahve fincanı"}, headers=IP_B)
    assert r.status_code == 429 and "kotası doldu" in r.json()["detail"]


def test_free_image_failure_returns_quota(client, monkeypatch):
    _enable_free_images(monkeypatch, [])
    monkeypatch.setattr(free_tier.requests, "post", lambda *a, **k: FakeResponse(500, {"errors": ["x"]}))
    r = client.post("/api/free/image", json={"concept": "kahve fincanı"}, headers=IP_A)
    assert r.status_code == 200 and r.json()["image_url"] is None
    assert r.json()["free"]["images"]["used"] == 0


def test_free_image_disabled_without_cloudflare(client):
    assert client.post("/api/free/image", json={"concept": "kahve fincanı"}).status_code == 503


PEXELS_PHOTO = {
    "id": 42,
    "width": 4000,
    "height": 3000,
    "url": "https://www.pexels.com/photo/kahve-42/",
    "photographer": "Ayşe",
    "photographer_url": "https://www.pexels.com/@ayse",
    "avg_color": "#886644",
    "alt": "Kahve fincanı",
    "src": {
        "medium": "https://images.pexels.com/photos/42/m.jpeg",
        "large": "https://images.pexels.com/photos/42/l.jpeg",
        "large2x": "https://images.pexels.com/photos/42/l2x.jpeg",
    },
}


def test_stock_search_is_cached(client, monkeypatch):
    monkeypatch.setattr(config, "PEXELS_API_KEY", "pexels-key")
    calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append({"url": url, "headers": headers, "params": params})
        return FakeResponse(200, {"photos": [PEXELS_PHOTO], "next_page": "x"})

    monkeypatch.setattr(free_tier.requests, "get", fake_get)
    r = client.get("/api/free/stock", params={"q": "kahve", "orientation": "square"}, headers=IP_A)
    assert r.status_code == 200, r.text
    photo = r.json()["photos"][0]
    assert photo["download"].endswith("l2x.jpeg") and photo["photographer"] == "Ayşe" and r.json()["has_more"]
    assert calls[0]["headers"]["Authorization"] == "pexels-key"
    assert calls[0]["params"]["locale"] == "tr-TR" and calls[0]["params"]["orientation"] == "square"
    # Aynı arama önbellekten gelir
    client.get("/api/free/stock", params={"q": "Kahve ", "orientation": "square"}, headers=IP_B)
    assert len(calls) == 1


def test_stock_save_requires_login_and_copies_to_blob(client, monkeypatch):
    monkeypatch.setattr(config, "PEXELS_API_KEY", "pexels-key")
    monkeypatch.setattr(config, "BLOB_READ_WRITE_TOKEN", BLOB_TOKEN)
    assert client.post("/api/free/stock/save", json={"photo_id": 42}).status_code == 401

    def fake_get(url, headers=None, params=None, timeout=None):
        if "api.pexels.com" in url:
            assert url.endswith("/photos/42")
            return FakeResponse(200, PEXELS_PHOTO)
        assert url == "https://images.pexels.com/photos/42/l2x.jpeg"
        r = FakeResponse(200, {})
        r.content = b"\xff\xd8\xffjpeg"
        return r

    monkeypatch.setattr(free_tier.requests, "get", fake_get)
    saved = {}
    monkeypatch.setattr(storage, "save", lambda d, m, f: saved.update(data=d, folder=f) or BLOB_URL + "stok.jpg")
    token = register(client)
    r = client.post("/api/free/stock/save", json={"photo_id": 42}, headers=auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["url"] == BLOB_URL + "stok.jpg" and saved["folder"].startswith("stok/")


def test_stock_rejects_foreign_download_host(client, monkeypatch):
    monkeypatch.setattr(config, "PEXELS_API_KEY", "pexels-key")
    monkeypatch.setattr(config, "BLOB_READ_WRITE_TOKEN", BLOB_TOKEN)
    bad = {**PEXELS_PHOTO, "src": {"large2x": "https://evil.example.com/x.jpg"}}
    monkeypatch.setattr(free_tier.requests, "get", lambda url, **k: FakeResponse(200, bad))
    token = register(client)
    assert client.post("/api/free/stock/save", json={"photo_id": 42}, headers=auth(token)).status_code == 503


def test_free_plan_listed_with_limits(client):
    data = client.get("/api/plans/").json()
    assert data["trial"]["name"] == "Ücretsiz" and data["trial"]["credits"] == 0
    assert data["free"] == {"chat_per_day": 10, "chat_per_day_guest": 5, "images_per_month": 3}


# ---------------- Ücretli sohbette maliyet sınırları ----------------

def test_paid_chat_charges_long_pdfs_by_pages(client, monkeypatch):
    _enable_media(monkeypatch)
    pdf = b"%PDF-1.4 " + b"<< /Type /Page >> " * 25 + b"<< /Type /Pages /Count 25 >>"
    monkeypatch.setattr(storage, "fetch", lambda url, max_bytes=0: pdf)
    monkeypatch.setattr(assistant, "chat_completion", lambda model, messages, max_tokens=0: "ok")
    token = register_paid(client)
    att = {"url": BLOB_URL + "k.pdf", "content_type": "application/pdf", "name": "k.pdf"}
    r = client.post("/api/content/chat", json={"messages": [{"role": "user", "content": "özetle", "attachments": [att]}]}, headers=auth(token))
    # mesaj 1 + ek 1 + 25 sayfa için 2 ek kredi
    assert r.status_code == 200 and r.json()["credits_spent"] == 4

    huge = b"%PDF-1.4 " + b"<< /Type /Page >> " * 61
    monkeypatch.setattr(storage, "fetch", lambda url, max_bytes=0: huge)
    r = client.post("/api/content/chat", json={"messages": [{"role": "user", "content": "özetle", "attachments": [att]}]}, headers=auth(token))
    assert r.status_code == 400 and "60 sayfalık" in r.json()["detail"]


def test_paid_chat_trims_history_and_limits_reply(client, monkeypatch):
    _enable_media(monkeypatch)
    seen = {}
    monkeypatch.setattr(assistant, "chat_completion", lambda model, messages, max_tokens=0: seen.update(m=messages, t=max_tokens) or "ok")
    token = register_paid(client)
    history = []
    for i in range(19):
        history += [{"role": "user", "content": "u" * 9000}, {"role": "assistant", "content": "a" * 9000}]
    history = history[-39:]
    history.append({"role": "user", "content": "son"})
    r = client.post("/api/content/chat", json={"messages": history}, headers=auth(token))
    assert r.status_code == 200, r.text
    sent = seen["m"][1:]
    assert seen["t"] == assistant.MAX_REPLY_TOKENS
    assert sent[0]["role"] == "user" and sent[-1]["content"] == "son"
    assert sum(len(m["content"]) for m in sent[:-1]) <= assistant.HISTORY_CHARS
    assert all(len(m["content"]) <= assistant.OLD_MESSAGE_CHARS for m in sent)


# ---------------- Ücretsiz sağlayıcı zinciri ----------------

def test_free_chain_falls_through_to_haiku(monkeypatch):
    from app.services import llm_service as ls

    monkeypatch.setattr(config, "GROQ_API_KEY", "gk")
    monkeypatch.setattr(config, "CEREBRAS_API_KEY", "ck")
    monkeypatch.setattr(config, "FREE_CHAT_CHAIN", "cerebras:gpt-oss-120b,groq:openai/gpt-oss-120b,bilinmeyen:x")
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append((url, json.get("model"), headers["Authorization"], json.get("reasoning_effort")))
        if "cerebras" in url:
            return FakeResponse(429, {"error": "quota"})
        return FakeResponse(200, {"choices": [{"message": {"content": "Groq yanıtı"}}]})

    monkeypatch.setattr(ls.requests, "post", fake_post)
    text, used = ls.free_chat_completion([{"role": "user", "content": "selam"}])
    assert text == "Groq yanıtı" and used == "groq:openai/gpt-oss-120b"
    assert calls[0] == ("https://api.cerebras.ai/v1/chat/completions", "gpt-oss-120b", "Bearer ck", "low")
    assert calls[1][0] == "https://api.groq.com/openai/v1/chat/completions"



def test_free_chat_uses_haiku_within_daily_budget(monkeypatch):
    from app.services import llm_service as ls

    monkeypatch.setattr(config, "GROQ_API_KEY", "gk")
    monkeypatch.setattr(config, "FREE_CHAT_CHAIN", "groq:openai/gpt-oss-120b")
    monkeypatch.setattr(ls, "gateway_ready", lambda: True)
    monkeypatch.setattr(config, "FREE_GATEWAY_DAILY_USD", 0.001)
    monkeypatch.setattr(ls, "_free_provider_call", lambda p, m, msgs, mt: "Groq yanıtı")

    def fake_gateway(model, messages, max_tokens=0, free=False):
        assert free is True
        ls.record_spend(model, {"prompt_tokens": 4000, "completion_tokens": 1000}, free=True)  # $0,0009
        return f"{model} yanıtı"

    monkeypatch.setattr(ls, "chat_completion", fake_gateway)
    # Ücretsiz sohbet Claude Haiku ile (bütçe içinde)
    assert ls.free_chat_completion([{"role": "user", "content": "selam"}], premium=False)[1] == "anthropic/claude-haiku-5.5"
    assert ls.free_chat_completion([{"role": "user", "content": "selam"}])[1] == "anthropic/claude-haiku-5.5"
    # Günlük ücretsiz bütçe ($0,001) aşıldı: ücretsiz zincire geçilir
    assert ls.free_chat_completion([{"role": "user", "content": "selam"}]) == ("Groq yanıtı", "groq:openai/gpt-oss-120b")
    assert ls.spent_today(free=True) > 0.001 and ls.spent_today() == ls.spent_today(free=True)


def test_paid_smart_chat_uses_sonnet_then_haiku(monkeypatch):
    from app.services import llm_service as ls

    monkeypatch.setattr(ls, "gateway_ready", lambda: True)
    tried = []

    def fake_gateway(model, messages, max_tokens=0, free=False):
        tried.append((model, free))
        if "sonnet" in model:
            raise LLMError("yoğun")
        return "ok"

    monkeypatch.setattr(ls, "chat_completion", fake_gateway)
    assert ls.smart_chat_completion([{"role": "user", "content": "x"}], paid=True) == ("ok", "anthropic/claude-haiku-5.5")
    assert tried == [("anthropic/claude-sonnet-5.5", False), ("anthropic/claude-haiku-5.5", False)]


def test_free_chain_skips_providers_without_keys(monkeypatch):
    from app.services import llm_service as ls

    monkeypatch.setattr(config, "GROQ_API_KEY", None)
    monkeypatch.setattr(config, "CEREBRAS_API_KEY", "ck")
    assert ls.free_chain() == [("cerebras", "gpt-oss-120b"), ("cerebras", "qwen-3.8-27b")]


def test_paid_chat_uses_sonnet():
    assert config.CHAT_MODEL == "anthropic/claude-sonnet-5.5"


PIXABAY_HIT = {
    "id": 77,
    "pageURL": "https://pixabay.com/photos/kahve-77/",
    "tags": "kahve, fincan",
    "previewURL": "https://cdn.pixabay.com/p/77_150.jpg",
    "webformatURL": "https://pixabay.com/get/77_640.jpg",
    "largeImageURL": "https://pixabay.com/get/77_1280.jpg",
    "imageWidth": 4000,
    "imageHeight": 4000,
    "user": "ayse",
    "user_id": 5,
}


def test_pixabay_preferred_for_stock(client, monkeypatch):
    monkeypatch.setattr(config, "PIXABAY_API_KEY", "px-key")
    monkeypatch.setattr(config, "PEXELS_API_KEY", "pexels-key")
    monkeypatch.setattr(config, "BLOB_READ_WRITE_TOKEN", BLOB_TOKEN)
    calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append((url, params))
        if url == "https://pixabay.com/api/":
            return FakeResponse(200, {"totalHits": 100, "hits": [PIXABAY_HIT]})
        assert url == "https://pixabay.com/get/77_1280.jpg"
        r = FakeResponse(200, {})
        r.content = b"\xff\xd8\xffjpeg"
        return r

    monkeypatch.setattr(free_tier.requests, "get", fake_get)
    r = client.get("/api/free/stock", params={"q": "kahve", "orientation": "portrait"}, headers=IP_A)
    data = r.json()
    assert data["source"] == "Pixabay" and data["has_more"] is True
    assert data["photos"][0]["download"].endswith("77_1280.jpg") and data["photos"][0]["photographer"] == "ayse"
    assert calls[0][1]["key"] == "px-key" and calls[0][1]["lang"] == "tr" and calls[0][1]["orientation"] == "vertical"

    monkeypatch.setattr(storage, "save", lambda d, m, f: BLOB_URL + "stok.jpg")
    token = register(client)
    r = client.post("/api/free/stock/save", json={"photo_id": 77}, headers=auth(token))
    assert r.status_code == 200 and calls[-2][1]["id"] == 77


def test_paid_text_chat_falls_back_to_free_chain(client, monkeypatch):
    _enable_media(monkeypatch)

    def gateway_down(model, messages, max_tokens=0):
        raise LLMError("ödeme yöntemi yok")

    monkeypatch.setattr(assistant, "chat_completion", gateway_down)
    monkeypatch.setattr(assistant, "smart_chat_completion", lambda messages, max_tokens=0, paid=False, skip=(): ("Groq yanıtı", "groq:openai/gpt-oss-120b"))
    token = register_paid(client)
    r = client.post("/api/content/chat", json={"messages": [{"role": "user", "content": "Fikir ver"}]}, headers=auth(token))
    assert r.status_code == 200 and r.json()["reply"] == "Groq yanıtı"


def test_free_chat_generates_image_when_asked(client, monkeypatch):
    calls = []
    _enable_free_images(monkeypatch, calls)
    monkeypatch.setattr(
        free_tier,
        "free_chat_completion",
        lambda messages, max_tokens=0, vision=False: ("Harika fikir! İşte görselin.\n[[GORSEL: a latte on a wooden table, morning light]]", "groq:x"),
    )
    r = client.post("/api/free/chat", json=_msg("Ahşap masada latte görseli üret"), headers=IP_A)
    data = r.json()
    assert r.status_code == 200, r.text
    assert data["reply"] == "Harika fikir! İşte görselin." and "[[" not in data["reply"]
    assert data["images"][0].startswith("data:image/jpeg;base64,")
    assert calls[0]["json"]["prompt"] == "a latte on a wooden table, morning light"  # çeviri yapılmadı
    assert data["free"]["images"]["used"] == 1


def test_free_chat_image_attachment_uses_vision_and_reference_model(client, monkeypatch):
    calls = []
    _enable_free_images(monkeypatch, calls)
    monkeypatch.setattr(config, "BLOB_READ_WRITE_TOKEN", BLOB_TOKEN)
    monkeypatch.setattr(free_tier, "free_chat_completion", lambda messages, max_tokens=0, vision=False: ("Tamam.\n[[GORSEL: the product in image 0 on a beach]]", "groq:x"))
    att = {"url": BLOB_URL + "urun.jpg", "content_type": "image/jpeg", "name": "urun.jpg"}
    body = {"messages": [{"role": "user", "content": "Bunu plajda göster", "attachments": [att]}]}

    import io
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (1200, 900), "red").save(buf, "JPEG")
    monkeypatch.setattr(storage, "fetch", lambda url, max_bytes=0: buf.getvalue())
    monkeypatch.setattr(storage, "save", lambda d, m, f: BLOB_URL + "uretilen.jpg")
    sent = {}

    def fake_post(url, headers=None, data=None, files=None, json=None, timeout=None):
        sent.update(url=url, data=data, files=files)
        return FakeResponse(200, {"result": {"image": base64.b64encode(b"jpg").decode()}})

    monkeypatch.setattr(free_tier.requests, "post", fake_post)
    token = register(client)
    r = client.post("/api/free/chat", json=body, headers={**IP_A, **auth(token)})
    assert r.status_code == 200, r.text
    assert r.json()["images"] == [BLOB_URL + "uretilen.jpg"]
    assert sent["url"].endswith("/ai/run/@cf/black-forest-labs/flux-2-klein-4b")
    ref = Image.open(io.BytesIO(sent["files"]["input_image_0"][1]))
    assert max(ref.size) < 512
    # örnekli üretim günlük tavanda iki kat sayılır
    from app.db import free_events, get_engine
    from sqlalchemy import select

    with get_engine().connect() as conn:
        kinds = [r.kind for r in conn.execute(select(free_events))]
    assert kinds.count("image") == 1 and kinds.count("image_extra") == 1


def test_social_login_creates_and_reuses_account(client, monkeypatch):
    from app.services import social_auth

    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "gid.apps.googleusercontent.com")
    assert client.get("/api/auth/providers").json()["google_client_id"] == "gid.apps.googleusercontent.com"
    monkeypatch.setattr(social_auth, "verify", lambda provider, token: {"email": "Ozan@Gmail.com", "name": "Ozan P", "email_verified": True})
    r1 = client.post("/api/auth/google", json={"credential": "x"})
    r2 = client.post("/api/auth/google", json={"credential": "x"})
    assert r1.status_code == 200 and r1.json()["user"]["id"] == r2.json()["user"]["id"]
    assert r1.json()["user"]["email"] == "ozan@gmail.com"
    # Bu hesaba şifreyle girilemez
    assert client.post("/api/auth/login", json={"email": "ozan@gmail.com", "password": "!social"}).status_code == 401

    def bad(provider, token):
        raise social_auth.SocialAuthError("Giriş doğrulanamadı")

    monkeypatch.setattr(social_auth, "verify", bad)
    assert client.post("/api/auth/apple", json={"id_token": "x"}).status_code == 401


def test_social_verify_checks_audience(monkeypatch):
    from app.services import social_auth

    monkeypatch.setattr(config, "APPLE_CLIENT_ID", None)
    import pytest

    with pytest.raises(social_auth.SocialAuthError):
        social_auth.verify("apple", "token")


def test_social_verify_real_signature(monkeypatch):
    import time

    import jwt as pyjwt
    import pytest
    from cryptography.hazmat.primitives.asymmetric import rsa

    from app.services import social_auth

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class FakeJwks:
        def get_signing_key_from_jwt(self, token):
            return type("K", (), {"key": key.public_key()})()

    monkeypatch.setattr(social_auth, "_jwks", lambda provider: FakeJwks())
    monkeypatch.setattr(config, "GOOGLE_CLIENT_ID", "gid")
    now = int(time.time())
    good = {"iss": "https://accounts.google.com", "aud": "gid", "sub": "1", "email": "a@b.com", "email_verified": True, "iat": now, "exp": now + 600}
    assert social_auth.verify("google", pyjwt.encode(good, key, algorithm="RS256"))["email"] == "a@b.com"
    for bad in ({**good, "aud": "baska"}, {**good, "iss": "https://evil.com"}, {**good, "exp": now - 10}, {**good, "email_verified": False}):
        with pytest.raises(social_auth.SocialAuthError):
            social_auth.verify("google", pyjwt.encode(bad, key, algorithm="RS256"))


def test_free_chat_reads_documents_and_forces_image_mode(client, monkeypatch):
    calls = []
    _enable_free_images(monkeypatch, calls)
    monkeypatch.setattr(config, "BLOB_READ_WRITE_TOKEN", BLOB_TOKEN)
    monkeypatch.setattr(storage, "fetch", lambda url, max_bytes=0: "Menü: latte 90 TL, mocha 110 TL".encode())
    seen = {}

    def fake(messages, max_tokens=0, vision=False):
        seen.update(messages=messages, vision=vision)
        return "Tamam.\n[[GORSEL: a coffee menu board]]", "groq:x"

    monkeypatch.setattr(free_tier, "free_chat_completion", fake)
    att = {"url": BLOB_URL + "menu.txt", "content_type": "text/plain", "name": "menu.txt"}
    r = client.post("/api/free/chat", json={"mode": "image", "messages": [{"role": "user", "content": "Buna göre", "attachments": [att]}]}, headers=IP_A)
    assert r.status_code == 200, r.text
    assert "latte 90 TL" in seen["messages"][-1]["content"] and seen["vision"] is False
    assert "Görsel oluştur" in seen["messages"][0]["content"]
    assert r.json()["images"]
    video = {"url": BLOB_URL + "v.mp4", "content_type": "video/mp4", "name": "v.mp4"}
    assert client.post("/api/free/chat", json={"messages": [{"role": "user", "content": "x", "attachments": [video]}]}, headers=IP_A).status_code == 400


def test_free_vision_chain_uses_only_qwen(monkeypatch):
    from app.services import llm_service as ls

    monkeypatch.setattr(config, "GROQ_API_KEY", "gk")
    monkeypatch.setattr(config, "CEREBRAS_API_KEY", None)
    used = []
    monkeypatch.setattr(ls, "_free_provider_call", lambda p, m, msgs, mt: used.append(m) or "ok")
    ls.free_chat_completion([{"role": "user", "content": "x"}], vision=True)
    assert used == ["qwen/qwen3.8-27b"]
