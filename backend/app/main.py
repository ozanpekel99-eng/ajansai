import logging
from contextlib import asynccontextmanager

import anyio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import config
from app.db import ensure_db, init_db, is_initialized
from app.routers import admin, ads, auth, chats, content, free, health, payments, plans, support, uploads, voice
from app.services import iyzico_service, llm_service

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

class OidcTokenMiddleware:
    """Vercel'in her isteğe eklediği OIDC token'ını AI Gateway çağrıları için saklar."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            for name, value in scope.get("headers", []):
                if name == b"x-vercel-oidc-token":
                    llm_service.current_oidc_token.set(value.decode("latin-1"))
                    break
        await self.app(scope, receive, send)


class DbReadyMiddleware:
    """Soğuk başlangıçta veritabanı hazırlığı başarısız olduysa ilk istekte yeniden dener.

    Hazırlık hâlâ olmuyorsa fonksiyon çökmez; anlaşılır bir 503 döner (istemci yeniden dener).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and not is_initialized():
            ok = await anyio.to_thread.run_sync(lambda: ensure_db(attempts=1))
            if not ok:
                response = JSONResponse({"detail": "Sunucu hazırlanıyor, lütfen birkaç saniye sonra tekrar deneyin."},
                                        status_code=503, headers={"Retry-After": "5"})
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


app.add_middleware(OidcTokenMiddleware)
app.add_middleware(DbReadyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(content.router, prefix="/api/content", tags=["content"])
app.include_router(ads.router, prefix="/api/ads", tags=["ads"])
app.include_router(plans.router, prefix="/api/plans", tags=["plans"])
app.include_router(payments.router, prefix="/api/payments", tags=["payments"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["uploads"])
app.include_router(free.router, prefix="/api/free", tags=["free"])
app.include_router(voice.router, prefix="/api/voice", tags=["voice"])
app.include_router(chats.router, prefix="/api/chats", tags=["chats"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(support.router, prefix="/api/support", tags=["support"])
app.include_router(health.router, prefix="/api/health", tags=["health"])


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        # Sırayla denenecek yapay zeka sağlayıcıları; ilki birincil, gerisi yedek.
        "ai": llm_service.available_providers(),
        "payments": iyzico_service.is_configured(),
        "database": "postgres" if config.DATABASE_URL.startswith("postgres") else "sqlite",
    }
