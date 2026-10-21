"""Paket (plan) tanımları — tek doğruluk kaynağı.

Fiyatlar ve kotalar, maliyet analizine göre ~%50 brüt marj hedefiyle belirlendi.
Video/görsel maliyeti: video $0.2875 (Runway Gen-4 Turbo + %15 hata payı),
görsel $0.0525 (Ideogram + %5 hata payı).

Paketler 30 günlük peşin ödemeyle açılır (iyzico). Süre bitince kullanıcı
ücretsiz "deneme" paketine döner. Deneme paketi satın alınamaz; yeni kayıt
olan herkes bununla başlar.
"""

PLANS = {
    "deneme": {
        "name": "Deneme",
        "price_try": 0,
        "price_usd": 0,
        "video_quota": 0,
        "image_quota": 0,
        # Ücretsiz kullanıcıların AI maliyetini sınırlamak için aylık fikir limiti.
        "idea_quota": 10,
        "ideas_unlimited": False,
        "ads_enabled": False,
        "purchasable": False,
    },
    "baslangic": {
        "name": "Başlangıç",
        "price_try": 499,
        "price_usd": 9.99,
        "video_quota": 10,
        "image_quota": 30,
        "idea_quota": None,
        "ideas_unlimited": True,
        "ads_enabled": False,
        "purchasable": True,
    },
    "pro": {
        "name": "Pro",
        "price_try": 1249,
        "price_usd": 26.99,
        "video_quota": 30,
        "image_quota": 60,
        "idea_quota": None,
        "ideas_unlimited": True,
        "ads_enabled": True,
        "purchasable": True,
    },
    "ajans": {
        "name": "Ajans",
        "price_try": 1999,
        "price_usd": 42.99,
        "video_quota": 45,
        "image_quota": 100,
        "idea_quota": None,
        "ideas_unlimited": True,
        "ads_enabled": True,
        "purchasable": True,
    },
}

FREE_PLAN = "deneme"
PLAN_DURATION_DAYS = 30


def get_plan(plan_id: str) -> dict:
    return PLANS.get(plan_id, PLANS[FREE_PLAN])


def is_purchasable(plan_id: str) -> bool:
    return plan_id in PLANS and PLANS[plan_id]["purchasable"]
