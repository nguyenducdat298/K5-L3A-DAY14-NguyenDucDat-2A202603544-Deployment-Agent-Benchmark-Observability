from fastapi import HTTPException
from app.config import settings
from app.redis_client import redis_client


def check_rate_limit(api_key: str) -> int:
    """Enforce per-minute rate limit backed by Redis; returns remaining requests."""
    key = f"rate_limit:{api_key}"
    try:
        current = redis_client.incr(key)
        if current == 1:
            redis_client.expire(key, 60)
        if current > settings.rate_limit_per_minute:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": settings.rate_limit_per_minute,
                    "window_seconds": 60,
                },
            )
        return max(0, settings.rate_limit_per_minute - current)
    except HTTPException:
        raise
    except Exception:
        # Fail-open if Redis is temporarily unavailable
        return settings.rate_limit_per_minute
