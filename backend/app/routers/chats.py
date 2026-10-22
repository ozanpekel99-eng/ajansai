"""Sohbet geçmişi: giriş yapmış kullanıcının sohbetleri sunucuda saklanır (her cihazdan görünür)."""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, select, update

from app.db import conversations, get_engine, utcnow
from app.security import get_current_user

router = APIRouter()

MAX_BYTES = 800_000  # bir sohbetin JSON boyutu
MAX_CHATS = 300  # kullanıcı başı; fazlası en eskiden silinir


class ChatIn(BaseModel):
    title: str = Field("Sohbet", max_length=200)
    messages: list[dict[str, Any]] = Field(default_factory=list, max_length=200)


def _own(conn, chat_id: str, user_id: str):
    return conn.execute(
        select(conversations).where(and_(conversations.c.id == chat_id, conversations.c.user_id == user_id))
    ).first()


@router.get("")
def list_chats(limit: int = 50, user: dict = Depends(get_current_user)):
    with get_engine().connect() as conn:
        rows = conn.execute(
            select(conversations.c.id, conversations.c.title, conversations.c.updated_at)
            .where(conversations.c.user_id == user["id"])
            .order_by(conversations.c.updated_at.desc())
            .limit(max(1, min(limit, 200)))
        ).all()
    return [{"id": r.id, "title": r.title, "updated_at": r.updated_at.isoformat() + "Z"} for r in rows]


@router.get("/{chat_id}")
def get_chat(chat_id: str, user: dict = Depends(get_current_user)):
    with get_engine().connect() as conn:
        row = _own(conn, chat_id, user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="Sohbet bulunamadı.")
    return {"id": row.id, "title": row.title, "messages": json.loads(row.messages), "updated_at": row.updated_at.isoformat() + "Z"}


@router.put("/{chat_id}")
def save_chat(chat_id: str, payload: ChatIn, user: dict = Depends(get_current_user)):
    if not (0 < len(chat_id) <= 64):
        raise HTTPException(status_code=400, detail="Geçersiz sohbet kimliği.")
    data = json.dumps(payload.messages, ensure_ascii=False)
    if len(data.encode()) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Sohbet çok uzun; yeni bir sohbet başlat.")
    title = (payload.title or "Sohbet").strip()[:200] or "Sohbet"
    now = utcnow()
    with get_engine().begin() as conn:
        existing = conn.execute(select(conversations.c.user_id).where(conversations.c.id == chat_id)).first()
        if existing is not None and existing.user_id != user["id"]:
            raise HTTPException(status_code=404, detail="Sohbet bulunamadı.")
        if existing is None:
            conn.execute(conversations.insert().values(id=chat_id, user_id=user["id"], title=title, messages=data, updated_at=now))
            old = conn.execute(
                select(conversations.c.id).where(conversations.c.user_id == user["id"])
                .order_by(conversations.c.updated_at.desc()).offset(MAX_CHATS)
            ).scalars().all()
            if old:
                conn.execute(delete(conversations).where(conversations.c.id.in_(old)))
        else:
            conn.execute(update(conversations).where(conversations.c.id == chat_id).values(title=title, messages=data, updated_at=now))
    return {"id": chat_id, "title": title, "updated_at": now.isoformat() + "Z"}


@router.delete("/{chat_id}", status_code=204)
def delete_chat(chat_id: str, user: dict = Depends(get_current_user)):
    with get_engine().begin() as conn:
        conn.execute(delete(conversations).where(and_(conversations.c.id == chat_id, conversations.c.user_id == user["id"])))
    return Response(status_code=204)
