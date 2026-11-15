import json
from datetime import datetime
from pathlib import Path

import pytest

from app import config
from app.services import social_queue as sq
from tests.conftest import auth, register

PLAN = Path(__file__).resolve().parents[2] / "marketing" / "2026-10-27" / "plan.json"
BASE = "https://x.public.blob.vercel-storage.com/marketing/2026-10-27"


@pytest.fixture
def admin(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_EMAILS", {"admin@example.com"})
    return auth(register(client, "admin@example.com"))


def _import(client, admin, posts=None):
    posts = posts if posts is not None else json.loads(PLAN.read_text())
    return client.post("/api/admin/social/import", json={"week": "2026-10-27", "media_base": BASE, "posts": posts},
                       headers=admin)


def test_schedule_is_istanbul_time_and_handles_year_end():
    assert sq.schedule_utc("2026-10-27", "Pazartesi 27 Ekim", "12:30") == datetime(2026, 10, 27, 9, 30)
    assert sq.schedule_utc("2026-10-27", "Cumartesi 1 Kasım", "20:30") == datetime(2026, 11, 1, 17, 30)
    assert sq.schedule_utc("2027-12-27", "Cumartesi 1 OCAK", "00:30") == datetime(2027, 12, 31, 21, 30)
    with pytest.raises(sq.QueueError):
        sq.schedule_utc("2026-10-27", "Pazartesi 3 Kasım", "12:30")  # başka hafta
    assert sq.weekday_warning("Pazartesi 27 Ekim", datetime(2026, 10, 27, 9, 30)).endswith("aslında salı; paylaşım tarihe göre planlandı.")
    assert sq.weekday_warning("Salı 27 Ekim", datetime(2026, 10, 27, 9, 30)) is None
    assert sq.weekday_warning("27 Ekim", datetime(2026, 10, 27, 9, 30)) is None
    with pytest.raises(sq.QueueError):
        sq.schedule_utc("2026-10-27", "Salı 28 Ekim", "25:00")


def test_kind_and_problems():
    assert sq.kind_of("Gönderi", ["a.png"]) == "image"
    assert sq.kind_of("Carousel (6)", ["a.png", "b.png"]) == "carousel"
    assert sq.kind_of("Reels", ["r.mp4"]) == "reels"
    assert sq.problems("image", "Merhaba", ["https://x/a.png"]) == []
    assert sq.problems("reels", "Merhaba", ["https://x/a.png"])
    assert sq.problems("carousel", "Merhaba", ["https://x/a.png"])  # tek dosyalı carousel olmaz
    assert sq.problems("image", "#a " * 31, ["https://x/a.png"])
    assert sq.problems("image", "x" * 2201, ["https://x/a.png"])


def test_admin_only(client, admin):
    user = auth(register(client, "user@example.com"))
    assert client.get("/api/admin/social/queue", headers=user).status_code == 403
    assert _import(client, user).status_code == 403


def test_import_real_plan_and_reimport_keeps_decisions(client, admin):
    r = _import(client, admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["created"], body["updated"], body["kept"]) == (7, 0, 0)
    # Plan 2026'da pazartesi olmayan 27 Ekim'den başlıyor: gün adları uyarı olarak döner
    assert body["warnings"][0] == "2026-10-27 pazartesi değil (salı)."
    posts = client.get("/api/admin/social/queue", params={"week": "2026-10-27"}, headers=admin).json()["posts"]
    assert [p["kind"] for p in posts] == ["image", "carousel", "reels", "carousel", "image", "reels", "carousel"]
    assert all(p["status"] == "pending" and p["problems"] == [] for p in posts)
    assert posts[0]["scheduled_local"] == "2026-10-27 12:30"
    assert posts[0]["media"] == [BASE + "/g1.png"]

    assert client.post(f"/api/admin/social/{posts[0]['id']}/approve", headers=admin).json()["status"] == "approved"
    assert client.post(f"/api/admin/social/{posts[1]['id']}/skip", headers=admin).json()["status"] == "skipped"
    again = _import(client, admin).json()
    assert (again["created"], again["updated"], again["kept"]) == (0, 5, 2)
    p0 = client.get("/api/admin/social/queue", headers=admin).json()["posts"][0]
    assert p0["status"] == "approved" and p0["approved_by"] == "admin@example.com"


def test_import_rejects_bad_rows(client, admin):
    r = _import(client, admin, [{"day": "Salı 4 Kasım", "time": "12:30", "type": "Gönderi", "files": ["a.png"],
                                 "caption": "x"}])
    assert r.status_code == 400 and "1. satır" in r.json()["detail"]
    r = client.post("/api/admin/social/import", headers=admin, json={
        "week": "2026-10-27", "posts": [{"day": "Salı 28 Ekim", "time": "12:30", "files": ["a.png"], "caption": "x"}]})
    assert r.status_code == 400 and "media_base" in r.json()["detail"]


def test_edit_resets_approval_and_invalid_post_cannot_be_approved(client, admin):
    _import(client, admin)
    pid = client.get("/api/admin/social/queue", headers=admin).json()["posts"][0]["id"]
    client.post(f"/api/admin/social/{pid}/approve", headers=admin)
    r = client.put(f"/api/admin/social/{pid}", json={"caption": "Yeni metin", "scheduled_local": "2026-10-27 18:00"},
                   headers=admin).json()
    assert r["status"] == "pending" and r["caption"] == "Yeni metin" and r["scheduled_local"] == "2026-10-27 18:00"
    assert r["scheduled_at"] == "2026-10-27T15:00:00Z"

    client.put(f"/api/admin/social/{pid}", json={"caption": "x" * 2300}, headers=admin)
    bad = client.post(f"/api/admin/social/{pid}/approve", headers=admin)
    assert bad.status_code == 400 and "2200" in bad.json()["detail"]
    assert client.put(f"/api/admin/social/{pid}", json={"scheduled_local": "yarın"}, headers=admin).status_code == 400
    assert client.post("/api/admin/social/yok/approve", headers=admin).status_code == 404


def test_published_post_is_locked_and_due_lists_approved_only(client, admin):
    _import(client, admin)
    posts = client.get("/api/admin/social/queue", headers=admin).json()["posts"]
    for p in posts[:3]:
        client.post(f"/api/admin/social/{p['id']}/approve", headers=admin)
    due = sq.due(datetime(2026, 10, 28, 12, 0))  # salı 15:00 İstanbul
    assert [d["id"] for d in due] == [posts[0]["id"], posts[1]["id"]]

    sq._set(posts[0]["id"], status="published", ig_media_id="1789")
    assert client.post(f"/api/admin/social/{posts[0]['id']}/skip", headers=admin).status_code == 400
    assert client.put(f"/api/admin/social/{posts[0]['id']}", json={"caption": "x"}, headers=admin).status_code == 400
    assert _import(client, admin).json()["kept"] == 3
