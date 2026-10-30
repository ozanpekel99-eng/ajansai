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


def _seed_production(now):
    import uuid
    from datetime import timedelta

    from app.db import credit_events, get_engine, video_tasks

    def ev(action, refunded, ago_h):
        i = str(uuid.uuid4())
        return i, dict(id=i, user_id="u1", action=action, credits=5, detail="gizli istem", refunded=refunded,
                       extra=0, created_at=now - timedelta(hours=ago_h))

    def task(ev_id, status, ago_h, error=None):
        return dict(id=str(uuid.uuid4()), user_id="u1", credit_event_id=ev_id, operation="{}", status=status,
                    error=error, created_at=now - timedelta(hours=ago_h))

    events, tasks = [], []
    for refunded, ago in [(0, 1), (1, 2), (1, 3), (1, 30)]:  # 3 görsel son 24 saatte (2 hata), 1 eski
        events.append(ev("image", refunded, ago)[1])
    for status, ago, err, refunded in [
        ("completed", 1, None, 0),
        ("failed", 2, "Veo boş döndü (filtre: celebrity) http://x", 1),
        ("failed", 3, "Veo boş döndü (filtre: celebrity) {\"raw\": 1}", 1),
        ("failed", 4, "Zaman aşımı", 1),
        ("pending", 2, None, 0),  # takılı
        ("pending", 0.1, None, 0),  # sürüyor
        ("failed", 40, "eski", 1),  # pencere dışı
    ]:
        i, e = ev("video", refunded, ago)
        events.append(e)
        tasks.append(task(i, status, ago, err))
    events.append(ev("video", 1, 5)[1])  # hiç başlatılamayan video (işi yok)
    events.append(ev("idea", 1, 1)[1])  # başka türler sayılmaz
    with get_engine().begin() as conn:
        conn.execute(credit_events.insert(), events)
        conn.execute(video_tasks.insert(), tasks)


def test_production_errors_counts_last_24h(client):
    from app.db import utcnow

    _seed_production(utcnow())
    pe = health.production_errors()
    assert pe["image"] == {"total": 3, "failed": 2}
    v = pe["video"]
    assert (v["total"], v["completed"], v["failed"], v["start_failed"], v["stuck"], v["pending"]) == (7, 1, 3, 1, 1, 1)
    assert v["top_errors"][0] == {"error": "Veo boş döndü (filtre: celebrity)", "count": 2}
    assert pe["failed_total"] == 6
    # Kullanıcı bilgisi / istem rapora sızmaz
    assert "u1" not in json.dumps(pe) and "gizli" not in json.dumps(pe)


def test_qa_endpoint_includes_production_errors(client, monkeypatch):
    from app.db import utcnow

    assert client.get("/api/health/qa").json()["production_errors"]["failed_total"] == 0
    _seed_production(utcnow())
    monkeypatch.setattr(health.gateway_media, "is_enabled", lambda: True)
    monkeypatch.setattr(health.media_planner, "direct_ad_prompt", lambda *a, **k: "prompt")
    monkeypatch.setattr(health.media_qa, "generate_checked", lambda *a, **k: (b"png", "image/png"))
    monkeypatch.setattr(health.media_qa, "check_image", lambda *a, **k: [])
    monkeypatch.setattr(health.storage, "save", lambda *a, **k: "https://x.public.blob.vercel-storage.com/qa/a.png")
    sent = []
    from app.services import support
    monkeypatch.setattr(support, "send_email", lambda to, subject, text, **k: sent.append(text) or {})
    r = client.post("/api/health/qa-run?video=0").json()
    assert r["production_errors"]["image"]["failed"] == 2
    assert "Gerçek üretimler (son 24 saat)" in sent[0] and "2× Veo boş döndü (filtre: celebrity)" in sent[0]
    assert client.get("/api/health/qa").json()["production_errors"]["video"]["failed"] == 3
