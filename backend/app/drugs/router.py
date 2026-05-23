from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.drugs import dailymed_api, rxnorm_api
from app.drugs.schemas import (
    DailyMedLabel,
    DailyMedSearchResponse,
    DrugConcept,
    DrugDetail,
    DrugSearchResponse,
)
from app.drugs.service import (
    autocomplete_drugs,
    get_attributes,
    get_drug_detail,
    get_related_concepts,
    search_drugs,
)

router = APIRouter()


# ---------- Local DB + RxNorm API fallback ----------


@router.get("/search", response_model=DrugSearchResponse)
async def search(
    q: str = Query(..., min_length=2),
    tty: str | None = Query(None, description="Comma-separated TTY filter: SCD,SBD,IN,BN"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    tty_filter = [t.strip().upper() for t in tty.split(",")] if tty else None

    # Try local DB first
    local_results = await search_drugs(db, q, tty_filter, limit)
    if local_results:
        return DrugSearchResponse(
            results=[DrugConcept.model_validate(r) for r in local_results],
            total=len(local_results),
            query=q,
            source="local",
        )

    # Fallback to RxNorm API
    api_results = await rxnorm_api.search_by_name(q)
    if tty_filter:
        api_results = [r for r in api_results if r["tty"] in tty_filter]
    api_results = api_results[:limit]

    return DrugSearchResponse(
        results=[DrugConcept(rxcui=r["rxcui"], tty=r["tty"], name=r["name"]) for r in api_results],
        total=len(api_results),
        query=q,
        source="rxnorm_api",
    )


@router.get("/autocomplete", response_model=list[DrugConcept])
async def autocomplete(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    # Try local DB first
    local_results = await autocomplete_drugs(db, q, limit)
    if local_results:
        return [DrugConcept.model_validate(r) for r in local_results]

    # Fallback: approximate match via RxNorm API
    api_results = await rxnorm_api.approximate_match(q, max_entries=limit)
    return [
        DrugConcept(rxcui=r["rxcui"], tty="", name=r["name"])
        for r in api_results
    ]


@router.get("/suggest")
async def spelling_suggestions(q: str = Query(..., min_length=2)):
    suggestions = await rxnorm_api.get_spelling_suggestions(q)
    return {"query": q, "suggestions": suggestions}


@router.get("/{rxcui}", response_model=DrugDetail)
async def get_drug(rxcui: int, db: AsyncSession = Depends(get_db)):
    # Try local DB first
    detail = await get_drug_detail(db, rxcui)
    if detail:
        return detail

    # Fallback to RxNorm API
    props = await rxnorm_api.get_properties(rxcui)
    if props is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Drug not found")

    all_related = await rxnorm_api.get_all_related(rxcui)
    ndcs = await rxnorm_api.get_ndcs(rxcui)

    ingredients = [DrugConcept(**c) for c in all_related.get("IN", [])]
    ingredients += [DrugConcept(**c) for c in all_related.get("MIN", [])]
    ingredients += [DrugConcept(**c) for c in all_related.get("PIN", [])]
    dose_forms = [DrugConcept(**c) for c in all_related.get("DF", [])]
    brands = [DrugConcept(**c) for c in all_related.get("BN", [])]
    generics = [DrugConcept(**c) for c in all_related.get("IN", [])]

    strengths = []
    for scd in all_related.get("SCDC", []):
        strengths.append(scd["name"])

    return DrugDetail(
        rxcui=props["rxcui"],
        tty=props["tty"],
        name=props["name"],
        ingredients=ingredients,
        dose_forms=dose_forms,
        brands=brands,
        generics=generics,
        strengths=strengths,
        ndc_codes=ndcs,
        source="rxnorm_api",
    )


@router.get("/{rxcui}/ingredients", response_model=list[DrugConcept])
async def get_ingredients(rxcui: int, db: AsyncSession = Depends(get_db)):
    local = await get_related_concepts(db, rxcui, "has_ingredient", ["IN", "MIN", "PIN"])
    if local:
        return [DrugConcept.model_validate(r) for r in local]

    results = await rxnorm_api.get_related(rxcui, "has_ingredient")
    return [DrugConcept(**r) for r in results]


@router.get("/{rxcui}/forms", response_model=list[DrugConcept])
async def get_forms(rxcui: int, db: AsyncSession = Depends(get_db)):
    local = await get_related_concepts(db, rxcui, "has_dose_form", ["DF"])
    if local:
        return [DrugConcept.model_validate(r) for r in local]

    results = await rxnorm_api.get_related(rxcui, "has_dose_form")
    return [DrugConcept(**r) for r in results]


@router.get("/{rxcui}/brands", response_model=list[DrugConcept])
async def get_brands(rxcui: int, db: AsyncSession = Depends(get_db)):
    local = await get_related_concepts(db, rxcui, "has_tradename", ["BN"])
    if local:
        return [DrugConcept.model_validate(r) for r in local]

    results = await rxnorm_api.get_related(rxcui, "has_tradename")
    return [DrugConcept(**r) for r in results]


@router.get("/{rxcui}/generics", response_model=list[DrugConcept])
async def get_generics(rxcui: int, db: AsyncSession = Depends(get_db)):
    local = await get_related_concepts(db, rxcui, "tradename_of", ["IN"])
    if local:
        return [DrugConcept.model_validate(r) for r in local]

    results = await rxnorm_api.get_related(rxcui, "tradename_of")
    return [DrugConcept(**r) for r in results]


@router.get("/{rxcui}/ndc", response_model=list[str])
async def get_ndc(rxcui: int, db: AsyncSession = Depends(get_db)):
    local = await get_attributes(db, rxcui, "NDC")
    if local:
        return local

    return await rxnorm_api.get_ndcs(rxcui)


# ---------- DailyMed endpoints ----------


@router.get("/dailymed/search", response_model=DailyMedSearchResponse)
async def dailymed_search(
    q: str = Query(..., min_length=2),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    result = await dailymed_api.search_spls(drug_name=q, page=page, page_size=page_size)
    return DailyMedSearchResponse(
        labels=[DailyMedLabel(**l) for l in result["labels"]],
        total=result["total"],
        page=result["page"],
        total_pages=result["total_pages"],
        query=q,
    )


@router.get("/dailymed/names")
async def dailymed_drug_names(q: str = Query(..., min_length=2)):
    names = await dailymed_api.search_drug_names(q)
    return {"query": q, "names": names}
