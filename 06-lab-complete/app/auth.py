from fastapi import Header, HTTPException
from app.config import settings


def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    """Validate X-API-Key header against configured AGENT_API_KEY."""
    if not x_api_key or x_api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-API-Key header",
        )
    return x_api_key
