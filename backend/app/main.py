import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.db import init_db
from app.routers import ads, auth, chats, content, free, payments, plans, uploads, voice
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


app.add_middleware(OidcTokenMiddleware)
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


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        # Sırayla denenecek yapay zeka sağlayıcıları; ilki birincil, gerisi yedek.
        "ai": llm_service.available_providers(),
        "payments": iyzico_service.is_configured(),
        "database": "postgres" if config.DATABASE_URL.startswith("postgres") else "sqlite",
    }
