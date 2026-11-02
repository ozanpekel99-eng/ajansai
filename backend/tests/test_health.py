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


def _qa_video_setup(monkeypatch):
    monkeypatch.setattr(health.gateway_media, "is_enabled", lambda: True)
    monkeypatch.setattr(health.media_planner, "direct_ad_prompt", lambda *a, **k: "prompt")
    monkeypatch.setattr(health.media_qa, "generate_checked", lambda *a, **k: (b"png", "image/png"))
    monkeypatch.setattr(health.media_qa, "check_image", lambda *a, **k: [])
    monkeypatch.setattr(health.storage, "save", lambda *a, **k: "https://x.public.blob.vercel-storage.com/qa/a.png")
    monkeypatch.setattr(health.media_planner, "plan_video", lambda *a, **k: {"prompt": "video", "frame_prompt": ""})
    monkeypatch.setattr(health, "_email", lambda r: None)
    started = {}
    monkeypatch.setattr(health.gateway_media, "start_video",
                        lambda p, d, r, image_url, *a, **k: started.update(image=image_url) or {"model": "veo"})
    return started


def test_qa_video_uses_fitted_frame_like_production(client, monkeypatch):
    """4:5 kaynak görsel, QA videosuna verilmeden önce 9:16'ya genişletilmeli (siyah bant olmasın)."""
    started = _qa_video_setup(monkeypatch)
    from app.services import video_frame

    monkeypatch.setattr(video_frame, "image_aspect", lambda url: 4 / 5)
    extended = []
    monkeypatch.setattr(video_frame.gateway_media, "generate_image",
                        lambda prompt, aspect, refs=None, **k: extended.append(aspect) or (b"png", "image/png"))
    # storage aynı modül: ilk 4 kayıt QA görselleri, 5.'si genişletilmiş açılış karesi
    urls = iter([f"https://x.public.blob.vercel-storage.com/qa/{n}.png" for n in ("a", "b", "c", "d", "kare916")])
    monkeypatch.setattr(video_frame.storage, "save", lambda *a, **k: next(urls))
    r = client.post("/api/health/qa-run?video=1").json()
    assert extended == ["9:16"]
    assert started["image"].endswith("kare916.png")
    assert r["video"]["frame_url"].endswith("kare916.png") and r["video"]["frame_fitted"] is True
    assert "frame_url" in client.get("/api/health/qa").json()["video"]


def test_qa_video_keeps_frame_already_in_ratio(client, monkeypatch):
    started = _qa_video_setup(monkeypatch)
    from app.services import video_frame

    monkeypatch.setattr(video_frame, "image_aspect", lambda url: 9 / 16)
    monkeypatch.setattr(video_frame.gateway_media, "generate_image",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("genişletme gerekmez")))
    r = client.post("/api/health/qa-run?video=1").json()
    assert started["image"].endswith("qa/a.png") and r["video"]["frame_fitted"] is False


def test_fit_frame_falls_back_to_original_on_error(monkeypatch):
    from app.services import video_frame

    monkeypatch.setattr(video_frame, "image_aspect", lambda url: 1.0)

    def boom(*a, **k):
        raise video_frame.gateway_media.MediaError("kapalı")

    monkeypatch.setattr(video_frame.gateway_media, "generate_image", boom)
    assert video_frame.fit_frame("https://x/a.png", "9:16", "qa") == "https://x/a.png"
    assert video_frame.needs_fit(4 / 5, "9:16") and not video_frame.needs_fit(0.57, "9:16")
    assert not video_frame.needs_fit(None, "9:16")
