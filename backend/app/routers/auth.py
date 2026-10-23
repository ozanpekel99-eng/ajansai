import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import get_engine, users, utcnow
from app.security import create_token, get_current_user, hash_password, verify_password
from app import config
from app.services import social_auth
from app.services.plans import FREE_PLAN
from app.services.usage_service import get_usage

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    name: str = Field("", max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., max_length=72)


def _public_user(user: dict) -> dict:
    return {"id": user["id"], "email": user["email"], "name": user["name"]}


def _new_user(email: str, password_hash: str, name: str) -> dict:
    now = utcnow()
    return {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": password_hash,
        "name": name.strip()[:200],
        "plan": FREE_PLAN,
        "plan_expires_at": None,
        "period_start": now,
        "video_used": 0,
        "image_used": 0,
        "idea_used": 0,
        "created_at": now,
    }


@router.post("/register", status_code=201)
def register(payload: RegisterRequest):
    if len(payload.password.encode("utf-8")) > 72:
        raise HTTPException(status_code=422, detail="Şifre en fazla 72 bayt olabilir.")

    email = payload.email.strip().lower()
    user = _new_user(email, hash_password(payload.password), payload.name)
    try:
        with get_engine().begin() as conn:
            conn.execute(users.insert().values(**user))
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Bu e-posta ile zaten bir hesap var.")

    return {"token": create_token(user["id"]), "user": _public_user(user)}


@router.post("/login")
def login(payload: LoginRequest):
    email = payload.email.strip().lower()
    with get_engine().connect() as conn:
        row = conn.execute(select(users).where(func.lower(users.c.email) == email)).first()

    if row is None or not verify_password(payload.password, row.password_hash):
        raise HTTPException(status_code=401, detail="E-posta veya şifre hatalı.")

    user = dict(row._mapping)
    return {"token": create_token(user["id"]), "user": _public_user(user)}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return {"user": _public_user(user), "usage": get_usage(user["id"])}


# ---------------- Google / Apple ile giriş ----------------

SOCIAL_PASSWORD = "!social"  # bcrypt özeti değil; bu hesaplara şifreyle girilemez


@router.get("/providers")
def providers():
    """Arayüzün göstereceği giriş yöntemleri (istemci kimlikleri gizli değildir)."""
    return {"google_client_id": config.GOOGLE_CLIENT_ID, "apple_client_id": config.APPLE_CLIENT_ID}


def _social_login(email: str, name: str) -> dict:
    with get_engine().connect() as conn:
        row = conn.execute(select(users).where(func.lower(users.c.email) == email)).first()
    created = row is None
    if row is None:
        user = _new_user(email, SOCIAL_PASSWORD, name)
        try:
            with get_engine().begin() as conn:
                conn.execute(users.insert().values(**user))
        except IntegrityError:  # aynı anda iki istek
            with get_engine().connect() as conn:
                user = dict(conn.execute(select(users).where(func.lower(users.c.email) == email)).first()._mapping)
    else:
        user = dict(row._mapping)
    return {"token": create_token(user["id"]), "user": _public_user(user), "created": created}


class GoogleLogin(BaseModel):
    credential: str = Field(..., max_length=5000)


@router.post("/google")
def google_login(payload: GoogleLogin):
    try:
        claims = social_auth.verify("google", payload.credential)
    except social_auth.SocialAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return _social_login(claims["email"].lower(), claims.get("name") or "")


class AppleLogin(BaseModel):
    id_token: str = Field(..., max_length=5000)
    # Apple adı yalnızca ilk girişte, token dışında gönderir
    name: str = Field("", max_length=200)


@router.post("/apple")
def apple_login(payload: AppleLogin):
    try:
        claims = social_auth.verify("apple", payload.id_token)
    except social_auth.SocialAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return _social_login(claims["email"].lower(), payload.name)
