import httpx

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=15.0)
    return _client


# ── RxNorm API ──


async def rxnorm_search(name: str) -> list[dict]:
    client = _get_client()
    resp = await client.get(
        "https://rxnav.nlm.nih.gov/REST/drugs.json", params={"name": name}
    )
    resp.raise_for_status()
    results = []
    for group in resp.json().get("drugGroup", {}).get("conceptGroup", []):
        for c in group.get("conceptProperties", []):
            results.append({"rxcui": int(c["rxcui"]), "name": c["name"], "tty": c["tty"]})
    return results


async def rxnorm_properties(rxcui: int) -> dict | None:
    client = _get_client()
    resp = await client.get(f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/properties.json")
    resp.raise_for_status()
    props = resp.json().get("properties")
    if not props:
        return None
    return {"rxcui": int(props["rxcui"]), "name": props["name"], "tty": props["tty"]}


async def rxnorm_all_related(rxcui: int) -> dict:
    client = _get_client()
    resp = await client.get(f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/allrelated.json")
    resp.raise_for_status()
    grouped = {}
    for group in resp.json().get("allRelatedGroup", {}).get("conceptGroup", []):
        tty = group.get("tty", "")
        concepts = [
            {"rxcui": int(c["rxcui"]), "name": c["name"], "tty": c["tty"]}
            for c in group.get("conceptProperties", [])
        ]
        if concepts:
            grouped[tty] = concepts
    return grouped


async def rxnorm_ndcs(rxcui: int) -> list[str]:
    client = _get_client()
    resp = await client.get(f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/ndcs.json")
    resp.raise_for_status()
    return resp.json().get("ndcGroup", {}).get("ndcList", {}).get("ndc", [])


async def rxnorm_spelling(term: str) -> list[str]:
    client = _get_client()
    resp = await client.get(
        "https://rxnav.nlm.nih.gov/REST/spellingsuggestions.json", params={"name": term}
    )
    resp.raise_for_status()
    return resp.json().get("suggestionGroup", {}).get("suggestionList", {}).get("suggestion", [])


# ── OpenFDA API ──


async def openfda_interaction_check(drug1: str, drug2: str) -> dict | None:
    client = _get_client()
    mentions = []

    for source_drug, target_drug in [(drug1, drug2), (drug2, drug1)]:
        query = (
            f'openfda.generic_name:"{source_drug}"'
            f' AND drug_interactions:"{target_drug}"'
        )
        resp = await client.get(
            "https://api.fda.gov/drug/label.json", params={"search": query, "limit": 1}
        )
        if resp.status_code != 200:
            continue
        data = resp.json()
        total = data.get("meta", {}).get("results", {}).get("total", 0)
        if total == 0:
            continue
        for r in data.get("results", []):
            openfda = r.get("openfda", {})
            interaction_text = r.get("drug_interactions", [""])[0]
            # Extract the relevant portion mentioning the target drug
            text_lower = interaction_text.lower()
            target_lower = target_drug.lower()
            idx = text_lower.find(target_lower)
            if idx >= 0:
                start = max(0, idx - 200)
                end = min(len(interaction_text), idx + 500)
                excerpt = interaction_text[start:end]
            else:
                excerpt = interaction_text[:700]
            mentions.append({
                "source_drug": openfda.get("generic_name", [source_drug])[0],
                "brand": openfda.get("brand_name", [""])[0],
                "target_drug": target_drug,
                "interaction_text": excerpt,
                "total_labels": total,
            })

    if not mentions:
        return None
    return {
        "drug1": drug1,
        "drug2": drug2,
        "found": True,
        "total_labels": sum(m["total_labels"] for m in mentions),
        "mentions": mentions,
    }


async def openfda_adverse_events(drug_name: str, limit: int = 10) -> list[dict]:
    client = _get_client()
    resp = await client.get(
        "https://api.fda.gov/drug/event.json",
        params={
            "search": f'patient.drug.openfda.generic_name:"{drug_name}"',
            "count": "patient.reaction.reactionmeddrapt.exact",
            "limit": limit,
        },
    )
    if resp.status_code != 200:
        return []
    return [{"reaction": r["term"], "count": r["count"]} for r in resp.json().get("results", [])]


async def openfda_recalls(drug_name: str, limit: int = 5) -> list[dict]:
    client = _get_client()
    resp = await client.get(
        "https://api.fda.gov/drug/enforcement.json",
        params={"search": f'reason_for_recall:"{drug_name}"', "limit": limit},
    )
    if resp.status_code != 200:
        return []
    return [
        {
            "product": r.get("product_description", "")[:200],
            "reason": r.get("reason_for_recall", "")[:300],
            "classification": r.get("classification", ""),
            "status": r.get("status", ""),
        }
        for r in resp.json().get("results", [])
    ]


async def openfda_drug_label_sections(drug_name: str) -> dict | None:
    client = _get_client()

    # Try Rx label with single-ingredient match first
    queries = [
        f'openfda.generic_name:"{drug_name}" AND openfda.product_type:"HUMAN PRESCRIPTION DRUG"',
        f'openfda.generic_name:"{drug_name}"',
        f'openfda.brand_name:"{drug_name}"',
    ]

    r = None
    for query in queries:
        resp = await client.get(
            "https://api.fda.gov/drug/label.json",
            params={"search": query, "limit": 5},
        )
        if resp.status_code != 200:
            continue
        results = resp.json().get("results", [])
        if not results:
            continue
        # Prefer single-ingredient products
        for candidate in results:
            names = candidate.get("openfda", {}).get("generic_name", [])
            if names and drug_name.lower() in names[0].lower() and " AND " not in names[0].upper():
                r = candidate
                break
        if r:
            break
        r = results[0]
        break

    if not r:
        return None

    openfda = r.get("openfda", {})

    # Merge multiple warning fields — OpenFDA uses different keys
    warnings = (
        _truncate_list(r.get("boxed_warning", []))
        + _truncate_list(r.get("warnings_and_cautions", []))
        + _truncate_list(r.get("warnings", []))
        + _truncate_list(r.get("warnings_and_precautions", []))
    )

    # Merge pregnancy fields (old format: nursing_mothers, new format: pregnancy)
    pregnancy = (
        _truncate_list(r.get("pregnancy", []))
        + _truncate_list(r.get("pregnancy_or_breast_feeding", []))
    )
    nursing = (
        _truncate_list(r.get("nursing_mothers", []))
        + _truncate_list(r.get("lactation", []))
    )

    return {
        "brand_name": openfda.get("brand_name", []),
        "generic_name": openfda.get("generic_name", []),
        "manufacturer": openfda.get("manufacturer_name", []),
        "route": openfda.get("route", []),
        "substance_name": openfda.get("substance_name", []),
        "product_type": openfda.get("product_type", []),
        "indications_and_usage": _truncate_list(r.get("indications_and_usage", [])),
        "dosage_and_administration": _truncate_list(r.get("dosage_and_administration", [])),
        "warnings": warnings,
        "contraindications": _truncate_list(r.get("contraindications", [])),
        "drug_interactions": _truncate_list(r.get("drug_interactions", [])),
        "adverse_reactions": _truncate_list(r.get("adverse_reactions", [])),
        "overdosage": _truncate_list(r.get("overdosage", [])),
        "pregnancy": pregnancy,
        "nursing_mothers": nursing,
        "pediatric_use": _truncate_list(r.get("pediatric_use", [])),
        "geriatric_use": _truncate_list(r.get("geriatric_use", [])),
        "mechanism_of_action": _truncate_list(r.get("mechanism_of_action", [])),
        "pharmacodynamics": _truncate_list(r.get("pharmacodynamics", [])),
        "how_supplied": _truncate_list(r.get("how_supplied", [])),
        "storage_and_handling": _truncate_list(r.get("storage_and_handling", [])),
    }


def _truncate_list(items: list, max_chars: int = 2000) -> list[str]:
    return [item[:max_chars] for item in items] if items else []


# ── DailyMed API ──


async def dailymed_search(drug_name: str, limit: int = 5) -> list[dict]:
    client = _get_client()
    resp = await client.get(
        "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json",
        params={"drug_name": drug_name, "pagesize": limit},
    )
    if resp.status_code != 200:
        return []
    return [
        {"setid": r["setid"], "title": r["title"], "published_date": r["published_date"]}
        for r in resp.json().get("data", [])
    ]
