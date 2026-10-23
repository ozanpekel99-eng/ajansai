"""Tüm ayarlar ortam değişkenlerinden okunur. Örnekler için .env.example'a bakın."""

import os

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is not None:
        value = value.strip().strip('"').strip("'")  # yapıştırırken gelen boşluk/tırnak
    return value if value not in (None, "") else default


def _bool(name: str, default: bool = False) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


ENVIRONMENT = _env("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"

# --- Veritabanı ---
# Railway Postgres eklenince DATABASE_URL otomatik tanımlanır. Yoksa yerel SQLite.
DATABASE_URL = _env("DATABASE_URL", "sqlite:///./data.db")

# --- Kimlik doğrulama ---
# Tanımlı değilse ilk açılışta rastgele üretilip veritabanında saklanır
# (bkz. security._jwt_secret). Böylece elle gizli anahtar girmeye gerek kalmaz
# ve sunucusuz ortamda bütün örnekler aynı anahtarı kullanır.
JWT_SECRET = _env("JWT_SECRET")

# Vercel gibi sunucusuz ortamlarda bağlantı havuzu tutulmaz.
IS_SERVERLESS = bool(_env("VERCEL"))
JWT_EXPIRE_DAYS = int(_env("JWT_EXPIRE_DAYS", "30"))

# Google / Apple ile giriş (gizli değildir; istemci kimlikleri)
# Google: Cloud Console → APIs & Services → Credentials → OAuth client ID (Web)
GOOGLE_CLIENT_ID = _env("GOOGLE_CLIENT_ID")
# Apple: Developer → Identifiers → Services ID (Sign in with Apple açık)
APPLE_CLIENT_ID = _env("APPLE_CLIENT_ID")

# --- CORS ---
# Virgülle ayrılmış liste. Örn: https://ajansai.vercel.app,https://www.ajansai.com
ALLOWED_ORIGINS = [
    o.strip()
    for o in (_env("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8081") or "").split(",")
    if o.strip()
]

# Web uygulamasının adresi (ödeme sonrası yönlendirme için)
WEB_URL = (_env("WEB_URL", "http://localhost:3000") or "").rstrip("/")
# Backend'in dışarıdan erişilen adresi (iyzico callback için)
PUBLIC_API_URL = (_env("PUBLIC_API_URL", "http://localhost:8000") or "").rstrip("/")

# --- Yapay zeka (metin) ---
# OmniRoute tanımlıysa tüm metin üretimi onun üzerinden gider; hata olursa
# ANTHROPIC_API_KEY varsa doğrudan Claude'a düşülür.
OMNIROUTE_BASE_URL = (_env("OMNIROUTE_BASE_URL") or "").rstrip("/") or None  # örn. https://omniroute-xxx.up.railway.app/v1
OMNIROUTE_API_KEY = _env("OMNIROUTE_API_KEY")
OMNIROUTE_MODEL = _env("OMNIROUTE_MODEL", "anthropic/claude-sonnet-5")
OMNIROUTE_TIMEOUT = float(_env("OMNIROUTE_TIMEOUT", "90"))

# Vercel AI Gateway: Vercel'de çalışırken API key gerektirmez (proje kimliği /
# OIDC token ile doğrulanır). AI_GATEWAY_API_KEY verilirse onu kullanır.
AI_GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh/v1"
AI_GATEWAY_API_KEY = _env("AI_GATEWAY_API_KEY")
AI_GATEWAY_MODEL = _env("AI_GATEWAY_MODEL", "anthropic/claude-haiku-5.5")
# Varsayılan: Vercel'de çalışıyorsa açık. Kapatmak için AI_GATEWAY_ENABLED=false.
AI_GATEWAY_ENABLED = _bool("AI_GATEWAY_ENABLED", bool(_env("VERCEL")) or bool(AI_GATEWAY_API_KEY))

ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = _env("ANTHROPIC_MODEL", "claude-sonnet-5")

# --- Görsel / video (Vercel AI Gateway üzerinden, ayrı anahtar gerekmez) ---
# Görsel: Gemini 3.1 Flash Image (Nano Banana 2) — ~9 sn, Türkçe yazıyı doğru basar, düzenlemede
# görseli bozmadan yalnızca isteneni değiştirir. Olmazsa Gemini 3 Pro Image, en son Seedream.
IMAGE_MODEL = _env("IMAGE_MODEL", "openai/gpt-image-2")  # ChatGPT'nin görsel modeli: kampanya yazısı ve düzende en iyi (~$0,063, ~20-35 sn)
IMAGE_MODEL_FALLBACK = _env("IMAGE_MODEL_FALLBACK", "google/gemini-3.1-flash-image")
IMAGE_MODEL_LAST = _env("IMAGE_MODEL_LAST", "google/gemini-3-pro-image")
# İstemi (görsel/video) netleştiren hızlı model
PLANNER_MODEL = _env("PLANNER_MODEL", "anthropic/claude-haiku-5.5")
# Görsel istemi: "chatgpt" = ChatGPT gibi güçlü modelle (Sonnet) reklam afişi istemi yazılır, kullanıcının
# verdiği her yazı/fiyat aynen korunur; "direct" = istek aynen gider; "planner" = eski Haiku planlayıcı.
IMAGE_PROMPT_MODE = _env("IMAGE_PROMPT_MODE", "chatgpt")
IMAGE_PROMPT_MODEL = _env("IMAGE_PROMPT_MODEL", "anthropic/claude-sonnet-5.5")
IMAGE_DIRECT = IMAGE_PROMPT_MODE != "planner"
# Görsel otomatik kalite kontrolü: kusur bulunursa bir kez düzeltilerek yeniden üretilir
IMAGE_QA = _env("IMAGE_QA", "1") == "1"
IMAGE_QA_MODEL = _env("IMAGE_QA_MODEL", "anthropic/claude-sonnet-5.5")
# Video yönetmeni: başlangıç karesini görür, gerekirse kareye kişi/el ekletir (Sonnet)
VIDEO_PROMPT_MODEL = _env("VIDEO_PROMPT_MODEL", "anthropic/claude-sonnet-5.5")
# Sohbet (ücretli paketler): Claude Sonnet 5.5 (mesaj başı ~$0,01-0,02); olmazsa Haiku 5.5.
# Video eki varsa Gemini ile anlaşılır.
CHAT_MODEL = _env("CHAT_MODEL", "anthropic/claude-sonnet-5.5")
CHAT_VIDEO_MODEL = _env("CHAT_VIDEO_MODEL", "google/gemini-3.6-flash")
# Çözünürlüğe göre video modeli ve sağlayıcıya gönderilen çözünürlük. Videolar
# dikey (9:16) üretilir; çözünürlük sağlayıcının kademe adıyla verilir.
# Veo 3.1: karşılaştırmada en gerçekçi fizik (yemek kesme, el hareketi) ve en hızlı (~50-80 sn).
# Süreler 4 / 6 / 8 sn.
VIDEO_MODELS = {
    "720p": (_env("VIDEO_MODEL_720P", "google/veo-3.1-fast-generate-001"), "1280x720"),  # 1080p ile aynı kaliteli model
    "1080p": (_env("VIDEO_MODEL_1080P", "google/veo-3.1-fast-generate-001"), "1920x1080"),
    "4k": (_env("VIDEO_MODEL_4K", "google/veo-3.1-fast-generate-001"), "3840x2160"),
}
# Yedek video modeli: Veo başlatılamazsa ya da iş hata verirse aynı istem ve açılış karesiyle Kling denenir.
# Kling yalnızca 5 / 10 sn üretir (4-6 sn → 5, 8 sn → 10). Sesli istekte sesi destekleyen 2.6 kullanılır.
VIDEO_FALLBACK = _env("VIDEO_FALLBACK", "1") == "1"
VIDEO_FALLBACK_I2V = _env("VIDEO_FALLBACK_I2V", "klingai/kling-v2.5-turbo-i2v")
VIDEO_FALLBACK_T2V = _env("VIDEO_FALLBACK_T2V", "klingai/kling-v2.5-turbo-t2v")
VIDEO_FALLBACK_AUDIO_I2V = _env("VIDEO_FALLBACK_AUDIO_I2V", "klingai/kling-v2.6-i2v")
VIDEO_FALLBACK_AUDIO_T2V = _env("VIDEO_FALLBACK_AUDIO_T2V", "klingai/kling-v2.6-t2v")
# --- Ücretsiz paket (üyelik gerektirmez; maliyeti sıfıra yakın) ---
# Ücretsiz sağlayıcı zinciri (Groq / Cerebras, $0): Claude bütçesi dolunca. "sağlayıcı:model" listesi.
GROQ_API_KEY = _env("GROQ_API_KEY")
CEREBRAS_API_KEY = _env("CEREBRAS_API_KEY")
FREE_CHAT_CHAIN = _env(
    "FREE_CHAT_CHAIN",
    "cerebras:gpt-oss-120b,groq:openai/gpt-oss-120b,cerebras:qwen-3.8-27b,groq:qwen/qwen3.8-27b",
)
FREE_CHAT_MODEL = _env("FREE_CHAT_MODEL", "anthropic/claude-haiku-5.5")
# Ücretsiz paket ve misafir Claude Haiku 5.5 ile yanıtlanır (mesaj başı ~$0,0006; karşılaştırmada Türkçe
# içerik ve analizde Groq/Cerebras modellerinden belirgin iyi). Site geneli günlük bu bütçe (~15.000 mesaj)
# dolunca ücretsiz katmanlara (Groq / Cerebras) geçilir.
FREE_GATEWAY_DAILY_USD = float(_env("FREE_GATEWAY_DAILY_USD", "10"))
FREE_CHAT_PER_DAY_USER = _int("FREE_CHAT_PER_DAY_USER", 10)
FREE_CHAT_PER_DAY_ANON = _int("FREE_CHAT_PER_DAY_ANON", 5)
FREE_CHAT_PER_DAY_TOTAL = _int("FREE_CHAT_PER_DAY_TOTAL", 10000)  # tüm site, günlük tavan
# Ücretsiz görsel: Cloudflare Workers AI (FLUX.2 klein). Günlük 10.000 neuron ücretsiz;
# 1024px görsel ~105 neuron (~$0,0012); ilk ~90 görsel/gün ücretsiz, sonrası Workers Paid ile ücretlenir.
# Site geneli tavan yalnızca güvenlik sınırı: 1500/gün ≈ en fazla ~$1,7/gün. Asıl sınır kişi başı aylık hak.
CLOUDFLARE_ACCOUNT_ID = _env("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_AI_TOKEN = _env("CLOUDFLARE_AI_TOKEN")
FREE_IMAGE_MODEL = _env("FREE_IMAGE_MODEL", "@cf/black-forest-labs/flux-2-klein-4b")
# Görselden görsel (örnek görselle üretim): FLUX.2 klein 4B, ~110 neuron → günlük tavanda 2 sayılır
FREE_IMAGE_REF_MODEL = _env("FREE_IMAGE_REF_MODEL", "@cf/black-forest-labs/flux-2-klein-4b")
FREE_IMAGES_PER_MONTH = _int("FREE_IMAGES_PER_MONTH", 3)
FREE_IMAGES_PER_DAY_TOTAL = _int("FREE_IMAGES_PER_DAY_TOTAL", 1500)
# Ücretsiz görseller de ücretli paketle aynı modelle (Gemini 3.1 Flash Image, ~$0,068) üretilir;
# site geneli günde bu kadarı aşılırsa günün kalanında FLUX (Cloudflare) yedeğine geçilir.
FREE_PREMIUM_IMAGES_PER_DAY = _int("FREE_PREMIUM_IMAGES_PER_DAY", 400)
# Gemini olmazsa / tavan dolarsa FLUX (Cloudflare) yedeği. Kalite ChatGPT düzeyinde olmadığı için kapalı:
# kullanıcı zayıf görsel yerine "hakkın düşülmedi, tekrar dene" mesajı görür.
FREE_IMAGE_FLUX_FALLBACK = _env("FREE_IMAGE_FLUX_FALLBACK", "0") == "1"
# Doğal sesli okuma: Google Cloud Text-to-Speech (Chirp 3 HD). Ayda 1M karakter ücretsiz;
# günlük tavan bunun altında tutulur, aşılırsa tarayıcının kendi sesine düşülür.
GOOGLE_TTS_API_KEY = _env("GOOGLE_TTS_API_KEY")
# Daha doğal ses: Gemini TTS (Google AI Studio API anahtarı, ücretsiz katman). Tanımlıysa önce bu denenir.
GEMINI_API_KEY = _env("GEMINI_API_KEY")
GEMINI_TTS_MODEL = _env("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
# Öncelikli yol: aynı Gemini sesi Vercel AI Gateway'den (Vercel kredisiyle ödenir). Boş bırakılırsa kapalı.
# Gerçek zamanlı sesli sohbet (konuşmadan konuşmaya, Vercel AI Gateway)
REALTIME_MODEL = _env("REALTIME_MODEL", "openai/gpt-realtime-mini")
REALTIME_VOICE = _env("REALTIME_VOICE", "marin")
REALTIME_CREDITS_PER_MINUTE = _int("REALTIME_CREDITS_PER_MINUTE", 3)
GATEWAY_TTS_MODEL = _env("GATEWAY_TTS_MODEL", "google/gemini-3.8-flash-tts")
TTS_USD_PER_M_AUDIO_TOKENS = float(_env("TTS_USD_PER_M_AUDIO_TOKENS", "9"))  # 2027'de 18
GEMINI_TTS_VOICE = _env("GEMINI_TTS_VOICE", "Sulafat")
TTS_STYLE = _env("TTS_STYLE", "sıcak, doğal ve samimi; günlük sohbet eder gibi, akıcı ve canlı")
TTS_VOICE = _env("TTS_VOICE", "tr-TR-Chirp3-HD-Achernar")
# Ücretsiz paket ve misafir: site geneli günlük tavan ve kişi başı günlük hak (~1000 karakter ≈ 1 dk ses)
TTS_DAILY_CHARS = _int("TTS_DAILY_CHARS", 20000)
TTS_CHARS_PER_DAY_SUBJECT = _int("TTS_CHARS_PER_DAY_SUBJECT", 1500)
# Ücretli paketler: her 500 karakter (~35 sn ses) 1 kredi; kişi başı günlük güvenlik tavanı
TTS_CHARS_PER_CREDIT = _int("TTS_CHARS_PER_CREDIT", 500)
TTS_PAID_CHARS_PER_DAY = _int("TTS_PAID_CHARS_PER_DAY", 60000)

# Sohbette canlı web araması: Groq yerleşik araması (GROQ_API_KEY ile) ya da Tavily
TAVILY_API_KEY = _env("TAVILY_API_KEY")
SEARCH_MODEL = _env("SEARCH_MODEL", "openai/gpt-oss-120b")

# Stok fotoğraf kütüphanesi: Pixabay (öncelikli) veya Pexels, ikisi de ücretsiz API anahtarı
PIXABAY_API_KEY = _env("PIXABAY_API_KEY")
PEXELS_API_KEY = _env("PEXELS_API_KEY")

# Üretilen dosyaların saklandığı Vercel Blob deposu (projeye bağlanınca otomatik gelir)
BLOB_READ_WRITE_TOKEN = _env("BLOB_READ_WRITE_TOKEN")

# --- Meta ---
META_APP_ID = _env("META_APP_ID")
META_APP_SECRET = _env("META_APP_SECRET")
# Facebook Login for Business yapılandırma kimliği (izinler: ads_management, ads_read,
# business_management, pages_show_list). Gizli değildir.
META_CONFIG_ID = _env("META_CONFIG_ID")
META_API_VERSION = _env("META_API_VERSION", "v26.0")
META_REDIRECT_URI = _env("META_REDIRECT_URI", f"{WEB_URL}/ads/callback")

# --- iyzico ---
IYZICO_API_KEY = _env("IYZICO_API_KEY")
IYZICO_SECRET_KEY = _env("IYZICO_SECRET_KEY")
# Test için sandbox; canlıya geçince https://api.iyzipay.com
IYZICO_BASE_URL = (_env("IYZICO_BASE_URL", "https://sandbox-api.iyzipay.com") or "").rstrip("/")
# Tahsilat para birimi. Fiyatlar USD; iyzico hesabında USD POS yoksa "TRY": tutar o günkü
# TCMB döviz satış kuruyla TL'ye çevrilip TL olarak çekilir. USD POS açılınca "USD" yapılabilir.
PAYMENT_CURRENCY = _env("PAYMENT_CURRENCY", "TRY")
USD_TRY_RATE = _env("USD_TRY_RATE", "")  # TCMB'ye ulaşılamazsa kullanılacak yedek kur


# Destek e-postası (support@ajansai.tr): Resend ile alınır, Claude ile otomatik yanıtlanır.
RESEND_API_KEY = _env("RESEND_API_KEY", "")
RESEND_WEBHOOK_SECRET = _env("RESEND_WEBHOOK_SECRET", "")  # whsec_...
SUPPORT_FROM = _env("SUPPORT_FROM", "ajansAI Destek <support@ajansai.tr>")
SUPPORT_ADDRESS = _env("SUPPORT_ADDRESS", "support@ajansai.tr")
SUPPORT_FORWARD_TO = _env("SUPPORT_FORWARD_TO", "")  # gelen mailin ve yanıtın kopyası (ör. kişisel Gmail)
SUPPORT_AUTO_REPLY = _env("SUPPORT_AUTO_REPLY", "1") not in ("0", "false", "False", "")
SUPPORT_REPLIES_PER_SENDER_PER_DAY = _int("SUPPORT_REPLIES_PER_SENDER_PER_DAY", 5)

# Yönetici e-postaları (model karşılaştırma uçları vb.)
ADMIN_EMAILS = {e.strip().lower() for e in _env("ADMIN_EMAILS", "ozanpekel99@gmail.com").split(",") if e.strip()}
