"""Vercel giriş noktası: Vercel bu dosyadaki `app` nesnesini çalıştırır.

Railway gibi sunucularda ise `uvicorn app.main:app` kullanılır (railway.json).
"""

from app.db import init_db
from app.main import app  # noqa: F401

# Sunucusuz ortamda başlangıç (lifespan) olayına güvenmeden tabloları
# soğuk başlangıçta oluştur. create_all idempotent: var olan tablolara dokunmaz.
init_db()
