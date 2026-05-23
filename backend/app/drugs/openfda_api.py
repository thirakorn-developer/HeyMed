"""
OpenFDA API client.
Free, no API key required (rate limited to 240 requests/min without key).
Docs: https://open.fda.gov/apis/
"""

import httpx

OPENFDA_BASE = "https://api.fda.gov"

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(base_url=OPENFDA_BASE, timeout=15.0)
    return _client


async def search_drug_labels(
    query: str, limit: int = 10, skip: int = 0
) -> dict:
    client = _get_client()
    resp = await client.get(
        "/drug/label.json",
        params={"search": query, "limit": limit, "skip": skip},
    )
    resp.raise_for_status()
    data = resp.json()
    meta = data.get("meta", {}).get("results", {})
    results = []
    for r in data.get("results", []):
        openfda = r.get("openfda", {})
        results.append({
            "brand_name": openfda.get("brand_name", []),
            "generic_name": openfda.get("generic_name", []),
            "manufacturer": openfda.get("manufacturer_name", []),
            "route": openfda.get("route", []),
            "product_type": openfda.get("product_type", []),
            "rxcui": openfda.get("rxcui", []),
            "indications": r.get("indications_and_usage", []),
            "warnings": r.get("warnings", []),
            "dosage": r.get("dosage_and_administration", []),
            "drug_interactions": r.get("drug_interactions", []),
            "adverse_reactions": r.get("adverse_reactions", []),
            "contraindications": r.get("contraindications", []),
        })
    return {"results": results, "total": meta.get("total", 0)}


async def get_drug_interactions_text(drug_name: str) -> list[dict]:
    client = _get_client()
    resp = await client.get(
        "/drug/label.json",
        params={
            "search": f'openfda.generic_name:"{drug_name}"',
            "limit": 1,
        },
    )
    if resp.status_code != 200:
        return []
    data = resp.json()
    results = []
    for r in data.get("results", []):
        openfda = r.get("openfda", {})
        interactions = r.get("drug_interactions", [])
        if interactions:
            results.append({
                "drug_name": openfda.get("generic_name", [drug_name])[0],
                "brand_name": openfda.get("brand_name", [""])[0],
                "interactions_text": interactions[0],
            })
    return results


async def check_interaction_from_labels(drug1: str, drug2: str) -> dict | None:
    client = _get_client()
    query = f'drug_interactions:"{drug1}" AND drug_interactions:"{drug2}"'
    resp = await client.get(
        "/drug/label.json", params={"search": query, "limit": 3}
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    total = data.get("meta", {}).get("results", {}).get("total", 0)
    if total == 0:
        return None

    mentions = []
    for r in data.get("results", []):
        openfda = r.get("openfda", {})
        interactions_text = r.get("drug_interactions", [""])[0]
        mentions.append({
            "source_drug": openfda.get("generic_name", [""])[0],
            "brand": openfda.get("brand_name", [""])[0],
            "interaction_text": interactions_text[:1000],
        })

    return {
        "drug1": drug1,
        "drug2": drug2,
        "found": True,
        "total_labels_mentioning": total,
        "mentions": mentions,
        "source": "openfda_labels",
    }


async def get_adverse_events(
    drug_name: str, limit: int = 10
) -> list[dict]:
    client = _get_client()
    resp = await client.get(
        "/drug/event.json",
        params={
            "search": f'patient.drug.openfda.generic_name:"{drug_name}"',
            "count": "patient.reaction.reactionmeddrapt.exact",
            "limit": limit,
        },
    )
    if resp.status_code != 200:
        return []
    data = resp.json()
    return [
        {"reaction": r["term"], "count": r["count"]}
        for r in data.get("results", [])
    ]


async def search_ndc(
    brand_name: str | None = None,
    generic_name: str | None = None,
    ndc: str | None = None,
    limit: int = 10,
) -> list[dict]:
    client = _get_client()
    parts = []
    if brand_name:
        parts.append(f'brand_name:"{brand_name}"')
    if generic_name:
        parts.append(f'generic_name:"{generic_name}"')
    if ndc:
        parts.append(f'product_ndc:"{ndc}"')

    if not parts:
        return []

    resp = await client.get(
        "/drug/ndc.json",
        params={"search": "+AND+".join(parts), "limit": limit},
    )
    if resp.status_code != 200:
        return []
    data = resp.json()

    results = []
    for r in data.get("results", []):
        ingredients = [
            {"name": i.get("name", ""), "strength": i.get("strength", "")}
            for i in r.get("active_ingredients", [])
        ]
        results.append({
            "product_ndc": r.get("product_ndc", ""),
            "brand_name": r.get("brand_name", ""),
            "generic_name": r.get("generic_name", ""),
            "dosage_form": r.get("dosage_form", ""),
            "route": r.get("route", []),
            "active_ingredients": ingredients,
            "marketing_category": r.get("marketing_category", ""),
            "labeler_name": r.get("labeler_name", ""),
        })
    return results


async def get_drug_recalls(
    drug_name: str | None = None,
    limit: int = 10,
) -> list[dict]:
    client = _get_client()
    query = f'reason_for_recall:"{drug_name}"' if drug_name else ""
    resp = await client.get(
        "/drug/enforcement.json",
        params={"search": query, "limit": limit} if query else {"limit": limit},
    )
    if resp.status_code != 200:
        return []
    data = resp.json()

    return [
        {
            "product": r.get("product_description", "")[:200],
            "reason": r.get("reason_for_recall", "")[:300],
            "classification": r.get("classification", ""),
            "status": r.get("status", ""),
            "recall_initiation_date": r.get("recall_initiation_date", ""),
            "city": r.get("city", ""),
            "state": r.get("state", ""),
        }
        for r in data.get("results", [])
    ]
