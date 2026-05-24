from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.chat.service import chat

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    model: str = ""


class ChatResponse(BaseModel):
    response: str
    model: str
    total_tokens: int
    tool_calls_made: int


@router.post("/message", response_model=ChatResponse)
async def send_message(body: ChatRequest):
    result = await chat(body.message, body.history, body.model)
    return ChatResponse(**result)


@router.get("/models")
async def list_models():
    return {
        "models": [
            {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini", "cost": "cheapest", "recommended": True},
            {"id": "gpt-4.1-nano", "name": "GPT-4.1 Nano", "cost": "ultra cheap", "recommended": False},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "cost": "cheap", "recommended": False},
            {"id": "gpt-4o", "name": "GPT-4o", "cost": "moderate", "recommended": False},
        ],
        "default": "gpt-4.1-mini",
        "note": "Tools do the heavy lifting — cheap models work well for routing.",
    }
