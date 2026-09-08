"""Application service for SQL-first and document-grounded questions.

Isolates provider failures and limits the request duration.
"""
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from app.chat import hybrid_agent, knowledge_agent, nl2sql_agent
from app.chat.models import MODEL_OPTIONS, ModelUnavailableError, resolve_model_id

MAX_QUESTION_LEN = 2000
CHAT_TIMEOUT_SECONDS = float(os.getenv("CHAT_TIMEOUT_SECONDS", "90"))
_EXECUTOR = ThreadPoolExecutor(
    max_workers=int(os.getenv("CHAT_MAX_CONCURRENT_REQUESTS", "4")),
    thread_name_prefix="chat",
)
logger = logging.getLogger("cinema_dashboard.chat")


def _normalized(text: str) -> str:
    import unicodedata

    return "".join(
        char for char in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(char)
    )


def question_route(question: str, history: list[str] | None = None) -> str:
    """Choose the cheapest adequate source. Ambiguous questions are SQL-first."""
    text = _normalized(question)
    context = _normalized(" ".join([*(history or [])[-2:], question]))

    source_terms = ("document", "norma", "legislacao", "instrucao normativa", "regulamento")
    comparison_terms = ("compare", "comparacao", "cruze", "cruzamento", "confronte", "relacione")
    database_terms = ("base", "banco", "dados", "parquet", "sql", "bilheteria", "estatistic")
    if (any(term in text for term in comparison_terms)
            and any(term in text for term in source_terms)
            and any(term in text for term in database_terms)):
        return "hybrid"

    quantitative_terms = (
        "quant", "total", "media", "soma", "publico", "renda", "sessao", "ranking",
        "maior", "menor", "evolucao", "por ano", "por mes", "bilheteria",
    )
    conceptual_cues = (
        "o que e", "o que sao", "conceito", "defina", "definicao", "explique",
        "como funciona", "qual a regra", "quais as regras", "obrigacao", "requisito",
        "segundo a norma", "de acordo com", "legislacao", "instrucao normativa",
    )
    if (any(cue in context for cue in conceptual_cues)
            and not any(term in text for term in quantitative_terms)):
        return "documents"
    return "sql"


def answer_question(question: str, model_id: str | None = None,
                    history: list[str] | None = None) -> dict:
    """Route to SQL by default; use documents only when the intent requires them."""
    route = question_route(question, history)
    if route == "hybrid":
        return hybrid_agent.answer_question(question, model_id, history)
    if route == "documents":
        return knowledge_agent.answer_question(question, model_id, history)
    return nl2sql_agent.answer_question(question, model_id, history)


def answer_chat_question(
    question: str, model_id: str | None = None, history: list[str] | None = None,
) -> dict:
    question = (question or "").strip()
    if not question:
        return _error("Digite uma pergunta.")
    if len(question) > MAX_QUESTION_LEN:
        return _error(f"Pergunta muito longa (máximo {MAX_QUESTION_LEN} caracteres).")
    if model_id and model_id not in MODEL_OPTIONS:
        return _error(f"Modelo de IA desconhecido: {model_id}.")

    try:
        started = time.monotonic()
        result = _EXECUTOR.submit(answer_question, question, model_id, history or []).result(
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
