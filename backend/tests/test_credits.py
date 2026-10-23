from datetime import timedelta

from sqlalchemy import update

from app import config
from app.db import get_engine, users, utcnow
from app.services import usage_service

from .conftest import auth, register
from .test_api import _user_id, register_paid


def _pay(client, monkeypatch, token, plan_id, cycle="monthly", tok="t1"):
    from app.routers import payments as pr

    monkeypatch.setattr(config, "IYZICO_API_KEY", "k")
    monkeypatch.setattr(config, "IYZICO_SECRET_KEY", "s")
    sent = {}
    monkeypatch.setattr(pr.iyzico_service, "initialize_checkout", lambda **kw: sent.update(kw) or {"token": tok, "payment_page_url": "u"})
    monkeypatch.setattr(pr.iyzico_service, "retrieve_checkout", lambda t, c, sandbox=False: {"paymentStatus": "SUCCESS", "paymentId": "p"})
    monkeypatch.setattr(pr.iyzico_service, "is_successful_payment", lambda result, **kw: True)
    billing = {"name": "Ozan", "surname": "P", "phone": "05350000000", "city": "Tekirdağ", "address": "Çorlu merkez 1"}
    r = client.post("/api/payments/checkout", json={"plan_id": plan_id, "cycle": cycle, "billing": billing}, headers=auth(token))
    if r.status_code != 200:
        return r, sent
    client.post("/api/payments/iyzico/callback", data={"token": tok}, follow_redirects=False)
    return r, sent


def test_yearly_credits_loaded_once_and_not_reset_monthly(client, monkeypatch):
    token = register(client)
    _pay(client, monkeypatch, token, "pro", "yearly")
    uid = _user_id(client, token)
    usage_service.consume(uid, "image", 4, "x")
    # 40 gün sonra: aylık dönem dolsa da yıllık kredi yenilenmez/silinmez
    with get_engine().begin() as conn:
        conn.execute(update(users).where(users.c.id == uid).values(period_start=utcnow() - timedelta(days=40)))
    c = client.get("/api/plans/usage", headers=auth(token)).json()["credits"]
    assert c["total"] == 6000 and c["used"] == 4


def test_credit_packs_require_paid_plan_and_are_used_after_period_credits(client, monkeypatch):
    assert [p["id"] for p in client.get("/api/payments/packs").json()["packs"]] == ["kredi_100", "kredi_250", "kredi_500"]
    q = client.get("/api/payments/quote", params={"plan_id": "kredi_250"}).json()
    assert q["net"] == 12.0 and q["total"] == 14.4
    assert client.get("/api/payments/quote", params={"plan_id": "kredi_300"}).status_code == 400  # satıştan kalktı

    free = register(client, email="free@ornek.com")
    r, _ = _pay(client, monkeypatch, free, "kredi_100")
    assert r.status_code == 400

    token = register_paid(client, plan="baslangic")
    r, sent = _pay(client, monkeypatch, token, "kredi_100", tok="t2")
    assert r.status_code == 200 and sent["plan_name"] == "100 ek kredi" and str(sent["amount"]) == "6.0"
    c = client.get("/api/plans/usage", headers=auth(token)).json()["credits"]
    assert c["extra"] == 100 and c["remaining"] == 300

    uid = _user_id(client, token)
    usage_service.consume(uid, "image", 198, "x")  # dönemde 2 kredi kalır
    ev = usage_service.consume(uid, "video", 12, "y")  # 2 dönem + 10 ek
    c = client.get("/api/plans/usage", headers=auth(token)).json()["credits"]
    assert c["used"] == 200 and c["extra"] == 90 and c["remaining"] == 90
    usage_service.refund(ev)
    c = client.get("/api/plans/usage", headers=auth(token)).json()["credits"]
    assert c["used"] == 198 and c["extra"] == 100
    # Dönem yenilense de ek kredi kalır
    with get_engine().begin() as conn:
        conn.execute(update(users).where(users.c.id == uid).values(period_start=utcnow() - timedelta(days=31)))
    c = client.get("/api/plans/usage", headers=auth(token)).json()["credits"]
    assert c["used"] == 0 and c["extra"] == 100
