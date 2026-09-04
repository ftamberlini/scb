"""Conexão DuckDB com as views da Ancine (bilheteria + cadastro CPB/ROE).

Extraído de server.py para ser compartilhado pela API REST (py/server.py) e
pelo agente de chat com IA (py/chat/) — os dois precisam do mesmo schema
(views + macros) sobre os Parquet em data/ancine/.
"""
from datetime import date, timedelta
import os
from pathlib import Path

import duckdb

ANCINE_DIR = Path(os.getenv("ANCINE_DATA_DIR", "./data/ancine"))

# "Semana cinematográfica": semana 1 de um ano começa na 1a quinta-feira do
# ano e vai até a quarta-feira seguinte (7 dias). O ano da semana ("ano_cine")
# é o ano dono dessa sequência de quintas — a última semana de um ano pode
# terminar em janeiro do ano seguinte (ex.: semana de 26/12/2024 a 01/01/2025
# pertence ao ano-cine 2024).
_ANCINE_MACROS = """
CREATE MACRO primeira_quinta(ano) AS (
    make_date(ano, 1, 1) + INTERVAL (((4 - isodow(make_date(ano, 1, 1))) % 7 + 7) % 7) DAY
);
CREATE MACRO ano_cine(d) AS (
    CASE WHEN d >= primeira_quinta(year(d)) THEN year(d) ELSE year(d) - 1 END
);
CREATE MACRO semana_cine(d) AS (
    CAST(FLOOR(date_diff('day', primeira_quinta(ano_cine(d)), d) / 7.0) AS INTEGER) + 1
);

-- Filmes brasileiros são registrados com CPB (código começa com 'B'), filmes
-- estrangeiros com ROE (começa com 'E'). Um punhado de códigos de bilheteria
-- não é nem CPB nem ROE — são categorias de eventos não fílmicos exibidos em
-- sala (ex. 'G0000000000001' = Eventos Esportivos) — caem em 'OUTRO'.
CREATE MACRO tipo_registro(codigo) AS (
    CASE WHEN codigo LIKE 'B%' THEN 'CPB'
         WHEN codigo LIKE 'E%' THEN 'ROE'
         ELSE 'OUTRO' END
);
"""


def _tipo_registro_py(codigo: str) -> str:
    if codigo.startswith("B"):
        return "CPB"
    if codigo.startswith("E"):
        return "ROE"
    return "OUTRO"


def _primeira_quinta_py(ano: int) -> date:
    jan1 = date(ano, 1, 1)
    dias_ate_quinta = (3 - jan1.weekday() + 7) % 7  # weekday(): Mon=0 .. Thu=3 .. Sun=6
    return jan1 + timedelta(days=dias_ate_quinta)


def _ano_cine_py(d: date) -> int:
    """Equivalente Python da macro SQL ano_cine — usado no pós-processamento
    (fora do SELECT) porque, combinada a certos JOINs/GROUP BYs, a macro em
    SQL provoca um plano de execução muito lento no DuckDB (ver histórico)."""
    ft = _primeira_quinta_py(d.year)
    return d.year if d >= ft else d.year - 1


def _semana_cine_py(d: date) -> int:
    """Equivalente Python da macro SQL semana_cine — mesmo motivo de
    _ano_cine_py: evita aplicar a macro por linha num GROUP BY sobre a
    `bilheteria` inteira."""
    ft = _primeira_quinta_py(_ano_cine_py(d))
    return (d - ft).days // 7 + 1


def _new_ancine_db() -> duckdb.DuckDBPyConnection:
    """Open a DuckDB in-memory connection with views over os Parquet da Ancine
    e as macros de semana cinematográfica (ano_cine/semana_cine) e de tipo de
    registro (tipo_registro).

    Uma obra é brasileira (CPB) ou estrangeira (ROE) — nunca as duas. As
    tabelas cpb_*/roe_* têm o mesmo papel em cada lado (país de origem,
    diretor, produtor); as views obra/obra_pais/obra_diretor/obra_produtor
    unem os dois lados (UNION ALL) em um schema comum, marcado por
    TIPO_REGISTRO, para permitir consultas/filtros que não precisam saber se
    a obra é CPB ou ROE.
    """
    con = duckdb.connect(":memory:")
    con.execute(_ANCINE_MACROS)

    def glob(pattern):
        return list(ANCINE_DIR.glob(pattern))

    if glob("bilheteria_*.parquet"):
        con.execute(f"CREATE VIEW bilheteria AS SELECT * FROM read_parquet('{ANCINE_DIR / 'bilheteria_*.parquet'}')")

    if (ANCINE_DIR / "cpb.parquet").exists() and (ANCINE_DIR / "roe.parquet").exists():
        con.execute(f"""
            CREATE VIEW obra AS
            SELECT
                CPB AS CODIGO, 'CPB' AS TIPO_REGISTRO,
                TITULO_ORIGINAL, NULL AS TITULO_BRASIL,
                DATA_EMISSAO_CPB AS DATA_EMISSAO,
                SITUACAO_OBRA, TIPO_OBRA, SUBTIPO_OBRA, CLASSIFICACAO_OBRA, ORGANIZACAO_TEMPORAL,
                DURACAO_TOTAL_MINUTOS, QUANTIDADE_EPISODIOS, ANO_PRODUCAO_INICIAL, ANO_PRODUCAO_FINAL,
                REQUERENTE, CNPJ_REQUERENTE, UF_REQUERENTE, MUNICIPIO_REQUERENTE
            FROM read_parquet('{ANCINE_DIR / 'cpb.parquet'}')
            UNION ALL
            SELECT
                ROE AS CODIGO, 'ROE' AS TIPO_REGISTRO,
                TITULO_ORIGINAL, TITULO_BRASIL,
                DATA_EMISSAO_ROE AS DATA_EMISSAO,
                SITUACAO_OBRA, TIPO_OBRA, SUBTIPO_OBRA, CLASSIFICACAO_OBRA, ORGANIZACAO_TEMPORAL,
                DURACAO_TOTAL_MINUTOS, QUANTIDADE_EPISODIOS, ANO_PRODUCAO_INICIAL, ANO_PRODUCAO_FINAL,
                REQUERENTE, CNPJ_REQUERENTE, NULL AS UF_REQUERENTE, NULL AS MUNICIPIO_REQUERENTE
            FROM read_parquet('{ANCINE_DIR / 'roe.parquet'}')
        """)

    if (ANCINE_DIR / "cpb_pais.parquet").exists() and (ANCINE_DIR / "roe_pais.parquet").exists():
        con.execute(f"""
            CREATE VIEW obra_pais AS
            SELECT CPB AS CODIGO, 'CPB' AS TIPO_REGISTRO, PAIS_ORIGEM, TITULO_ORIGINAL
            FROM read_parquet('{ANCINE_DIR / 'cpb_pais.parquet'}')
            UNION ALL
            SELECT ROE AS CODIGO, 'ROE' AS TIPO_REGISTRO, PAIS_ORIGEM, TITULO_ORIGINAL
            FROM read_parquet('{ANCINE_DIR / 'roe_pais.parquet'}')
        """)

    if (ANCINE_DIR / "cpb_diretor.parquet").exists() and (ANCINE_DIR / "roe_diretor.parquet").exists():
        con.execute(f"""
            CREATE VIEW obra_diretor AS
            SELECT CPB AS CODIGO, 'CPB' AS TIPO_REGISTRO, DIRETOR, PAIS_DIRETOR, TITULO_ORIGINAL
            FROM read_parquet('{ANCINE_DIR / 'cpb_diretor.parquet'}')
            UNION ALL
            SELECT ROE AS CODIGO, 'ROE' AS TIPO_REGISTRO, DIRETOR, NULL AS PAIS_DIRETOR, TITULO_ORIGINAL
            FROM read_parquet('{ANCINE_DIR / 'roe_diretor.parquet'}')
        """)

    if (ANCINE_DIR / "cpb_produtor.parquet").exists() and (ANCINE_DIR / "roe_produtor.parquet").exists():
        con.execute(f"""
            CREATE VIEW obra_produtor AS
            SELECT CPB AS CODIGO, 'CPB' AS TIPO_REGISTRO, PRODUTOR, CNPJ_PRODUTOR, PAIS_PRODUTOR, TITULO_ORIGINAL
            FROM read_parquet('{ANCINE_DIR / 'cpb_produtor.parquet'}')
            UNION ALL
            SELECT ROE AS CODIGO, 'ROE' AS TIPO_REGISTRO, PRODUTOR, NULL AS CNPJ_PRODUTOR, NULL AS PAIS_PRODUTOR, TITULO_ORIGINAL
            FROM read_parquet('{ANCINE_DIR / 'roe_produtor.parquet'}')
        """)

    if (ANCINE_DIR / "salaexibicao.parquet").exists():
        con.execute(f"CREATE VIEW salaexibicao AS SELECT * FROM read_parquet('{ANCINE_DIR / 'salaexibicao.parquet'}')")

    return con
