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

ANTHROPIC_API_KEY = _env("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = _env("ANTHROPIC_MODEL", "claude-sonnet-5")

# --- Görsel / video ---
IDEOGRAM_API_KEY = _env("IDEOGRAM_API_KEY")
RUNWAY_API_KEY = _env("RUNWAY_API_KEY")

# --- Meta ---
META_APP_ID = _env("META_APP_ID")
META_APP_SECRET = _env("META_APP_SECRET")
META_REDIRECT_URI = _env("META_REDIRECT_URI", f"{WEB_URL}/ads/callback")

# --- iyzico ---
IYZICO_API_KEY = _env("IYZICO_API_KEY")
IYZICO_SECRET_KEY = _env("IYZICO_SECRET_KEY")
# Test için sandbox; canlıya geçince https://api.iyzipay.com
IYZICO_BASE_URL = (_env("IYZICO_BASE_URL", "https://sandbox-api.iyzipay.com") or "").rstrip("/")
