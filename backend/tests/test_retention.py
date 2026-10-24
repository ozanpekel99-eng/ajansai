from datetime import datetime, timedelta, timezone

from app.db import get_engine, media, payments, users, utcnow
from app.routers import health
from app.services import retention, storage


def _user(conn, uid, email, plan="deneme"):
    now = utcnow()
    conn.execute(users.insert().values(id=uid, email=email, password_hash="x", name="", plan=plan,
                                       period_start=now, created_at=now))


def test_cleanup_deletes_only_expired_free_files(client, monkeypatch):
    free_id, paid_id, lapsed_id = "a" * 36, "b" * 36, "c" * 36
    with get_engine().begin() as conn:
        _user(conn, free_id, "free@x.com")
        _user(conn, paid_id, "paid@x.com", plan="pro")
        _user(conn, lapsed_id, "lapsed@x.com")  # ödeme yapmış, paketi bitmiş
        conn.execute(payments.insert().values(id="p1", user_id=lapsed_id, plan_id="pro", amount_try=100,
                                              status="success", created_at=utcnow()))
        conn.execute(media.insert().values(id="m1", user_id=free_id, kind="image",
                                           url="https://s.public.blob.vercel-storage.com/gorsel/" + free_id + "/old.png",
                                           prompt="", source="sohbet", created_at=utcnow()))
    old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat().replace("+00:00", "Z")
    new = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    base = "https://s.public.blob.vercel-storage.com/"
    blobs = {
        "gorsel/": [
            {"url": base + f"gorsel/{free_id}/old.png", "pathname": f"gorsel/{free_id}/old.png", "size": 2_000_000, "uploadedAt": old},
            {"url": base + f"gorsel/{free_id}/new.png", "pathname": f"gorsel/{free_id}/new.png", "size": 1, "uploadedAt": new},
            {"url": base + f"gorsel/{paid_id}/old.png", "pathname": f"gorsel/{paid_id}/old.png", "size": 1, "uploadedAt": old},
            {"url": base + f"gorsel/{lapsed_id}/old.png", "pathname": f"gorsel/{lapsed_id}/old.png", "size": 1, "uploadedAt": old},
            {"url": base + "gorsel/ucretsiz/g.png", "pathname": "gorsel/ucretsiz/g.png", "size": 1, "uploadedAt": old},
            {"url": base + "gorsel/x.png", "pathname": "gorsel/x.png", "size": 1, "uploadedAt": old},
        ],
        "yuklemeler/": [{"url": base + "yuklemeler/misafir/u.jpg", "pathname": "yuklemeler/misafir/u.jpg", "size": 1, "uploadedAt": old}],
    }
    monkeypatch.setattr(storage, "is_enabled", lambda: True)
    monkeypatch.setattr(storage, "list_blobs", lambda prefix, **k: blobs.get(prefix, []))
    deleted = []
    monkeypatch.setattr(storage, "delete", lambda urls: deleted.extend(urls) or len(urls))

    dry = client.get("/api/health/cleanup?dry_run=true").json()
    assert dry["candidates"] == 3 and dry["deleted"] == 0 and not deleted

    r = client.post("/api/health/cleanup").json()
    assert r["deleted"] == 3
    assert sorted(u.split("blob.vercel-storage.com/")[1] for u in deleted) == sorted(
        [f"gorsel/{free_id}/old.png", "gorsel/ucretsiz/g.png", "yuklemeler/misafir/u.jpg"])
    with get_engine().connect() as conn:
        assert conn.execute(media.select().where(media.c.id == "m1")).first() is None
    assert client.post("/api/health/cleanup").json()["deleted"] == 0  # 20 saatte bir
