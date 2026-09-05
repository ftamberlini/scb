"""Natural-language query endpoints."""

import hmac
import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.chat.models import list_model_options
from app.chat.service import answer_chat_question
from app.runtime import SlidingWindowRateLimiter

router = APIRouter(prefix="/api/chat", tags=["chat"])
rate_limiter = SlidingWindowRateLimiter(
    limit=int(os.getenv("CHAT_RATE_LIMIT", "10")),
    window_seconds=float(os.getenv("CHAT_RATE_WINDOW_SECONDS", "60")),
)


class ChatQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    model: str | None = None


@router.get("/models")
def get_chat_models():
    return list_model_options()


@router.post("/query")
def query_chat(body: ChatQuestion, request: Request):
    access_key = os.getenv("CHAT_ACCESS_KEY")
    supplied_key = request.headers.get("X-Chat-Key", "")
    if access_key and not hmac.compare_digest(access_key, supplied_key):
        raise HTTPException(status_code=401, detail="Credencial do chat inválida.")
    identity = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(identity):
        raise HTTPException(
            status_code=429,
            detail="Limite de consultas atingido. Tente novamente em breve.",
        )
    return answer_chat_question(body.question, body.model)
