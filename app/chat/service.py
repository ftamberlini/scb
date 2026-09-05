"""Application service for natural-language data questions.
Used by the `/api/chat/query` route. It isolates agent and provider errors
ausente, rate limit, etc.) para que a API sempre devolva um JSON previsível
em vez de propagar uma exceção 500 crua para o front-end."""
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from app.chat.models import MODEL_OPTIONS, ModelUnavailableError, resolve_model_id
from app.chat.nl2sql_agent import answer_question

MAX_QUESTION_LEN = 2000
CHAT_TIMEOUT_SECONDS = float(os.getenv("CHAT_TIMEOUT_SECONDS", "90"))
_EXECUTOR = ThreadPoolExecutor(
    max_workers=int(os.getenv("CHAT_MAX_CONCURRENT_REQUESTS", "4")),
    thread_name_prefix="chat",
)
logger = logging.getLogger("cinema_dashboard.chat")


def answer_chat_question(question: str, model_id: str | None = None) -> dict:
    question = (question or "").strip()
    if not question:
        return _error("Digite uma pergunta.")
    if len(question) > MAX_QUESTION_LEN:
        return _error(f"Pergunta muito longa (máximo {MAX_QUESTION_LEN} caracteres).")
    if model_id and model_id not in MODEL_OPTIONS:
        return _error(f"Modelo de IA desconhecido: {model_id}.")

    try:
        started = time.monotonic()
        result = _EXECUTOR.submit(answer_question, question, model_id).result(
            timeout=CHAT_TIMEOUT_SECONDS
        )
        logger.info(
            "Chat request completed",
            extra={
                "model": resolve_model_id(model_id),
                "elapsedMs": round((time.monotonic() - started) * 1000, 3),
                "rowCount": result.get("rowCount", 0),
            },
        )
        return result
    except TimeoutError:
        logger.warning("Chat request timed out", extra={"model": model_id})
        return _error("A consulta excedeu o tempo limite. Tente uma pergunta mais específica.")
    except ModelUnavailableError:
        return _error("O provedor do modelo selecionado não está configurado.")
    except Exception:
        logger.exception("Chat request failed", extra={"model": model_id})
        return _error("Não foi possível consultar a IA neste momento.")


def _error(message: str) -> dict:
    return {"answer": "", "sql": None, "columns": [], "rows": [], "rowCount": 0, "error": message}
