"""
Scrape Thai FDA (อย.) drug registration data.
Source: https://pertento.fda.moph.go.th/FDA_SEARCH_DRUG/SEARCH_DRUG/FRM_SEARCH_DRUG.aspx

Usage:
    python -m scripts.scrape_thai_fda [--output ../data/thai_fda_drugs.json]

Scrapes common drug categories and saves structured data.
"""

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://pertento.fda.moph.go.th/FDA_SEARCH_DRUG/SEARCH_DRUG/FRM_SEARCH_DRUG.aspx"

COMMON_DRUGS_TO_SCRAPE = [
    "paracetamol", "ibuprofen", "amoxicillin", "metformin", "amlodipine",
    "omeprazole", "atorvastatin", "cetirizine", "losartan", "aspirin",
    "azithromycin", "ciprofloxacin", "diclofenac", "doxycycline",
    "enalapril", "fluoxetine", "gabapentin", "hydrochlorothiazide",
    "insulin", "lansoprazole", "lisinopril", "loratadine", "metoprolol",
    "naproxen", "pantoprazole", "prednisolone", "propranolol",
    "ranitidine", "rosuvastatin", "sertraline", "simvastatin",
    "warfarin", "cephalexin", "clindamycin", "domperidone",
    "glipizide", "levofloxacin", "meloxicam", "metronidazole",
    "montelukast", "salbutamol", "tramadol", "valsartan",
]


def get_initial_state() -> dict:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=15)
    html = resp.read().decode("utf-8")

    vs = re.search(r'id="__VIEWSTATE".*?value="([^"]+)"', html)
    vsg = re.search(r'id="__VIEWSTATEGENERATOR".*?value="([^"]+)"', html)
    ev = re.search(r'id="__EVENTVALIDATION".*?value="([^"]+)"', html)

    return {
        "__VIEWSTATE": vs.group(1) if vs else "",
        "__VIEWSTATEGENERATOR": vsg.group(1) if vsg else "",
        "__EVENTVALIDATION": ev.group(1) if ev else "",
    }


def search_drug(state: dict, drug_name: str) -> list[dict]:
    data = urllib.parse.urlencode({
        "__VIEWSTATE": state["__VIEWSTATE"],
        "__VIEWSTATEGENERATOR": state["__VIEWSTATEGENERATOR"],
        "__EVENTVALIDATION": state["__EVENTVALIDATION"],
        "ctl00$ContentPlaceHolder1$txt_Product_THAI": "",
        "ctl00$ContentPlaceHolder1$txt_Product_ENG": drug_name,
        "ctl00$ContentPlaceHolder1$txt_substance": "",
        "ctl00$ContentPlaceHolder1$Txt_fdpdtno": "",
        "ctl00$ContentPlaceHolder1$btn_sea_drug": "ค้นหา",
    }).encode()

    req = urllib.request.Request(URL, data=data, headers={
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": URL,
    })

    try:
        resp = urllib.request.urlopen(req, timeout=20)
        html = resp.read().decode("utf-8")
    except Exception as e:
        print(f"  Error fetching {drug_name}: {e}")
        return []

    # Update state for next request
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
        eng_name = cleaned[5] or ""
        reg_number = cleaned[12] or cleaned[15] or ""
        manufacturer = cleaned[18] or ""
        drug_category = cleaned[19] or ""
        dosage_form = cleaned[20] or ""
        status = cleaned[21] or ""

        if not eng_name and not thai_name:
            continue

        results.append({
            "thai_name": thai_name,
            "english_name": eng_name,
            "registration_number": reg_number,
            "manufacturer": manufacturer,
            "drug_category": drug_category,
            "dosage_form": dosage_form,
            "status": status,
            "search_term": drug_name,
        })

    return results


def main():
    parser = argparse.ArgumentParser(description="Scrape Thai FDA drug data")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "data" / "thai_fda_drugs.json",
    )
    args = parser.parse_args()

    print(f"Scraping Thai FDA ({URL})")
    print(f"Output: {args.output}")
    print(f"Drugs to scrape: {len(COMMON_DRUGS_TO_SCRAPE)}")
    print()

    state = get_initial_state()
    print("Got initial form state")

    all_drugs = []
    for i, drug in enumerate(COMMON_DRUGS_TO_SCRAPE, 1):
        print(f"  [{i}/{len(COMMON_DRUGS_TO_SCRAPE)}] Searching: {drug}...", end=" ")
        results = search_drug(state, drug)
        active = [r for r in results if r["status"] == "คงอยู่"]
        print(f"found {len(results)} ({len(active)} active)")
        all_drugs.extend(active)
        time.sleep(1)

        # Re-get state every 10 queries to avoid expiration
        if i % 10 == 0:
            state = get_initial_state()

    # Deduplicate by registration number
    seen = set()
    unique = []
    for d in all_drugs:
        key = d["registration_number"]
        if key and key not in seen:
            seen.add(key)
            unique.append(d)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    print(f"\nDone! {len(unique)} unique active drugs saved to {args.output}")


if __name__ == "__main__":
    main()
