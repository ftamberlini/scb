"""Ponto de entrada do módulo de chat com IA — chamado pelo endpoint
/api/chat/query em py/server.py. Isola erros do agente/LLM (chave da API
ausente, rate limit, etc.) para que a API sempre devolva um JSON previsível
em vez de propagar uma exceção 500 crua para o front-end."""
from py.chat.models import MODEL_OPTIONS
from py.chat.nl2sql_agent import answer_question

MAX_QUESTION_LEN = 2000


def answer_chat_question(question: str, model_id: str | None = None) -> dict:
    question = (question or "").strip()
    if not question:
        return _error("Digite uma pergunta.")
    if len(question) > MAX_QUESTION_LEN:
        return _error(f"Pergunta muito longa (máximo {MAX_QUESTION_LEN} caracteres).")
    if model_id and model_id not in MODEL_OPTIONS:
        return _error(f"Modelo de IA desconhecido: {model_id}.")

    try:
        return answer_question(question, model_id)
    except Exception as e:
        return _error(f"Não foi possível consultar a IA: {e}")


def _error(message: str) -> dict:
    return {"answer": "", "sql": None, "columns": [], "rows": [], "rowCount": 0, "error": message}
