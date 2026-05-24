from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.drugs.ndc_models import NdcPackage, NdcProduct

router = APIRouter()


@router.get("/search")
async def search_ndc(
    q: str = Query(..., min_length=2),
    product_type: str | None = Query(None, description="HUMAN PRESCRIPTION DRUG, HUMAN OTC DRUG"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    tsquery = func.plainto_tsquery("english", q)
    stmt = (
        select(NdcProduct)
        .where(NdcProduct.search_vector.op("@@")(tsquery))
        .order_by(func.ts_rank(NdcProduct.search_vector, tsquery).desc())
        .limit(limit)
    )
    if product_type:
        stmt = stmt.where(NdcProduct.product_type == product_type)

    result = await db.execute(stmt)
    products = result.scalars().all()

    return {
        "results": [
            {
                "product_ndc": p.product_ndc,
                "brand_name": p.brand_name,
                "generic_name": p.generic_name,
                "dosage_form": p.dosage_form,
                "route": p.route,
                "substance_name": p.substance_name,
                "strength": p.strength,
                "strength_unit": p.strength_unit,
                "labeler_name": p.labeler_name,
                "product_type": p.product_type,
                "dea_schedule": p.dea_schedule,
                "pharm_classes": p.pharm_classes,
            }
            for p in products
        ],
        "total": len(products),
        "query": q,
        "source": "fda_ndc_local",
    }


@router.get("/lookup/{ndc_code}")
async def lookup_ndc(ndc_code: str, db: AsyncSession = Depends(get_db)):
    # Try exact package NDC match
    pkg_result = await db.execute(
        select(NdcPackage).where(NdcPackage.ndc_package_code == ndc_code)
    )
    package = pkg_result.scalar_one_or_none()

    product_ndc = ndc_code
    if package:
        product_ndc = package.product_ndc

    # Get product info
    prod_result = await db.execute(
        select(NdcProduct).where(NdcProduct.product_ndc == product_ndc)
    )
    products = prod_result.scalars().all()

    if not products:
        # Try prefix match
        prod_result = await db.execute(
            select(NdcProduct).where(NdcProduct.product_ndc.startswith(ndc_code[:9]))
        )
        products = prod_result.scalars().all()

    if not products:
        return {"found": False, "ndc_code": ndc_code}

    # Get all packages for this product
    pkg_result = await db.execute(
        select(NdcPackage).where(NdcPackage.product_ndc == products[0].product_ndc)
    )
    packages = pkg_result.scalars().all()

    p = products[0]
    return {
        "found": True,
        "ndc_code": ndc_code,
        "product": {
            "product_ndc": p.product_ndc,
            "brand_name": p.brand_name,
            "generic_name": p.generic_name,
            "dosage_form": p.dosage_form,
            "route": p.route,
            "substance_name": p.substance_name,
            "strength": p.strength,
            "strength_unit": p.strength_unit,
            "labeler_name": p.labeler_name,
            "product_type": p.product_type,
            "marketing_category": p.marketing_category,
            "application_number": p.application_number,
            "dea_schedule": p.dea_schedule,
            "pharm_classes": p.pharm_classes,
        },
        "packages": [
            {
                "ndc_package_code": pkg.ndc_package_code,
                "description": pkg.package_description,
            }
            for pkg in packages
        ],
    }


@router.get("/alternatives")
async def find_alternatives(
    drug_name: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    source = (await db.execute(
        select(NdcProduct)
        .where(NdcProduct.search_vector.op("@@")(func.plainto_tsquery("english", drug_name)))
        .where(NdcProduct.pharm_classes.is_not(None))
        .where(~NdcProduct.substance_name.contains(";"))
        .order_by(func.ts_rank(NdcProduct.search_vector, func.plainto_tsquery("english", drug_name)).desc())
        .limit(1)
    )).scalar_one_or_none()

    if not source or not source.pharm_classes:
        return {"drug_name": drug_name, "error": "No pharmacological class found", "alternatives": []}

    epcs = []
    for cls in source.pharm_classes.split(","):
        cls = cls.strip()
        if "[EPC]" in cls:
            epcs.append(cls.replace("[EPC]", "").strip())

    if not epcs:
        return {"drug_name": drug_name, "error": "No EPC class found", "alternatives": []}

    epc = epcs[0]
    result = await db.execute(
        select(NdcProduct.generic_name, NdcProduct.brand_name, NdcProduct.dosage_form,
               NdcProduct.route, NdcProduct.strength, NdcProduct.strength_unit)
        .where(NdcProduct.pharm_classes.ilike(f"%{epc}%"))
        .where(~NdcProduct.generic_name.ilike(f"%{drug_name}%"))
        .where(~NdcProduct.substance_name.ilike(f"%{drug_name}%"))
        .where(~NdcProduct.substance_name.contains(";"))
        .distinct(func.upper(NdcProduct.generic_name))
        .order_by(func.upper(NdcProduct.generic_name), NdcProduct.brand_name)
        .limit(limit)
    )

    return {
        "drug_name": drug_name,
        "matched_from": source.generic_name,
        "pharmacologic_class": epc,
        "all_classes": epcs,
        "alternatives": [
            {"generic_name": r[0], "brand_name": r[1], "dosage_form": r[2],
             "route": r[3], "strength": r[4], "strength_unit": r[5]}
            for r in result.all()
        ],
    }


@router.get("/stats")
async def ndc_stats(db: AsyncSession = Depends(get_db)):
    prod_count = await db.execute(select(func.count(NdcProduct.id)))
    pkg_count = await db.execute(select(func.count(NdcPackage.id)))

    type_counts = await db.execute(
        select(NdcProduct.product_type, func.count(NdcProduct.id))
        .group_by(NdcProduct.product_type)
        .order_by(func.count(NdcProduct.id).desc())
    )

    return {
        "total_products": prod_count.scalar(),
        "total_packages": pkg_count.scalar(),
        "by_type": {row[0]: row[1] for row in type_counts.all()},
    }
