"""
Import scraped Thai FDA drug data into PostgreSQL.

Usage:
    python -m scripts.seed_thai_fda [--data ../data/thai_fda_drugs.json]
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "data" / "thai_fda_drugs.json",
    )
    args = parser.parse_args()

    if not args.data.exists():
        print(f"ERROR: {args.data} not found. Run scrape_thai_fda.py first.")
        sys.exit(1)

    with open(args.data, encoding="utf-8") as f:
        drugs = json.load(f)

    print(f"Loaded {len(drugs)} drugs from {args.data}")

    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        # Create table if not exists
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS thai_fda_drugs (
                id SERIAL PRIMARY KEY,
                thai_name TEXT,
                english_name TEXT NOT NULL,
                registration_number VARCHAR(50),
                manufacturer TEXT,
                drug_category VARCHAR(200),
                dosage_form VARCHAR(200),
                status VARCHAR(50) DEFAULT 'คงอยู่',
                search_term VARCHAR(200),
                search_vector TSVECTOR
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_thai_fda_search ON thai_fda_drugs USING GIN(search_vector)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_thai_fda_reg ON thai_fda_drugs(registration_number)"
        ))

        await conn.execute(text("TRUNCATE thai_fda_drugs"))

        for d in drugs:
            await conn.execute(
                text("""
                    INSERT INTO thai_fda_drugs
                        (thai_name, english_name, registration_number, manufacturer,
                         drug_category, dosage_form, status, search_term)
                    VALUES (:thai_name, :eng_name, :reg_num, :mfr, :cat, :form, :status, :term)
                """),
                {
                    "thai_name": d.get("thai_name") or None,
                    "eng_name": d["english_name"],
                    "reg_num": d.get("registration_number") or None,
                    "mfr": d.get("manufacturer") or None,
                    "cat": d.get("drug_category") or None,
                    "form": d.get("dosage_form") or None,
                    "status": d.get("status", "คงอยู่"),
                    "term": d.get("search_term") or None,
                },
            )

        # Build search vector
        await conn.execute(text("""
            UPDATE thai_fda_drugs SET search_vector =
                to_tsvector('simple',
                    coalesce(thai_name, '') || ' ' ||
                    coalesce(english_name, '') || ' ' ||
                    coalesce(manufacturer, '') || ' ' ||
                    coalesce(search_term, '')
                )
        """))

    await engine.dispose()
    print(f"Imported {len(drugs)} drugs into thai_fda_drugs table")


if __name__ == "__main__":
    asyncio.run(main())
