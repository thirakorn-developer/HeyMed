from itertools import combinations

from fastapi import APIRouter, Query

from app.drugs import openfda_api
from app.interactions.schemas import (
    AdverseEvent,
    AdverseEventsResponse,
    DrugRecall,
    InteractionCheckRequest,
    InteractionCheckResponse,
    InteractionResult,
)

router = APIRouter()


@router.post("/check", response_model=InteractionCheckResponse)
async def check_interactions(body: InteractionCheckRequest):
    drug_names = [name.strip().lower() for name in body.drug_names if name.strip()]
    if len(drug_names) < 2:
        return InteractionCheckResponse(interactions_found=0, checked_pairs=0, interactions=[])

    pairs = list(combinations(drug_names, 2))
    interactions: list[InteractionResult] = []

    for drug1, drug2 in pairs:
        result = await openfda_api.check_interaction_from_labels(drug1, drug2)
        if result and result["found"]:
            interactions.append(InteractionResult(**result))

    return InteractionCheckResponse(
        interactions_found=len(interactions),
        checked_pairs=len(pairs),
        interactions=interactions,
    )


@router.get("/adverse-events", response_model=AdverseEventsResponse)
async def adverse_events(
    drug_name: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
):
    events = await openfda_api.get_adverse_events(drug_name, limit=limit)
    return AdverseEventsResponse(
        drug_name=drug_name,
        top_reactions=[AdverseEvent(**e) for e in events],
    )


@router.get("/recalls", response_model=list[DrugRecall])
async def drug_recalls(
    drug_name: str = Query(None, min_length=2),
    limit: int = Query(10, ge=1, le=50),
):
    results = await openfda_api.get_drug_recalls(drug_name=drug_name, limit=limit)
    return [DrugRecall(**r) for r in results]


@router.get("/label-info")
async def drug_label_info(
    drug_name: str = Query(..., min_length=2),
):
    results = await openfda_api.get_drug_interactions_text(drug_name)
    return {"drug_name": drug_name, "label_interactions": results}
