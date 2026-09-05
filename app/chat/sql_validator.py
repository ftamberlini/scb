"""Safety boundary between LLM-generated SQL and DuckDB.

Usa sqlglot para: (1) validar a sintaxe, (2) garantir que é uma única
consulta de leitura (SELECT/UNION/INTERSECT/EXCEPT — nunca DROP/UPDATE/
DELETE/INSERT/ALTER/etc.), (3) restringir as tabelas às views da Ancine
(nunca funções-tabela como read_parquet/scans, que dariam acesso a arquivos
arbitrários) e (4) aplicar um LIMIT no resultado para não escanear a
`bilheteria` inteira (~37M linhas) sem agregação."""
import sqlglot
from sqlglot import exp

DIALECT = "duckdb"

# Únicas tabelas que o agente pode consultar — as views definidas em
# app/database.py. Qualquer outro nome (ou função-tabela) é rejeitado.
ALLOWED_TABLES = {"bilheteria", "obra", "obra_pais", "obra_diretor", "obra_produtor", "salaexibicao"}

# Funções que dão acesso a arquivos/sistema/extensões do DuckDB e nunca são
# legítimas nas consultas do agente (ex.: read_text, read_csv, sqlite_scan,
# pragma_version, glob, httpfs, install/load de extensões).
_DENY_SUBSTR = (
    "read_", "scan", "glob", "pragma", "attach", "detach", "install",
    "load_", "export", "import", "getenv", "system", "shell", "httpfs", "copy_to",
)

_FORBIDDEN_STATEMENTS = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter,
    exp.Create, exp.TruncateTable, exp.Merge, exp.Command, exp.Pragma,
)

DEFAULT_ROW_LIMIT = 500
MAX_ROW_LIMIT = 2000


class SQLValidationError(ValueError):
    """SQL gerado pelo modelo falhou na validação — nunca chega ao DuckDB."""


def _check_function_name(name: str) -> None:
    n = (name or "").lower()
    if any(bad in n for bad in _DENY_SUBSTR):
        raise SQLValidationError(f"Função não permitida: {name}.")


def validate_and_prepare(sql: str) -> str:
    """Valida uma consulta gerada pelo LLM e devolve o SQL final (com LIMIT
    garantido) pronto para execução. Levanta SQLValidationError em qualquer
    tentativa de sair de um único SELECT de leitura sobre as views da Ancine."""
    raw = (sql or "").strip()
    if not raw:
        raise SQLValidationError("Consulta SQL vazia.")

    try:
        statements = [s for s in sqlglot.parse(raw, read=DIALECT) if s is not None]
    except Exception as e:
        raise SQLValidationError(f"SQL com sintaxe inválida: {e}") from e

    if len(statements) != 1:
        raise SQLValidationError("Apenas uma única instrução SELECT é permitida por consulta (sem ';' extras).")

    stmt = statements[0]
    if not isinstance(stmt, (exp.Select, exp.Union, exp.Except, exp.Intersect)):
        raise SQLValidationError(
            f"Somente consultas SELECT são permitidas (recebido: {type(stmt).__name__})."
        )

    hit = next(iter(stmt.find_all(*_FORBIDDEN_STATEMENTS)), None)
    if hit is not None:
        raise SQLValidationError(f"Operação não permitida: {type(hit).__name__}.")

    # aliases de CTE (WITH x AS (...)) também são referenciáveis em FROM —
    # não são tabelas reais, então entram na allowlist só para esta consulta
    cte_aliases = {cte.alias.lower() for cte in stmt.find_all(exp.CTE) if cte.alias}

    for table in stmt.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            raise SQLValidationError("Funções de tabela (ex.: read_parquet, scans) não são permitidas.")
        if table.args.get("db") or table.args.get("catalog"):
            raise SQLValidationError("Referências qualificadas a schema/catálogo não são permitidas.")
        name = (table.name or "").lower()
        if name not in ALLOWED_TABLES and name not in cte_aliases:
            raise SQLValidationError(f"Tabela não permitida: {table.name}.")

    for fn in stmt.find_all(exp.Anonymous):
        _check_function_name(fn.this)

    limit_node = stmt.args.get("limit")
    if limit_node is None:
        stmt = stmt.limit(DEFAULT_ROW_LIMIT)
    else:
        try:
            n = int(limit_node.expression.this)
        except (TypeError, ValueError, AttributeError):
            n = None
        if n is not None and n > MAX_ROW_LIMIT:
            stmt.set("limit", exp.Limit(expression=exp.Literal.number(MAX_ROW_LIMIT)))

    return stmt.sql(dialect=DIALECT)
