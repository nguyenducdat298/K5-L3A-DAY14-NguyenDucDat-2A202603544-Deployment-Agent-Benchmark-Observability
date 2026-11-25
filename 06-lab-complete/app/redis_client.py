import redis
from app.config import settings

redis_client = redis.Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)


def check_redis_health() -> bool:
    """Return True if Redis responds to PING, False otherwise."""
    try:
        return bool(redis_client.ping())
    except Exception:
        return False
