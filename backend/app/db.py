"""Veritabanı katmanı.

DATABASE_URL Postgres'i gösteriyorsa (Railway) Postgres, yoksa yerel SQLite
kullanılır. Sorgular SQLAlchemy Core ile yazıldığı için ikisinde de aynı kod
çalışır.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from app import config

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("email", String(320), nullable=False, unique=True),
    Column("password_hash", String(200), nullable=False),
    Column("name", String(200), nullable=False, default=""),
    Column("plan", String(32), nullable=False),
    # Ücretli paketin bitiş zamanı. Geçince kullanıcı deneme paketine döner.
    Column("plan_expires_at", DateTime, nullable=True),
    Column("period_start", DateTime, nullable=False),
    Column("video_used", Integer, nullable=False, default=0),
    Column("image_used", Integer, nullable=False, default=0),
    Column("idea_used", Integer, nullable=False, default=0),
    Column("created_at", DateTime, nullable=False),
)

# Video üretimi asenkron: kota job başlarken düşülür, job FAILED olursa iade edilir.
video_jobs = Table(
    "video_jobs",
    metadata,
    Column("job_id", String(100), primary_key=True),
    Column("user_id", String(36), nullable=False, index=True),
    Column("released", Integer, nullable=False, default=0),
    Column("created_at", DateTime, nullable=False),
)

payments = Table(
    "payments",
    metadata,
    # iyzico'ya conversationId ve basketId olarak da bu değer gönderilir.
    Column("id", String(36), primary_key=True),
    Column("user_id", String(36), nullable=False, index=True),
    Column("plan_id", String(32), nullable=False),
    Column("amount_try", Numeric(10, 2), nullable=False),
    Column("status", String(16), nullable=False),  # pending | success | failure
    Column("iyzico_token", String(200), nullable=True, unique=True),
    Column("iyzico_payment_id", String(100), nullable=True),
    Column("error", Text, nullable=True),
    Column("created_at", DateTime, nullable=False),
    Column("completed_at", DateTime, nullable=True),
)

# Kullanıcının Meta hesabını bağladığında aldığımız token sunucuda saklanır;
# istemciye geri gönderilmez.
meta_connections = Table(
    "meta_connections",
    metadata,
    Column("user_id", String(36), primary_key=True),
    Column("access_token", Text, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)

# Uygulamanın kendi ürettiği ayarlar (ör. JWT_SECRET tanımlı değilse oluşturulan anahtar).
app_settings = Table(
    "app_settings",
    metadata,
    Column("key", String(100), primary_key=True),
    Column("value", Text, nullable=False),
)


def _normalize_url(url: str) -> str:
    # Railway "postgresql://" veya "postgres://" verir; psycopg 3 sürücüsünü seçiyoruz.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = _normalize_url(config.DATABASE_URL)
        kwargs = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            # Neon/PgBouncer gibi havuzlayıcılar sunucu tarafı hazır sorguları
            # desteklemez; psycopg'nin otomatik hazırlamasını kapatıyoruz.
            kwargs["connect_args"] = {"prepare_threshold": None}
            if config.IS_SERVERLESS:
                # Her fonksiyon örneği kısa ömürlü; bağlantıyı açık tutmuyoruz.
                kwargs["poolclass"] = NullPool
                kwargs.pop("pool_pre_ping")
        _engine = create_engine(url, **kwargs)
    return _engine


def reset_engine(url: str | None = None) -> None:
    """Testler için: motoru farklı bir veritabanıyla yeniden kurar."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None
    if url is not None:
        config.DATABASE_URL = url


def init_db() -> None:
    metadata.create_all(get_engine())


def utcnow() -> datetime:
    """Veritabanına naive UTC olarak yazılır (SQLite ve Postgres'te aynı davranış)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
