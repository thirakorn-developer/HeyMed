import json
from datetime import date as date_type
from itertools import combinations

from mcp.server.fastmcp import FastMCP

from heymed_mcp import db, external_apis
from heymed_mcp.dosing_data import get_dosing, list_available_drugs

mcp = FastMCP(
    "HeyMed Pharmacy AI",
    instructions="""You are a pharmacy AI assistant with access to drug databases.
Use these tools to look up real drug data — never guess drug facts from memory.
Always check interactions when a patient takes multiple medications.
Data sources: FDA NDC Directory (113K products), RxNorm, OpenFDA, DailyMed.
Patient safety: medication records, allergy cross-reactivity, therapeutic duplicate detection.""",
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


# ── Dosage Calculator Tools ──


@mcp.tool()
async def calculate_dose(
    drug_name: str,
    patient_weight_kg: float = 0,
    patient_age_years: float = 0,
    is_pediatric: bool = False,
) -> str:
    """Calculate recommended dosage for a drug based on patient weight and age.
    For pediatric patients, set is_pediatric=true and provide weight in kg.
    Returns: calculated dose + FDA label reference for verification.
    IMPORTANT: Always verify calculated dose against FDA label before dispensing."""
    dosing = get_dosing(drug_name)

    # Always fetch FDA label as authoritative reference
    # FDA uses "acetaminophen" not "paracetamol"
    fda_lookup_name = drug_name
    if dosing:
        generic = dosing.get("generic_name", drug_name)
        if "acetaminophen" in generic.lower():
            fda_lookup_name = "acetaminophen"
    fda_dosing = await external_apis.openfda_drug_label_sections(fda_lookup_name)
    fda_text = ""
    if fda_dosing:
        fda_text = (fda_dosing.get("dosage_and_administration", [""])[0])[:1500]

    if not dosing:
        return json.dumps({
            "drug_name": drug_name,
            "calculation_available": False,
            "fda_dosing_text": fda_text or "No FDA label found",
            "message": f"No structured dosing data for '{drug_name}'. See FDA label text above for dosing guidance.",
            "available_drugs_for_calculation": list_available_drugs(),
            "disclaimer": "Always verify dosing with official FDA label or clinical reference before dispensing.",
        })

    strengths = dosing["available_strengths"]
    result: dict = {
        "drug_name": dosing["generic_name"],
        "available_strengths_mg": strengths,
    }

    if is_pediatric or (patient_age_years > 0 and patient_age_years < 18):
        ped = dosing.get("pediatric", {})
        if not ped or not ped.get("dose_per_kg"):
            return json.dumps({"error": f"No pediatric dosing data for {drug_name}"})

        min_age_months = ped.get("min_age_months", 0)
        age_months = patient_age_years * 12
        if age_months < min_age_months:
            result["warning"] = f"Not recommended under {min_age_months} months. {ped.get('notes', '')}"

        if patient_weight_kg <= 0:
            return json.dumps({"error": "Patient weight (kg) required for pediatric dosing"})

        dose_mg = round(ped["dose_per_kg"] * patient_weight_kg, 1)
        dose_low = round(ped["dose_range_per_kg"][0] * patient_weight_kg, 1)
        dose_high = round(ped["dose_range_per_kg"][1] * patient_weight_kg, 1)
        max_single = round(ped["max_single_dose_per_kg"] * patient_weight_kg, 1)
        max_daily = round(ped.get("max_daily_dose_per_kg", 0) * patient_weight_kg, 1)

        best_strength = _find_best_strength(dose_mg, strengths)
        tablets = round(dose_mg / best_strength, 2) if best_strength else None

        result.update({
            "patient_type": "pediatric",
            "weight_kg": patient_weight_kg,
            "age_years": patient_age_years,
            "recommended_dose_mg": dose_mg,
            "dose_range_mg": [dose_low, dose_high],
            "max_single_dose_mg": max_single,
            "max_daily_dose_mg": max_daily,
            "frequency": f"Every {ped['frequency_hours']} hours",
            "min_frequency": f"Not more often than every {ped['min_frequency_hours']} hours",
            "best_tablet_strength_mg": best_strength,
            "tablets_per_dose": tablets,
            "route": "oral",
            "notes": ped.get("notes", ""),
        })
    else:
        adult = dosing["adult"]
        dose_mg = adult["standard_dose"]
        best_strength = _find_best_strength(dose_mg, strengths)
        tablets = round(dose_mg / best_strength, 2) if best_strength else None

        result.update({
            "patient_type": "adult",
            "recommended_dose_mg": dose_mg,
            "dose_range_mg": adult["dose_range"],
            "max_single_dose_mg": adult["max_single_dose"],
            "max_daily_dose_mg": adult["max_daily_dose"],
            "max_doses_per_day": adult["max_doses_per_day"],
            "frequency": f"Every {adult['frequency_hours']} hours",
            "min_frequency": f"Not more often than every {adult['min_frequency_hours']} hours",
            "best_tablet_strength_mg": best_strength,
            "tablets_per_dose": tablets,
            "route": adult["route"],
            "notes": adult.get("notes", ""),
        })

    result["renal_adjustment"] = dosing.get("renal_adjustment", "")
    result["hepatic_adjustment"] = dosing.get("hepatic_adjustment", "")
    result["calculation_available"] = True
    result["fda_dosing_text"] = fda_text or "FDA label not available — verify with official reference"
    result["disclaimer"] = "CALCULATED DOSE — verify against FDA label before dispensing. This is a clinical decision support tool, not a substitute for professional judgment."
    return json.dumps(result)


@mcp.tool()
async def check_max_dose(drug_name: str, dose_mg: float, doses_per_day: int, patient_weight_kg: float = 0, is_pediatric: bool = False) -> str:
    """Check if a prescribed dose exceeds the maximum safe dose.
    Returns whether the dose is safe, and the maximum allowed."""
    dosing = get_dosing(drug_name)
    if not dosing:
        return json.dumps({"error": f"No dosing data for '{drug_name}'"})

    daily_total = dose_mg * doses_per_day

    if is_pediatric and patient_weight_kg > 0:
        ped = dosing.get("pediatric", {})
        if not ped:
            return json.dumps({"error": f"No pediatric dosing data for {drug_name}"})
        max_single = ped["max_single_dose_per_kg"] * patient_weight_kg
        max_daily = ped.get("max_daily_dose_per_kg", 999) * patient_weight_kg
        ref_type = "pediatric (weight-based)"
    else:
        adult = dosing["adult"]
        max_single = adult["max_single_dose"]
        max_daily = adult["max_daily_dose"]
        ref_type = "adult"

    single_ok = dose_mg <= max_single
    daily_ok = daily_total <= max_daily

    alerts = []
    if not single_ok:
        alerts.append(f"Single dose {dose_mg}mg exceeds max {max_single}mg")
    if not daily_ok:
        alerts.append(f"Daily total {daily_total}mg exceeds max {max_daily}mg")

    return json.dumps({
        "drug_name": dosing["generic_name"],
        "prescribed_dose_mg": dose_mg,
        "doses_per_day": doses_per_day,
        "daily_total_mg": daily_total,
        "max_single_dose_mg": round(max_single, 1),
        "max_daily_dose_mg": round(max_daily, 1),
        "reference_type": ref_type,
        "single_dose_ok": single_ok,
        "daily_dose_ok": daily_ok,
        "overall_safe": single_ok and daily_ok,
        "alerts": alerts,
    })


@mcp.tool()
async def list_dosing_drugs() -> str:
    """List all drugs that have structured dosing data available for calculation.
    These drugs support calculate_dose and check_max_dose tools."""
    drugs = list_available_drugs()
    details = []
    for name in drugs:
        d = get_dosing(name)
        if d:
            details.append({
                "drug_name": name,
                "generic_name": d["generic_name"],
                "strengths_mg": d["available_strengths"],
                "adult_standard_dose_mg": d["adult"]["standard_dose"],
                "adult_max_daily_mg": d["adult"]["max_daily_dose"],
                "has_pediatric": bool(d.get("pediatric", {}).get("dose_per_kg")),
            })
    return json.dumps({"drugs": details, "total": len(details)})


def _find_best_strength(target_dose: float, strengths: list[float]) -> float | None:
    if not strengths:
        return None
    exact = [s for s in strengths if target_dose % s == 0]
    if exact:
        return max(exact)
    below = [s for s in strengths if s <= target_dose]
    return max(below) if below else min(strengths)


# ── Patient Safety Tools ──


@mcp.tool()
async def create_patient(full_name: str, date_of_birth: str = "", gender: str = "", phone: str = "") -> str:
    """Create a new patient record. Returns the patient ID for use with other patient tools.
    date_of_birth format: YYYY-MM-DD"""
    dob = None
    if date_of_birth:
        dob = date_type.fromisoformat(date_of_birth)
    row = await db.query_one(
        """
        INSERT INTO patients (id, full_name, date_of_birth, gender, phone, is_active)
        VALUES (gen_random_uuid(), $1, $2, NULLIF($3,''), NULLIF($4,''), true)
        RETURNING id, full_name, date_of_birth, gender, phone, created_at
        """,
        full_name,
        dob,
        gender,
        phone,
    )
    return json.dumps({"patient": row}, default=str)


@mcp.tool()
async def search_patients(query: str) -> str:
    """Search patients by name or phone number."""
    rows = await db.query(
        """
        SELECT id, full_name, date_of_birth, gender, phone, is_active, created_at
        FROM patients
        WHERE full_name ILIKE $1 OR phone ILIKE $1
        ORDER BY full_name
        LIMIT 20
        """,
        f"%{query}%",
    )
    return json.dumps({"patients": rows, "total": len(rows)}, default=str)


@mcp.tool()
async def add_patient_medication(
    patient_id: str,
    drug_name: str,
    dosage: str = "",
    frequency: str = "",
    route: str = "",
    prescriber: str = "",
) -> str:
    """Add a medication to a patient's active medication list. This is used to track
    what the patient is currently taking for interaction and safety checks."""
    # Look up pharm class for the drug
    ndc_info = await db.query_one(
        """
        SELECT generic_name, product_ndc FROM ndc_products
        WHERE search_vector @@ plainto_tsquery('english', $1)
        ORDER BY ts_rank(search_vector, plainto_tsquery('english', $1)) DESC
        LIMIT 1
        """,
        drug_name,
    )
    row = await db.query_one(
        """
        INSERT INTO patient_medications
            (id, patient_id, drug_name, generic_name, product_ndc, dosage, frequency, route, prescriber, status)
        VALUES
            (gen_random_uuid(), $1::uuid, $2, $3, $4, NULLIF($5,''), NULLIF($6,''), NULLIF($7,''), NULLIF($8,''), 'active')
        RETURNING id, drug_name, generic_name, dosage, frequency, status, created_at
        """,
        patient_id,
        drug_name,
        ndc_info["generic_name"] if ndc_info else drug_name,
        ndc_info["product_ndc"] if ndc_info else None,
        dosage,
        frequency,
        route,
        prescriber,
    )
    return json.dumps({"medication_added": row}, default=str)


@mcp.tool()
async def get_patient_medications(patient_id: str) -> str:
    """Get all active medications for a patient. Essential for interaction checking
    and prescription review."""
    patient = await db.query_one("SELECT full_name FROM patients WHERE id = $1::uuid", patient_id)
    if not patient:
        return json.dumps({"error": "Patient not found"})

    meds = await db.query(
        """
        SELECT id, drug_name, generic_name, dosage, frequency, route, prescriber,
               start_date, status, created_at
        FROM patient_medications
        WHERE patient_id = $1::uuid AND status = 'active'
        ORDER BY created_at DESC
        """,
        patient_id,
    )
    return json.dumps({
        "patient_id": patient_id,
        "patient_name": patient["full_name"],
        "active_medications": meds,
        "total": len(meds),
    }, default=str)


@mcp.tool()
async def add_patient_allergy(
    patient_id: str,
    allergen: str,
    reaction: str = "",
    severity: str = "moderate",
) -> str:
    """Record a drug allergy for a patient. Severity: mild, moderate, severe, life_threatening.
    The system will auto-detect the drug's pharmacologic class for cross-reactivity checking."""
    # Look up pharm class for cross-reactivity
    ndc_info = await db.query_one(
        """
        SELECT pharm_classes FROM ndc_products
        WHERE generic_name ILIKE $1
          AND pharm_classes IS NOT NULL AND pharm_classes != ''
          AND substance_name NOT LIKE '%;%'
        LIMIT 1
        """,
        f"%{allergen}%",
    )
    pharm_class = None
    if ndc_info and ndc_info["pharm_classes"]:
        for cls in ndc_info["pharm_classes"].split(","):
            if "[EPC]" in cls:
                pharm_class = cls.replace("[EPC]", "").strip()
                break

    row = await db.query_one(
        """
        INSERT INTO patient_allergies
            (id, patient_id, allergen, allergen_type, reaction, severity, pharm_class)
        VALUES
            (gen_random_uuid(), $1::uuid, $2, 'drug', NULLIF($3,''), $4::allergyseverity, $5)
        RETURNING id, allergen, reaction, severity, pharm_class, created_at
        """,
        patient_id, allergen, reaction, severity, pharm_class,
    )
    return json.dumps({"allergy_recorded": row}, default=str)


@mcp.tool()
async def get_patient_allergies(patient_id: str) -> str:
    """Get all recorded allergies for a patient."""
    patient = await db.query_one("SELECT full_name FROM patients WHERE id = $1::uuid", patient_id)
    if not patient:
        return json.dumps({"error": "Patient not found"})

    allergies = await db.query(
        """
        SELECT id, allergen, reaction, severity, pharm_class, created_at
        FROM patient_allergies
        WHERE patient_id = $1::uuid
        ORDER BY severity DESC, created_at DESC
        """,
        patient_id,
    )
    return json.dumps({
        "patient_id": patient_id,
        "patient_name": patient["full_name"],
        "allergies": allergies,
        "total": len(allergies),
    }, default=str)


@mcp.tool()
async def check_allergy_cross_reactivity(patient_id: str, drug_name: str) -> str:
    """Check if a drug could cause an allergic reaction based on the patient's recorded allergies.
    Uses pharmacologic class matching — if a patient is allergic to penicillin, flags all
    penicillin-class drugs. Critical safety check before dispensing."""
    allergies = await db.query(
        "SELECT allergen, reaction, severity, pharm_class FROM patient_allergies WHERE patient_id = $1::uuid",
        patient_id,
    )
    if not allergies:
        return json.dumps({"safe": True, "message": "No allergies recorded for this patient"})

    # Get the drug's pharm class
    drug_info = await db.query_one(
        """
        SELECT generic_name, pharm_classes FROM ndc_products
        WHERE search_vector @@ plainto_tsquery('english', $1)
          AND pharm_classes IS NOT NULL
          AND substance_name NOT LIKE '%;%'
        ORDER BY ts_rank(search_vector, plainto_tsquery('english', $1)) DESC
        LIMIT 1
        """,
        drug_name,
    )

    alerts = []
    drug_name_lower = drug_name.lower()

    for allergy in allergies:
        # Direct name match
        if allergy["allergen"].lower() in drug_name_lower or drug_name_lower in allergy["allergen"].lower():
            alerts.append({
                "type": "DIRECT_MATCH",
                "severity": "critical",
                "allergen": allergy["allergen"],
                "reaction": allergy["reaction"],
                "recorded_severity": allergy["severity"],
                "message": f"DIRECT ALLERGY: Patient is allergic to {allergy['allergen']}!",
            })
            continue

        # Cross-reactivity via pharmacologic class
        if allergy["pharm_class"] and drug_info and drug_info["pharm_classes"]:
            if allergy["pharm_class"].lower() in drug_info["pharm_classes"].lower():
                alerts.append({
                    "type": "CROSS_REACTIVITY",
                    "severity": "high",
                    "allergen": allergy["allergen"],
                    "drug_class": allergy["pharm_class"],
                    "reaction": allergy["reaction"],
                    "message": f"CROSS-REACTIVITY: {drug_name} is in the same class ({allergy['pharm_class']}) as allergen {allergy['allergen']}",
                })

    return json.dumps({
        "patient_id": patient_id,
        "drug_checked": drug_name,
        "safe": len(alerts) == 0,
        "alerts": alerts,
        "total_alerts": len(alerts),
    }, default=str)


@mcp.tool()
async def patient_safety_check(patient_id: str, new_drug: str) -> str:
    """Comprehensive safety check before dispensing a new drug to a patient.
    Checks: 1) allergy cross-reactivity, 2) interactions with current meds,
    3) therapeutic duplicates. This is the ONE tool to call before dispensing."""
    patient = await db.query_one(
        "SELECT full_name FROM patients WHERE id = $1::uuid", patient_id
    )
    if not patient:
        return json.dumps({"error": "Patient not found"})

    # 1. Allergy check
    allergy_result = json.loads(await check_allergy_cross_reactivity(patient_id, new_drug))

    # 2. Get current meds
    meds = await db.query(
        "SELECT drug_name, generic_name FROM patient_medications WHERE patient_id = $1::uuid AND status = 'active'",
        patient_id,
    )
    med_names = [m["generic_name"] or m["drug_name"] for m in meds]

    # 3. Interaction check with current meds
    interaction_alerts = []
    if med_names:
        for med_name in med_names:
            result = await external_apis.openfda_interaction_check(new_drug, med_name)
            if result:
                interaction_alerts.append({
                    "current_med": med_name,
                    "new_drug": new_drug,
                    "total_labels": result["total_labels"],
                    "excerpt": result["mentions"][0]["interaction_text"][:500] if result["mentions"] else "",
                })

    # 4. Therapeutic duplicate check
    all_drugs = med_names + [new_drug]
    dup_result = json.loads(await check_therapeutic_duplicates(all_drugs)) if len(all_drugs) >= 2 else {"duplicates": []}

    is_safe = (
        allergy_result.get("safe", True)
        and len(interaction_alerts) == 0
        and len(dup_result.get("duplicates", [])) == 0
    )

    return json.dumps({
        "patient_name": patient["full_name"],
        "new_drug": new_drug,
        "overall_safe": is_safe,
        "allergy_check": {
            "safe": allergy_result.get("safe", True),
            "alerts": allergy_result.get("alerts", []),
        },
        "interaction_check": {
            "current_medications": med_names,
            "interactions_found": len(interaction_alerts),
            "interactions": interaction_alerts,
        },
        "duplicate_check": {
            "duplicates_found": len(dup_result.get("duplicates", [])),
            "duplicates": dup_result.get("duplicates", []),
        },
    }, default=str)


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
