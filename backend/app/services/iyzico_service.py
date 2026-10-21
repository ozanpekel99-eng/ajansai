"""iyzico Checkout Form entegrasyonu (resmi SDK yerine doğrudan REST).

Kimlik doğrulama IYZWSv2 (HMAC-SHA256):
    imza = hex(HMACSHA256(secretKey, randomKey + uriPath + body))
    Authorization: IYZWSv2 base64("apiKey:..&randomKey:..&signature:..")

Akış:
1. initialize_checkout  -> iyzico ödeme sayfası adresi (paymentPageUrl) + token
2. Kullanıcı ödemeyi yapar, iyzico callbackUrl'e `token` POST eder
3. retrieve_checkout(token) -> ödemenin gerçek sonucu (sunucudan sunucuya)
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from decimal import Decimal

import requests

from app import config

INIT_PATH = "/payment/iyzipos/checkoutform/initialize/auth/ecom"
RETRIEVE_PATH = "/payment/iyzipos/checkoutform/auth/ecom/detail"


class IyzicoError(Exception):
    pass


class IyzicoUnavailable(IyzicoError):
    """Ağ/bağlantı hatası: ödemenin sonucu bilinmiyor (başarısız sayılmamalı)."""


def is_configured() -> bool:
    return bool(config.IYZICO_API_KEY and config.IYZICO_SECRET_KEY)


def build_auth_headers(uri_path: str, body: str, random_key: str | None = None) -> dict:
    random_key = random_key or f"{int(time.time() * 1000)}{secrets.randbelow(10**9):09d}"
    signature = hmac.new(
        config.IYZICO_SECRET_KEY.encode("utf-8"),
        (random_key + uri_path + body).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    auth = f"apiKey:{config.IYZICO_API_KEY}&randomKey:{random_key}&signature:{signature}"
    return {
        "Authorization": "IYZWSv2 " + base64.b64encode(auth.encode("utf-8")).decode("ascii"),
        "x-iyzi-rnd": random_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _post(path: str, payload: dict, raise_on_failure: bool = True) -> dict:
    if not is_configured():
        raise IyzicoError("Ödeme sistemi henüz yapılandırılmadı.")
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    try:
        response = requests.post(
            config.IYZICO_BASE_URL + path,
            data=body.encode("utf-8"),
            headers=build_auth_headers(path, body),
            timeout=30,
        )
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        raise IyzicoUnavailable("Ödeme sistemine ulaşılamadı, lütfen tekrar dene.") from e

    if raise_on_failure and data.get("status") != "success":
        raise IyzicoError(data.get("errorMessage") or "Ödeme işlemi başlatılamadı.")
    return data


def _money(amount: Decimal) -> str:
    return f"{Decimal(amount):.2f}"


def initialize_checkout(
    *,
    payment_id: str,
    amount_try: Decimal,
    plan_id: str,
    plan_name: str,
    user: dict,
    billing: dict,
    buyer_ip: str,
) -> dict:
    """Ödeme formunu başlatır. {"token", "payment_page_url"} döndürür."""
    price = _money(amount_try)
    contact_name = f"{billing['name']} {billing['surname']}"
    address = {
        "contactName": contact_name,
        "city": billing["city"],
        "country": "Turkey",
        "address": billing["address"],
    }
    payload = {
        "locale": "tr",
        "conversationId": payment_id,
        "price": price,
        "paidPrice": price,
        "currency": "TRY",
        "basketId": payment_id,
        "paymentGroup": "PRODUCT",
        "callbackUrl": f"{config.PUBLIC_API_URL}/api/payments/iyzico/callback",
        "enabledInstallments": [1],
        "buyer": {
            "id": user["id"],
            "name": billing["name"],
            "surname": billing["surname"],
            # TCKN zorunlu alan; kullanıcı girmezse iyzico'nun kabul ettiği
            # genel değer gönderilir (fatura kesilecekse gerçek TCKN alınmalı).
            "identityNumber": billing.get("identity_number") or "11111111111",
            "email": user["email"],
            "gsmNumber": billing["phone"],
            "registrationAddress": billing["address"],
            "city": billing["city"],
            "country": "Turkey",
            "ip": buyer_ip,
        },
        "billingAddress": address,
        "shippingAddress": address,
        "basketItems": [
            {
                "id": plan_id,
                "name": f"ajansAI {plan_name} paketi (30 gün)",
                "category1": "Yazılım",
                "category2": "Abonelik",
                "itemType": "VIRTUAL",
                "price": price,
            }
        ],
    }
    data = _post(INIT_PATH, payload)
    if not data.get("token") or not data.get("paymentPageUrl"):
        raise IyzicoError("Ödeme sayfası oluşturulamadı.")
    return {"token": data["token"], "payment_page_url": data["paymentPageUrl"]}


def retrieve_checkout(token: str, conversation_id: str) -> dict:
    """Ödemenin sonucunu iyzico'dan sorgular (callback'e güvenmek yerine).

    Başarısız ödemelerde de yanıtı döndürür; kararı çağıran taraf verir.
    Yalnızca iyzico'ya ulaşılamazsa IyzicoUnavailable fırlatır.
    """
    return _post(
        RETRIEVE_PATH,
        {"locale": "tr", "conversationId": conversation_id, "token": token},
        raise_on_failure=False,
    )


def is_successful_payment(result: dict, *, payment_id: str, amount_try: Decimal) -> bool:
    """iyzico yanıtının gerçekten bu ödemeye ait başarılı bir ödeme olduğunu doğrular."""
    if result.get("status") != "success" or result.get("paymentStatus") != "SUCCESS":
        return False
    if result.get("basketId") != payment_id:
        return False
    if (result.get("currency") or "TRY") != "TRY":
        return False
    try:
        paid = Decimal(str(result.get("paidPrice")))
    except Exception:
        return False
    return paid >= Decimal(amount_try)
