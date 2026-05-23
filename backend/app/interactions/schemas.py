from pydantic import BaseModel


class InteractionCheckRequest(BaseModel):
    drug_names: list[str]


class InteractionResult(BaseModel):
    drug1: str
    drug2: str
    found: bool
    total_labels_mentioning: int = 0
    mentions: list[dict] = []
    source: str = "openfda_labels"


class InteractionCheckResponse(BaseModel):
    interactions_found: int
    checked_pairs: int
    interactions: list[InteractionResult]


class AdverseEvent(BaseModel):
    reaction: str
    count: int


class AdverseEventsResponse(BaseModel):
    drug_name: str
    top_reactions: list[AdverseEvent]
    source: str = "openfda"


class DrugRecall(BaseModel):
    product: str
    reason: str
    classification: str
    status: str
    recall_initiation_date: str
    city: str = ""
    state: str = ""
