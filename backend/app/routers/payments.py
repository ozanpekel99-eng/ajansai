import logging
import uuid
from decimal import Decimal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, select, update

from app import config
from app.db import get_engine, payments, utcnow
from app.security import get_current_user
from app.services import fx, iyzico_service, revenuecat
from typing import Literal

from app.services.plans import (
    ALL_PACKS, BILLING_CYCLES, CURRENCY, FREE_PLAN, get_plan, is_credit_pack, is_purchasable, is_sellable_pack, item_name,
    price_breakdown, public_packs,
)
from app.services.usage_service import activate_plan, add_extra_credits, get_user

router = APIRouter()
logger = logging.getLogger("ajansai.payments")


class BillingInfo(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    surname: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=10, max_length=20, examples=["+905350000000"])
    city: str = Field(..., min_length=2, max_length=100)
    address: str = Field(..., min_length=5, max_length=500)
    identity_number: str | None = Field(None, pattern=r"^\d{11}$")


class CheckoutRequest(BaseModel):
    plan_id: str  # paket id'si ya da ek kredi paketi (kredi_100, kredi_250, kredi_500)
    cycle: Literal["monthly", "yearly"] = "monthly"
    billing: BillingInfo


@router.get("/packs")
def packs():
    """Ek kredi paketleri."""
    return {"packs": public_packs()}


@router.get("/quote")
def quote(plan_id: str, cycle: Literal["monthly", "yearly"] = "monthly"):
    """Ödeme ekranındaki özet: KDV hariç tutar, KDV ve toplam."""
    if not (is_purchasable(plan_id) or is_sellable_pack(plan_id)):
        raise HTTPException(status_code=400, detail="Geçersiz paket.")
    prices = price_breakdown(plan_id, cycle)
    out = {"plan_id": plan_id, "cycle": cycle, **prices}
    try:
        out["charge"] = _charge_amount(prices)
    except fx.FxError:
        out["charge"] = None
    return out


def _charge_amount(prices: dict) -> dict:
    """Karttan çekilecek tutar: USD fiyat, tahsilat TL ise TCMB kuruyla TL'ye çevrilir."""
    if config.PAYMENT_CURRENCY == "TRY" and prices["currency"] == "USD":
        rate = fx.usd_try_rate()
        return {"amount": float(fx.to_try(prices["total"])), "currency": "TRY", "rate": float(rate)}
    return {"amount": prices["total"], "currency": prices["currency"], "rate": None}


def _normalize_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if digits.startswith("90") and len(digits) == 12:
        return "+" + digits
    if digits.startswith("0") and len(digits) == 11:
        return "+9" + digits
    if len(digits) == 10:
        return "+90" + digits
    return "+" + digits


@router.post("/checkout")
def checkout(payload: CheckoutRequest, request: Request, user: dict = Depends(get_current_user)):
    """Seçilen paket için iyzico ödeme sayfasını başlatır ve adresini döndürür."""
    pack = is_sellable_pack(payload.plan_id)
    if not (is_purchasable(payload.plan_id) or pack):
        raise HTTPException(status_code=400, detail="Geçersiz paket.")
    if pack and get_user(user["id"])["plan"] == FREE_PLAN:
        raise HTTPException(status_code=400, detail="Ek kredi, ücretli bir paketin varken alınabilir. Önce bir paket seç.")
    # Yönetici hesapları sandbox anahtarları tanımlıysa test ödemesi yapar (gerçek para çekilmez).
    sandbox = (user.get("email") or "").lower() in config.ADMIN_EMAILS and iyzico_service.is_configured(sandbox=True)
    if not iyzico_service.is_configured(sandbox):
        raise HTTPException(status_code=503, detail="Ödeme sistemi henüz yapılandırılmadı.")

    cycle = "credits" if pack else payload.cycle
    payment_id = str(uuid.uuid4())
    prices = price_breakdown(payload.plan_id, payload.cycle)
    try:
        charge = _charge_amount(prices)
    except fx.FxError as e:
        raise HTTPException(status_code=503, detail=str(e))
    amount = Decimal(str(charge["amount"]))  # KDV dahil tahsil edilen tutar (tahsilat biriminde)
    currency = charge["currency"]

    with get_engine().begin() as conn:
        conn.execute(
            payments.insert().values(
                id=payment_id,
                user_id=user["id"],
                plan_id=payload.plan_id,
                amount_try=amount,  # sütun adı eski; tutar `currency` biriminde
                currency=currency,
                billing=cycle,
                status="pending",
                created_at=utcnow(),
                sandbox=sandbox,
            )
        )

    billing = payload.billing.model_dump()
    billing["phone"] = _normalize_phone(billing["phone"])

    try:
        result = iyzico_service.initialize_checkout(
            payment_id=payment_id,
            amount=amount,
            currency=currency,
            plan_id=payload.plan_id,
            plan_name=item_name(payload.plan_id) if pack else f'{get_plan(payload.plan_id)["name"]} ({"yıllık" if payload.cycle == "yearly" else "aylık"})',
            user=user,
            billing=billing,
            buyer_ip=request.client.host if request.client else "127.0.0.1",
            sandbox=sandbox,
        )
    except iyzico_service.IyzicoError as e:
        with get_engine().begin() as conn:
            conn.execute(
                update(payments)
                .where(payments.c.id == payment_id)
                .values(status="failure", error=str(e)[:500], completed_at=utcnow())
            )
        raise HTTPException(status_code=502, detail=str(e))

    with get_engine().begin() as conn:
        conn.execute(update(payments).where(payments.c.id == payment_id).values(iyzico_token=result["token"]))

    return {"payment_id": payment_id, "payment_page_url": result["payment_page_url"], "sandbox": sandbox}


def _result_redirect(status: str, payment_id: str | None = None) -> RedirectResponse:
    query = {"status": status}
    if payment_id:
        query["payment_id"] = payment_id
    return RedirectResponse(f"{config.WEB_URL}/payment/result?{urlencode(query)}", status_code=303)


@router.post("/iyzico/callback", include_in_schema=False)
def iyzico_callback(token: str = Form(...)):
    """iyzico, ödeme bitince kullanıcının tarayıcısı üzerinden buraya `token` gönderir.

    Bu isteğe güvenmiyoruz: token ile ödemenin sonucunu iyzico'ya sunucudan
    sunucuya soruyor, tutarı ve sepet kimliğini kontrol ediyoruz. Paket yalnızca
    ödeme doğrulanırsa açılır. Aynı token iki kez gelse bile paket bir kez açılır.
    """
    with get_engine().connect() as conn:
        payment = conn.execute(select(payments).where(payments.c.iyzico_token == token)).first()

    if payment is None:
        return _result_redirect("failure")
    if payment.status != "pending":
        return _result_redirect(payment.status, payment.id)

    try:
        result = iyzico_service.retrieve_checkout(token, payment.id, sandbox=bool(payment.sandbox))
    except iyzico_service.IyzicoError as e:
        # Sonuç bilinmiyor; ödeme 'pending' kalır, kullanıcı sonuç sayfasında tekrar sorgulayabilir.
        logger.error("iyzico sonucu sorgulanamadı (%s): %s", payment.id, e)
        return _result_redirect("pending", payment.id)

    return _finalize(payment, result)


def _finalize(payment, result: dict) -> RedirectResponse:
    success = iyzico_service.is_successful_payment(
        result, payment_id=payment.id, amount=Decimal(payment.amount_try), currency=payment.currency or "TRY"
    )
    new_status = "success" if success else "failure"

    with get_engine().begin() as conn:
        changed = conn.execute(
            update(payments)
            .where(and_(payments.c.id == payment.id, payments.c.status == "pending"))
            .values(
                status=new_status,
                iyzico_payment_id=result.get("paymentId"),
                error=None if success else (result.get("errorMessage") or result.get("paymentStatus") or "")[:500],
                completed_at=utcnow(),
            )
        ).rowcount

    if changed and success:
        cycle = getattr(payment, "billing", None) or "monthly"
        if is_credit_pack(payment.plan_id):
            add_extra_credits(payment.user_id, ALL_PACKS[payment.plan_id]["credits"])
            logger.info("Ek kredi yüklendi: kullanıcı=%s paket=%s ödeme=%s", payment.user_id, payment.plan_id, payment.id)
        else:
            activate_plan(payment.user_id, payment.plan_id, BILLING_CYCLES.get(cycle, BILLING_CYCLES["monthly"])["days"], cycle)
            logger.info("Paket açıldı: kullanıcı=%s paket=%s ödeme=%s", payment.user_id, payment.plan_id, payment.id)

    return _result_redirect(new_status, payment.id)


@router.post("/revenuecat/webhook", include_in_schema=False)
async def revenuecat_webhook(request: Request):
    """Mobil uygulama içi satın alma olayları (RevenueCat → App Store / Google Play).

    `REVENUECAT_WEBHOOK_AUTH` tanımlı değilse kapalıdır. Authorization başlığı panelde girilen
    değerle eşleşmezse reddedilir. Aynı olay tekrar gelirse paket/kredi ikinci kez yüklenmez.
    """
    if not revenuecat.is_configured():
        raise HTTPException(status_code=503, detail="Uygulama içi satın alma henüz yapılandırılmadı.")
    try:
        revenuecat.check_auth(request.headers.get("authorization"))
    except revenuecat.WebhookAuthError:
        raise HTTPException(status_code=401, detail="Yetkisiz.")
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz istek.")
    return await run_in_threadpool(revenuecat.handle_event, body)


@router.get("/")
def list_payments(user: dict = Depends(get_current_user)):
    """Kullanıcının ödeme geçmişi (en yeni önce, son 50)."""
    with get_engine().connect() as conn:
        rows = conn.execute(
            select(payments)
            .where(payments.c.user_id == user["id"])
            .order_by(payments.c.created_at.desc())
            .limit(50)
        ).all()
    return {
        "payments": [
            {
                "payment_id": r.id,
                "plan": r.plan_id,
                "plan_name": item_name(r.plan_id, r.billing or "monthly"),
                "amount": float(r.amount_try),
                "currency": r.currency or "TRY",
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }


@router.get("/{payment_id}")
def payment_status(payment_id: str, user: dict = Depends(get_current_user)):
    """Ödeme sonuç sayfası için durum. 'pending' kaldıysa iyzico'ya tekrar sorar."""
    with get_engine().connect() as conn:
        payment = conn.execute(
            select(payments).where(and_(payments.c.id == payment_id, payments.c.user_id == user["id"]))
        ).first()
    if payment is None:
        raise HTTPException(status_code=404, detail="Ödeme bulunamadı.")

    status = payment.status
    if status == "pending" and payment.iyzico_token:
        try:
            result = iyzico_service.retrieve_checkout(payment.iyzico_token, payment.id, sandbox=bool(payment.sandbox))
            # Kullanıcı ödeme sayfasını henüz tamamlamadıysa iyzico sonuç döndürmez; pending kalır.
            if result.get("paymentStatus"):
                _finalize(payment, result)
                with get_engine().connect() as conn:
                    status = conn.execute(select(payments.c.status).where(payments.c.id == payment_id)).scalar_one()
        except iyzico_service.IyzicoError:
            pass

    return {"payment_id": payment_id, "status": status, "plan": payment.plan_id,
            "plan_name": item_name(payment.plan_id, payment.billing or "monthly"),
            "amount": float(payment.amount_try), "currency": payment.currency or "TRY"}
