from fastapi import HTTPException
from app.config import settings
from app.redis_client import redis_client

_memory_spent_usd = 0.0
COST_PER_REQUEST_USD = 0.001


def check_budget(api_key: str) -> float:
    """Ensure daily budget is not exceeded; raises HTTP 402 if exhausted."""
    global _memory_spent_usd
    key = f"budget_spent:{api_key}"
    try:
        spent = float(redis_client.get(key) or 0.0)
    except Exception:
        spent = _memory_spent_usd

    if spent >= settings.daily_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Daily budget exceeded",
                "spent_usd": spent,
                "daily_budget_usd": settings.daily_budget_usd,
            },
        )
    return max(0.0, settings.daily_budget_usd - spent)


def record_cost(api_key: str, cost_usd: float = COST_PER_REQUEST_USD) -> float:
    """Record request cost in Redis (and in-memory fallback)."""
    global _memory_spent_usd
    _memory_spent_usd += cost_usd
    key = f"budget_spent:{api_key}"
    try:
        new_spent = redis_client.incrbyfloat(key, cost_usd)
        redis_client.expire(key, 86400)
        return float(new_spent)
    except Exception:
        return _memory_spent_usd
