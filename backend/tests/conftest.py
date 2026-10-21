import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 40)

from app import config  # noqa: E402
from app.db import init_db, metadata, reset_engine, get_engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Her test temiz bir veritabanıyla başlar.

    TEST_DATABASE_URL tanımlıysa (ör. Postgres) o kullanılır, yoksa geçici SQLite.
    """
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}"
    reset_engine(url)
    metadata.drop_all(get_engine())
    init_db()
    # Testler dış servislere gitmesin
    config.OMNIROUTE_BASE_URL = None
    config.ANTHROPIC_API_KEY = None
    config.AI_GATEWAY_ENABLED = False
    config.AI_GATEWAY_API_KEY = None
    config.IYZICO_API_KEY = None
    config.IYZICO_SECRET_KEY = None
    yield
    metadata.drop_all(get_engine())
    reset_engine()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def register(client, email="ozan@example.com", password="gizlisifre123"):
    r = client.post("/api/auth/register", json={"email": email, "password": password, "name": "Ozan"})
    assert r.status_code == 201, r.text
    return r.json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}
