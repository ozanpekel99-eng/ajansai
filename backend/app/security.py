"""Şifre özetleme, JWT üretimi ve istekten giriş yapmış kullanıcıyı bulma."""

import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import config
from app.db import app_settings, get_engine
from app.services.usage_service import UserNotFoundError, get_user

ALGORITHM = "HS256"
_bearer = HTTPBearer(auto_error=False)
_cached_secret: str | None = None


def _jwt_secret() -> str:
    """JWT_SECRET ortam değişkeni varsa onu, yoksa veritabanında saklanan anahtarı kullanır.

    Veritabanında da yoksa güçlü bir anahtar üretilip saklanır. Aynı anda iki
    örnek üretmeye çalışırsa birincisinin yazdığı kazanır, ikincisi onu okur.
    """
    global _cached_secret
    if config.JWT_SECRET:
        return config.JWT_SECRET
    if _cached_secret:
        return _cached_secret

    engine = get_engine()
    with engine.connect() as conn:
        value = conn.execute(select(app_settings.c.value).where(app_settings.c.key == "jwt_secret")).scalar()
    if value is None:
        try:
            with engine.begin() as conn:
                conn.execute(app_settings.insert().values(key="jwt_secret", value=secrets.token_urlsafe(48)))
        except IntegrityError:
            pass
        with engine.connect() as conn:
            value = conn.execute(select(app_settings.c.value).where(app_settings.c.key == "jwt_secret")).scalar_one()
    _cached_secret = value
    return value


def hash_password(password: str) -> str:
    # bcrypt en fazla 72 bayt işler; daha uzun şifreleri kayıtta reddediyoruz.
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_token(user_id: str, purpose: str = "access", expires: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "typ": purpose,
        "iat": now,
        "exp": now + (expires or timedelta(days=config.JWT_EXPIRE_DAYS)),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=ALGORITHM)


def decode_token(token: str, purpose: str = "access") -> str:
    """Geçerliyse kullanıcı ID'sini döndürür, değilse ValueError fırlatır."""
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[ALGORITHM])
    except jwt.PyJWTError as e:
        raise ValueError("Geçersiz veya süresi dolmuş oturum") from e
    if payload.get("typ") != purpose or not payload.get("sub"):
        raise ValueError("Geçersiz oturum")
    return payload["sub"]


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Bu işlem için giriş yapmalısın.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized
    try:
        user_id = decode_token(credentials.credentials)
        return get_user(user_id)
    except (ValueError, UserNotFoundError):
        raise unauthorized
