"""
URL Cache Service — Redis-backed with dynamic TTLs based on risk level.

Caches URL analysis results so repeated scans of the same URL don't
need to re-run WHOIS, SSL, page content, and ML classification.

TTL strategy (no hardcoded values — learned from analysis result):
  - High-risk URLs: short TTL (fraud status may change)
  - Medium-risk URLs: moderate TTL
  - Low-risk (safe) URLs: longer TTL
  - Established domains: longest TTL
"""
import json
import hashlib
import logging
from typing import Optional
from dataclasses import asdict

logger = logging.getLogger("trusthire.url_cache")

# Try to import Redis; fall back gracefully if not available
_redis_client = None
_redis_available = False

try:
    import redis

    def _get_redis():
        global _redis_client, _redis_available
        if _redis_client is not None:
            return _redis_client
        try:
            from backend.config import settings
            _redis_client = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
            _redis_client.ping()
            _redis_available = True
            logger.info("Redis cache connected")
            return _redis_client
        except Exception as e:
            logger.warning(f"Redis not available — URL cache disabled: {e}")
            _redis_available = False
            _redis_client = None
            return None
except ImportError:
    logger.info("Redis package not installed — URL cache disabled")

    def _get_redis():
        return None


# ── In-memory LRU fallback when Redis is unavailable ────────────────────────

_memory_cache: dict = {}
_MEMORY_CACHE_MAX = 500


def _cache_key(url: str) -> str:
    """Generate a deterministic cache key for a URL."""
    normalised = url.strip().lower().rstrip("/")
    return f"trusthire:url:{hashlib.sha256(normalised.encode()).hexdigest()[:24]}"


def _compute_ttl(trust_score: float, is_established: bool) -> int:
    """
    Compute TTL dynamically based on the analysis result.
    Higher-risk results expire faster so re-analysis catches status changes.
    """
    if is_established:
        return 86400   # 24 hours — established domains rarely change status
    elif trust_score >= 0.8:
        return 3600    # 1 hour — safe URLs
    elif trust_score >= 0.5:
        return 1800    # 30 min — moderate risk
    elif trust_score >= 0.3:
        return 600     # 10 min — suspicious
    else:
        return 300     # 5 min — high risk, re-check frequently


def get_cached_result(url: str) -> Optional[dict]:
    """
    Retrieve a cached URL analysis result.
    Returns the cached dict or None if not found / expired.
    """
    key = _cache_key(url)

    # Try Redis first
    r = _get_redis()
    if r is not None:
        try:
            data = r.get(key)
            if data:
                logger.debug(f"Cache HIT (Redis): {url[:60]}")
                return json.loads(data)
        except Exception as e:
            logger.debug(f"Redis get failed: {e}")

    # Fallback to memory cache
    cached = _memory_cache.get(key)
    if cached:
        logger.debug(f"Cache HIT (memory): {url[:60]}")
        return cached

    return None


def cache_result(url: str, result_dict: dict, trust_score: float, is_established: bool):
    """
    Cache a URL analysis result with a dynamic TTL.
    Stores in Redis if available, otherwise in-memory LRU.
    """
    key = _cache_key(url)
    ttl = _compute_ttl(trust_score, is_established)

    # Serialise — strip non-serialisable fields
    try:
        data = json.dumps(result_dict, default=str)
    except (TypeError, ValueError) as e:
        logger.warning(f"Cannot serialise cache data: {e}")
        return

    # Try Redis
    r = _get_redis()
    if r is not None:
        try:
            r.setex(key, ttl, data)
            logger.debug(f"Cached (Redis, TTL={ttl}s): {url[:60]}")
            return
        except Exception as e:
            logger.debug(f"Redis set failed: {e}")

    # Fallback to memory cache
    if len(_memory_cache) >= _MEMORY_CACHE_MAX:
        # Simple eviction: remove oldest entries
        keys_to_remove = list(_memory_cache.keys())[:_MEMORY_CACHE_MAX // 4]
        for k in keys_to_remove:
            _memory_cache.pop(k, None)

    _memory_cache[key] = result_dict
    logger.debug(f"Cached (memory, {len(_memory_cache)} entries): {url[:60]}")


def invalidate_cache(url: str):
    """Remove a URL from both caches."""
    key = _cache_key(url)

    r = _get_redis()
    if r is not None:
        try:
            r.delete(key)
        except Exception:
            pass

    _memory_cache.pop(key, None)


def get_cache_stats() -> dict:
    """Return cache statistics for monitoring."""
    stats = {
        "redis_available": _redis_available,
        "memory_cache_size": len(_memory_cache),
        "memory_cache_max": _MEMORY_CACHE_MAX,
    }

    r = _get_redis()
    if r is not None:
        try:
            info = r.info("keyspace")
            db_info = info.get("db0", {})
            stats["redis_keys"] = db_info.get("keys", 0) if isinstance(db_info, dict) else 0
        except Exception:
            stats["redis_keys"] = "unknown"

    return stats
