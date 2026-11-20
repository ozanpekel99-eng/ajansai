"""Soğuk başlangıç dayanıklılığı: veritabanı hazırlığı çökertmesin, eksikleri tamamlasın."""

import importlib

from sqlalchemy import inspect, text

from app import db


def test_init_db_creates_only_missing_tables_and_columns():
    engine = db.get_engine()
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE app_settings"))
        conn.execute(text("ALTER TABLE credit_events DROP COLUMN extra"))
    db.init_db()
    insp = inspect(engine)
    assert "app_settings" in insp.get_table_names()
    assert "extra" in {c["name"] for c in insp.get_columns("credit_events")}
    db.init_db()  # ikinci çağrı hiçbir şeyi bozmaz
    assert db.is_initialized()


def test_init_db_uses_single_connection(monkeypatch):
    """NullPool'da her bağlantı yeni TLS el sıkışması; hazırlık tek bağlantıyla yapılmalı."""
    engine = db.get_engine()
    opened = []
    real_connect = engine.connect
    monkeypatch.setattr(engine, "connect", lambda *a, **k: opened.append(1) or real_connect(*a, **k))
    db.init_db()
    assert len(opened) == 1


def test_ensure_db_retries_then_succeeds(monkeypatch):
    db.reset_engine()
    real = db.init_db
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise OSError("bağlantı zaman aşımı")
        real()

    monkeypatch.setattr(db, "init_db", flaky)
    assert db.ensure_db(attempts=2, delay=0) is True
    assert len(calls) == 2
    assert db.ensure_db() is True and len(calls) == 2  # başarıdan sonra tekrar denemez


def test_ensure_db_never_raises(monkeypatch):
    db.reset_engine()
    monkeypatch.setattr(db, "init_db", lambda: (_ for _ in ()).throw(OSError("veritabanı kapalı")))
    assert db.ensure_db(attempts=2, delay=0) is False
    assert not db.is_initialized()


def test_index_import_survives_db_failure(monkeypatch):
    """Vercel giriş dosyası veritabanı hatasında çökmemeli (FUNCTION_INVOCATION_FAILED olmasın)."""
    import index

    db.reset_engine()
    monkeypatch.setattr(db, "init_db", lambda: (_ for _ in ()).throw(OSError("veritabanı kapalı")))
    monkeypatch.setattr(db.time, "sleep", lambda s: None)
    importlib.reload(index)
    assert not db.is_initialized()


def test_first_request_retries_and_returns_503_until_ready(monkeypatch):
    from fastapi.testclient import TestClient

    from app import main

    real = db.init_db
    state = {"down": True}

    def maybe():
        if state["down"]:
            raise OSError("veritabanı kapalı")
        real()

    # lifespan'sız istemci: Vercel'deki gibi yalnızca index.py yüklemesi + istekler
    db.reset_engine()
    monkeypatch.setattr(db, "init_db", maybe)
    monkeypatch.setattr(main, "ensure_db", db.ensure_db)
    c = TestClient(main.app)
    r = c.get("/api/health")
    assert r.status_code == 503
    assert "tekrar deneyin" in r.json()["detail"]
    assert r.headers["retry-after"] == "5"

    state["down"] = False
    r = c.get("/api/health")
    assert r.status_code == 200 and r.json()["db"] is True
    assert db.is_initialized()
