"""
RxNorm REST API client.
Free, no registration required.
Docs: https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html
"""

import httpx

RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(base_url=RXNORM_BASE, timeout=15.0)
    return _client


async def search_by_name(name: str) -> list[dict]:
    client = _get_client()
    resp = await client.get("/drugs.json", params={"name": name})
    resp.raise_for_status()
    data = resp.json()

    results = []
    groups = data.get("drugGroup", {}).get("conceptGroup", [])
    for group in groups:
        for concept in group.get("conceptProperties", []):
            results.append({
                "rxcui": int(concept["rxcui"]),
                "name": concept["name"],
                "tty": concept["tty"],
                "synonym": concept.get("synonym", ""),
            })
    return results


async def approximate_match(term: str, max_entries: int = 10) -> list[dict]:
    client = _get_client()
    resp = await client.get(
        "/approximateTerm.json", params={"term": term, "maxEntries": max_entries}
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    seen = set()
    candidates = data.get("approximateGroup", {}).get("candidate", [])
    for c in candidates:
        rxcui = int(c["rxcui"])
        if rxcui in seen or "name" not in c:
            continue
        seen.add(rxcui)
        results.append({
            "rxcui": rxcui,
            "name": c["name"],
            "score": float(c.get("score", 0)),
        })
    return results


async def get_properties(rxcui: int) -> dict | None:
    client = _get_client()
    resp = await client.get(f"/rxcui/{rxcui}/properties.json")
    resp.raise_for_status()
    data = resp.json()
    props = data.get("properties")
    if not props:
        return None
    return {
        "rxcui": int(props["rxcui"]),
        "name": props["name"],
        "tty": props["tty"],
        "synonym": props.get("synonym", ""),
    }


async def get_related(rxcui: int, relation: str = "has_ingredient") -> list[dict]:
    client = _get_client()
    resp = await client.get(
        f"/rxcui/{rxcui}/related.json", params={"rela": relation}
    )
    resp.raise_for_status()
    data = resp.json()

    results = []
    groups = data.get("relatedGroup", {}).get("conceptGroup", [])
    for group in groups:
        for concept in group.get("conceptProperties", []):
            results.append({
                "rxcui": int(concept["rxcui"]),
                "name": concept["name"],
                "tty": concept["tty"],
            })
    return results


async def get_all_related(rxcui: int) -> dict:
    client = _get_client()
    resp = await client.get(f"/rxcui/{rxcui}/allrelated.json")
    resp.raise_for_status()
    data = resp.json()

    grouped = {}
    groups = data.get("allRelatedGroup", {}).get("conceptGroup", [])
    for group in groups:
        tty = group.get("tty", "")
        concepts = []
        for concept in group.get("conceptProperties", []):
            concepts.append({
                "rxcui": int(concept["rxcui"]),
                "name": concept["name"],
                "tty": concept["tty"],
            })
        if concepts:
            grouped[tty] = concepts
    return grouped


async def get_ndcs(rxcui: int) -> list[str]:
    client = _get_client()
    resp = await client.get(f"/rxcui/{rxcui}/ndcs.json")
    resp.raise_for_status()
    data = resp.json()
    ndc_group = data.get("ndcGroup", {})
    return ndc_group.get("ndcList", {}).get("ndc", [])


async def get_spelling_suggestions(term: str) -> list[str]:
    client = _get_client()
    resp = await client.get("/spellingsuggestions.json", params={"name": term})
    resp.raise_for_status()
    data = resp.json()
    group = data.get("suggestionGroup", {})
    return group.get("suggestionList", {}).get("suggestion", [])
