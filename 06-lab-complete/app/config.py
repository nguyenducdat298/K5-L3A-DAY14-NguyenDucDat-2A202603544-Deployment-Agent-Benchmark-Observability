import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    environment: str = os.getenv("ENVIRONMENT", "production")
    port: int = int(os.getenv("PORT", "8000"))
    agent_api_key: str = os.getenv("AGENT_API_KEY", "dev-secret-key")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    daily_budget_usd: float = float(os.getenv("DAILY_BUDGET_USD", "1.0"))
    monthly_budget_usd: float = float(os.getenv("MONTHLY_BUDGET_USD", "20.0"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
