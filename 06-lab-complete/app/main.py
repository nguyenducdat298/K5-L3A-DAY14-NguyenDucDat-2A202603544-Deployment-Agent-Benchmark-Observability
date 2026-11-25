import json
import logging
import sys
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import check_redis_health, redis_client
from utils.mock_llm import ask


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload, ensure_ascii=False)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logging.root.handlers = [handler]
logging.root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

for uv_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    uv_logger = logging.getLogger(uv_logger_name)
    uv_logger.handlers = [handler]
    uv_logger.propagate = False

logger = logging.getLogger("agent")

is_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global is_ready
    logger.info(json.dumps({"event": "startup", "port": settings.port, "env": settings.environment}))
    is_ready = True
    yield
    is_ready = False
    logger.info(json.dumps({"event": "shutdown", "status": "draining"}))
    time.sleep(0.1)
    try:
        redis_client.close()
    except Exception:
        pass
    logger.info(json.dumps({"event": "shutdown", "status": "complete"}))


app = FastAPI(title="Production AI Agent", version="1.0.0", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if not is_ready or not check_redis_health():
        raise HTTPException(status_code=503, detail="Service not ready: Redis unavailable")
    return {"status": "ready", "redis": "ok"}


@app.post("/ask")
def ask_agent(body: AskRequest, api_key: str = Depends(verify_api_key)):
    remaining_reqs = check_rate_limit(api_key)
    check_budget(api_key)
    answer = ask(body.question)
    spent = record_cost(api_key)
    logger.info(json.dumps({"event": "ask", "question_len": len(body.question), "spent_usd": spent}))
    return {
        "question": body.question,
        "answer": answer,
        "usage": {
            "requests_remaining": remaining_reqs,
            "spent_usd": spent,
        },
    }
