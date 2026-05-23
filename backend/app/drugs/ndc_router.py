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
