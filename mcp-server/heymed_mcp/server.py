import json
from itertools import combinations

from mcp.server.fastmcp import FastMCP

from heymed_mcp import db, external_apis

mcp = FastMCP(
    "HeyMed Pharmacy AI",
    instructions="""You are a pharmacy AI assistant with access to drug databases.
Use these tools to look up real drug data — never guess drug facts from memory.
Always check interactions when a patient takes multiple medications.
Data sources: FDA NDC Directory (113K products), RxNorm, OpenFDA, DailyMed.""",
)


# ── Drug Search Tools ──


@mcp.tool()
async def search_drugs_ndc(query: str, limit: int = 10) -> str:
    """Search the FDA NDC Directory (113K+ products) by drug name, brand name, or ingredient.
    Returns brand/generic name, dosage form, strength, route, manufacturer, and pharmacological class.
    Use this as the primary drug search — it's fast (local database) and comprehensive."""
    rows = await db.query(
        """
        SELECT product_ndc, brand_name, generic_name, dosage_form, route,
               substance_name, strength, strength_unit, labeler_name,
               product_type, dea_schedule, pharm_classes
        FROM ndc_products
        WHERE search_vector @@ plainto_tsquery('english', $1)
        ORDER BY ts_rank(search_vector, plainto_tsquery('english', $1)) DESC
        LIMIT $2
        """,
        query, limit,
    )
    if not rows:
        return json.dumps({"results": [], "hint": "No local results. Try search_drugs_rxnorm."})
    return json.dumps({"results": rows, "total": len(rows), "source": "fda_ndc_local"}, default=str)


@mcp.tool()
async def search_drugs_rxnorm(name: str) -> str:
    """Search drugs via the RxNorm API by name. Returns RXCUI identifiers, drug names, and term types (IN=Ingredient, SCD=Clinical Drug, SBD=Branded Drug, BN=Brand Name).
    Use RXCUI from results to call get_drug_detail for full information."""
    results = await external_apis.rxnorm_search(name)
    return json.dumps({"results": results[:20], "total": len(results)})


@mcp.tool()
async def get_drug_detail(rxcui: int) -> str:
    """Get comprehensive drug details by RXCUI: ingredients, dose forms, brand names, strengths, and NDC codes.
    Use this after finding an RXCUI from search_drugs_rxnorm."""
    props = await external_apis.rxnorm_properties(rxcui)
    if not props:
        return json.dumps({"error": "Drug not found"})
    related = await external_apis.rxnorm_all_related(rxcui)
    ndcs = await external_apis.rxnorm_ndcs(rxcui)
    return json.dumps({
        **props,
        "ingredients": related.get("IN", []) + related.get("MIN", []) + related.get("PIN", []),
        "dose_forms": related.get("DF", []),
        "brands": related.get("BN", []),
        "strengths": [s["name"] for s in related.get("SCDC", [])],
        "ndc_codes": ndcs[:20],
        "source": "rxnorm_api",
    })


@mcp.tool()
async def lookup_ndc(ndc_code: str) -> str:
    """Look up a drug by its NDC (National Drug Code). Useful for barcode scanning.
    Returns full product info + all package sizes available."""
    pkg = await db.query_one(
        "SELECT product_ndc FROM ndc_packages WHERE ndc_package_code = $1", ndc_code
    )
    product_ndc = pkg["product_ndc"] if pkg else ndc_code

    products = await db.query(
        """
        SELECT product_ndc, brand_name, generic_name, dosage_form, route,
               substance_name, strength, strength_unit, labeler_name,
               product_type, marketing_category, application_number,
               dea_schedule, pharm_classes
        FROM ndc_products WHERE product_ndc = $1
        """,
        product_ndc,
    )
    if not products:
        return json.dumps({"found": False, "ndc_code": ndc_code})

    packages = await db.query(
        "SELECT ndc_package_code, package_description FROM ndc_packages WHERE product_ndc = $1",
        product_ndc,
    )
    return json.dumps({
        "found": True,
        "product": products[0],
        "packages": packages,
    }, default=str)


@mcp.tool()
async def suggest_spelling(term: str) -> str:
    """Get spelling suggestions for a drug name. Useful when the user misspells a drug name."""
    suggestions = await external_apis.rxnorm_spelling(term)
    return json.dumps({"query": term, "suggestions": suggestions})


# ── Drug Interaction Tools ──


@mcp.tool()
async def check_drug_interactions(drug_names: list[str]) -> str:
    """Check drug-drug interactions between 2 or more drugs using FDA drug label data.
    Pass generic drug names (e.g., ["aspirin", "warfarin", "lisinopril"]).
    Returns interaction details from FDA-approved drug labels with clinical significance."""
    names = list(dict.fromkeys(n.strip().lower() for n in drug_names if n.strip()))
    if len(names) < 2:
        return json.dumps({"error": "Need at least 2 different drug names"})

    pairs = list(combinations(names, 2))
    interactions = []
    for d1, d2 in pairs:
        result = await external_apis.openfda_interaction_check(d1, d2)
        if result:
            interactions.append(result)

    return json.dumps({
        "interactions_found": len(interactions),
        "pairs_checked": len(pairs),
        "interactions": interactions,
        "source": "openfda_labels",
    })


@mcp.tool()
async def get_adverse_events(drug_name: str, limit: int = 10) -> str:
    """Get the most commonly reported adverse events (side effects) for a drug
    from real-world FDA reports. Returns reactions ranked by number of reports."""
    events = await external_apis.openfda_adverse_events(drug_name, limit)
    return json.dumps({
        "drug_name": drug_name,
        "top_reactions": events,
        "source": "openfda_adverse_events",
    })


@mcp.tool()
async def get_drug_recalls(drug_name: str, limit: int = 5) -> str:
    """Check if a drug has any FDA recall/enforcement actions.
    Returns recall reason, classification (Class I=most serious), and status."""
    recalls = await external_apis.openfda_recalls(drug_name, limit)
    return json.dumps({
        "drug_name": drug_name,
        "recalls": recalls,
        "total": len(recalls),
        "source": "openfda_enforcement",
    })


# ── Drug Label & Clinical Info Tools ──


@mcp.tool()
async def search_drug_labels(drug_name: str, limit: int = 5) -> str:
    """Search FDA-approved drug labels from DailyMed.
    Returns SPL (Structured Product Labeling) documents with title and publish date."""
    labels = await external_apis.dailymed_search(drug_name, limit)
    return json.dumps({"drug_name": drug_name, "labels": labels, "source": "dailymed"})


@mcp.tool()
async def get_drug_label_full(drug_name: str) -> str:
    """Get comprehensive FDA drug label information including: indications, dosing,
    warnings, contraindications, interactions, adverse reactions, pregnancy/nursing info,
    pediatric/geriatric use, mechanism of action, and how supplied.
    This is the most detailed drug info tool — use it when you need clinical details."""
    label = await external_apis.openfda_drug_label_sections(drug_name)
    if not label:
        return json.dumps({"error": f"No FDA label found for {drug_name}"})
    return json.dumps({"drug_name": drug_name, **label, "source": "openfda_labels"})


@mcp.tool()
async def get_dosing_info(drug_name: str) -> str:
    """Get FDA-approved dosage and administration guidelines for a drug.
    Returns dosing info from the official drug label."""
    label = await external_apis.openfda_drug_label_sections(drug_name)
    if not label:
        return json.dumps({"error": f"No dosing info found for {drug_name}"})
    return json.dumps({
        "drug_name": drug_name,
        "brand_name": label.get("brand_name", []),
        "generic_name": label.get("generic_name", []),
        "route": label.get("route", []),
        "dosage_and_administration": label.get("dosage_and_administration", []),
        "how_supplied": label.get("how_supplied", []),
        "overdosage": label.get("overdosage", []),
        "source": "openfda_labels",
    })


@mcp.tool()
async def get_pregnancy_lactation_info(drug_name: str) -> str:
    """Get pregnancy and lactation/nursing safety information for a drug from FDA labels.
    Critical for counseling pregnant or breastfeeding patients."""
    label = await external_apis.openfda_drug_label_sections(drug_name)
    if not label:
        return json.dumps({"error": f"No pregnancy info found for {drug_name}"})
    return json.dumps({
        "drug_name": drug_name,
        "brand_name": label.get("brand_name", []),
        "pregnancy": label.get("pregnancy", []),
        "nursing_mothers": label.get("nursing_mothers", []),
        "pediatric_use": label.get("pediatric_use", []),
        "contraindications": label.get("contraindications", []),
        "source": "openfda_labels",
    })


@mcp.tool()
async def get_warnings_contraindications(drug_name: str) -> str:
    """Get warnings, contraindications, and boxed warnings for a drug.
    Essential for patient safety checks before dispensing."""
    label = await external_apis.openfda_drug_label_sections(drug_name)
    if not label:
        return json.dumps({"error": f"No warnings found for {drug_name}"})
    return json.dumps({
        "drug_name": drug_name,
        "brand_name": label.get("brand_name", []),
        "warnings": label.get("warnings", []),
        "contraindications": label.get("contraindications", []),
        "adverse_reactions": label.get("adverse_reactions", []),
        "source": "openfda_labels",
    })


# ── Pharmacy Helper Tools ──


@mcp.tool()
async def find_alternatives(drug_name: str, pharmacologic_class: str = "", limit: int = 10) -> str:
    """Find alternative drugs in the same pharmacological class.
    Optionally specify pharmacologic_class (e.g., "HMG-CoA Reductase Inhibitor") to pick
    the exact class. If omitted, auto-detects from single-ingredient products first."""
    if pharmacologic_class:
        pharmacologic_class = _resolve_class_alias(pharmacologic_class)
    if not pharmacologic_class:
        source = await db.query_one(
            """
            SELECT pharm_classes, generic_name, substance_name
            FROM ndc_products
            WHERE generic_name ILIKE $1
              AND pharm_classes IS NOT NULL
              AND pharm_classes != ''
            ORDER BY
                CASE WHEN substance_name NOT LIKE '%;%' THEN 0 ELSE 1 END,
                LENGTH(generic_name)
            LIMIT 1
            """,
            f"%{drug_name}%",
        )
        if not source or not source["pharm_classes"]:
            return json.dumps({"error": f"No pharmacological class found for {drug_name}"})

        epcs = []
        for cls in source["pharm_classes"].split(","):
            cls = cls.strip()
            if "[EPC]" in cls:
                epcs.append(cls.replace("[EPC]", "").strip())

        if not epcs:
            return json.dumps({"error": "No Established Pharmacologic Class found"})

        pharmacologic_class = epcs[0]
        all_classes = epcs
    else:
        all_classes = [pharmacologic_class]

    alternatives = await db.query(
        """
        SELECT DISTINCT ON (UPPER(generic_name))
            generic_name, brand_name, dosage_form, route, strength, strength_unit, labeler_name
        FROM ndc_products
        WHERE pharm_classes ILIKE $1
          AND generic_name NOT ILIKE $2
          AND substance_name NOT ILIKE $2
          AND substance_name NOT LIKE '%;%'
        ORDER BY UPPER(generic_name), brand_name
        LIMIT $3
        """,
        f"%{pharmacologic_class}%", f"%{drug_name}%", limit,
    )
    return json.dumps({
        "drug_name": drug_name,
        "matched_class": pharmacologic_class,
        "all_classes": all_classes,
        "alternatives": alternatives,
    }, default=str)


CLASS_ALIASES = {
    "ace inhibitor": "Angiotensin Converting Enzyme Inhibitor",
    "arb": "Angiotensin 2 Receptor Blocker",
    "nsaid": "Nonsteroidal Anti-inflammatory Drug",
    "ssri": "Serotonin Reuptake Inhibitor",
    "snri": "Serotonin and Norepinephrine Reuptake Inhibitor",
    "ppi": "Proton Pump Inhibitor",
    "statin": "HMG-CoA Reductase Inhibitor",
    "beta blocker": "beta-Adrenergic Blocker",
    "ccb": "Calcium Channel Blocker",
    "thiazide": "Thiazide Diuretic",
    "benzodiazepine": "Benzodiazepine",
    "opioid": "Opioid Agonist",
    "antihistamine": "Histamine H1 Receptor Antagonist",
    "glp-1": "GLP-1 Receptor Agonist",
    "sglt2": "Sodium-Glucose Transporter 2 Inhibitor",
    "dpp-4": "Dipeptidyl Peptidase 4 Inhibitor",
}


def _resolve_class_alias(name: str) -> str:
    return CLASS_ALIASES.get(name.lower().strip(), name)


@mcp.tool()
async def browse_drug_class(pharmacologic_class: str, limit: int = 20) -> str:
    """Browse all drugs in a given pharmacological class. Accepts common abbreviations
    (e.g., "ACE inhibitor", "statin", "NSAID", "PPI", "ARB", "SSRI", "beta blocker",
    "CCB", "GLP-1", "SGLT2", "DPP-4") or full EPC names."""
    pharmacologic_class = _resolve_class_alias(pharmacologic_class)
    rows = await db.query(
        """
        SELECT DISTINCT ON (UPPER(generic_name))
            generic_name, brand_name, dosage_form, route, substance_name,
            strength, strength_unit, labeler_name
        FROM ndc_products
        WHERE pharm_classes ILIKE $1
          AND substance_name NOT LIKE '%;%'
        ORDER BY UPPER(generic_name), brand_name
        LIMIT $2
        """,
        f"%{pharmacologic_class}%", limit,
    )
    return json.dumps({
        "pharmacologic_class": pharmacologic_class,
        "drugs": rows,
        "total": len(rows),
    }, default=str)


@mcp.tool()
async def list_drug_classes(query: str = "") -> str:
    """List available pharmacological classes (EPC) in the database.
    Optionally filter by keyword (e.g., "inhibitor", "blocker", "agonist")."""
    rows = await db.query(
        "SELECT DISTINCT pharm_classes FROM ndc_products WHERE pharm_classes IS NOT NULL LIMIT 5000"
    )
    classes: dict[str, int] = {}
    for row in rows:
        for cls in row["pharm_classes"].split(","):
            cls = cls.strip()
            if "[EPC]" in cls:
                name = cls.replace("[EPC]", "").strip()
                if query.lower() in name.lower():
                    classes[name] = classes.get(name, 0) + 1

    sorted_classes = sorted(classes.items(), key=lambda x: -x[1])[:50]
    return json.dumps({
        "query": query,
        "classes": [{"name": name, "product_count": count} for name, count in sorted_classes],
    })


@mcp.tool()
async def search_controlled_substances(schedule: str = "", query: str = "", limit: int = 20) -> str:
    """Search for DEA-scheduled controlled substances. Filter by schedule
    (CI, CII, CIII, CIV, CV) and/or drug name. Essential for controlled substance management."""
    conditions = ["dea_schedule IS NOT NULL", "dea_schedule != ''"]
    params: list = []
    idx = 1

    if schedule:
        conditions.append(f"dea_schedule = ${idx}")
        params.append(schedule.upper())
        idx += 1
    if query:
        conditions.append(f"search_vector @@ plainto_tsquery('english', ${idx})")
        params.append(query)
        idx += 1

    params.append(limit)
    where = " AND ".join(conditions)
    rows = await db.query(
        f"""
        SELECT DISTINCT ON (UPPER(generic_name))
            product_ndc, brand_name, generic_name, dosage_form, route,
            substance_name, strength, strength_unit, dea_schedule, labeler_name
        FROM ndc_products
        WHERE {where}
        ORDER BY UPPER(generic_name), brand_name
        LIMIT ${idx}
        """,
        *params,
    )
    return json.dumps({
        "schedule_filter": schedule or "all",
        "query": query,
        "results": rows,
        "total": len(rows),
    }, default=str)


@mcp.tool()
async def check_therapeutic_duplicates(drug_names: list[str]) -> str:
    """Check if a patient's medication list contains therapeutic duplicates — two or more drugs
    in the same pharmacological class. This is a safety check to prevent unnecessary polypharmacy.
    Pass generic drug names (e.g., ["omeprazole", "lansoprazole", "atorvastatin"])."""
    names = list(dict.fromkeys(n.strip().lower() for n in drug_names if n.strip()))
    if len(names) < 2:
        return json.dumps({"error": "Need at least 2 drugs to check for duplicates"})

    drug_classes: dict[str, list[str]] = {}
    for name in names:
        row = await db.query_one(
            """
            SELECT pharm_classes FROM ndc_products
            WHERE generic_name ILIKE $1
              AND pharm_classes IS NOT NULL AND pharm_classes != ''
            ORDER BY CASE WHEN substance_name NOT LIKE '%;%' THEN 0 ELSE 1 END
            LIMIT 1
            """,
            f"%{name}%",
        )
        if not row or not row["pharm_classes"]:
            continue
        for cls in row["pharm_classes"].split(","):
            cls = cls.strip()
            if "[EPC]" in cls:
                epc = cls.replace("[EPC]", "").strip()
                drug_classes.setdefault(epc, []).append(name)

    duplicates = []
    for epc, drugs in drug_classes.items():
        if len(drugs) > 1:
            duplicates.append({
                "pharmacologic_class": epc,
                "duplicate_drugs": drugs,
                "warning": f"Patient has {len(drugs)} drugs in the same class: {', '.join(drugs)}",
            })

    return json.dumps({
        "drugs_checked": names,
        "duplicates_found": len(duplicates),
        "duplicates": duplicates,
        "is_safe": len(duplicates) == 0,
    })


@mcp.tool()
async def get_special_population_dosing(drug_name: str) -> str:
    """Get dosing adjustments for special populations: renal impairment, hepatic impairment,
    pediatric, and geriatric patients. Extracted from FDA-approved labels."""
    label = await external_apis.openfda_drug_label_sections(drug_name)
    if not label:
        return json.dumps({"error": f"No FDA label found for {drug_name}"})

    dosing_text = label.get("dosage_and_administration", [""])[0] if label.get("dosage_and_administration") else ""
    renal_excerpt = ""
    hepatic_excerpt = ""
    for keyword in ["renal", "kidney", "egfr", "creatinine clearance", "clcr"]:
        idx = dosing_text.lower().find(keyword)
        if idx >= 0:
            start = max(0, idx - 100)
            end = min(len(dosing_text), idx + 500)
            renal_excerpt = dosing_text[start:end]
            break
    for keyword in ["hepatic", "liver", "child-pugh"]:
        idx = dosing_text.lower().find(keyword)
        if idx >= 0:
            start = max(0, idx - 100)
            end = min(len(dosing_text), idx + 500)
            hepatic_excerpt = dosing_text[start:end]
            break

    return json.dumps({
        "drug_name": drug_name,
        "brand_name": label.get("brand_name", []),
        "renal_dosing": renal_excerpt or "No specific renal dosing information found in label",
        "hepatic_dosing": hepatic_excerpt or "No specific hepatic dosing information found in label",
        "pediatric_use": label.get("pediatric_use", []),
        "geriatric_use": label.get("geriatric_use", []),
        "source": "openfda_labels",
    })


@mcp.tool()
async def get_ndc_stats() -> str:
    """Get statistics about the FDA NDC database: total products, packages, breakdown by type."""
    stats = await db.query(
        """
        SELECT product_type, COUNT(*) as count
        FROM ndc_products
        GROUP BY product_type
        ORDER BY count DESC
        """
    )
    total_products = sum(r["count"] for r in stats)
    total_packages = await db.query_one("SELECT COUNT(*) as count FROM ndc_packages")
    return json.dumps({
        "total_products": total_products,
        "total_packages": total_packages["count"] if total_packages else 0,
        "by_type": {r["product_type"]: r["count"] for r in stats},
    })


def main():
    mcp.run()


if __name__ == "__main__":
    main()
