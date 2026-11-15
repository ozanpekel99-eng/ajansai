"""Mobil uygulama içi satın alma (App Store / Google Play) — RevenueCat webhook işleme.

Mobil uygulama RevenueCat'e `Purchases.logIn(<ajansAI kullanıcı id>)` ile giriş yapar; böylece
webhook olaylarındaki `app_user_id` doğrudan bizim kullanıcı kimliğimizdir. Mağaza ürün kimliği
web'deki paketlere eşlenir; paket/kredi web'deki iyzico ödemesiyle aynı fonksiyonlarla açılır.

Her olay `store_events` tablosuna event_id ile yazılır; aynı olay tekrar gelirse (RevenueCat
200 alamazsa yeniden dener) ikinci kez paket/kredi yüklenmez.
"""

import hmac
import json
import logging
import uuid
from decimal import Decimal, InvalidOperation

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app import config
from app.db import get_engine, payments, store_events, users, utcnow
from app.services.plans import ALL_PACKS, BILLING_CYCLES, CREDIT_PACKS, is_credit_pack, is_purchasable
from app.services.usage_service import activate_plan, add_extra_credits

logger = logging.getLogger("ajansai.revenuecat")

# Mağazalarda açılacak ürün kimlikleri (App Store ve Play'de aynı ad kullanılırsa tek satır yeter).
# Değer: "paket:dönem" (abonelik) ya da ek kredi paketi kimliği (tüketilebilir ürün).
DEFAULT_PRODUCTS = {
    "ajansai_baslangic_aylik": "baslangic:monthly",
    "ajansai_baslangic_yillik": "baslangic:yearly",
    "ajansai_pro_aylik": "pro:monthly",
    "ajansai_pro_yillik": "pro:yearly",
    "ajansai_advanced_aylik": "ajans:monthly",
    "ajansai_advanced_yillik": "ajans:yearly",
    "ajansai_kredi_100": "kredi_100",
    "ajansai_kredi_250": "kredi_250",
    "ajansai_kredi_500": "kredi_500",
}

# Paketi açan / krediyi yükleyen olaylar. İptal ve süre bitimi şimdilik yalnızca kaydedilir:
# paket zaten `plan_expires_at` gelince kendiliğinden ücretsiz pakete döner.
GRANT_TYPES = {"INITIAL_PURCHASE", "RENEWAL", "NON_RENEWING_PURCHASE"}


class WebhookAuthError(Exception):
    pass


def is_configured() -> bool:
    return bool(config.REVENUECAT_WEBHOOK_AUTH)


def check_auth(header: str | None) -> None:
    """RevenueCat, panelde girilen değeri olduğu gibi Authorization başlığında gönderir."""
    secret = config.REVENUECAT_WEBHOOK_AUTH or ""
    got = (header or "").strip()
    if got.lower().startswith("bearer ") and not secret.lower().startswith("bearer "):
        got = got[7:].strip()
    if not secret or not hmac.compare_digest(got.encode(), secret.encode()):
        raise WebhookAuthError()


def product_map() -> dict[str, str]:
    mapping = dict(DEFAULT_PRODUCTS)
    raw = (config.REVENUECAT_PRODUCTS or "").strip()
    if raw:
        try:
            extra = json.loads(raw)
            if isinstance(extra, dict):
                mapping.update({str(k): str(v) for k, v in extra.items()})
        except ValueError:
            logger.error("REVENUECAT_PRODUCTS geçerli JSON değil; varsayılan eşleşme kullanılıyor.")
    return mapping


def resolve_product(product_id: str | None) -> tuple[str, str] | None:
    """Ürün kimliği → (plan_id, billing). billing: monthly | yearly | credits. Bilinmiyorsa None."""
    if not product_id:
        return None
    mapping = product_map()
    target = mapping.get(product_id)
    if target is None and ":" in product_id:
        # Google Play abonelikleri RevenueCat'e "<abonelik kimliği>:<temel plan>" olarak gelir.
        target = mapping.get(product_id.split(":", 1)[0])
    if target is None:
        return None
    if target in CREDIT_PACKS:
        return target, "credits"
    plan_id, _, cycle = target.partition(":")
    cycle = cycle or "monthly"
    if is_purchasable(plan_id) and cycle in BILLING_CYCLES:
        return plan_id, cycle
    return None


def _find_user(event: dict) -> str | None:
    """app_user_id, original_app_user_id ve aliases içinden ajansAI kullanıcısını bulur."""
    candidates = [event.get("app_user_id"), event.get("original_app_user_id"), *(event.get("aliases") or [])]
    ids = [c for c in dict.fromkeys(candidates) if isinstance(c, str) and c and not c.startswith("$RCAnonymousID")]
    if not ids:
        return None
    with get_engine().connect() as conn:
        rows = conn.execute(select(users.c.id).where(users.c.id.in_(ids))).scalars().all()
    for c in ids:  # app_user_id öncelikli
        if c in rows:
            return c
    return None


def _amount(event: dict) -> tuple[Decimal, str]:
    raw = event.get("price_in_purchased_currency")
    currency = event.get("currency")
    if raw is None:
        raw, currency = event.get("price"), "USD"
    try:
        amount = Decimal(str(raw if raw is not None else 0)).quantize(Decimal("0.01"))
    except InvalidOperation:
        amount = Decimal("0")
    return max(amount, Decimal("0")), (str(currency or "USD")[:3].upper())


def handle_event(body: dict) -> dict:
    """Webhook gövdesini işler. Dönen sözlük yanıt olarak verilir (her zaman 200)."""
    event = body.get("event") if isinstance(body, dict) else None
    if not isinstance(event, dict) or not event.get("id"):
        return {"ok": False, "status": "invalid"}

    event_id = str(event["id"])[:100]
    etype = str(event.get("type") or "")[:40]
    product_id = event.get("product_id")
    if etype == "TEST":
        logger.info("RevenueCat test olayı alındı: %s", event_id)
        return {"ok": True, "status": "test"}

    user_id = _find_user(event)
    product = resolve_product(product_id)
    if etype not in GRANT_TYPES:
        status = "ignored"
    elif user_id is None:
        status = "unknown_user"
    elif product is None:
        status = "unknown_product"
    else:
        status = "applied"

    sandbox = str(event.get("environment") or "").upper() == "SANDBOX"
    payment_id = str(uuid.uuid4()) if status == "applied" else None
    now = utcnow()
    try:
        with get_engine().begin() as conn:
            conn.execute(
                store_events.insert().values(
                    event_id=event_id,
                    type=etype or "?",
                    app_user_id=str(event.get("app_user_id") or "")[:200],
                    user_id=user_id,
                    product_id=(str(product_id)[:200] if product_id else None),
                    store=(str(event.get("store"))[:30] if event.get("store") else None),
                    environment=(str(event.get("environment"))[:20] if event.get("environment") else None),
                    status=status,
                    payment_id=payment_id,
                    created_at=now,
                )
            )
            if status == "applied":
                plan_id, billing = product
                amount, currency = _amount(event)
                conn.execute(
                    payments.insert().values(
                        id=payment_id,
                        user_id=user_id,
                        plan_id=plan_id,
                        amount_try=amount,  # sütun adı eski; tutar `currency` biriminde
                        currency=currency,
                        billing=billing,
                        status="success",
                        error=f"store:{event.get('store') or '?'} tx:{event.get('transaction_id') or '?'}"[:500],
                        created_at=now,
                        completed_at=now,
                        sandbox=sandbox,
                    )
                )
    except IntegrityError:
        logger.info("RevenueCat olayı zaten işlenmiş: %s", event_id)
        return {"ok": True, "status": "duplicate"}

    if status == "applied":
        plan_id, billing = product
        try:
            if is_credit_pack(plan_id):
                add_extra_credits(user_id, ALL_PACKS[plan_id]["credits"])
            else:
                activate_plan(user_id, plan_id, BILLING_CYCLES[billing]["days"], billing)
        except Exception:
            # Kaydı geri al: yanıt 500 olur, RevenueCat olayı yeniden gönderir ve tekrar denenir.
            with get_engine().begin() as conn:
                conn.execute(delete(store_events).where(store_events.c.event_id == event_id))
                conn.execute(delete(payments).where(payments.c.id == payment_id))
            raise
        logger.info("Mağaza satın alması uygulandı: kullanıcı=%s paket=%s (%s) olay=%s", user_id, plan_id, billing, event_id)
    elif status in ("unknown_user", "unknown_product"):
        logger.error("RevenueCat olayı uygulanamadı (%s): olay=%s ürün=%s kullanıcı=%s",
                     status, event_id, product_id, event.get("app_user_id"))
    return {"ok": True, "status": status}

