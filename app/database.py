"""DuckDB connections and views for ANCINE and IMDb datasets.

Shared by the REST API and the natural-language query agent. Both use the
same views and macros over the Parquet files in `data/ancine`.
"""
import os
import threading
from datetime import date, timedelta
from pathlib import Path

import duckdb

ANCINE_DATA_DIR = Path(os.getenv("ANCINE_DATA_DIR", "./data/ancine"))
INGRESSO_HIVE_DIR = ANCINE_DATA_DIR / "ingresso_hive"
QUERY_TIMEOUT_SECONDS = float(os.getenv("QUERY_TIMEOUT_SECONDS", "60"))


def execute_with_timeout(connection, sql: str, parameters=None):
    """Execute a DuckDB statement and interrupt it after the configured deadline."""
    timer = threading.Timer(QUERY_TIMEOUT_SECONDS, connection.interrupt)
    timer.start()
    try:
        if parameters is None:
            return connection.execute(sql)
        return connection.execute(sql, parameters)
    finally:
        timer.cancel()

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


def classify_registration(code: str) -> str:
    if code.startswith("B"):
        return "CPB"
    if code.startswith("E"):
        return "ROE"
    return "OUTRO"


def first_thursday(year: int) -> date:
    january_first = date(year, 1, 1)
    days_until_thursday = (3 - january_first.weekday() + 7) % 7
    return january_first + timedelta(days=days_until_thursday)


def cinema_year(value: date) -> int:
    """Equivalente Python da macro SQL ano_cine — usado no pós-processamento
    (fora do SELECT) porque, combinada a certos JOINs/GROUP BYs, a macro em
    SQL provoca um plano de execução muito lento no DuckDB (ver histórico)."""
    boundary = first_thursday(value.year)
    return value.year if value >= boundary else value.year - 1


def cinema_week(value: date) -> int:
    """Equivalente Python da macro SQL semana_cine — mesmo motivo de
    cinema_year: evita aplicar a macro por linha num GROUP BY sobre a
    `bilheteria` inteira."""
    boundary = first_thursday(cinema_year(value))
    return (value - boundary).days // 7 + 1


def connect_ancine() -> duckdb.DuckDBPyConnection:
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

    # The session-level source is the Hive-partitioned ingresso dataset.  Keep
    # the public view name ``bilheteria`` so the API and NL-to-SQL contract do
    # not change, while exposing the legacy column names expected by queries.
    # The sala join supplies exhibitor/location attributes that are not stored
    # in ingresso itself.  Deduplicate sala records first to avoid multiplying
    # sessions when a registration appears more than once in the catalog.
    ingresso_files = list(INGRESSO_HIVE_DIR.glob("**/*.parquet"))
    if ingresso_files:
        ingresso_glob = INGRESSO_HIVE_DIR / "**" / "*.parquet"
        sala_path = ANCINE_DATA_DIR / "salaexibicao.parquet"
        sala_join = """
            LEFT JOIN (
                SELECT * FROM read_parquet('{sala}')
                QUALIFY ROW_NUMBER() OVER (
                    PARTITION BY REGISTRO_SALA ORDER BY REGISTRO_SALA
                ) = 1
            ) s ON TRY_CAST(i.NR_REGISTRO_SALA_EXIBICAO AS BIGINT) = s.REGISTRO_SALA
        """.format(sala=sala_path) if sala_path.exists() else ""
        con.execute(f"""
            CREATE VIEW bilheteria AS
            SELECT
                CAST(SUBSTR(i.DH_INICIO_SESSAO, 1, 10) AS DATE) AS DATA_EXIBICAO,
                TRY_CAST(i.DH_INICIO_SESSAO AS TIMESTAMP) AS SESSAO,
                i.NM_TITULO_ORIGINAL AS TITULO_ORIGINAL,
                i.NM_TITULO_BRASIL AS TITULO_BRASIL,
                i.NR_OBRA AS CPB_ROE,
                NULL::VARCHAR AS AUDIO,
                NULL::VARCHAR AS LEGENDADA,
                i.NM_PAIS_OBRA AS PAIS_OBRA,
                s.REGISTRO_SALA AS REGISTRO_SALA,
                s.NOME_SALA AS NOME_SALA,
                i.QT_PUBLICO_TOTAL AS PUBLICO,
                NULL::BIGINT AS REGISTRO_GRUPO_EXIBIDOR,
                s.REGISTRO_EXIBIDOR AS REGISTRO_EXIBIDOR,
                s.REGISTRO_COMPLEXO AS REGISTRO_COMPLEXO,
                s.MUNICIPIO_COMPLEXO AS MUNICIPIO_SALA_COMPLEXO,
                s.UF_COMPLEXO AS UF_SALA_COMPLEXO,
                s.NOME_EXIBIDOR AS RAZAO_SOCIAL_EXIBIDORA,
                s.CNPJ_EXIBIDOR AS CNPJ_EXIBIDORA
            FROM read_parquet('{ingresso_glob}', hive_partitioning = true) i
            {sala_join}
        """)

    if (ANCINE_DATA_DIR / "cpb.parquet").exists() and (ANCINE_DATA_DIR / "roe.parquet").exists():
        con.execute(f"""
            CREATE VIEW obra AS
            SELECT
                CPB AS CODIGO, 'CPB' AS TIPO_REGISTRO,
                TITULO_ORIGINAL, NULL AS TITULO_BRASIL,
                DATA_EMISSAO_CPB AS DATA_EMISSAO,
                SITUACAO_OBRA, TIPO_OBRA, SUBTIPO_OBRA, CLASSIFICACAO_OBRA, ORGANIZACAO_TEMPORAL,
                DURACAO_TOTAL_MINUTOS, QUANTIDADE_EPISODIOS, ANO_PRODUCAO_INICIAL, ANO_PRODUCAO_FINAL,
                REQUERENTE, CNPJ_REQUERENTE, UF_REQUERENTE, MUNICIPIO_REQUERENTE
            FROM read_parquet('{ANCINE_DATA_DIR / 'cpb.parquet'}')
            UNION ALL
            SELECT
                ROE AS CODIGO, 'ROE' AS TIPO_REGISTRO,
                TITULO_ORIGINAL, TITULO_BRASIL,
                DATA_EMISSAO_ROE AS DATA_EMISSAO,
                SITUACAO_OBRA, TIPO_OBRA, SUBTIPO_OBRA, CLASSIFICACAO_OBRA, ORGANIZACAO_TEMPORAL,
                DURACAO_TOTAL_MINUTOS, QUANTIDADE_EPISODIOS, ANO_PRODUCAO_INICIAL, ANO_PRODUCAO_FINAL,
                REQUERENTE, CNPJ_REQUERENTE, NULL AS UF_REQUERENTE, NULL AS MUNICIPIO_REQUERENTE
            FROM read_parquet('{ANCINE_DATA_DIR / 'roe.parquet'}')
        """)

    if (ANCINE_DATA_DIR / "cpb_pais.parquet").exists() and (ANCINE_DATA_DIR / "roe_pais.parquet").exists():
        con.execute(f"""
            CREATE VIEW obra_pais AS
            SELECT CPB AS CODIGO, 'CPB' AS TIPO_REGISTRO, PAIS_ORIGEM, TITULO_ORIGINAL
            FROM read_parquet('{ANCINE_DATA_DIR / 'cpb_pais.parquet'}')
            UNION ALL
            SELECT ROE AS CODIGO, 'ROE' AS TIPO_REGISTRO, PAIS_ORIGEM, TITULO_ORIGINAL
            FROM read_parquet('{ANCINE_DATA_DIR / 'roe_pais.parquet'}')
        """)

    if (ANCINE_DATA_DIR / "cpb_diretor.parquet").exists() and (ANCINE_DATA_DIR / "roe_diretor.parquet").exists():
        con.execute(f"""
            CREATE VIEW obra_diretor AS
            SELECT CPB AS CODIGO, 'CPB' AS TIPO_REGISTRO, DIRETOR, PAIS_DIRETOR, TITULO_ORIGINAL
            FROM read_parquet('{ANCINE_DATA_DIR / 'cpb_diretor.parquet'}')
            UNION ALL
            SELECT ROE AS CODIGO, 'ROE' AS TIPO_REGISTRO, DIRETOR, NULL AS PAIS_DIRETOR, TITULO_ORIGINAL
            FROM read_parquet('{ANCINE_DATA_DIR / 'roe_diretor.parquet'}')
        """)

    if (ANCINE_DATA_DIR / "cpb_produtor.parquet").exists() and (ANCINE_DATA_DIR / "roe_produtor.parquet").exists():
        con.execute(f"""
            CREATE VIEW obra_produtor AS
            SELECT CPB AS CODIGO, 'CPB' AS TIPO_REGISTRO, PRODUTOR, CNPJ_PRODUTOR, PAIS_PRODUTOR, TITULO_ORIGINAL
            FROM read_parquet('{ANCINE_DATA_DIR / 'cpb_produtor.parquet'}')
            UNION ALL
            SELECT ROE AS CODIGO, 'ROE' AS TIPO_REGISTRO, PRODUTOR, NULL AS CNPJ_PRODUTOR, NULL AS PAIS_PRODUTOR, TITULO_ORIGINAL
            FROM read_parquet('{ANCINE_DATA_DIR / 'roe_produtor.parquet'}')
        """)

    if (ANCINE_DATA_DIR / "salaexibicao.parquet").exists():
        con.execute(f"CREATE VIEW salaexibicao AS SELECT * FROM read_parquet('{ANCINE_DATA_DIR / 'salaexibicao.parquet'}')")

    return con
