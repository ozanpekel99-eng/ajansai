"""Vercel giriş noktası: Vercel bu dosyadaki `app` nesnesini çalıştırır.

Railway gibi sunucularda ise `uvicorn app.main:app` kullanılır (railway.json).
"""

from app.db import ensure_db
from app.main import app  # noqa: F401

# Sunucusuz ortamda başlangıç (lifespan) olayına güvenmeden tabloları
# soğuk başlangıçta oluştur. create_all idempotent: var olan tablolara dokunmaz.
# Hata fırlatmaz: veritabanına o an ulaşılamazsa (soğuk Neon, ağ) modül yüklemesi
# çökmesin diye (Vercel FUNCTION_INVOCATION_FAILED); ilk istekte DbReadyMiddleware yeniden dener.
ensure_db()
