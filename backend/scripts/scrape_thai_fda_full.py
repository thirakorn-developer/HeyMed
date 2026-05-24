"""
Full scraper for Thai FDA (อย.) drug registration database.
Searches A-Z by English name + common Thai prefixes to get comprehensive coverage.

Usage:
    python -m scripts.scrape_thai_fda_full [--output ../data/thai_fda_drugs_full.json]
"""

import argparse
import json
import re
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://pertento.fda.moph.go.th/FDA_SEARCH_DRUG/SEARCH_DRUG/FRM_SEARCH_DRUG.aspx"

# Search terms: A-Z for English, common Thai generic name prefixes, substance names
ENGLISH_SEARCHES = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

SUBSTANCE_SEARCHES = [
    "paracetamol", "acetaminophen", "ibuprofen", "amoxicillin", "metformin",
    "amlodipine", "omeprazole", "atorvastatin", "cetirizine", "losartan",
    "aspirin", "azithromycin", "ciprofloxacin", "diclofenac", "doxycycline",
    "enalapril", "fluoxetine", "gabapentin", "hydrochlorothiazide", "insulin",
    "lansoprazole", "lisinopril", "loratadine", "metoprolol", "naproxen",
    "pantoprazole", "prednisolone", "propranolol", "rosuvastatin", "sertraline",
    "simvastatin", "warfarin", "cephalexin", "clindamycin", "domperidone",
    "glipizide", "levofloxacin", "meloxicam", "metronidazole", "montelukast",
    "salbutamol", "tramadol", "valsartan", "sildenafil", "esomeprazole",
    "clopidogrel", "levothyroxine", "fluconazole", "acyclovir", "furosemide",
    "spironolactone", "carbamazepine", "phenytoin", "valproic", "alprazolam",
    "diazepam", "amitriptyline", "nifedipine", "diltiazem", "captopril",
    "digoxin", "isosorbide", "clopidogrel", "ticagrelor", "rivaroxaban",
    "empagliflozin", "sitagliptin", "pioglitazone", "gliclazide",
]

# Create SSL context that doesn't verify (Thai FDA cert sometimes causes issues)
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


def get_initial_state() -> dict:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=30, context=ssl_ctx)
    html = resp.read().decode("utf-8")
    vs = re.search(r'id="__VIEWSTATE".*?value="([^"]+)"', html)
    vsg = re.search(r'id="__VIEWSTATEGENERATOR".*?value="([^"]+)"', html)
    ev = re.search(r'id="__EVENTVALIDATION".*?value="([^"]+)"', html)
    return {
        "__VIEWSTATE": vs.group(1) if vs else "",
        "__VIEWSTATEGENERATOR": vsg.group(1) if vsg else "",
        "__EVENTVALIDATION": ev.group(1) if ev else "",
    }


def search_drug(state: dict, eng_name: str = "", substance: str = "") -> list[dict]:
    data = urllib.parse.urlencode({
        "__VIEWSTATE": state["__VIEWSTATE"],
        "__VIEWSTATEGENERATOR": state["__VIEWSTATEGENERATOR"],
        "__EVENTVALIDATION": state["__EVENTVALIDATION"],
        "ctl00$ContentPlaceHolder1$txt_Product_THAI": "",
        "ctl00$ContentPlaceHolder1$txt_Product_ENG": eng_name,
        "ctl00$ContentPlaceHolder1$txt_substance": substance,
        "ctl00$ContentPlaceHolder1$Txt_fdpdtno": "",
        "ctl00$ContentPlaceHolder1$btn_sea_drug": "ค้นหา",
    }).encode()

    req = urllib.request.Request(URL, data=data, headers={
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": URL,
    })

    try:
        resp = urllib.request.urlopen(req, timeout=30, context=ssl_ctx)
        html = resp.read().decode("utf-8")
    except Exception as e:
        print(f"    Error: {e}")
        return []

    # Update state
    vs = re.search(r'id="__VIEWSTATE".*?value="([^"]+)"', html)
    if vs:
        state["__VIEWSTATE"] = vs.group(1)
    ev = re.search(r'id="__EVENTVALIDATION".*?value="([^"]+)"', html)
    if ev:
        state["__EVENTVALIDATION"] = ev.group(1)

    rows = re.findall(r'<tr[^>]*class="rg(?:Alt)?Row[^"]*"[^>]*>(.*?)</tr>', html, re.DOTALL)
    results = []
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        cleaned = [re.sub(r"<[^>]+>", "", c).strip().replace("&nbsp;", "").strip() for c in cells]
        if len(cleaned) < 22:
            continue
        thai_name = cleaned[4] or ""
        eng_name_val = cleaned[5] or ""
        reg_number = cleaned[12] or cleaned[15] or ""
        manufacturer = cleaned[18] or ""
        drug_category = cleaned[19] or ""
        dosage_form = cleaned[20] or ""
        status = cleaned[21] or ""
        if not eng_name_val and not thai_name:
            continue
        results.append({
            "thai_name": thai_name,
            "english_name": eng_name_val,
            "registration_number": reg_number,
            "manufacturer": manufacturer,
            "drug_category": drug_category,
            "dosage_form": dosage_form,
            "status": status,
        })
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "data" / "thai_fda_drugs_full.json",
    )
    args = parser.parse_args()

    print(f"Full Thai FDA scraper")
    print(f"Output: {args.output}")

    state = get_initial_state()
    print("Got initial form state\n")

    all_drugs: dict[str, dict] = {}  # keyed by registration_number

    # Phase 1: Search A-Z by English name
    print("Phase 1: English name A-Z")
    for i, letter in enumerate(ENGLISH_SEARCHES, 1):
        print(f"  [{i}/26] Letter '{letter}'...", end=" ", flush=True)
        results = search_drug(state, eng_name=letter)
        active = [r for r in results if r["status"] == "คงอยู่"]
        new = 0
        for r in active:
            key = r["registration_number"]
            if key and key not in all_drugs:
                all_drugs[key] = r
                new += 1
        print(f"{len(results)} found, {len(active)} active, {new} new (total: {len(all_drugs)})")
        time.sleep(0.5)
        if i % 10 == 0:
            state = get_initial_state()

    # Phase 2: Search by substance name
    print(f"\nPhase 2: Substance names ({len(SUBSTANCE_SEARCHES)} terms)")
    for i, substance in enumerate(SUBSTANCE_SEARCHES, 1):
        print(f"  [{i}/{len(SUBSTANCE_SEARCHES)}] '{substance}'...", end=" ", flush=True)
        results = search_drug(state, substance=substance)
        active = [r for r in results if r["status"] == "คงอยู่"]
        new = 0
        for r in active:
            key = r["registration_number"]
            if key and key not in all_drugs:
                all_drugs[key] = r
                new += 1
        print(f"{len(active)} active, {new} new (total: {len(all_drugs)})")
        time.sleep(0.5)
        if i % 10 == 0:
            state = get_initial_state()

    # Save
    drug_list = list(all_drugs.values())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(drug_list, f, ensure_ascii=False, indent=2)

    print(f"\nDone! {len(drug_list)} unique active drugs saved to {args.output}")


if __name__ == "__main__":
    main()
