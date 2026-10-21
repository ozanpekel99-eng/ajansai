"""Tüm ayarlar ortam değişkenlerinden okunur. Örnekler için .env.example'a bakın."""

import os

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _bool(name: str, default: bool = False) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


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
AI_GATEWAY_MODEL = _env("AI_GATEWAY_MODEL", "anthropic/claude-sonnet-5")
# Varsayılan: Vercel'de çalışıyorsa açık. Kapatmak için AI_GATEWAY_ENABLED=false.
AI_GATEWAY_ENABLED = _bool("AI_GATEWAY_ENABLED", bool(_env("VERCEL")) or bool(AI_GATEWAY_API_KEY))

ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = _env("ANTHROPIC_MODEL", "claude-sonnet-5")

# --- Görsel / video (Vercel AI Gateway üzerinden, ayrı anahtar gerekmez) ---
IMAGE_MODEL = _env("IMAGE_MODEL", "bytedance/seedream-5.0-pro")
# Fikir sohbeti: metin, görsel ve belge Claude ile; video eki varsa Gemini ile anlaşılır.
CHAT_MODEL = _env("CHAT_MODEL", "anthropic/claude-sonnet-5")
CHAT_VIDEO_MODEL = _env("CHAT_VIDEO_MODEL", "google/gemini-3.6-flash")
# Çözünürlüğe göre video modeli ve sağlayıcıya gönderilen çözünürlük. Videolar
# dikey (9:16) üretilir; çözünürlük sağlayıcının kademe adıyla verilir.
VIDEO_MODELS = {
    "720p": (_env("VIDEO_MODEL_720P", "bytedance/seedance-v1.5-pro"), "1280x720"),
    "1080p": (_env("VIDEO_MODEL_1080P", "bytedance/seedance-v1.5-pro"), "1920x1080"),
    "4k": (_env("VIDEO_MODEL_4K", "bytedance/seedance-2.0"), "3840x2160"),
}
# Üretilen dosyaların saklandığı Vercel Blob deposu (projeye bağlanınca otomatik gelir)
BLOB_READ_WRITE_TOKEN = _env("BLOB_READ_WRITE_TOKEN")

# --- Meta ---
META_APP_ID = _env("META_APP_ID")
META_APP_SECRET = _env("META_APP_SECRET")
META_REDIRECT_URI = _env("META_REDIRECT_URI", f"{WEB_URL}/ads/callback")

# --- iyzico ---
IYZICO_API_KEY = _env("IYZICO_API_KEY")
IYZICO_SECRET_KEY = _env("IYZICO_SECRET_KEY")
# Test için sandbox; canlıya geçince https://api.iyzipay.com
IYZICO_BASE_URL = (_env("IYZICO_BASE_URL", "https://sandbox-api.iyzipay.com") or "").rstrip("/")
