"""Veritabanı katmanı.

DATABASE_URL Postgres'i gösteriyorsa (Railway) Postgres, yoksa yerel SQLite
kullanılır. Sorgular SQLAlchemy Core ile yazıldığı için ikisinde de aynı kod
çalışır.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    inspect,
    text,
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
    # Bu dönemde harcanan kredi. Bakiye = paketin kredisi - credits_used.
    Column("credits_used", Integer, nullable=False, default=0, server_default="0"),
    # Dönem kredisi (yıllık pakette 12 aylık kredi tek seferde). Boşsa paketin aylık kredisi.
    Column("period_credits", Integer, nullable=True),
    Column("cycle", String(10), nullable=False, default="monthly", server_default="monthly"),
    # Satın alınan ek krediler: dönem kredisi bitince kullanılır, dönem yenilenince silinmez.
    Column("extra_credits", Integer, nullable=False, default=0, server_default="0"),
    Column("created_at", DateTime, nullable=False),
)

# Her kredi harcaması bir satır. Kullanıcıya "neye kaç kredi harcadım" gösterilir;
# başarısız üretimde refunded=1 yapılıp kredi iade edilir.
credit_events = Table(
    "credit_events",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(36), nullable=False, index=True),
    Column("action", String(32), nullable=False),  # idea | image | video | ads_draft
    Column("credits", Integer, nullable=False),
    Column("detail", String(300), nullable=False, default=""),
    Column("refunded", Integer, nullable=False, default=0),
    # Bu harcamanın ek krediden karşılanan kısmı (iade doğru bakiyeye yapılır)
    Column("extra", Integer, nullable=False, default=0, server_default="0"),
    Column("created_at", DateTime, nullable=False),
)

# AI Gateway video işleri: durum sorgusu için gateway'in "operation" nesnesi saklanır.
video_tasks = Table(
    "video_tasks",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(36), nullable=False, index=True),
    Column("credit_event_id", String(36), nullable=False),
    Column("operation", Text, nullable=False),
    Column("status", String(16), nullable=False),  # pending | completed | failed
    Column("video_url", Text, nullable=True),
    Column("error", Text, nullable=True),
    Column("prompt", String(500), nullable=True),
    # Revizyon için: modele giden istem, açılış karesi ve ayarlar (JSON)
    Column("plan", Text, nullable=True),
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
    Column("amount_try", Numeric(10, 2), nullable=False),  # tutar; birimi `currency`
    Column("currency", String(3), nullable=False, default="TRY", server_default="TRY"),
    Column("billing", String(10), nullable=False, default="monthly", server_default="monthly"),  # monthly | yearly
    Column("status", String(16), nullable=False),  # pending | success | failure
    Column("iyzico_token", String(200), nullable=True, unique=True),
    Column("iyzico_payment_id", String(100), nullable=True),
    Column("error", Text, nullable=True),
    Column("created_at", DateTime, nullable=False),
    Column("completed_at", DateTime, nullable=True),
    # Yönetici test ödemesi: iyzico sandbox ortamında alındı (gerçek para çekilmez).
    Column("sandbox", Boolean, nullable=False, default=False, server_default=text("false")),
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

# ajansAI üzerinden oluşturulan Meta reklamları (durum ve metrikler Meta'dan canlı okunur).
meta_ads = Table(
    "meta_ads",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(36), nullable=False, index=True),
    Column("ad_account_id", String(50), nullable=False),
    Column("campaign_id", String(50), nullable=False),
    Column("adset_id", String(50), nullable=False),
    Column("ad_id", String(50), nullable=False),
    Column("name", String(200), nullable=False),
    Column("objective", String(20), nullable=False),
    Column("daily_budget", Numeric(12, 2), nullable=False),
    Column("currency", String(3), nullable=False),
    Column("media_url", Text, nullable=True),
    Column("budget_type", String(10), nullable=True),  # daily | lifetime
    Column("created_at", DateTime, nullable=False),
)

# Ücretsiz paket kullanımı (kredisiz): kim (kullanıcı veya ziyaretçi IP özeti), ne zaman, ne.
# Günlük/aylık sınırlar ve site geneli günlük tavan bu tablodan sayılır.
free_events = Table(
    "free_events",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("subject", String(80), nullable=False, index=True),  # u:<user_id> | ip:<özet>
    Column("kind", String(16), nullable=False, index=True),  # chat | image | stock
    Column("created_at", DateTime, nullable=False, index=True),
)

# Sesli okuma (TTS) günlük karakter sayacı: ücretsiz kotayı aşmamak için.
tts_usage = Table(
    "tts_usage",
    metadata,
    Column("key", String(120), primary_key=True),  # "<gün>" veya "<gün>:<kişi>"
    Column("chars", Integer, nullable=False, default=0),
)

# Üretilen görsel ve videolar (kütüphane)
media = Table(
    "media",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(36), nullable=False, index=True),
    Column("kind", String(10), nullable=False),  # image | video
    Column("url", Text, nullable=False),
    Column("prompt", String(500), nullable=False, default=""),
    Column("source", String(20), nullable=False, default=""),  # gorsel | video | sohbet
    Column("created_at", DateTime, nullable=False, index=True),
)

# Sohbet geçmişi (giriş yapmış kullanıcılar; her cihazdan görünür)
conversations = Table(
    "conversations",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(36), nullable=False, index=True),
    Column("title", String(200), nullable=False),
    Column("messages", Text, nullable=False),  # JSON
    Column("updated_at", DateTime, nullable=False, index=True),
)

# Yapay zeka harcaması (AI Gateway), milyonda bir dolar cinsinden. Anahtar: "<gün>" veya "<gün>:free".
ai_spend = Table(
    "ai_spend",
    metadata,
    Column("key", String(120), primary_key=True),
    Column("micro_usd", Integer, nullable=False, default=0),
)

# Pexels arama sonuçları önbelleği (Pexels API saatlik istek sınırı için).
stock_cache = Table(
    "stock_cache",
    metadata,
    Column("key", String(300), primary_key=True),
    Column("data", Text, nullable=False),
    Column("created_at", DateTime, nullable=False),
)

# Destek e-postaları (support@ajansai.tr) ve otomatik yanıtlar
support_tickets = Table(
    "support_tickets",
    metadata,
    Column("id", String(64), primary_key=True),  # Resend email_id
    Column("from_addr", String(320), nullable=False, index=True),
    Column("subject", String(500), nullable=False),
    Column("body", Text, nullable=False),
    Column("reply", Text, nullable=True),
    Column("status", String(20), nullable=False),  # replied | escalated | skipped | error
    Column("note", String(300), nullable=True),
    Column("created_at", DateTime, nullable=False, index=True),
)

# Uygulamanın kendi ürettiği ayarlar (ör. JWT_SECRET tanımlı değilse oluşturulan anahtar).
app_settings = Table(
    "app_settings",
    metadata,
    Column("key", String(100), primary_key=True),
    Column("value", Text, nullable=False),
)

# @ajansai.tr Instagram hesabına gelen (in) ve hesaptan gönderilen (out) DM'ler. Meta webhook'u ile gelir;
# aynı mesaj (mid) iki kez kaydedilmez. `thread` müşterinin Instagram kimliğidir (IGSID).
instagram_messages = Table(
    "instagram_messages",
    metadata,
    Column("id", String(200), primary_key=True),  # Meta mesaj kimliği (mid)
    Column("thread", String(64), nullable=False, index=True),
    Column("ig_account", String(64), nullable=False, default=""),
    Column("direction", String(3), nullable=False),  # in | out
    Column("text", Text, nullable=False, default=""),
    Column("attachments", Text, nullable=True),  # JSON: [{"type": "image", "url": "..."}]
    Column("status", String(12), nullable=False),  # received | replied | escalated | skipped | error | sent
    Column("note", String(300), nullable=True),
    Column("sent_at", DateTime, nullable=False, index=True),  # Meta'daki mesaj zamanı (naive UTC)
    Column("created_at", DateTime, nullable=False),
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
    engine = get_engine()
    metadata.create_all(engine)
    # Eski kurulumlara sonradan eklenen sütunlar (create_all mevcut tabloya sütun eklemez).
    migrations = {
        "users": {
            "credits_used": "INTEGER NOT NULL DEFAULT 0",
            "period_credits": "INTEGER",
            "cycle": "VARCHAR(10) NOT NULL DEFAULT 'monthly'",
            "extra_credits": "INTEGER NOT NULL DEFAULT 0",
        },
        "credit_events": {"extra": "INTEGER NOT NULL DEFAULT 0"},
        "meta_ads": {"budget_type": "VARCHAR(10)"},
        "video_tasks": {"prompt": "VARCHAR(500)", "plan": "TEXT"},
        "payments": {
            "currency": "VARCHAR(3) NOT NULL DEFAULT 'TRY'",
            "billing": "VARCHAR(10) NOT NULL DEFAULT 'monthly'",
            "sandbox": "BOOLEAN NOT NULL DEFAULT FALSE",
        },
    }
    for table, cols in migrations.items():
        existing = {c["name"] for c in inspect(engine).get_columns(table)}
        for name, ddl in cols.items():
            if name not in existing:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def utcnow() -> datetime:
    """Veritabanına naive UTC olarak yazılır (SQLite ve Postgres'te aynı davranış)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
