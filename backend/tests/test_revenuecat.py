"""Mobil uygulama içi satın alma: RevenueCat webhook'u."""

import pytest
from sqlalchemy import select

from app import config
from app.db import get_engine, store_events
from app.services import revenuecat

from .conftest import auth, register
from .test_api import _user_id

URL = "/api/payments/revenuecat/webhook"
SECRET = "rc-gizli-deger"


@pytest.fixture
def rc(monkeypatch):
    monkeypatch.setattr(config, "REVENUECAT_WEBHOOK_AUTH", SECRET)
    monkeypatch.setattr(config, "REVENUECAT_PRODUCTS", "")


def _event(user_id, product_id="ajansai_pro_aylik", etype="INITIAL_PURCHASE", eid="ev-1", **kw):
    ev = {
        "id": eid, "type": etype, "app_user_id": user_id, "original_app_user_id": user_id, "aliases": [user_id],
        "product_id": product_id, "store": "APP_STORE", "environment": "PRODUCTION",
        "price_in_purchased_currency": 549.99, "currency": "TRY", "price": 16.5, "transaction_id": "tx1",
    }
    ev.update(kw)
    return {"api_version": "1.0", "event": ev}


def _post(client, body, header=SECRET):
    return client.post(URL, json=body, headers={"Authorization": header} if header is not None else {})


def _plan(client, token):
    return client.get("/api/plans/usage", headers=auth(token)).json()["plan"]


def _credits(client, token):
    return client.get("/api/plans/usage", headers=auth(token)).json()["credits"]


def test_webhook_closed_without_secret(client, monkeypatch):
    monkeypatch.setattr(config, "REVENUECAT_WEBHOOK_AUTH", None)
    assert _post(client, _event("x")).status_code == 503


def test_webhook_rejects_wrong_or_missing_auth(client, rc):
    assert _post(client, _event("x"), header="yanlis").status_code == 401
    assert _post(client, _event("x"), header=None).status_code == 401
    # "Bearer <değer>" biçimi de kabul edilir
    assert _post(client, {"event": {"id": "t", "type": "TEST", "app_user_id": "x"}}, header=f"Bearer {SECRET}").json()["status"] == "test"


def test_subscription_purchase_activates_plan_once(client, rc):
    token = register(client)
    uid = _user_id(client, token)
    r = _post(client, _event(uid))
    assert r.status_code == 200 and r.json()["status"] == "applied"
    assert _plan(client, token) == "pro"
    assert _credits(client, token)["total"] == 500

    # RevenueCat aynı olayı yeniden gönderirse ikinci kez işlenmez
    assert _post(client, _event(uid)).json()["status"] == "duplicate"
    hist = client.get("/api/payments/", headers=auth(token)).json()["payments"]
    assert len(hist) == 1 and hist[0]["status"] == "success" and hist[0]["currency"] == "TRY"
    assert hist[0]["amount"] == 549.99


def test_yearly_and_renewal(client, rc):
    token = register(client)
    uid = _user_id(client, token)
    _post(client, _event(uid, product_id="ajansai_baslangic_yillik"))
    assert _credits(client, token)["total"] == 200 * 12
    assert _post(client, _event(uid, product_id="ajansai_baslangic_yillik", etype="RENEWAL", eid="ev-2")).json()["status"] == "applied"


def test_consumable_credit_pack_adds_extra_credits(client, rc):
    token = register(client)
    uid = _user_id(client, token)
    _post(client, _event(uid))  # önce Pro
    r = _post(client, _event(uid, product_id="ajansai_kredi_250", etype="NON_RENEWING_PURCHASE", eid="ev-k"))
    assert r.json()["status"] == "applied"
    assert _credits(client, token)["extra"] == 250
    assert _post(client, _event(uid, product_id="ajansai_kredi_250", etype="NON_RENEWING_PURCHASE", eid="ev-k")).json()["status"] == "duplicate"
    assert _credits(client, token)["extra"] == 250


def test_unknown_user_product_and_non_grant_events_are_recorded_not_applied(client, rc):
    token = register(client)
    uid = _user_id(client, token)
    assert _post(client, _event("$RCAnonymousID:abc", eid="a")).json()["status"] == "unknown_user"
    assert _post(client, _event("yok-boyle-biri", eid="b", aliases=[])).json()["status"] == "unknown_user"
    assert _post(client, _event(uid, product_id="baska_urun", eid="c")).json()["status"] == "unknown_product"
    assert _post(client, _event(uid, etype="CANCELLATION", eid="d")).json()["status"] == "ignored"
    assert _post(client, _event(uid, etype="EXPIRATION", eid="e")).json()["status"] == "ignored"
    assert _plan(client, token) == "deneme"
    with get_engine().connect() as conn:
        rows = conn.execute(select(store_events.c.event_id, store_events.c.status)).all()
    assert len(rows) == 5
    assert _post(client, {"nope": 1}).json()["status"] == "invalid"


def test_alias_user_id_is_matched(client, rc):
    token = register(client)
    uid = _user_id(client, token)
    body = _event("$RCAnonymousID:zz", original_app_user_id="$RCAnonymousID:zz", aliases=["$RCAnonymousID:zz", uid])
    assert _post(client, body).json()["status"] == "applied"
    assert _plan(client, token) == "pro"


def test_sandbox_purchase_marked(client, rc):
    token = register(client)
    uid = _user_id(client, token)
    _post(client, _event(uid, environment="SANDBOX"))
    from app.db import payments
    with get_engine().connect() as conn:
        assert conn.execute(select(payments.c.sandbox)).scalar_one() is True


def test_product_map_override(monkeypatch):
    monkeypatch.setattr(config, "REVENUECAT_PRODUCTS", '{"ajansai_pro:aylik": "pro:monthly", "x": "deneme:monthly", "y": "kredi_300"}')
    assert revenuecat.resolve_product("ajansai_pro:aylik") == ("pro", "monthly")
    assert revenuecat.resolve_product("ajansai_kredi_100") == ("kredi_100", "credits")
    assert revenuecat.resolve_product("x") is None  # ücretsiz paket satılmaz
    assert revenuecat.resolve_product("y") is None  # satıştan kalkmış kredi paketi
    assert revenuecat.resolve_product("ajansai_baslangic_yillik:yillik") == ("baslangic", "yearly")  # Google Play
    monkeypatch.setattr(config, "REVENUECAT_PRODUCTS", "{bozuk")
    assert revenuecat.resolve_product("ajansai_pro_yillik") == ("pro", "yearly")
