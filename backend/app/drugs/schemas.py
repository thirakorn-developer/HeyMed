from pydantic import BaseModel


class DrugConcept(BaseModel):
    rxcui: int
    tty: str
    name: str

    model_config = {"from_attributes": True}


class DrugDetail(BaseModel):
    rxcui: int
    tty: str
    name: str
    ingredients: list[DrugConcept] = []
    dose_forms: list[DrugConcept] = []
    brands: list[DrugConcept] = []
    generics: list[DrugConcept] = []
    strengths: list[str] = []
    ndc_codes: list[str] = []
    source: str = "local"


class DrugSearchResponse(BaseModel):
    results: list[DrugConcept]
    total: int
    query: str
    source: str = "local"


class DailyMedLabel(BaseModel):
    setid: str
    title: str
    published_date: str
    version: int


class DailyMedSearchResponse(BaseModel):
    labels: list[DailyMedLabel]
    total: int
    page: int
    total_pages: int
    query: str
