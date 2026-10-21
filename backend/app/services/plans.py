"""Paket (plan) ve kredi tanımları — tek doğruluk kaynağı.

Her paket 30 günlük bir kredi bakiyesi verir; her üretim işlemi sabit sayıda
kredi düşer. Kredi maliyetleri sağlayıcı maliyetine göre belirlendi
(Vercel AI Gateway fiyatları, Ekim 2026):

- Fikir (Claude Sonnet 5): 2 fikir ≈ $0.006 → her 2 fikir 1 kredi
- Görsel (Seedream 5.0 Pro): $0.035 → 4 kredi
- Video 720p, sessiz (Seedance 1.5 Pro): $0.026/sn → 5 sn 12, 10 sn 24 kredi

Böylece 1 kredinin bize maliyeti en fazla ~$0.011 olur. Paket fiyatları
KDV ve iyzico komisyonu düşüldükten sonra ~%60 brüt marj bırakır.

Deneme paketi satın alınamaz; yeni kayıt olan herkes bununla başlar.
"""

import math

CREDIT_COSTS = {
    "idea_per_2": 1,  # her 2 fikir için
    "image": 4,
    "video_5": 12,
    "video_10": 24,
    "ads_draft": 0,
}

PLANS = {
    "deneme": {
        "name": "Deneme",
        "price_try": 0,
        "price_usd": 0,
        "credits": 20,
        "video_enabled": False,
        "ads_enabled": False,
        "purchasable": False,
    },
    "baslangic": {
        "name": "Başlangıç",
        "price_try": 499,
        "price_usd": 9.99,
        "credits": 300,
        "video_enabled": True,
        "ads_enabled": False,
        "purchasable": True,
    },
    "pro": {
        "name": "Pro",
        "price_try": 1249,
        "price_usd": 26.99,
        "credits": 800,
        "video_enabled": True,
        "ads_enabled": True,
        "purchasable": True,
    },
    "ajans": {
        "name": "Ajans",
        "price_try": 1999,
        "price_usd": 42.99,
        "credits": 1400,
        "video_enabled": True,
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


def idea_cost(count: int) -> int:
    return max(1, math.ceil(count / 2)) * CREDIT_COSTS["idea_per_2"]


def video_cost(duration: int) -> int:
    return CREDIT_COSTS["video_10"] if duration > 5 else CREDIT_COSTS["video_5"]


def public_plan(plan_id: str) -> dict:
    """Arayüze gönderilen paket bilgisi: kredi ve o krediyle neler yapılabileceği."""
    p = get_plan(plan_id)
    c = p["credits"]
    return {
        "id": plan_id,
        "name": p["name"],
        "price_try": p["price_try"],
        "price_usd": p["price_usd"],
        "credits": c,
        "video_enabled": p["video_enabled"],
        "ads_enabled": p["ads_enabled"],
        # "Bu krediyle yalnızca X yaparsan" örnekleri
        "examples": {
            "ideas": c // CREDIT_COSTS["idea_per_2"] * 2,
            "images": c // CREDIT_COSTS["image"],
            "videos_5": c // CREDIT_COSTS["video_5"] if p["video_enabled"] else 0,
            "videos_10": c // CREDIT_COSTS["video_10"] if p["video_enabled"] else 0,
        },
    }
