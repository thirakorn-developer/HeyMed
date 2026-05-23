---
name: heymed-test
description: Quick smoke test of HeyMed MCP tools — tests one drug through all tools in under 60 seconds
---

Run a quick smoke test of the HeyMed pharmacy system. Test one drug through ALL MCP tools:

**Test drug**: Use the argument if provided, otherwise default to "metformin"

Run these MCP tool calls and report pass/fail for each:

1. `search_drugs_ndc` — search the drug name → expect results
2. `search_drugs_rxnorm` — search via RxNorm API → expect RXCUI
3. `get_drug_detail` — use RXCUI from step 2 → expect ingredients, forms
4. `lookup_ndc` — use product_ndc from step 1 → expect product info
5. `suggest_spelling` — misspell the drug name → expect correction
6. `check_drug_interactions` — check with "aspirin" → expect interaction data
7. `get_adverse_events` — get side effects → expect reactions with counts
8. `get_drug_recalls` — check recalls → expect results (may be empty)
9. `get_dosing_info` — get dosing guidelines → expect dosage text
10. `get_pregnancy_lactation_info` — get pregnancy info → expect safety data
11. `get_warnings_contraindications` — get warnings → expect warnings text
12. `find_alternatives` — find alternatives → expect drugs in same class
13. `list_drug_classes` — search classes → expect class list
14. `get_ndc_stats` — get DB stats → expect product/package counts

Report format:
```
HeyMed Smoke Test: [drug name]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 1. NDC Search:        ✅ (X results)
 2. RxNorm Search:     ✅ (X results, RXCUI: Y)
 3. Drug Detail:       ✅ (X ingredients, Y forms)
 ...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Result: 14/14 passed
```
