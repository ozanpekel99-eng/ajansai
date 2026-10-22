"""Paket (plan) ve kredi tanımları — tek doğruluk kaynağı.

Her paket 30 günlük bir kredi bakiyesi verir; her üretim işlemi sabit sayıda
kredi düşer. Kredi maliyetleri sağlayıcı maliyetine göre belirlendi
(Vercel AI Gateway fiyatları, Ekim 2026); 1 kredi ≈ en fazla $0.011 maliyet:

- Fikir (Claude Haiku 5.5): 2 fikir ≈ $0.001 → her 2 fikir 1 kredi
- Görsel (Seedream 5.0 Pro): $0.035 → 4 kredi
- Sohbet mesajı (Claude Haiku 5.5 / video ekinde Gemini 3.6 Flash): ≈ $0.001 → 1 kredi, her ek +1
  (ücretsiz pakette Groq/Cerebras ücretsiz katmanları, $0)
- Video 720p (Seedance 1.5 Pro): sessiz $0.0259/sn, sesli $0.0518/sn
- Video 1080p (Seedance 1.5 Pro): sessiz $0.0583/sn, sesli $0.1166/sn
- Video 4K (Seedance 2.0): token ile ücretlenir, $4 / 1M token;
  token = 3840×2160×24 fps×sn / 1024 ≈ 194.400/sn → ≈ $0.78/sn (en kötü durum)

Paketler $10 / $20 / $30 (aylık) + %20 KDV; yıllıkta %20 indirim, kredi her 30 günde yenilenir.
Ücretsiz paket (id: deneme) satın alınamaz; yeni kayıt olan herkes bununla başlar.
"""

import math

VIDEO_DURATIONS = (5, 7, 10)
VIDEO_RESOLUTIONS = ("720p", "1080p", "4k")

CREDIT_COSTS = {
    "idea_per_2": 1,  # her 2 fikir için (eski form akışı)
    "chat_message": 1,  # fikir sohbetinde her mesaj
    "chat_attachment": 1,  # mesaja eklenen her dosya
    "chat_pdf_pages": 10,  # PDF ekinde her 10 sayfa 1 kredi (ilk 10 sayfa eke dahil)
    "describe": 1,  # örnek görsel/videodan konsept çıkarma
    "image": 4,
    "ads_draft": 0,
    # çözünürlük → süre (sn) → kredi
    "video": {
        "720p": {"5": 12, "7": 17, "10": 24},
        "1080p": {"5": 27, "7": 37, "10": 53},
        "4k": {"5": 355, "7": 495, "10": 710},
    },
    # sesli video (4K'da ses fiyatı değişmez)
    "video_audio": {
        "720p": {"5": 24, "7": 34, "10": 48},
        "1080p": {"5": 53, "7": 75, "10": 106},
        "4k": {"5": 355, "7": 495, "10": 710},
    },
}

PLANS = {
    # Ücretsiz paket: kredi yok; Haiku ile fikir sohbeti, ayda 6 ücretsiz AI görseli ve
    # stok fotoğraf kütüphanesi kredisiz kullanılır (bkz. services/free_tier.py).
    "deneme": {
        "name": "Ücretsiz",
        "price": 0,
        "credits": 0,
        "video_enabled": False,
        "ads_enabled": False,
        "purchasable": False,
    },
    "baslangic": {
        "name": "Başlangıç",
        "price": 10,
        "credits": 200,
        "video_enabled": True,
        "ads_enabled": False,
        "purchasable": True,
    },
    "pro": {
        "name": "Pro",
        "price": 20,
        "credits": 500,
        "video_enabled": True,
        "ads_enabled": True,
        "purchasable": True,
    },
    # id "ajans" eski kayıtlarla uyum için korunuyor; görünen adı Advanced
    "ajans": {
        "name": "Advanced",
        "price": 30,
        "credits": 1000,
        "video_enabled": True,
        "ads_enabled": True,
        "purchasable": True,
    },
}

# Paketler dolar cinsinden satılır; iyzico ödemeyi USD olarak alır
# (iyzico üye işyeri hesabında döviz ile ödeme açık olmalı).
CURRENCY = "USD"

FREE_PLAN = "deneme"
PLAN_DURATION_DAYS = 30

# Fiyatlar KDV hariçtir; ödemede KDV eklenerek tahsil edilir.
VAT_RATE = 20  # %
BILLING_CYCLES = {
    "monthly": {"days": 30, "months": 1, "discount": 0},
    "yearly": {"days": 365, "months": 12, "discount": 20},  # %20 indirim
}


def get_plan(plan_id: str) -> dict:
    return PLANS.get(plan_id, PLANS[FREE_PLAN])


def is_purchasable(plan_id: str) -> bool:
    return plan_id in PLANS and PLANS[plan_id]["purchasable"]


def idea_cost(count: int) -> int:
    return max(1, math.ceil(count / 2)) * CREDIT_COSTS["idea_per_2"]


def video_cost(duration: int, resolution: str = "720p", audio: bool = False) -> int:
    return CREDIT_COSTS["video_audio" if audio else "video"][resolution][str(duration)]


def pdf_extra_credits(pages: int) -> int:
    """İlk 10 sayfa ek ücretine dahil; sonraki her 10 sayfa +1 kredi."""
    per = CREDIT_COSTS["chat_pdf_pages"]
    return max(0, math.ceil(pages / per) - 1)


def chat_cost(attachments: int, pdf_pages: list[int] | None = None) -> int:
    extra = sum(pdf_extra_credits(p) for p in (pdf_pages or []))
    return CREDIT_COSTS["chat_message"] + attachments * CREDIT_COSTS["chat_attachment"] + extra


def cycle_price(plan_id: str, billing: str = "monthly") -> float:
    """KDV hariç dönem fiyatı (yıllıkta 12 ay × %20 indirim)."""
    c = BILLING_CYCLES[billing]
    return round(get_plan(plan_id)["price"] * c["months"] * (100 - c["discount"]) / 100, 2)


def price_breakdown(plan_id: str, billing: str = "monthly") -> dict:
    net = cycle_price(plan_id, billing)
    vat = round(net * VAT_RATE / 100, 2)
    return {"net": net, "vat": vat, "vat_rate": VAT_RATE, "total": round(net + vat, 2), "currency": CURRENCY}


def public_plan(plan_id: str) -> dict:
    """Arayüze gönderilen paket bilgisi: kredi ve o krediyle neler yapılabileceği."""
    p = get_plan(plan_id)
    c = p["credits"]
    return {
        "id": plan_id,
        "name": p["name"],
        "price": p["price"],
        "currency": CURRENCY,
        "price_yearly": cycle_price(plan_id, "yearly") if p["price"] else 0,
        "yearly_discount": BILLING_CYCLES["yearly"]["discount"],
        "vat_rate": VAT_RATE,
        "credits": c,
        "video_enabled": p["video_enabled"],
        "ads_enabled": p["ads_enabled"],
        # "Bu krediyle yalnızca X yaparsan" örnekleri
        "examples": {
            "messages": c // CREDIT_COSTS["chat_message"],  # dosyasız fikir sohbeti mesajı
            "images": c // CREDIT_COSTS["image"],
            # 5 sn videolar, çözünürlüğe göre
            "videos": {
                res: (c // video_cost(5, res) if p["video_enabled"] else 0) for res in VIDEO_RESOLUTIONS
            },
        },
    }
