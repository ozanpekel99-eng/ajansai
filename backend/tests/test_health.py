import json

from app.routers import health


def test_health_ok(client):
    r = client.get("/api/health").json()
    assert r["db"] is True


def test_qa_run_reports_and_rate_limits(client, monkeypatch):
    monkeypatch.setattr(health.gateway_media, "is_enabled", lambda: True)
    monkeypatch.setattr(health.media_planner, "direct_ad_prompt", lambda *a, **k: "prompt")
    monkeypatch.setattr(health.media_qa, "generate_checked", lambda *a, **k: (b"png", "image/png"))
    calls = iter([[], ["Fiyat yanlış"], [], []])
    monkeypatch.setattr(health.media_qa, "check_image", lambda *a, **k: next(calls))
    monkeypatch.setattr(health.storage, "save", lambda *a, **k: "https://x.public.blob.vercel-storage.com/qa/a.png")
    monkeypatch.setattr(health, "_email", lambda r: None)
    r = client.post("/api/health/qa-run?video=0").json()
    assert r["total"] == 4 and r["passed"] == 3 and "video" not in r
    again = client.post("/api/health/qa-run?video=0").json()
    assert again["skipped"] is True
    assert client.get("/api/health/qa").json()["passed"] == 3


def test_daily_report_sends_once(client, monkeypatch):
    sent = []
    from app.services import support
    monkeypatch.setattr(support, "send_email", lambda to, subject, text, **k: sent.append(text) or {})
    assert client.post("/api/health/daily-report").json() == {"sent": True}
    assert client.post("/api/health/daily-report").json()["sent"] is False
    assert "günlük kullanım raporu" in sent[0]


def test_qa_run_reports_first_attempt_and_retry(client, monkeypatch):
    from app.services import gateway_media, media_qa

    monkeypatch.setattr(health.gateway_media, "is_enabled", lambda: True)
    monkeypatch.setattr(health.media_planner, "direct_ad_prompt", lambda *a, **k: "prompt")
    monkeypatch.setattr(gateway_media, "generate_image", lambda *a, **k: (b"png", "image/png"))
    # Gerçek generate_checked çalışır: ilk görsel (1. çağrı) kusurlu → yeniden üretim; son denetim sorunsuz.
    # Diğer üç görselde ilk denetim temiz.
    target = health.QA_PROMPTS[0][1]
    seen: list[str] = []

    def fake_check(data, request, urls=None):
        seen.append(request)
        return ["CILT yazılmış"] if request == target and seen.count(target) == 1 else []

    monkeypatch.setattr(media_qa, "check_image", fake_check)
    monkeypatch.setattr(health.storage, "save", lambda *a, **k: "https://x.public.blob.vercel-storage.com/qa/a.png")
    sent = []
    monkeypatch.setattr(health, "_email", lambda r: sent.append(r))
    r = client.post("/api/health/qa-run?video=0").json()
    by_name = {i["name"]: i for i in r["images"]}
    first = by_name[health.QA_PROMPTS[0][0]]
    assert first["first_problems"] == ["CILT yazılmış"] and first["retried"] is True
    assert first["problems"] == [] and first["ok"] is True
    others = [i for i in r["images"] if i is not first]
    assert all(i["first_problems"] == [] and i["retried"] is False for i in others)
    assert r["passed"] == 4 and "retry_error" not in first


def test_generate_checked_trace_records_retry_failure(monkeypatch):
    from app.services import gateway_media, media_qa

    calls = []

    def gen(p, a, r=None, q="standard"):
        calls.append(p)
        if len(calls) > 1:
            raise gateway_media.MediaError("kota doldu")
        return b"img1", "image/png"

    monkeypatch.setattr(gateway_media, "generate_image", gen)
    monkeypatch.setattr(media_qa, "check_image", lambda data, req, urls=None: ["fiyat eksik"])
    trace: dict = {}
    data, _ = media_qa.generate_checked("P", "4:5", None, "istek", trace=trace)
    assert data == b"img1"
    assert trace == {"first_problems": ["fiyat eksik"], "retried": False, "retry_error": "kota doldu"}
    # trace verilmezse davranış değişmez
    calls.clear()
    assert media_qa.generate_checked("P", "4:5", None, "istek")[0] == b"img1"


def test_qa_email_shows_first_attempt(monkeypatch):
    from app.services import support

    sent = []
    monkeypatch.setattr(health.config, "ADMIN_EMAILS", {"a@b.c"})
    monkeypatch.setattr(support, "send_email", lambda to, subject, text, **k: sent.append(text))
    health._email({"finished_at": "2026-11-15T03:00:00", "passed": 1, "total": 1, "images": [
        {"name": "guzellik", "ok": True, "seconds": 90.0, "url": "u", "problems": [],
         "first_problems": ["CILT yazılmış"], "retried": True}]})
    assert "İlk denemede 1 kusur (yeniden üretildi)" in sent[0] and "CILT yazılmış" in sent[0]
