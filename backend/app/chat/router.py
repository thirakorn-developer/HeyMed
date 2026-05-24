from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.models import ChatSession
from app.chat.service import chat_in_session, create_session, get_session_messages
from app.database import get_db

router = APIRouter()


class CreateSessionRequest(BaseModel):
    patient_id: str | None = None
    pharmacist_id: str | None = None
    title: str = ""
    model: str = "gpt-4.1-mini"


class SendMessageRequest(BaseModel):
    message: str
    model: str = ""


@router.post("/sessions")
async def create_chat_session(body: CreateSessionRequest, db: AsyncSession = Depends(get_db)):
    session = await create_session(db, body.patient_id, body.pharmacist_id, body.title, body.model)
    return {
        "session_id": str(session.id),
        "title": session.title,
        "model": session.model_used,
        "created_at": session.created_at.isoformat(),
    }


@router.get("/sessions")
async def list_sessions(
    patient_id: str | None = Query(None),
    status: str = Query("active"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ChatSession).order_by(ChatSession.updated_at.desc()).limit(limit)
    if patient_id:
        stmt = stmt.where(ChatSession.patient_id == patient_id)
    if status:
        stmt = stmt.where(ChatSession.status == status)
    result = await db.execute(stmt)
    sessions = result.scalars().all()
    return {
        "sessions": [
            {
                "session_id": str(s.id),
                "patient_id": str(s.patient_id) if s.patient_id else None,
                "pharmacist_id": str(s.pharmacist_id) if s.pharmacist_id else None,
                "title": s.title,
                "model": s.model_used,
                "total_tokens": s.total_tokens,
                "total_messages": s.total_messages,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
            }
            for s in sessions
        ],
        "total": len(sessions),
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    messages = await get_session_messages(db, session_id)
    return {
        "session_id": session_id,
        "messages": messages,
        "total_messages": len(messages),
    }


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    body: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await chat_in_session(db, session_id, body.message, body.model)
    return result


@router.get("/models")
async def list_models():
    return {
        "models": [
            {"id": "gpt-4.1-nano", "name": "GPT-4.1 Nano", "cost": "$0.10/M input", "speed": "fastest"},
            {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini", "cost": "$0.40/M input", "speed": "fast", "recommended": True},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "cost": "$0.15/M input", "speed": "fast"},
            {"id": "gpt-4o", "name": "GPT-4o", "cost": "$2.50/M input", "speed": "moderate"},
        ],
        "default": "gpt-4.1-mini",
    }
