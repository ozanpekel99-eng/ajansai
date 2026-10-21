import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.db import init_db
from app.routers import ads, auth, content, payments, plans
from app.services import iyzico_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="ajansAI - İçerik ve Reklam Asistanı API",
    lifespan=lifespan,
    # Production'da API dokümantasyonunu herkese açık bırakmıyoruz.
    docs_url=None if config.IS_PRODUCTION else "/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(content.router, prefix="/api/content", tags=["content"])
app.include_router(ads.router, prefix="/api/ads", tags=["ads"])
app.include_router(plans.router, prefix="/api/plans", tags=["plans"])
app.include_router(payments.router, prefix="/api/payments", tags=["payments"])


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "ai": "omniroute" if config.OMNIROUTE_BASE_URL else ("anthropic" if config.ANTHROPIC_API_KEY else "yok"),
        "ai_fallback": bool(config.OMNIROUTE_BASE_URL and config.ANTHROPIC_API_KEY),
        "payments": iyzico_service.is_configured(),
        "database": "postgres" if config.DATABASE_URL.startswith("postgres") else "sqlite",
    }
