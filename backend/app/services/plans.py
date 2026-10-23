"""Paket (plan) ve kredi tanımları — tek doğruluk kaynağı.

Her paket 30 günlük bir kredi bakiyesi verir; her üretim işlemi sabit sayıda
kredi düşer. Kredi maliyetleri sağlayıcı maliyetine göre belirlendi
(Vercel AI Gateway fiyatları, Ekim 2026); 1 kredi ≈ en fazla $0.011 maliyet:

- Fikir (Claude Haiku 5.5): 2 fikir ≈ $0.001 → her 2 fikir 1 kredi
- Görsel (Seedream 5.0 Pro): $0.035 → 4 kredi
- Sohbet mesajı (Claude Sonnet 5.5, $2/$10 per 1M token; video ekinde Gemini 3.6 Flash): tipik ≈ $0.01-0.02
  → 1 kredi, her ek +1. Kredinin en düşük satış değeri $0.03 (Advanced), marj korunur.
  (ücretsiz pakette Claude Haiku 5.5, günlük bütçe dolunca Groq/Cerebras ücretsiz katmanları)
- Video 720p (Seedance 1.5 Pro): sessiz $0.0259/sn, sesli $0.0518/sn
- Video 1080p (Seedance 1.5 Pro): sessiz $0.0583/sn, sesli $0.1166/sn
- Video 4K (Seedance 2.0): token ile ücretlenir, $4 / 1M token;
  token = 3840×2160×24 fps×sn / 1024 ≈ 194.400/sn → ≈ $0.78/sn (en kötü durum)

Paketler $10 / $20 / $30 (aylık) + %20 KDV; yıllıkta %20 indirim, kredi her 30 günde yenilenir.
Ücretsiz paket (id: deneme) satın alınamaz; yeni kayıt olan herkes bununla başlar.
"""

import math

VIDEO_DURATIONS = (4, 6, 8)
VIDEO_RESOLUTIONS = ("1080p", "4k")  # 720p kaldırıldı: tüm videolar kaliteli modelle (Veo 3.1 Fast)

CREDIT_COSTS = {
    "idea_per_2": 1,  # her 2 fikir için (eski form akışı)
    "chat_message": 1,  # fikir sohbetinde her mesaj
    "chat_attachment": 1,  # mesaja eklenen her dosya
    "chat_pdf_pages": 10,  # PDF ekinde her 10 sayfa 1 kredi (ilk 10 sayfa eke dahil)
    "describe": 1,  # örnek görsel/videodan konsept çıkarma
    "image": 4,
    "file": 3,  # sohbetten sunum / belge / tablo dosyası (Claude ile tasarımlı içerik)
    "ads_draft": 0,
    # çözünürlük → süre (sn) → kredi. Veo 3.1 maliyeti: 720p (Lite) $0,03/sn, 1080p (Fast) $0,10/sn,
    # 4K $0,30/sn; sesli: $0,05 / $0,15 / $0,35. Kredi ~$0,04 → en az ~2,4 kat pay.
    "video": {
        "720p": {"4": 25, "6": 36, "8": 48},  # eski istekler 1080p olarak işlenir
        "1080p": {"4": 25, "6": 36, "8": 48},
        "4k": {"4": 72, "6": 108, "8": 144},
    },
    # sesli video
    "video_audio": {
        "720p": {"4": 36, "6": 54, "8": 72},
        "1080p": {"4": 36, "6": 54, "8": 72},
        "4k": {"4": 84, "6": 126, "8": 168},
    },
}

PLANS = {
    # Ücretsiz paket: kredi yok; Claude Haiku ile sohbet (günde 10 mesaj), ayda 3 AI görseli ve
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
        "credits": 900,
        "video_enabled": True,
        "ads_enabled": True,
        "purchasable": True,
    },
}

# Ek kredi paketleri (KDV hariç, USD). Dönem kredisi bitince kullanılır; dönem yenilense de silinmez.
# Fiyatlar paket içi kredi fiyatının üstünde tutulur (paket yükseltmek hep daha avantajlı kalsın)
# ve en pahalı işlemin kredi başı maliyetini (~$0.011; 2027 ses fiyatıyla ~$0.016) rahatça karşılar.
CREDIT_PACKS = {
    # Kredi başı fiyat her zaman paket içi fiyatın (Başlangıç $0.050, Pro $0.040, Advanced $0.033) üstünde
    # ya da eşit kalır; ortalama maliyet ~$0.017/kredi (en kötü ~$0.021) ile marj %55-60.
    "kredi_100": {"name": "100 ek kredi", "credits": 100, "price": 5},  # $0.050 / kredi
    "kredi_250": {"name": "250 ek kredi", "credits": 250, "price": 12},  # $0.048 / kredi
    "kredi_500": {"name": "500 ek kredi", "credits": 500, "price": 22},  # $0.044 / kredi
}

# Satıştan kalkmış paketler: yarım kalan ödemeler ve ödeme geçmişi için tutulur, satın alınamaz.
LEGACY_PACKS = {
    "kredi_300": {"name": "300 ek kredi", "credits": 300, "price": 13},
    "kredi_800": {"name": "800 ek kredi", "credits": 800, "price": 30},
}
ALL_PACKS = {**CREDIT_PACKS, **LEGACY_PACKS}

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


def is_credit_pack(item_id: str) -> bool:
    """Ödeme kaydındaki kalem bir ek kredi paketi mi (eski paketler dahil)."""
    return item_id in ALL_PACKS


def is_sellable_pack(item_id: str) -> bool:
    return item_id in CREDIT_PACKS


def item_name(item_id: str, billing: str = "monthly") -> str:
    if is_credit_pack(item_id):
        return ALL_PACKS[item_id]["name"]
    return get_plan(item_id)["name"] + (" (yıllık)" if billing == "yearly" else "")


def public_packs() -> list[dict]:
    return [
        {"id": k, "name": v["name"], "credits": v["credits"], "price": v["price"], "currency": CURRENCY,
         "vat_rate": VAT_RATE, "per_credit": round(v["price"] / v["credits"], 4)}
        for k, v in CREDIT_PACKS.items()
    ]


def is_purchasable(plan_id: str) -> bool:
    return plan_id in PLANS and PLANS[plan_id]["purchasable"]


def idea_cost(count: int) -> int:
    return max(1, math.ceil(count / 2)) * CREDIT_COSTS["idea_per_2"]


def video_cost(duration: int, resolution: str = "1080p", audio: bool = False) -> int:
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
    net = float(ALL_PACKS[plan_id]["price"]) if is_credit_pack(plan_id) else cycle_price(plan_id, billing)
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
        "credits_yearly": c * BILLING_CYCLES["yearly"]["months"],
        "yearly_discount": BILLING_CYCLES["yearly"]["discount"],
        "vat_rate": VAT_RATE,
        "credits": c,
        "video_enabled": p["video_enabled"],
        "ads_enabled": p["ads_enabled"],
        # "Bu krediyle yalnızca X yaparsan" örnekleri
        "examples": {
            "messages": c // CREDIT_COSTS["chat_message"],  # dosyasız fikir sohbeti mesajı
            "images": c // CREDIT_COSTS["image"],
            # 6 sn videolar, çözünürlüğe göre
            "videos": {
                res: (c // video_cost(6, res) if p["video_enabled"] else 0) for res in VIDEO_RESOLUTIONS
            },
        },
    }
