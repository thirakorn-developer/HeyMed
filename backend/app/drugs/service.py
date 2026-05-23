from sqlalchemy import Select, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.drugs.models import RxnAttribute, RxnConcept, RxnRelationship
from app.drugs.schemas import DrugConcept, DrugDetail


async def search_drugs(
    db: AsyncSession, query: str, tty_filter: list[str] | None = None, limit: int = 20
) -> list[RxnConcept]:
    tsquery = func.plainto_tsquery("english", query)
    stmt: Select = (
        select(RxnConcept)
        .where(RxnConcept.search_vector.op("@@")(tsquery))
        .where(RxnConcept.suppress == "N")
        .order_by(func.ts_rank(RxnConcept.search_vector, tsquery).desc())
        .limit(limit)
    )
    if tty_filter:
        stmt = stmt.where(RxnConcept.tty.in_(tty_filter))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def autocomplete_drugs(db: AsyncSession, query: str, limit: int = 10) -> list[RxnConcept]:
    stmt = (
        select(RxnConcept)
        .where(RxnConcept.name.ilike(f"{query}%"))
        .where(RxnConcept.suppress == "N")
        .where(RxnConcept.tty.in_(["SCD", "SBD", "IN", "BN"]))
        .order_by(RxnConcept.name)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_concept(db: AsyncSession, rxcui: int) -> RxnConcept | None:
    result = await db.execute(select(RxnConcept).where(RxnConcept.rxcui == rxcui))
    return result.scalar_one_or_none()


async def get_related_concepts(
    db: AsyncSession, rxcui: int, rela: str, target_tty: list[str] | None = None
) -> list[RxnConcept]:
    stmt = (
        select(RxnConcept)
        .join(RxnRelationship, RxnRelationship.rxcui2 == RxnConcept.rxcui)
        .where(RxnRelationship.rxcui1 == rxcui)
        .where(RxnRelationship.rela == rela)
    )
    if target_tty:
        stmt = stmt.where(RxnConcept.tty.in_(target_tty))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_attributes(db: AsyncSession, rxcui: int, atn: str) -> list[str]:
    stmt = (
        select(RxnAttribute.atv)
        .where(RxnAttribute.rxcui == rxcui)
        .where(RxnAttribute.atn == atn)
        .where(RxnAttribute.atv.is_not(None))
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


async def get_drug_detail(db: AsyncSession, rxcui: int) -> DrugDetail | None:
    concept = await get_concept(db, rxcui)
    if concept is None:
        return None

    ingredients = await get_related_concepts(db, rxcui, "has_ingredient", ["IN", "MIN", "PIN"])
    dose_forms = await get_related_concepts(db, rxcui, "has_dose_form", ["DF"])
    brands = await get_related_concepts(db, rxcui, "has_tradename", ["BN"])
    generics = await get_related_concepts(db, rxcui, "tradename_of", ["IN"])
    strengths = await get_attributes(db, rxcui, "RXN_STRENGTH")
    ndc_codes = await get_attributes(db, rxcui, "NDC")

    return DrugDetail(
        rxcui=concept.rxcui,
        tty=concept.tty,
        name=concept.name,
        ingredients=[DrugConcept.model_validate(c) for c in ingredients],
        dose_forms=[DrugConcept.model_validate(c) for c in dose_forms],
        brands=[DrugConcept.model_validate(c) for c in brands],
        generics=[DrugConcept.model_validate(c) for c in generics],
        strengths=strengths,
        ndc_codes=ndc_codes,
    )
