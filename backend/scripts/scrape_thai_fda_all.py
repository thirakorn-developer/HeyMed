"""
Comprehensive Thai FDA scraper — aims to get ALL registered drugs.
Strategy: search with 2-letter English prefixes (aa-zz = 676 combinations)
+ top 200 substance names from US FDA. Dedup by registration number.

Usage:
    python -m scripts.scrape_thai_fda_all [--output ../data/thai_fda_drugs_all.json]
"""

import argparse
import json
import re
import ssl
import string
import time
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://pertento.fda.moph.go.th/FDA_SEARCH_DRUG/SEARCH_DRUG/FRM_SEARCH_DRUG.aspx"

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


def get_state() -> dict:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=45, context=ssl_ctx)
    html = resp.read().decode("utf-8")
    vs = re.search(r'id="__VIEWSTATE".*?value="([^"]+)"', html)
    vsg = re.search(r'id="__VIEWSTATEGENERATOR".*?value="([^"]+)"', html)
    ev = re.search(r'id="__EVENTVALIDATION".*?value="([^"]+)"', html)
    return {
        "__VIEWSTATE": vs.group(1) if vs else "",
        "__VIEWSTATEGENERATOR": vsg.group(1) if vsg else "",
        "__EVENTVALIDATION": ev.group(1) if ev else "",
    }


def search(state: dict, eng: str = "", substance: str = "") -> list[dict]:
    data = urllib.parse.urlencode({
        "__VIEWSTATE": state["__VIEWSTATE"],
        "__VIEWSTATEGENERATOR": state["__VIEWSTATEGENERATOR"],
        "__EVENTVALIDATION": state["__EVENTVALIDATION"],
        "ctl00$ContentPlaceHolder1$txt_Product_THAI": "",
        "ctl00$ContentPlaceHolder1$txt_Product_ENG": eng,
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
        resp = urllib.request.urlopen(req, timeout=45, context=ssl_ctx)
        html = resp.read().decode("utf-8")
    except Exception as e:
        return []

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
        c = [re.sub(r"<[^>]+>", "", x).strip().replace("&nbsp;", "").strip() for x in cells]
        if len(c) < 22:
            continue
        if not c[5] and not c[4]:
            continue
        results.append({
            "thai_name": c[4] or "",
            "english_name": c[5] or "",
            "registration_number": c[12] or c[15] or "",
            "manufacturer": c[18] or "",
            "drug_category": c[19] or "",
            "dosage_form": c[20] or "",
            "status": c[21] or "",
        })
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "data" / "thai_fda_drugs_all.json")
    args = parser.parse_args()

    print("=== Thai FDA Full Database Scraper ===")
    print(f"Output: {args.output}")

    all_drugs: dict[str, dict] = {}
    state = get_state()
    errors = 0

    # Phase 1: 2-letter English name prefixes
    prefixes = [a + b for a in string.ascii_lowercase for b in string.ascii_lowercase]
    print(f"\nPhase 1: {len(prefixes)} two-letter prefixes (eng name)")

    for i, prefix in enumerate(prefixes, 1):
        if errors > 10:
            print("  Too many errors, refreshing state...")
            try:
                state = get_state()
                errors = 0
            except Exception:
                time.sleep(5)
                state = get_state()
                errors = 0

        results = search(state, eng=prefix)
        if results is None:
            errors += 1
            continue

        active = [r for r in results if r.get("status") == "คงอยู่"]
        new = 0
        for r in active:
            key = r["registration_number"]
            if key and key not in all_drugs:
                all_drugs[key] = r
                new += 1

        if i % 26 == 0 or new > 0:
            print(f"  [{i}/{len(prefixes)}] '{prefix}' → {len(active)} active, {new} new (total: {len(all_drugs)})")

        time.sleep(0.3)

        if i % 50 == 0:
            try:
                state = get_state()
            except Exception:
                time.sleep(3)
                state = get_state()

    # Phase 2: Top substance names (common drugs that might have different English product names)
    top_substances = [
        "acetaminophen", "ibuprofen", "amoxicillin", "metformin", "amlodipine",
        "omeprazole", "atorvastatin", "cetirizine", "losartan", "aspirin",
        "azithromycin", "ciprofloxacin", "diclofenac", "doxycycline", "enalapril",
        "fluoxetine", "gabapentin", "hydrochlorothiazide", "insulin", "lansoprazole",
        "lisinopril", "loratadine", "metoprolol", "naproxen", "pantoprazole",
        "prednisolone", "propranolol", "rosuvastatin", "sertraline", "simvastatin",
        "warfarin", "cephalexin", "clindamycin", "domperidone", "glipizide",
        "levofloxacin", "metronidazole", "montelukast", "salbutamol", "tramadol",
        "valsartan", "acyclovir", "furosemide", "spironolactone", "carbamazepine",
        "phenytoin", "alprazolam", "diazepam", "amitriptyline", "nifedipine",
        "diltiazem", "captopril", "digoxin", "clopidogrel", "levothyroxine",
        "fluconazole", "dexamethasone", "methylprednisolone", "prednisone",
        "erythromycin", "clarithromycin", "gentamicin", "vancomycin",
        "methotrexate", "cyclosporine", "tacrolimus", "mycophenolate",
        "sildenafil", "tadalafil", "esomeprazole", "rabeprazole",
        "empagliflozin", "dapagliflozin", "sitagliptin", "linagliptin",
        "pioglitazone", "gliclazide", "glimepiride", "repaglinide",
        "rivaroxaban", "apixaban", "dabigatran", "enoxaparin", "heparin",
        "morphine", "fentanyl", "oxycodone", "codeine", "buprenorphine",
        "ondansetron", "metoclopramide", "ranitidine", "sucralfate",
        "loperamide", "bisacodyl", "lactulose", "senna",
        "allopurinol", "colchicine", "febuxostat",
        "montelukast", "fluticasone", "budesonide", "beclomethasone",
        "ipratropium", "tiotropium", "formoterol", "salmeterol",
    ]

    print(f"\nPhase 2: {len(top_substances)} substance names")
    state = get_state()

    for i, sub in enumerate(top_substances, 1):
        results = search(state, substance=sub)
        active = [r for r in results if r.get("status") == "คงอยู่"]
        new = 0
        for r in active:
            key = r["registration_number"]
            if key and key not in all_drugs:
                all_drugs[key] = r
                new += 1
        if new > 0:
            print(f"  [{i}/{len(top_substances)}] '{sub}' → {new} new (total: {len(all_drugs)})")
        time.sleep(0.3)
        if i % 30 == 0:
            try:
                state = get_state()
            except Exception:
                time.sleep(3)
                state = get_state()

    # Save
    drug_list = list(all_drugs.values())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(drug_list, f, ensure_ascii=False, indent=2)

    # Stats
    cats = {}
    for d in drug_list:
        cat = d.get("drug_category", "unknown")
        cats[cat] = cats.get(cat, 0) + 1

    print(f"\n=== DONE ===")
    print(f"Total unique active drugs: {len(drug_list)}")
    print(f"By category:")
    for k, v in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print(f"Saved to: {args.output}")


if __name__ == "__main__":
    main()
