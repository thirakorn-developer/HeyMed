"""
Redis cache for API responses.
Caches OpenFDA, RxNorm, and DailyMed responses to reduce API calls.

Default TTLs:
- Drug data (RxNorm, OpenFDA labels): 24 hours (data changes monthly)
- Adverse events: 6 hours (updated more frequently)
- Drug recalls: 1 hour (time-sensitive)
"""

import hashlib
import json
import os

import redis.asyncio as redis

_pool: redis.Redis | None = None

TTL_DRUG_DATA = 86400     # 24 hours
TTL_ADVERSE = 21600       # 6 hours
TTL_RECALLS = 3600        # 1 hour
TTL_INTERACTIONS = 86400  # 24 hours


def _get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        _pool = redis.Redis(host=host, port=port, decode_responses=True)
    return _pool


def _cache_key(prefix: str, *args) -> str:
    raw = json.dumps(args, sort_keys=True, default=str)
    hashed = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"heymed:{prefix}:{hashed}"


async def get_cached(prefix: str, *args) -> str | None:
    try:
        r = _get_redis()
        key = _cache_key(prefix, *args)
        return await r.get(key)
    except Exception:
        return None


async def set_cached(prefix: str, value: str, ttl: int, *args):
    try:
        r = _get_redis()
        key = _cache_key(prefix, *args)
        await r.set(key, value, ex=ttl)
    except Exception:
        pass


async def get_cache_stats() -> dict:
    try:
        r = _get_redis()
        info = await r.info("stats")
        keys = await r.dbsize()
        return {
            "connected": True,
            "total_keys": keys,
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0),
            "hit_rate": round(
                info.get("keyspace_hits", 0)
                / max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1)
                * 100, 1
            ),
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}
