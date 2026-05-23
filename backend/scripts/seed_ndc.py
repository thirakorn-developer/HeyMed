"""
Import FDA NDC Directory into PostgreSQL.

Usage:
    python -m scripts.seed_ndc [--data-dir ../data/ndc_directory]

Files expected:
    - product.txt (tab-delimited, with header)
    - package.txt (tab-delimited, with header)
"""

import argparse
import asyncio
import csv
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings

BATCH_SIZE = 5000


async def seed_products(engine, data_dir: Path):
    filepath = data_dir / "product.txt"
    if not filepath.exists():
        print(f"ERROR: {filepath} not found")
        sys.exit(1)

    print(f"Reading {filepath}...")
    batch: list[dict] = []
    total = 0
    skipped = 0

    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE ndc_products CASCADE"))

        with open(filepath, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                if row.get("NDC_EXCLUDE_FLAG", "").strip() == "Y":
                    skipped += 1
                    continue

                batch.append({
                    "product_ndc": row.get("PRODUCTNDC", "").strip(),
                    "product_type": row.get("PRODUCTTYPENAME", "").strip(),
                    "brand_name": row.get("PROPRIETARYNAME", "").strip() or None,
                    "brand_name_suffix": row.get("PROPRIETARYNAMESUFFIX", "").strip() or None,
                    "generic_name": row.get("NONPROPRIETARYNAME", "").strip() or None,
                    "dosage_form": row.get("DOSAGEFORMNAME", "").strip() or None,
                    "route": row.get("ROUTENAME", "").strip() or None,
                    "marketing_category": row.get("MARKETINGCATEGORYNAME", "").strip() or None,
                    "application_number": row.get("APPLICATIONNUMBER", "").strip() or None,
                    "labeler_name": row.get("LABELERNAME", "").strip() or None,
                    "substance_name": row.get("SUBSTANCENAME", "").strip() or None,
                    "strength": row.get("ACTIVE_NUMERATOR_STRENGTH", "").strip() or None,
                    "strength_unit": row.get("ACTIVE_INGRED_UNIT", "").strip() or None,
                    "pharm_classes": row.get("PHARM_CLASSES", "").strip() or None,
                    "dea_schedule": row.get("DEASCHEDULE", "").strip() or None,
                })

                if len(batch) >= BATCH_SIZE:
                    await conn.execute(
                        text("""
                            INSERT INTO ndc_products
                            (product_ndc, product_type, brand_name, brand_name_suffix,
                             generic_name, dosage_form, route, marketing_category,
                             application_number, labeler_name, substance_name,
                             strength, strength_unit, pharm_classes, dea_schedule)
                            VALUES
                            (:product_ndc, :product_type, :brand_name, :brand_name_suffix,
                             :generic_name, :dosage_form, :route, :marketing_category,
                             :application_number, :labeler_name, :substance_name,
                             :strength, :strength_unit, :pharm_classes, :dea_schedule)
                        """),
                        batch,
                    )
                    total += len(batch)
                    print(f"  Products: {total} inserted...", end="\r")
                    batch = []

        if batch:
            await conn.execute(
                text("""
                    INSERT INTO ndc_products
                    (product_ndc, product_type, brand_name, brand_name_suffix,
                     generic_name, dosage_form, route, marketing_category,
                     application_number, labeler_name, substance_name,
                     strength, strength_unit, pharm_classes, dea_schedule)
                    VALUES
                    (:product_ndc, :product_type, :brand_name, :brand_name_suffix,
                     :generic_name, :dosage_form, :route, :marketing_category,
                     :application_number, :labeler_name, :substance_name,
                     :strength, :strength_unit, :pharm_classes, :dea_schedule)
                """),
                batch,
            )
            total += len(batch)

        print(f"\n  Building search index...")
        await conn.execute(
            text("""
                UPDATE ndc_products SET search_vector =
                    to_tsvector('english',
                        coalesce(brand_name, '') || ' ' ||
                        coalesce(generic_name, '') || ' ' ||
                        coalesce(substance_name, '') || ' ' ||
                        coalesce(labeler_name, '')
                    )
            """)
        )

    print(f"  Products: {total} total ({skipped} excluded)")


async def seed_packages(engine, data_dir: Path):
    filepath = data_dir / "package.txt"
    if not filepath.exists():
        print(f"WARNING: {filepath} not found, skipping packages")
        return

    print(f"Reading {filepath}...")
    batch: list[dict] = []
    total = 0
    skipped = 0

    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE ndc_packages"))

        with open(filepath, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                if row.get("NDC_EXCLUDE_FLAG", "").strip() == "Y":
                    skipped += 1
                    continue

                ndc_code = row.get("NDCPACKAGECODE", "").strip()
                if not ndc_code:
                    continue

                batch.append({
                    "product_ndc": row.get("PRODUCTNDC", "").strip(),
                    "ndc_package_code": ndc_code,
                    "package_description": row.get("PACKAGEDESCRIPTION", "").strip() or None,
                })

                if len(batch) >= BATCH_SIZE:
                    await conn.execute(
                        text("""
                            INSERT INTO ndc_packages (product_ndc, ndc_package_code, package_description)
                            VALUES (:product_ndc, :ndc_package_code, :package_description)
                            ON CONFLICT (ndc_package_code) DO NOTHING
                        """),
                        batch,
                    )
                    total += len(batch)
                    print(f"  Packages: {total} inserted...", end="\r")
                    batch = []

        if batch:
            await conn.execute(
                text("""
                    INSERT INTO ndc_packages (product_ndc, ndc_package_code, package_description)
                    VALUES (:product_ndc, :ndc_package_code, :package_description)
                    ON CONFLICT (ndc_package_code) DO NOTHING
                """),
                batch,
            )
            total += len(batch)

    print(f"\n  Packages: {total} total ({skipped} excluded)")


async def main():
    parser = argparse.ArgumentParser(description="Import FDA NDC Directory into PostgreSQL")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "data" / "ndc_directory",
    )
    args = parser.parse_args()

    print(f"Data directory: {args.data_dir}")
    print(f"Database: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    print()

    engine = create_async_engine(settings.database_url)

    await seed_products(engine, args.data_dir)
    await seed_packages(engine, args.data_dir)

    await engine.dispose()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
