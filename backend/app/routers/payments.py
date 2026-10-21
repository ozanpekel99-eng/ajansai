import logging
import uuid
from decimal import Decimal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, select, update

from app import config
from app.db import get_engine, payments, utcnow
from app.security import get_current_user
from app.services import iyzico_service
from app.services.plans import CURRENCY, get_plan, is_purchasable
from app.services.usage_service import activate_plan

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
    plan_id: str
    billing: BillingInfo


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
    if not is_purchasable(payload.plan_id):
        raise HTTPException(status_code=400, detail="Geçersiz paket.")
    if not iyzico_service.is_configured():
        raise HTTPException(status_code=503, detail="Ödeme sistemi henüz yapılandırılmadı.")

    plan = get_plan(payload.plan_id)
    payment_id = str(uuid.uuid4())
    amount = Decimal(plan["price"])

    with get_engine().begin() as conn:
        conn.execute(
            payments.insert().values(
                id=payment_id,
                user_id=user["id"],
                plan_id=payload.plan_id,
                amount_try=amount,  # sütun adı eski; tutar `currency` biriminde
                currency=CURRENCY,
                status="pending",
                created_at=utcnow(),
            )
        )

    billing = payload.billing.model_dump()
    billing["phone"] = _normalize_phone(billing["phone"])

    try:
        result = iyzico_service.initialize_checkout(
            payment_id=payment_id,
            amount=amount,
            currency=CURRENCY,
            plan_id=payload.plan_id,
            plan_name=plan["name"],
            user=user,
            billing=billing,
            buyer_ip=request.client.host if request.client else "127.0.0.1",
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

    return {"payment_id": payment_id, "payment_page_url": result["payment_page_url"]}


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
        result = iyzico_service.retrieve_checkout(token, payment.id)
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
        activate_plan(payment.user_id, payment.plan_id)
        logger.info("Paket açıldı: kullanıcı=%s paket=%s ödeme=%s", payment.user_id, payment.plan_id, payment.id)

    return _result_redirect(new_status, payment.id)


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
                "plan_name": get_plan(r.plan_id)["name"],
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
            result = iyzico_service.retrieve_checkout(payment.iyzico_token, payment.id)
            # Kullanıcı ödeme sayfasını henüz tamamlamadıysa iyzico sonuç döndürmez; pending kalır.
            if result.get("paymentStatus"):
                _finalize(payment, result)
                with get_engine().connect() as conn:
                    status = conn.execute(select(payments.c.status).where(payments.c.id == payment_id)).scalar_one()
        except iyzico_service.IyzicoError:
            pass

    plan = get_plan(payment.plan_id)
    return {"payment_id": payment_id, "status": status, "plan": payment.plan_id, "plan_name": plan["name"]}
