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
