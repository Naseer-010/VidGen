"""
DIME — Redis Cache Manager.

Hash → video URL mapping with configurable TTL (default 6 months).
Gracefully degrades if Redis is unavailable.
"""

from __future__ import annotations

import logging
from typing import Optional

import redis.asyncio as aioredis

from src.config import settings

logger = logging.getLogger(__name__)

# ── Redis connection (lazy) ──────────────────────────────────
_redis: Optional[aioredis.Redis] = None


async def get_redis() -> Optional[aioredis.Redis]:
    """Get or create Redis connection. Returns None if unavailable."""
    global _redis
    if _redis is None:
        try:
            _redis = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            await _redis.ping()
            logger.info("Redis connected at %s", settings.redis_url)
        except Exception as e:
            logger.warning("Redis unavailable (%s) — cache disabled", e)
            _redis = None
    return _redis


async def get_cached_video(question_hash: str) -> Optional[str]:
    """Check Redis for a cached video URL by question hash."""
    r = await get_redis()
    if r is None:
        return None
    try:
        url = await r.get(f"video:{question_hash}")
        if url:
            logger.info("Cache HIT: %s → %s", question_hash[:12], url)
        return url
    except Exception as e:
        logger.warning("Cache lookup failed: %s", e)
        return None


async def set_cached_video(question_hash: str, video_url: str) -> None:
    """Store video URL in Redis cache with TTL."""
    r = await get_redis()
    if r is None:
        return
    try:
        await r.set(
            f"video:{question_hash}",
            video_url,
            ex=settings.video_cache_ttl_seconds,
        )
        logger.info("Cache SET: %s → %s", question_hash[:12], video_url)
    except Exception as e:
        logger.warning("Cache write failed: %s", e)


async def get_latex_cache(expr_hash: str) -> Optional[str]:
    """Get cached LaTeX SVG path."""
    r = await get_redis()
    if r is None:
        return None
    try:
        return await r.get(f"latex:{expr_hash}")
    except Exception:
        return None


async def set_latex_cache(expr_hash: str, svg_path: str) -> None:
    """Cache a compiled LaTeX SVG path (no TTL — persists forever)."""
    r = await get_redis()
    if r is None:
        return
    try:
        await r.set(f"latex:{expr_hash}", svg_path)
    except Exception:
        pass
