import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import get_engine, users, utcnow
from app.security import create_token, get_current_user, hash_password, verify_password
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


@router.post("/register", status_code=201)
def register(payload: RegisterRequest):
    if len(payload.password.encode("utf-8")) > 72:
        raise HTTPException(status_code=422, detail="Şifre en fazla 72 bayt olabilir.")

    email = payload.email.strip().lower()
    now = utcnow()
    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name.strip(),
        "plan": FREE_PLAN,
        "plan_expires_at": None,
        "period_start": now,
        "video_used": 0,
        "image_used": 0,
        "idea_used": 0,
        "created_at": now,
    }
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
