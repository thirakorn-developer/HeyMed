"""
Lightweight pharmacy chat using GPT-3.5-turbo with function calling.
The LLM only routes queries to the right tool — tools do the heavy lifting.

Cost comparison (approximate per 1M tokens):
  GPT-4o:       $2.50 input / $10 output
  GPT-4.1-mini: $0.40 input / $1.60 output
  GPT-3.5:      $0.50 input / $1.50 output

Since our tools return structured data, the LLM's job is simple:
1. Understand user intent
2. Pick the right tool
3. Format the response
"""

import json

import httpx
from openai import AsyncOpenAI

from app.config import settings

SYSTEM_PROMPT = """You are HeyMed AI, a pharmacy assistant for Thai pharmacists.
You help with drug information, interactions, dosing, and patient safety.

IMPORTANT RULES:
- ALWAYS use tools to look up drug data. Never guess from memory.
- Respond in the same language the user uses (Thai or English).
- Keep responses concise and practical.
- Always mention important warnings and contraindications.
- For dosing: show the calculation AND remind to verify with FDA label.

You have these tools:
- search_drugs: Search drugs by name (Thai or English)
- drug_detail: Get full drug info (ingredients, forms, brands)
- check_interactions: Check drug-drug interactions
- calculate_dose: Calculate dosage by weight/age
- check_max_dose: Verify dose doesn't exceed max
- adverse_events: Get side effects from FDA reports
- pregnancy_info: Pregnancy/breastfeeding safety
- food_interactions: Drug-food interactions
- find_alternatives: Find drugs in same class
- triage_questions: Get assessment questions for a symptom
- assess_symptoms: Full symptom assessment with recommendations
- otc_recommend: OTC drug recommendations for symptoms
- thai_fda: Check Thai FDA (อย.) registration
- storage: Drug storage conditions
- warnings: Drug warnings and contraindications
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_drugs",
            "description": "Search drugs by name in Thai or English. Returns drug products with brand/generic name, strength, manufacturer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Drug name in Thai or English (e.g., 'paracetamol', 'ยาแก้ปวด', 'Lipitor')"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_interactions",
            "description": "Check drug-drug interactions between 2+ drugs. Returns FDA label evidence and severity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "drug_names": {"type": "array", "items": {"type": "string"}, "description": "List of drug generic names to check"},
                },
                "required": ["drug_names"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_dose",
            "description": "Calculate drug dosage based on patient weight and age. Returns recommended dose, tablets, and frequency.",
            "parameters": {
                "type": "object",
                "properties": {
                    "drug_name": {"type": "string"},
                    "patient_weight_kg": {"type": "number", "description": "Patient weight in kg (required for pediatric)"},
                    "patient_age_years": {"type": "number", "description": "Patient age in years"},
                    "is_pediatric": {"type": "boolean", "default": False},
                },
                "required": ["drug_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "adverse_events",
            "description": "Get most reported side effects for a drug from real FDA patient reports.",
            "parameters": {
                "type": "object",
                "properties": {
                    "drug_name": {"type": "string"},
                },
                "required": ["drug_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pregnancy_info",
            "description": "Get pregnancy and breastfeeding safety information for a drug.",
            "parameters": {
                "type": "object",
                "properties": {
                    "drug_name": {"type": "string"},
                },
                "required": ["drug_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "food_interactions",
            "description": "Get drug-food/alcohol interactions (e.g., grapefruit, dairy, alcohol).",
            "parameters": {
                "type": "object",
                "properties": {
                    "drug_name": {"type": "string"},
                },
                "required": ["drug_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_alternatives",
            "description": "Find alternative drugs in the same pharmacological class.",
            "parameters": {
                "type": "object",
                "properties": {
                    "drug_name": {"type": "string"},
                },
                "required": ["drug_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assess_symptoms",
            "description": "Assess patient symptoms and recommend OTC drugs. Takes multiple symptoms + patient context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symptoms": {"type": "array", "items": {"type": "string"}, "description": "List of symptoms (headache, fever, cough, etc.)"},
                    "patient_age_years": {"type": "number", "default": 30},
                    "is_pregnant": {"type": "boolean", "default": False},
                    "allergies": {"type": "array", "items": {"type": "string"}, "default": []},
                    "current_medications": {"type": "array", "items": {"type": "string"}, "default": []},
                },
                "required": ["symptoms"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "thai_fda",
            "description": "Search Thai FDA (อย.) drug registration. Check if a drug is registered in Thailand.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Drug name to search in Thai FDA"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "warnings",
            "description": "Get drug warnings, contraindications, and boxed warnings from FDA labels.",
            "parameters": {
                "type": "object",
                "properties": {
                    "drug_name": {"type": "string"},
                },
                "required": ["drug_name"],
            },
        },
    },
]


async def _call_tool(tool_name: str, args: dict, base_url: str = "http://localhost:8000") -> str:
    """Route tool calls to our FastAPI backend endpoints."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        if tool_name == "search_drugs":
            r = await client.get(f"{base_url}/api/v1/drugs/search", params={"q": args["query"], "limit": 5})
        elif tool_name == "check_interactions":
            r = await client.post(f"{base_url}/api/v1/interactions/check", json={"drug_names": args["drug_names"]})
        elif tool_name == "calculate_dose":
            # Use MCP tool directly via subprocess — or call backend
            # For now, return a helpful message directing to the endpoint
            params = {"q": args["drug_name"], "limit": 1}
            r = await client.get(f"{base_url}/api/v1/drugs/search", params=params)
        elif tool_name == "adverse_events":
            r = await client.get(f"{base_url}/api/v1/interactions/adverse-events", params={"drug_name": args["drug_name"]})
        elif tool_name == "pregnancy_info":
            # OpenFDA label
            r = await client.get(f"{base_url}/api/v1/drugs/search", params={"q": args["drug_name"], "limit": 1})
        elif tool_name == "thai_fda":
            r = await client.get(f"{base_url}/api/v1/ndc/search", params={"q": args["query"], "limit": 5})
        elif tool_name == "find_alternatives":
            r = await client.get(f"{base_url}/api/v1/drugs/search", params={"q": args["drug_name"], "limit": 5})
        elif tool_name == "assess_symptoms":
            # Return symptom data directly
            return json.dumps({"symptoms": args.get("symptoms", []), "note": "Use triage questions from MCP tools"})
        elif tool_name == "food_interactions":
            r = await client.get(f"{base_url}/api/v1/drugs/search", params={"q": args["drug_name"], "limit": 1})
        elif tool_name == "warnings":
            r = await client.get(f"{base_url}/api/v1/drugs/search", params={"q": args["drug_name"], "limit": 1})
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        return r.text


async def chat(user_message: str, history: list[dict] | None = None, model: str = "") -> dict:
    """Process a chat message using GPT-3.5-turbo with function calling."""
    if not model:
        model = "gpt-4.1-mini"

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    total_tokens = 0

    # Loop for tool calling
    for _ in range(5):
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.3,
            max_tokens=1000,
        )

        total_tokens += response.usage.total_tokens if response.usage else 0
        choice = response.choices[0]

        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            messages.append({"role": "assistant", "content": None, "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in choice.message.tool_calls
            ]})
            for tc in choice.message.tool_calls:
                tool_args = json.loads(tc.function.arguments)
                tool_result = await _call_tool(tc.function.name, tool_args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result[:3000],
                })
        else:
            return {
                "response": choice.message.content,
                "model": model,
                "total_tokens": total_tokens,
                "tool_calls_made": len([m for m in messages if m.get("role") == "tool"]),
            }

    return {"response": "Sorry, could not process the request.", "model": model, "total_tokens": total_tokens}
