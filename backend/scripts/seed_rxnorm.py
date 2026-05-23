"""
Import RxNorm RRF files into PostgreSQL.

Usage:
    python -m scripts.seed_rxnorm [--data-dir ../data/rxnorm/rrf]

Expects these files in the data directory:
    - RXNCONSO.RRF
    - RXNREL.RRF
    - RXNSAT.RRF

Only imports SAB='RXNORM' entries (normalized names, not source-provided).
"""

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings

BATCH_SIZE = 5000

RELEVANT_TTYS = {
    "IN", "PIN", "MIN", "BN", "DF", "DFG",
    "SCDC", "SCDF", "SCDG", "SCD",
    "SBDC", "SBDF", "SBDG", "SBD",
    "GPCK", "BPCK", "PSN", "SY", "TMSY",
}

RELEVANT_ATNS = {"NDC", "RXN_HUMAN_DRUG", "RXN_STRENGTH", "RXTERM_FORM", "UNII_CODE"}


def parse_rrf_line(line: str) -> list[str]:
    return line.rstrip("\n").rstrip("|").split("|")


async def seed_concepts(engine, data_dir: Path):
    filepath = data_dir / "RXNCONSO.RRF"
    if not filepath.exists():
        print(f"ERROR: {filepath} not found")
        sys.exit(1)

    print(f"Reading {filepath}...")
    seen_rxcuis: set[int] = set()
    batch: list[dict] = []
    total = 0

    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE rxn_concepts CASCADE"))

        with open(filepath, encoding="utf-8") as f:
            for line in f:
                fields = parse_rrf_line(line)
                sab = fields[11]
                tty = fields[12]
                suppress = fields[16]

                if sab != "RXNORM" or tty not in RELEVANT_TTYS:
                    continue

                rxcui = int(fields[0])
                if rxcui in seen_rxcuis:
                    continue
                seen_rxcuis.add(rxcui)

                batch.append({
                    "rxcui": rxcui,
                    "tty": tty,
                    "name": fields[14],
                    "suppress": suppress if suppress else "N",
                })

                if len(batch) >= BATCH_SIZE:
                    await conn.execute(
                        text(
                            "INSERT INTO rxn_concepts (rxcui, tty, name, suppress) "
                            "VALUES (:rxcui, :tty, :name, :suppress) "
                            "ON CONFLICT (rxcui) DO NOTHING"
                        ),
                        batch,
                    )
                    total += len(batch)
                    print(f"  Concepts: {total} inserted...", end="\r")
                    batch = []

        if batch:
            await conn.execute(
                text(
                    "INSERT INTO rxn_concepts (rxcui, tty, name, suppress) "
                    "VALUES (:rxcui, :tty, :name, :suppress) "
                    "ON CONFLICT (rxcui) DO NOTHING"
                ),
                batch,
            )
            total += len(batch)

        # Build tsvector search index
        await conn.execute(
            text(
                "UPDATE rxn_concepts SET search_vector = to_tsvector('english', name)"
            )
        )

    print(f"\n  Concepts: {total} total")


async def seed_relationships(engine, data_dir: Path):
    filepath = data_dir / "RXNREL.RRF"
    if not filepath.exists():
        print(f"WARNING: {filepath} not found, skipping relationships")
        return

    print(f"Reading {filepath}...")
    batch: list[dict] = []
    total = 0

    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE rxn_relationships"))

        with open(filepath, encoding="utf-8") as f:
            for line in f:
                fields = parse_rrf_line(line)
                sab = fields[10]
                if sab != "RXNORM":
                    continue

                rxcui1_str = fields[0]
                rxcui2_str = fields[4]
                if not rxcui1_str or not rxcui2_str:
                    continue

                batch.append({
                    "rxcui1": int(rxcui1_str),
                    "rel": fields[3],
                    "rela": fields[7] or None,
                    "rxcui2": int(rxcui2_str),
                })

                if len(batch) >= BATCH_SIZE:
                    await conn.execute(
                        text(
                            "INSERT INTO rxn_relationships (rxcui1, rel, rela, rxcui2) "
                            "VALUES (:rxcui1, :rel, :rela, :rxcui2)"
                        ),
                        batch,
                    )
                    total += len(batch)
                    print(f"  Relationships: {total} inserted...", end="\r")
                    batch = []

        if batch:
            await conn.execute(
                text(
                    "INSERT INTO rxn_relationships (rxcui1, rel, rela, rxcui2) "
                    "VALUES (:rxcui1, :rel, :rela, :rxcui2)"
                ),
                batch,
            )
            total += len(batch)

    print(f"\n  Relationships: {total} total")


async def seed_attributes(engine, data_dir: Path):
    filepath = data_dir / "RXNSAT.RRF"
    if not filepath.exists():
        print(f"WARNING: {filepath} not found, skipping attributes")
        return

    print(f"Reading {filepath}...")
    batch: list[dict] = []
    total = 0

    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE rxn_attributes"))

        with open(filepath, encoding="utf-8") as f:
            for line in f:
                fields = parse_rrf_line(line)
                atn = fields[8]
                sab = fields[9]

                if sab != "RXNORM" or atn not in RELEVANT_ATNS:
                    continue

                rxcui_str = fields[0]
                if not rxcui_str:
                    continue

                batch.append({
                    "rxcui": int(rxcui_str),
                    "atn": atn,
                    "atv": fields[10] or None,
                })

                if len(batch) >= BATCH_SIZE:
                    await conn.execute(
                        text(
                            "INSERT INTO rxn_attributes (rxcui, atn, atv) "
                            "VALUES (:rxcui, :atn, :atv)"
                        ),
                        batch,
                    )
                    total += len(batch)
                    print(f"  Attributes: {total} inserted...", end="\r")
                    batch = []

        if batch:
            await conn.execute(
                text(
                    "INSERT INTO rxn_attributes (rxcui, atn, atv) "
                    "VALUES (:rxcui, :atn, :atv)"
                ),
                batch,
            )
            total += len(batch)

    print(f"\n  Attributes: {total} total")


async def main():
    parser = argparse.ArgumentParser(description="Import RxNorm RRF into PostgreSQL")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent.parent / "data" / "rxnorm" / "rrf",
    )
    args = parser.parse_args()

    print(f"Data directory: {args.data_dir}")
    print(f"Database: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    print()

    engine = create_async_engine(settings.database_url)

    await seed_concepts(engine, args.data_dir)
    await seed_relationships(engine, args.data_dir)
    await seed_attributes(engine, args.data_dir)

    await engine.dispose()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
