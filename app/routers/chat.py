"""Natural-language query endpoints."""

import hashlib
import os
from typing import Annotated

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
    history: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(
        default_factory=list, max_length=20,
    )


@router.get("/models")
def get_chat_models():
    return list_model_options()


@router.post("/query")
def query_chat(body: ChatQuestion, request: Request):
    user = request.state.user
    identity = hashlib.sha256(
        f"{user['provider']}|{user['issuer']}|{user['subject']}".encode()
    ).hexdigest()
    if not rate_limiter.allow(identity):
        raise HTTPException(
            status_code=429,
            detail="Limite de consultas atingido. Tente novamente em breve.",
        )
    return answer_chat_question(body.question, body.model, body.history)
