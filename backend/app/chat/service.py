"""
Pharmacy chat with session persistence.
Saves all conversations for audit trail and continuity.
"""

import json
import uuid

import httpx
from openai import AsyncOpenAI
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User  # noqa: F401 — ensure model loaded
from app.customers.models import Patient  # noqa: F401 — ensure model loaded
from app.chat.models import ChatMessage, ChatSession
from app.config import settings

SYSTEM_PROMPT = """You are HeyMed AI, a pharmacy assistant for Thai pharmacists.
You help with drug information, interactions, dosing, and patient safety.

RULES:
- ALWAYS use tools to look up drug data. Never guess or say "no data available" without trying a tool first.
- Respond in the same language the user uses (Thai or English).
- Keep responses concise and practical for pharmacy use.
- Always mention important warnings and contraindications.
- For dosing: show the calculation AND remind to verify with FDA label.
- When patient has an allergy: use find_alternatives to suggest drugs in different classes.
- When asking about drugs in Thailand: use thai_fda_search.
- For drug class questions: use browse_drug_class (supports abbreviations like "statin", "ACE inhibitor", "NSAID").
- Use multiple tools in sequence if needed to give a complete answer."""

TOOLS = [
    {"type": "function", "function": {
        "name": "search_drugs",
        "description": "Search drugs by name in Thai or English.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Drug name (e.g., 'paracetamol', 'ยาแก้ปวด')"},
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "check_interactions",
        "description": "Check drug-drug interactions between 2+ drugs.",
        "parameters": {"type": "object", "properties": {
            "drug_names": {"type": "array", "items": {"type": "string"}},
        }, "required": ["drug_names"]},
    }},
    {"type": "function", "function": {
        "name": "calculate_dose",
        "description": "Calculate drug dosage by weight/age.",
        "parameters": {"type": "object", "properties": {
            "drug_name": {"type": "string"},
            "patient_weight_kg": {"type": "number"},
            "patient_age_years": {"type": "number"},
            "is_pediatric": {"type": "boolean", "default": False},
        }, "required": ["drug_name"]},
    }},
    {"type": "function", "function": {
        "name": "adverse_events",
        "description": "Get side effects from FDA patient reports.",
        "parameters": {"type": "object", "properties": {
            "drug_name": {"type": "string"},
        }, "required": ["drug_name"]},
    }},
    {"type": "function", "function": {
        "name": "pregnancy_info",
        "description": "Pregnancy and breastfeeding safety.",
        "parameters": {"type": "object", "properties": {
            "drug_name": {"type": "string"},
        }, "required": ["drug_name"]},
    }},
    {"type": "function", "function": {
        "name": "food_interactions",
        "description": "Drug-food/alcohol interactions.",
        "parameters": {"type": "object", "properties": {
            "drug_name": {"type": "string"},
        }, "required": ["drug_name"]},
    }},
    {"type": "function", "function": {
        "name": "find_alternatives",
        "description": "Find drugs in the same pharmacological class.",
        "parameters": {"type": "object", "properties": {
            "drug_name": {"type": "string"},
        }, "required": ["drug_name"]},
    }},
    {"type": "function", "function": {
        "name": "assess_symptoms",
        "description": "Assess symptoms and recommend OTC drugs with safety checks.",
        "parameters": {"type": "object", "properties": {
            "symptoms": {"type": "array", "items": {"type": "string"}},
            "patient_age_years": {"type": "number", "default": 30},
            "is_pregnant": {"type": "boolean", "default": False},
            "allergies": {"type": "array", "items": {"type": "string"}, "default": []},
        }, "required": ["symptoms"]},
    }},
    {"type": "function", "function": {
        "name": "warnings",
        "description": "Drug warnings and contraindications from FDA labels.",
        "parameters": {"type": "object", "properties": {
            "drug_name": {"type": "string"},
        }, "required": ["drug_name"]},
    }},
    {"type": "function", "function": {
        "name": "drug_recalls",
        "description": "Check FDA drug recalls.",
        "parameters": {"type": "object", "properties": {
            "drug_name": {"type": "string"},
        }, "required": ["drug_name"]},
    }},
    {"type": "function", "function": {
        "name": "find_alternatives",
        "description": "Find alternative drugs in the same pharmacological class. Use when patient needs a substitute (e.g., allergic to one drug, need another in same class, or looking for generic options).",
        "parameters": {"type": "object", "properties": {
            "drug_name": {"type": "string", "description": "Drug to find alternatives for"},
        }, "required": ["drug_name"]},
    }},
    {"type": "function", "function": {
        "name": "storage_conditions",
        "description": "Get drug storage requirements (refrigeration, room temperature, light sensitivity).",
        "parameters": {"type": "object", "properties": {
            "drug_name": {"type": "string"},
        }, "required": ["drug_name"]},
    }},
    {"type": "function", "function": {
        "name": "thai_fda_search",
        "description": "Search Thai FDA (อย.) drug registration database. Check if drug is registered in Thailand.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"},
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "dosing_info",
        "description": "Get FDA-approved dosage and administration guidelines from official drug label.",
        "parameters": {"type": "object", "properties": {
            "drug_name": {"type": "string"},
        }, "required": ["drug_name"]},
    }},
    {"type": "function", "function": {
        "name": "browse_drug_class",
        "description": "Browse all drugs in a pharmacological class. Accepts abbreviations: statin, ACE inhibitor, PPI, NSAID, ARB, SSRI, beta blocker, CCB.",
        "parameters": {"type": "object", "properties": {
            "pharmacologic_class": {"type": "string", "description": "Class name or abbreviation"},
        }, "required": ["pharmacologic_class"]},
    }},
]

TOOL_ENDPOINT_MAP = {
    "search_drugs": ("GET", "/api/v1/drugs/search", lambda a: {"q": a["query"], "limit": 5}),
    "check_interactions": ("POST", "/api/v1/interactions/check", lambda a: a),
    "adverse_events": ("GET", "/api/v1/interactions/adverse-events", lambda a: {"drug_name": a["drug_name"]}),
    "food_interactions": ("GET", "/api/v1/drugs/search", lambda a: {"q": a["drug_name"], "limit": 3}),
    "find_alternatives": ("GET", "/api/v1/ndc/alternatives", lambda a: {"drug_name": a["drug_name"], "limit": 10}),
    "pregnancy_info": ("GET", "/api/v1/drugs/search", lambda a: {"q": a["drug_name"], "limit": 1}),
    "storage_conditions": ("GET", "/api/v1/drugs/search", lambda a: {"q": a["drug_name"], "limit": 1}),
    "thai_fda_search": ("GET", "/api/v1/ndc/search", lambda a: {"q": a["query"], "limit": 5}),
    "dosing_info": ("GET", "/api/v1/drugs/search", lambda a: {"q": a["drug_name"], "limit": 1}),
    "browse_drug_class": ("GET", "/api/v1/ndc/search", lambda a: {"q": a["pharmacologic_class"], "limit": 10}),
    "warnings": ("GET", "/api/v1/drugs/search", lambda a: {"q": a["drug_name"], "limit": 1}),
    "drug_recalls": ("GET", "/api/v1/interactions/recalls", lambda a: {"drug_name": a["drug_name"]}),
    "calculate_dose": ("GET", "/api/v1/drugs/search", lambda a: {"q": a["drug_name"], "limit": 1}),
    "assess_symptoms": (None, None, None),
}


async def _call_tool(tool_name: str, args: dict) -> str:
    mapping = TOOL_ENDPOINT_MAP.get(tool_name)
    if not mapping or not mapping[0]:
        return json.dumps({"note": f"Tool '{tool_name}' executed locally", "args": args})

    method, path, param_fn = mapping
    url = f"http://localhost:8000{path}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        if method == "GET":
            r = await client.get(url, params=param_fn(args))
        else:
            r = await client.post(url, json=param_fn(args))
        return r.text[:3000]


async def create_session(
    db: AsyncSession,
    patient_id: str | None = None,
    pharmacist_id: str | None = None,
    title: str = "",
    model: str = "gpt-4.1-mini",
) -> ChatSession:
    session = ChatSession(
        patient_id=uuid.UUID(patient_id) if patient_id else None,
        pharmacist_id=uuid.UUID(pharmacist_id) if pharmacist_id else None,
        title=title or "New consultation",
        model_used=model,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session_messages(db: AsyncSession, session_id: str) -> list[dict]:
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == uuid.UUID(session_id))
        .order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "tool_name": m.tool_name,
            "tokens_used": m.tokens_used,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


async def _save_message(
    db: AsyncSession,
    session_id: uuid.UUID,
    role: str,
    content: str | None = None,
    tool_calls: dict | None = None,
    tool_name: str | None = None,
    tool_result: str | None = None,
    tokens: int = 0,
):
    msg = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        tool_calls=tool_calls,
        tool_name=tool_name,
        tool_result=tool_result,
        tokens_used=tokens,
    )
    db.add(msg)


async def chat_in_session(
    db: AsyncSession,
    session_id: str,
    user_message: str,
    model: str = "",
) -> dict:
    sid = uuid.UUID(session_id)

    # Load session
    session = (await db.execute(
        select(ChatSession).where(ChatSession.id == sid)
    )).scalar_one_or_none()
    if not session:
        return {"error": "Session not found"}

    if not model:
        model = session.model_used or "gpt-4.1-mini"

    # Load history from DB
    history_rows = (await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == sid)
        .where(ChatMessage.role.in_(["user", "assistant"]))
        .order_by(ChatMessage.created_at)
    )).scalars().all()

    # Build messages for LLM (last 20 messages for context)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in history_rows[-20:]:
        if m.content:
            messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": user_message})

    # Save user message
    await _save_message(db, sid, "user", content=user_message)
    await db.flush()

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    total_tokens = 0
    tool_call_count = 0

    for iteration in range(8):
        try:
            response = await client.chat.completions.create(
                model=model, messages=messages, tools=TOOLS,
                tool_choice="auto", temperature=0.3, max_tokens=1000,
            )
        except Exception as e:
            ai_response = f"API error: {e}"
            await _save_message(db, sid, "assistant", content=ai_response)
            await db.commit()
            return {"session_id": session_id, "response": ai_response, "model": model,
                    "tokens_this_turn": total_tokens, "tool_calls_made": 0}

        total_tokens += response.usage.total_tokens if response.usage else 0
        choice = response.choices[0]

        has_tool_calls = choice.message.tool_calls and len(choice.message.tool_calls) > 0

        if has_tool_calls:
            tool_calls_data = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in choice.message.tool_calls
            ]
            messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls_data})

            for tc in choice.message.tool_calls:
                try:
                    tool_args = json.loads(tc.function.arguments)
                    tool_result = await _call_tool(tc.function.name, tool_args)
                except Exception as e:
                    tool_result = json.dumps({"error": str(e)})

                tool_call_count += 1
                await _save_message(db, sid, "tool",
                                    tool_name=tc.function.name,
                                    tool_result=tool_result[:2000])
                await db.flush()

                messages.append({
                    "role": "tool", "tool_call_id": tc.id,
                    "content": tool_result[:3000],
                })
            continue
        else:
            ai_response = choice.message.content or ""
            await _save_message(db, sid, "assistant", content=ai_response, tokens=total_tokens)

            # Update session stats
            await db.execute(
                update(ChatSession)
                .where(ChatSession.id == sid)
                .values(
                    total_tokens=ChatSession.total_tokens + total_tokens,
                    total_messages=ChatSession.total_messages + 2,
                    updated_at=func.now(),
                )
            )
            await db.commit()

            return {
                "session_id": session_id,
                "response": ai_response,
                "model": model,
                "tokens_this_turn": total_tokens,
                "tool_calls_made": tool_call_count,
            }

    # If we get here, the loop exhausted — try to get whatever content was last
    last_content = ""
    if messages:
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "assistant" and m.get("content"):
                last_content = m["content"]
                break

    if last_content:
        await _save_message(db, sid, "assistant", content=last_content, tokens=total_tokens)
        await db.commit()
        return {"session_id": session_id, "response": last_content, "model": model,
                "tokens_this_turn": total_tokens, "tool_calls_made": tool_call_count}

    await db.commit()
    return {"session_id": session_id, "response": "ขออภัย ไม่สามารถประมวลผลได้ กรุณาลองใหม่อีกครั้ง", "model": model,
            "tokens_this_turn": total_tokens, "tool_calls_made": tool_call_count}


# Need this import for the update statement
from sqlalchemy import func  # noqa: E402
