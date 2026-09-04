"""Agente LangChain que converte perguntas em linguagem natural em SQL sobre
o schema Ancine, executa via sql_guard.py (sqlglot) e responde ao usuário —
a única ferramenta do agente é `run_sql_query`, que valida e roda a consulta
no DuckDB. O modelo de IA (Claude/DeepSeek/Qwen) é escolhido por quem chama
answer_question — ver py/chat/models.py para o registro de opções."""
from langchain.agents import create_agent
from langchain_core.tools import tool

from py.ancine_db import _new_ancine_db
from py.chat.models import build_chat_model, resolve_model_id
from py.chat.schema import ANCINE_SCHEMA_PROMPT
from py.chat.sql_guard import SQLValidationError, validate_and_prepare

MAX_AGENT_STEPS = 20
TOOL_PREVIEW_ROWS = 20

SYSTEM_PROMPT = f"""\
Você é o assistente de dados do painel de Bilheteria do Cinema Brasileiro \
(dados da Ancine). Seu trabalho é responder perguntas em português sobre \
bilheteria, obras, diretores, produtores e salas de exibição, SEMPRE \
consultando o banco através da ferramenta `run_sql_query` — nunca invente \
números.

{ANCINE_SCHEMA_PROMPT}

Regras:
- Gere sempre uma única consulta SELECT (dialeto DuckDB) e chame a \
  ferramenta `run_sql_query` para executá-la. Nunca tente DROP, UPDATE, \
  DELETE, INSERT, ALTER ou qualquer alteração — a ferramenta rejeita e você \
  não tem esse objetivo de qualquer forma.
- Se a ferramenta devolver um erro (sintaxe, tabela/função não permitida, \
  etc.), leia a mensagem, corrija a consulta e chame a ferramenta de novo. \
  Tente no máximo 3 vezes; se continuar falhando, explique o problema ao \
  usuário em vez de insistir.
- Prefira consultas agregadas (GROUP BY, SUM, COUNT) — a tabela `bilheteria` \
  tem dezenas de milhões de linhas.
- Depois que a consulta rodar com sucesso, responda em português, de forma \
  direta e objetiva, citando os números concretos que a consulta retornou. \
  Não repita a tabela inteira na resposta em texto — o resultado tabular já \
  é mostrado ao usuário separadamente pela interface.
- Se a pergunta não puder ser respondida com os dados disponíveis, diga \
  isso claramente em vez de tentar forçar uma resposta.
"""


class QueryRun:
    """Captura a última consulta executada pela tool `run_sql_query` durante
    uma invocação do agente — o agente devolve só a resposta em texto do
    modelo; o front-end também precisa da tabela (colunas/linhas) e do SQL
    usado, então guardamos isso aqui em vez de tentar reconstruir a partir
    da mensagem final."""

    def __init__(self):
        self.sql: str | None = None
        self.columns: list[str] = []
        self.rows: list[list] = []
        self.error: str | None = None


def _make_run_sql_tool(con, capture: QueryRun):
    @tool
    def run_sql_query(sql: str) -> str:
        """Executa uma consulta SQL SELECT (dialeto DuckDB) sobre o schema
        Ancine descrito no prompt do sistema e retorna uma prévia do
        resultado. Use SOMENTE SELECT — qualquer outra operação (DROP,
        UPDATE, DELETE, INSERT, ALTER, funções de acesso a arquivo/sistema)
        é rejeitada antes de chegar ao banco."""
        try:
            safe_sql = validate_and_prepare(sql)
        except SQLValidationError as e:
            capture.error = str(e)
            return f"ERRO DE VALIDAÇÃO — corrija a consulta: {e}"

        try:
            cur = con.execute(safe_sql)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
        except Exception as e:
            capture.error = str(e)
            return f"ERRO AO EXECUTAR NO DUCKDB — corrija a consulta: {e}"

        capture.sql = safe_sql
        capture.columns = cols
        capture.rows = [list(r) for r in rows]
        capture.error = None

        preview = rows[:TOOL_PREVIEW_ROWS]
        lines = [" | ".join(cols)] + [" | ".join(str(v) for v in r) for r in preview]
        lines.append(f"({len(rows)} linha(s) no total; mostrando até {TOOL_PREVIEW_ROWS})")
        return "\n".join(lines)

    return run_sql_query


def answer_question(question: str, model_id: str | None = None) -> dict:
    """Roda o agente para uma pergunta e devolve resposta + SQL + tabela."""
    con = _new_ancine_db()
    try:
        capture = QueryRun()
        model = build_chat_model(model_id)
        agent = create_agent(
            model=model,
            tools=[_make_run_sql_tool(con, capture)],
            system_prompt=SYSTEM_PROMPT,
        )

        result = agent.invoke(
            {"messages": [{"role": "user", "content": question}]},
            config={"recursion_limit": MAX_AGENT_STEPS},
        )
        final_message = result["messages"][-1]
        content = final_message.content
        if isinstance(content, list):
            content = "".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )

        return {
            "answer": content or "",
            "sql": capture.sql,
            "columns": capture.columns,
            "rows": capture.rows,
            "rowCount": len(capture.rows),
            "error": capture.error if capture.sql is None else None,
            "model": resolve_model_id(model_id),
        }
    finally:
        con.close()
