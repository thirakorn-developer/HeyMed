import os

import asyncpg

_pool: asyncpg.Pool | None = None


def _dsn() -> str:
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "heymed")
    user = os.getenv("POSTGRES_USER", "heymed")
    pw = os.getenv("POSTGRES_PASSWORD", "heymed_secret")
    return f"postgresql://{user}:{pw}@{host}:{port}/{db}"


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None or _pool._closed:
        _pool = await asyncpg.create_pool(_dsn(), min_size=1, max_size=5)
    return _pool


async def query(sql: str, *args) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *args)
        return [dict(r) for r in rows]


async def query_one(sql: str, *args) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *args)
        return dict(row) if row else None
