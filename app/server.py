"""FastAPI backend for the Brazilian cinema box-office dashboard.

Esqueleto inicial: ainda serve o schema/dados herdados do projeto de referência
(rs_movie_dashboard, MovieLens/IMDb). Será adaptado por partes para bilheteria
de cinema no Brasil (schema, queries e endpoints)."""
import json
import logging
import os
import re
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import duckdb
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()  # ANTHROPIC_API_KEY / CHAT_LLM_MODEL (chat com IA), lidos de .env em dev

from app.auth.web import ROOT, install_auth
from app.database import (
    ANCINE_DATA_DIR,
    cinema_week,
    cinema_year,
    classify_registration,
    connect_ancine,
    execute_with_timeout,
)
from app.routers.chat import router as chat_router
from app.runtime import BoundedTTLCache, RuntimeState

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(message)s",
)
logger = logging.getLogger("cinema_dashboard")

RUNTIME = RuntimeState()
ANALYTICS_CACHE = BoundedTTLCache(
    max_entries=int(os.getenv("ANALYTICS_CACHE_MAX_ENTRIES", "128")),
    ttl_seconds=float(os.getenv("ANALYTICS_CACHE_TTL_SECONDS", "300")),
)
QUERY_SLOTS = threading.BoundedSemaphore(int(os.getenv("MAX_CONCURRENT_REQUESTS", "8")))

DATA_DIR = Path(os.getenv("DATA_DIR", "./data/imdb"))

_PARQUET_TABLES = [
    "country", "ml_imdb", "director", "writer",
    "movie_imdb", "movie_country", "movie_ml_genre", "movie_imdb_genre",
    "movie_director", "movie_writer", "movie_rating",
]


def _new_db() -> duckdb.DuckDBPyConnection:
    """Open a DuckDB in-memory connection with views over the Parquet files."""
    con = duckdb.connect(":memory:")
    for t in _PARQUET_TABLES:
        p = DATA_DIR / f"{t}.parquet"
        if p.exists():
            con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{p}')")
    return con


# ── Ancine (bilheteria) ─────────────────────────────────────────────────────
# The ANCINE data directory, cinema-calendar helpers, and DuckDB connection
# live in app/database.py and are shared with the chat agent.


# ── Detalhes do Filme (data/imdb/, via join CPB/ROE → imdbID) ──────────────

_FILME_DETALHE_TABLES = [
    "movie_imdb", "director", "movie_director", "writer", "movie_writer",
    "movie_cast", "output_cast",
]


def _new_filme_detalhe_db() -> duckdb.DuckDBPyConnection:
    """Conexão com as views IMDb (data/imdb/) + o cadastro Ancine (data/ancine/
    cpb.parquet, roe.parquet) + o mapeamento CPB/ROE → imdbID (data/ancine/
    ancine_cpb.parquet, ancine_roe.parquet) — usada para a seção "Detalhes do
    Filme" (dados Ancine sempre + Movie/Crew Detail do IMDb quando houver
    correspondência) das abas Filme/Diretor/Produtor."""
    con = duckdb.connect(":memory:")
    for t in _FILME_DETALHE_TABLES:
        p = DATA_DIR / f"{t}.parquet"
        if p.exists():
            con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{p}')")
    for t in ("cpb", "roe", "ancine_cpb", "ancine_roe"):
        p = ANCINE_DATA_DIR / f"{t}.parquet"
        if p.exists():
            con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{p}')")
    return con


def _clean(val) -> str:
    """Normaliza valores vindos do IMDb/OMDB — None, "N/A", "" e "UNKNOWN"
    (usado nas colunas de raça/etnia/religião) viram string vazia."""
    v = (str(val) if val is not None else "").strip()
    return "" if v.upper() in ("N/A", "NAN", "", "UNKNOWN", "NONE") else v


def _norm_gender(val) -> str:
    v = _clean(val).upper()
    if v in ("MALE", "M"):
        return "Male"
    if v in ("FEMALE", "F"):
        return "Female"
    return ""


def _chars_to_list(val) -> list[str]:
    """Converte CHARACTERS '["Woody","Rex"]' -> ['Woody', 'Rex']; se não for
    JSON, devolve a string original numa lista de 1 elemento."""
    s = _clean(val)
    if not s:
        return []
    try:
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if x]
    except (ValueError, TypeError):
        pass
    return [s]


def _in_clause(col: str, values: list) -> tuple[str, list]:
    """'col IN (?, ?, ...)' — vazio ('') vira condição sempre-falsa (nenhum valor casa)."""
    if not values:
        return "1=1", []
    placeholders = ", ".join(["?"] * len(values))
    return f"{col} IN ({placeholders})", list(values)


def _ancine_filmes_where(f: dict) -> tuple[str, list]:
    """Monta a cláusula WHERE (sobre `bilheteria` aliasada `b`) para os filtros
    da sidebar (Período/Obra/Sala de Exibição/Diretor/Produtor/Requerente)."""
    parts = ["tipo_registro(b.CPB_ROE) IN ('CPB', 'ROE')"]
    params: list = []

    if f["anos"]:
        cl, p = _in_clause("b.ANO_CINEMATOGRAFICO", f["anos"]); parts.append(cl); params += p
    if f["semanaInicio"] is not None:
        parts.append("semana_cine(b.DATA_EXIBICAO) >= ?"); params.append(f["semanaInicio"])
    if f["semanaFim"] is not None:
        parts.append("semana_cine(b.DATA_EXIBICAO) <= ?"); params.append(f["semanaFim"])
    if f["cpbRoe"]:
        parts.append("b.CPB_ROE ILIKE ?"); params.append(f"%{f['cpbRoe']}%")
    if f["tituloBrasileiro"]:
        # "Título Brasil" = TITULO_BRASIL (ROE) unido com TITULO_ORIGINAL (CPB) —
        # obras nacionais não têm um título "traduzido" separado do original.
        parts.append("b.CPB_ROE IN (SELECT CODIGO FROM obra WHERE COALESCE(TITULO_BRASIL, TITULO_ORIGINAL) ILIKE ?)")
        params.append(f"%{f['tituloBrasileiro']}%")
    if f["tituloOriginal"]:
        parts.append("b.TITULO_ORIGINAL ILIKE ?"); params.append(f"%{f['tituloOriginal']}%")
    if f["paisOrigem"]:
        cl, p = _in_clause("PAIS_ORIGEM", f["paisOrigem"])
        parts.append(f"b.CPB_ROE IN (SELECT CODIGO FROM obra_pais WHERE {cl})"); params += p
    if f["nacionalidade"]:
        # Nacionalidade: CPB = obra brasileira, ROE = obra estrangeira.
        tipos = ["CPB" if v == "Brasileira" else "ROE" for v in f["nacionalidade"]]
        cl, p = _in_clause("tipo_registro(b.CPB_ROE)", tipos); parts.append(cl); params += p
    if f["tipoObra"]:
        cl, p = _in_clause("TIPO_OBRA", f["tipoObra"])
        parts.append(f"b.CPB_ROE IN (SELECT CODIGO FROM obra WHERE {cl})"); params += p
    if f["subtipoObra"]:
        cl, p = _in_clause("SUBTIPO_OBRA", f["subtipoObra"])
        parts.append(f"b.CPB_ROE IN (SELECT CODIGO FROM obra WHERE {cl})"); params += p
    if f["registroSala"]:
        parts.append("(CAST(b.REGISTRO_SALA AS VARCHAR) ILIKE ? OR CAST(b.REGISTRO_COMPLEXO AS VARCHAR) ILIKE ?)")
        params.append(f"%{f['registroSala']}%"); params.append(f"%{f['registroSala']}%")
    if f["grupoExibidor"]:
        cl, p = _in_clause("NOME_GRUPO_EXIBIDOR", f["grupoExibidor"])
        parts.append(f"b.REGISTRO_SALA IN (SELECT REGISTRO_SALA FROM salaexibicao WHERE {cl})"); params += p
    if f["municipioSala"]:
        cl, p = _in_clause("b.MUNICIPIO_SALA_COMPLEXO", f["municipioSala"]); parts.append(cl); params += p
    if f["ufSala"]:
        cl, p = _in_clause("b.UF_SALA_COMPLEXO", f["ufSala"]); parts.append(cl); params += p
    if f["nomeDiretor"]:
        parts.append("b.CPB_ROE IN (SELECT CODIGO FROM obra_diretor WHERE DIRETOR ILIKE ?)")
        params.append(f"%{f['nomeDiretor']}%")
    if f["nomeProdutor"]:
        parts.append("b.CPB_ROE IN (SELECT CODIGO FROM obra_produtor WHERE PRODUTOR ILIKE ?)")
        params.append(f"%{f['nomeProdutor']}%")
    if f["cnpjRequerente"]:
        parts.append("b.CPB_ROE IN (SELECT CODIGO FROM obra WHERE CNPJ_REQUERENTE ILIKE ?)")
        params.append(f"%{f['cnpjRequerente']}%")
    if f["nomeRequerente"]:
        parts.append("b.CPB_ROE IN (SELECT CODIGO FROM obra WHERE REQUERENTE ILIKE ?)")
        params.append(f"%{f['nomeRequerente']}%")
    if f["municipioRequerente"]:
        cl, p = _in_clause("MUNICIPIO_REQUERENTE", f["municipioRequerente"])
        parts.append(f"b.CPB_ROE IN (SELECT CODIGO FROM obra WHERE {cl})"); params += p
    if f["ufRequerente"]:
        cl, p = _in_clause("UF_REQUERENTE", f["ufRequerente"])
        parts.append(f"b.CPB_ROE IN (SELECT CODIGO FROM obra WHERE {cl})"); params += p

    return " AND ".join(parts), params


# ── Value parsers ─────────────────────────────────────────────────────────────

def _float(s):
    try:
        return round(float(s), 1)
    except (TypeError, ValueError):
        return None


def _int(s):
    if not s or s == "N/A":
        return 0
    cleaned = re.sub(r"[^0-9]", "", str(s))
    return int(cleaned) if cleaned else 0


def _box(s):
    """'$14,648,076' → 14.65  (USD millions)."""
    if not s or s in ("N/A", "$0", ""):
        return 0.0
    digits = re.sub(r"[^0-9]", "", str(s))
    return round(int(digits) / 1_000_000, 2) if digits else 0.0


def _gender(g):
    if not g:
        return "Unknown"
    u = g.upper()
    if u == "MALE":
        return "Male"
    if u == "FEMALE":
        return "Female"
    return "Unknown"


def _race(r):
    if not r:
        return "UNKNOWN"
    return "UNKNOWN" if r.upper() == "UNDEFINED" else r.upper()


# ── Main films query (DuckDB / Parquet) ───────────────────────────────────────

_FILMS_QUERY = """\
WITH
  m AS (
    SELECT IMDBID, MOVIEID, TITLE, YEAR, IMDBRATING, IMDBVOTES, BOXOFFICE,
           OSCAR_WINNING, OSCAR_NOMINATION,
           AWARD_WINNING, AWARD_NOMINATION,
           BAFTA_WINNING, BAFTA_NOMINATION,
           EMMY_WINNING,  EMMY_NOMINATION,
           GENRE    AS IMDB_GENRE_RAW,
           COUNTRY  AS IMDB_COUNTRY_RAW
    FROM movie_imdb
    WHERE TYPE     = 'movie'
      AND IMDBRATING IS NOT NULL
      AND IMDBRATING != 'N/A'
      AND RESPONSE  = 'true'
  ),
  fc AS (
    SELECT mc.IMDBID, mc.COUNTRY,
           COALESCE(ci.CONTINENT, cn.CONTINENT) AS CONTINENT,
           COALESCE(ci.REGION,    cn.REGION)    AS REGION,
           ROW_NUMBER() OVER (PARTITION BY mc.IMDBID) AS rn
    FROM movie_country mc
    LEFT JOIN country ci ON ci.ISO     = mc.ISO
    LEFT JOIN country cn ON cn.COUNTRY = mc.COUNTRY AND ci.ISO IS NULL
    JOIN m ON m.IMDBID = mc.IMDBID
  ),
  fg AS (
    SELECT mg.MOVIEID, mg.GENRE,
           ROW_NUMBER() OVER (PARTITION BY mg.MOVIEID) AS rn
    FROM movie_ml_genre mg
    JOIN m ON m.MOVIEID = mg.MOVIEID
  ),
  fi AS (
    SELECT ig.IMDBID, ig.GENRE,
           ROW_NUMBER() OVER (PARTITION BY ig.IMDBID) AS rn
    FROM movie_imdb_genre ig
    JOIN m ON m.IMDBID = ig.IMDBID
  ),
  fd AS (
    SELECT md.IMDBID, md.DIRECTORID,
           d.NAME, d.GENDER, d.GENDER_LLM, d.RACE, d.BIRTHYEAR, d.NATIONALITY,
           ROW_NUMBER() OVER (PARTITION BY md.IMDBID) AS rn
    FROM movie_director md
    JOIN director d ON d.DIRECTORID = md.DIRECTORID
    JOIN m          ON m.IMDBID     = md.IMDBID
  ),
  fw AS (
    SELECT mw.IMDBID, mw.WRITERID,
           w.NAME, w.GENDER, w.RACE, w.BIRTHYEAR, w.NATIONALITY,
           ROW_NUMBER() OVER (PARTITION BY mw.IMDBID) AS rn
    FROM movie_writer mw
    JOIN writer w ON w.WRITERID = mw.WRITERID
    JOIN m        ON m.IMDBID   = mw.IMDBID
  ),
  fv AS (
    SELECT m.MOVIEID, SUM(mr.COUNT_RATING) AS VOTES_ML
    FROM movie_rating mr
    JOIN m ON m.MOVIEID = mr.MOVIEID
    GROUP BY m.MOVIEID
  ),
  fd_all AS (
    SELECT md.IMDBID,
           STRING_AGG(d.NAME, ', ') AS ALL_DIRS
    FROM movie_director md
    JOIN director d ON d.DIRECTORID = md.DIRECTORID
    JOIN m          ON m.IMDBID     = md.IMDBID
    GROUP BY md.IMDBID
  ),
  fc_all AS (
    SELECT mc.IMDBID,
           STRING_AGG(COALESCE(ci.COUNTRY, cn.COUNTRY, mc.COUNTRY), ', ') AS ALL_COUNTRIES
    FROM movie_country mc
    LEFT JOIN country ci ON ci.ISO     = mc.ISO
    LEFT JOIN country cn ON cn.COUNTRY = mc.COUNTRY AND ci.ISO IS NULL
    JOIN m ON m.IMDBID = mc.IMDBID
    GROUP BY mc.IMDBID
  ),
  fg_all AS (
    SELECT mg.MOVIEID,
           STRING_AGG(mg.GENRE, ', ') AS ALL_ML_GENRES
    FROM movie_ml_genre mg
    JOIN m ON m.MOVIEID = mg.MOVIEID
    GROUP BY mg.MOVIEID
  ),
  fi_all AS (
    SELECT ig.IMDBID,
           STRING_AGG(ig.GENRE, ', ') AS ALL_IMDB_GENRES
    FROM movie_imdb_genre ig
    JOIN m ON m.IMDBID = ig.IMDBID
    GROUP BY ig.IMDBID
  )
SELECT
  m.IMDBID, m.MOVIEID, m.TITLE, m.YEAR,
  m.IMDBRATING, m.IMDBVOTES, m.BOXOFFICE,
  m.OSCAR_WINNING,   m.OSCAR_NOMINATION,
  m.AWARD_WINNING,   m.AWARD_NOMINATION,
  m.BAFTA_WINNING,   m.BAFTA_NOMINATION,
  m.EMMY_WINNING,    m.EMMY_NOMINATION,
  m.IMDB_GENRE_RAW,  m.IMDB_COUNTRY_RAW,
  fc.COUNTRY,    fc.CONTINENT,  fc.REGION,
  fg.GENRE       AS ML_GENRE,
  fi.GENRE       AS IMDB_GENRE,
  COALESCE(fd.GENDER, fd.GENDER_LLM) AS DIR_GENDER,
  fd.DIRECTORID  AS DIR_ID,
  fd.NAME        AS DIR_NAME,
  fd.RACE        AS DIR_RACE,
  fd.BIRTHYEAR   AS DIR_BY,
  fd.NATIONALITY AS DIR_NAT,
  fw.WRITERID    AS WRI_ID,
  fw.NAME        AS WRI_NAME,
  fw.GENDER      AS WRI_GENDER,
  fw.RACE        AS WRI_RACE,
  fw.BIRTHYEAR   AS WRI_BY,
  fw.NATIONALITY AS WRI_NAT,
  fv.VOTES_ML,
  fd_all.ALL_DIRS,
  fc_all.ALL_COUNTRIES,
  COALESCE(fg_all.ALL_ML_GENRES, fi_all.ALL_IMDB_GENRES) AS ALL_GENRES
FROM m
LEFT JOIN fc     ON fc.IMDBID    = m.IMDBID  AND fc.rn = 1
LEFT JOIN fg     ON fg.MOVIEID   = m.MOVIEID AND fg.rn = 1
LEFT JOIN fi     ON fi.IMDBID    = m.IMDBID  AND fi.rn = 1
LEFT JOIN fd     ON fd.IMDBID    = m.IMDBID  AND fd.rn = 1
LEFT JOIN fw     ON fw.IMDBID    = m.IMDBID  AND fw.rn = 1
LEFT JOIN fv     ON fv.MOVIEID   = m.MOVIEID
LEFT JOIN fd_all ON fd_all.IMDBID  = m.IMDBID
LEFT JOIN fc_all ON fc_all.IMDBID  = m.IMDBID
LEFT JOIN fg_all ON fg_all.MOVIEID = m.MOVIEID
LEFT JOIN fi_all ON fi_all.IMDBID  = m.IMDBID
ORDER BY m.TITLE
"""


# ── Cache ─────────────────────────────────────────────────────────────────────
_FILMS:        list[dict] = []
_RATINGS_DIST: list[dict] = []
_READY:        bool       = False

_PERIODO_OPTIONS: dict = {"anos": [], "semanas": [], "dataMin": None, "dataMax": None}


def _load_periodo_options() -> dict:
    """Anos e semanas cinematográficas distintos, e período (data mín/máx) coberto
    pelo dataset Hive data/ancine/ingresso_hive."""
    con = connect_ancine()
    try:
        anos = con.execute(
            "SELECT DISTINCT ANO_CINEMATOGRAFICO AS ano FROM bilheteria WHERE ANO_CINEMATOGRAFICO IS NOT NULL ORDER BY ano"
        ).fetchall()
        semanas = con.execute(
            "SELECT DISTINCT semana_cine(DATA_EXIBICAO) AS sem FROM bilheteria ORDER BY sem"
        ).fetchall()
        data_min, data_max = con.execute(
            "SELECT MIN(DATA_EXIBICAO), MAX(DATA_EXIBICAO) FROM bilheteria"
        ).fetchone()
        return {
            "anos": [r[0] for r in anos],
            "semanas": [r[0] for r in semanas],
            "dataMin": data_min.strftime("%d/%m/%Y") if data_min else None,
            "dataMax": data_max.strftime("%d/%m/%Y") if data_max else None,
        }
    except duckdb.CatalogException:
        # data/ancine/ingresso_hive ainda não existe neste ambiente
        return {"anos": [], "semanas": [], "dataMin": None, "dataMax": None}
    finally:
        con.close()


_OBRA_OPTIONS: dict = {"paisOrigem": [], "tipoObra": [], "subtipoObra": []}


def _load_obra_options() -> dict:
    """País de origem, tipo e subtipo de obra distintos (CPB + ROE) em
    data/ancine/, para o filtro Filme (Obra). Tipo/subtipo só consideram
    obras com pelo menos uma sessão em `bilheteria` — o cadastro CPB/ROE tem
    obras registradas que nunca chegaram a ser exibidas."""
    con = connect_ancine()
    try:
        pais_rows = con.execute(
            "SELECT DISTINCT PAIS_ORIGEM FROM obra_pais WHERE PAIS_ORIGEM IS NOT NULL ORDER BY 1"
        ).fetchall()
        con.execute("CREATE OR REPLACE TEMP VIEW _codigos_com_bilheteria AS SELECT DISTINCT CPB_ROE AS CODIGO FROM bilheteria")
        tipo_rows = con.execute("""
            SELECT DISTINCT TIPO_OBRA FROM obra
            WHERE TIPO_OBRA IS NOT NULL AND CODIGO IN (SELECT CODIGO FROM _codigos_com_bilheteria)
            ORDER BY 1
        """).fetchall()
        subtipo_rows = con.execute("""
            SELECT DISTINCT SUBTIPO_OBRA FROM obra
            WHERE SUBTIPO_OBRA IS NOT NULL AND CODIGO IN (SELECT CODIGO FROM _codigos_com_bilheteria)
            ORDER BY 1
        """).fetchall()
        return {
            "paisOrigem": [r[0] for r in pais_rows],
            "tipoObra": [r[0] for r in tipo_rows],
            "subtipoObra": [r[0] for r in subtipo_rows],
        }
    except duckdb.CatalogException:
        # data/ancine/ ainda não está completo neste ambiente
        return {"paisOrigem": [], "tipoObra": [], "subtipoObra": []}
    finally:
        con.close()


_SALA_OPTIONS: dict = {"combos": []}


def _load_sala_options() -> dict:
    """Combinações distintas (grupo exibidor, UF, município) em data/ancine/
    salaexibicao.parquet, para o filtro Exibidor — o frontend deriva as opções
    de cada campo a partir daqui, em cascata (grupo -> UF -> município)."""
    con = connect_ancine()
    try:
        rows = con.execute(
            "SELECT DISTINCT NOME_GRUPO_EXIBIDOR, UF_COMPLEXO, MUNICIPIO_COMPLEXO FROM salaexibicao"
            " WHERE UF_COMPLEXO IS NOT NULL AND UF_COMPLEXO != ''"
            " AND MUNICIPIO_COMPLEXO IS NOT NULL AND MUNICIPIO_COMPLEXO != ''"
            " ORDER BY 1, 2, 3"
        ).fetchall()
        combos = []
        for grupo, uf, municipio in rows:
            if grupo in (None, "", "NÃO PERTENCE A NENHUM GRUPO EXIBIDOR"):
                grupo = None
            combos.append({"grupoExibidor": grupo, "uf": uf, "municipio": municipio})
        return {"combos": combos}
    except duckdb.CatalogException:
        # data/ancine/salaexibicao.parquet ainda não existe neste ambiente
        return {"combos": []}
    finally:
        con.close()


def _load_ratings_dist() -> list[dict]:
    con = _new_db()
    rows = con.execute(
        "SELECT RATING, SUM(COUNT_RATING) AS VOTES"
        " FROM movie_rating GROUP BY RATING ORDER BY RATING"
    ).fetchall()
    con.close()
    return [{"rating": float(r[0]), "votes": int(r[1])} for r in rows]


def _load_films() -> list[dict]:
    con = _new_db()

    # ISO-3 code → (country_name, continent, region)
    nat: dict[str, tuple] = {
        r[0]: (r[1], r[2], r[3])
        for r in con.execute(
            "SELECT ISO, COUNTRY, CONTINENT, REGION FROM country WHERE ISO IS NOT NULL"
        ).fetchall()
    }

    films: list[dict] = []
    cur = con.execute(_FILMS_QUERY)
    cols = [d[0] for d in cur.description]
    for raw in cur.fetchall():
            r = dict(zip(cols, raw))

            rating = _float(r["IMDBRATING"])
            if rating is None:
                continue

            # Country / continent / region
            country   = r["COUNTRY"] or (r["IMDB_COUNTRY_RAW"] or "").split(",")[0].strip() or "Unknown"
            continent = r["CONTINENT"] or "Other"
            region    = r["REGION"] or ""

            # Genre
            ml_g   = r["ML_GENRE"]
            imdb_g = r["IMDB_GENRE"] or (r["IMDB_GENRE_RAW"] or "").split(",")[0].strip() or None
            genre  = ml_g or imdb_g or "Other"

            # Awards (Parquet stores as DOUBLE — convert to int)
            osc_w = int(r["OSCAR_WINNING"]    or 0)
            osc_n = int(r["OSCAR_NOMINATION"] or 0)
            aw_w  = int(r["AWARD_WINNING"]    or 0)
            aw_n  = int(r["AWARD_NOMINATION"] or 0)
            ba_w  = int(r["BAFTA_WINNING"]    or 0)
            ba_n  = int(r["BAFTA_NOMINATION"] or 0)
            em_w  = int(r["EMMY_WINNING"]     or 0)
            em_n  = int(r["EMMY_NOMINATION"]  or 0)
            other_awards = max(0, aw_w - osc_w) + max(0, aw_n - osc_n) + ba_w + ba_n + em_w + em_n

            year = int(r["YEAR"]) if r["YEAR"] else None

            # Director nationality → country/region lookup
            dn      = nat.get(r["DIR_NAT"] or "", (None, None, None))
            dir_age = (year - int(r["DIR_BY"])) if year and r["DIR_BY"] else None

            # Writer nationality → country/region lookup
            wn      = nat.get(r["WRI_NAT"] or "", (None, None, None))
            wri_age = (year - int(r["WRI_BY"])) if year and r["WRI_BY"] else None

            genres_all = r["ALL_GENRES"] or (r["IMDB_GENRE_RAW"] or "").replace(",", ", ") or genre

            films.append({
                "imdbid":        r["IMDBID"],
                "movieid":       r["MOVIEID"],
                "title":         r["TITLE"],
                "director":      r["DIR_NAME"] or "",
                "directorid":    r["DIR_ID"],
                "directorsAll":  r["ALL_DIRS"] or r["DIR_NAME"] or "",
                "year":          year,
                "country":       country,
                "countriesAll":  r["ALL_COUNTRIES"] or country,
                "genre":         genre,
                "genresAll":     genres_all.strip() if genres_all else genre,
                "mlGenre":     ml_g or genre,
                "imdbGenre":   imdb_g or genre,
                "rating":      rating,
                "box":         _box(r["BOXOFFICE"]),
                "continent":   continent,
                "region":      region,
                "ratingImdb":  rating,
                "ratingMl":    round(rating / 2.0, 1),
                "votesImdb":   _int(r["IMDBVOTES"]),
                "votesMl":     int(r["VOTES_ML"]) if r["VOTES_ML"] else 0,
                "oscars":      osc_w,
                "otherAwards": other_awards,
                "dir": {
                    "gender":  _gender(r["DIR_GENDER"]),
                    "race":    _race(r["DIR_RACE"]),
                    "country": dn[0] or country,
                    "region":  dn[2] or region,
                    "age":     dir_age,
                },
                "wri": {
                    "name":    r["WRI_NAME"] or "",
                    "id":      r["WRI_ID"],
                    "gender":  _gender(r["WRI_GENDER"]),
                    "race":    _race(r["WRI_RACE"]),
                    "country": wn[0] or country,
                    "region":  wn[2] or region,
                    "age":     wri_age,
                },
            })

    con.close()
    print(f"[BilheteriaBR] {len(films)} films loaded from Parquet")
    return films


# ── FastAPI app ───────────────────────────────────────────────────────────────

def _load_all_data() -> None:
    global _FILMS, _RATINGS_DIST, _PERIODO_OPTIONS, _OBRA_OPTIONS, _SALA_OPTIONS, _FILMES_SEM_FILTRO_CACHE, _READY
    RUNTIME.mark_loading()
    logger.info(json.dumps({"event": "startup_loading"}))
    try:
        _FILMS = _load_films()
        _RATINGS_DIST = _load_ratings_dist()
        _PERIODO_OPTIONS = _load_periodo_options()
        _OBRA_OPTIONS = _load_obra_options()
        _SALA_OPTIONS = _load_sala_options()
        _FILMES_SEM_FILTRO_CACHE = _load_filmes_sem_filtro()
        _load_ancine_sem_filtro_caches()
    except Exception as error:
        RUNTIME.mark_failed(error)
        logger.exception(json.dumps({"event": "startup_failed", "errorType": type(error).__name__}))
        return
    _READY = True
    RUNTIME.mark_ready()
    logger.info(json.dumps({"event": "startup_ready"}))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start data loading in background so the server binds to the port immediately.
    # Cloud Run health checks will see /health return 503 until _READY = True.
    threading.Thread(target=_load_all_data, daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(chat_router)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def observe_and_limit_requests(request: Request, call_next):
    started = time.monotonic()
    limited = request.url.path.startswith("/api/")
    acquired = not limited or QUERY_SLOTS.acquire(blocking=False)
    if not acquired:
        RUNTIME.record_rejection()
        return JSONResponse(status_code=503, content={"error": "Servidor ocupado. Tente novamente."})
    try:
        response = await call_next(request)
    except Exception:
        RUNTIME.record_request(request.url.path, time.monotonic() - started, 500)
        logger.exception(json.dumps({"event": "request_failed", "path": request.url.path}))
        raise
    finally:
        if limited and acquired:
            QUERY_SLOTS.release()
    elapsed = time.monotonic() - started
    RUNTIME.record_request(request.url.path, elapsed, response.status_code)
    logger.info(json.dumps({
        "event": "request",
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "elapsedMs": round(elapsed * 1000, 3),
    }))
    return response


@app.get("/health")
def health():
    if RUNTIME.status != "ready":
        return JSONResponse(
            status_code=503,
            content={"status": RUNTIME.status, "error": RUNTIME.startup_error},
        )
    return {"status": "ok"}


@app.get("/health/live")
def liveness():
    return {"status": "alive"}


@app.get("/health/ready")
def readiness():
    return health()


@app.get("/metrics")
def metrics():
    snapshot = RUNTIME.snapshot()
    snapshot["analyticsCacheEntries"] = len(ANALYTICS_CACHE)
    return snapshot


@app.get("/api/films")
def api_films():
    return _FILMS


@app.get("/api/ratings-dist")
def api_ratings_dist():
    return _RATINGS_DIST


@app.get("/api/ancine/periodo-options")
def api_ancine_periodo_options():
    """Anos e semanas cinematográficas distintos, para o filtro Período."""
    return _PERIODO_OPTIONS


@app.get("/api/ancine/obra-options")
def api_ancine_obra_options():
    """País de origem distintos (CPB + ROE), para o filtro Obra."""
    return _OBRA_OPTIONS


@app.get("/api/ancine/sala-options")
def api_ancine_sala_options():
    """Grupo exibidor, UF e município distintos (salaexibicao.parquet), para o filtro Exibidor."""
    return _SALA_OPTIONS


@app.get("/api/ancine/titulo-brasil-sugestoes")
def api_ancine_titulo_brasil_sugestoes(q: str = ""):
    """Sugestões de autocomplete para o filtro "Título Brasil" — busca em
    COALESCE(TITULO_BRASIL, TITULO_ORIGINAL) da view `obra` (CPB + ROE)."""
    q = q.strip()
    if len(q) < 2:
        return []
    con = connect_ancine()
    try:
        rows = con.execute(
            """
            SELECT DISTINCT COALESCE(TITULO_BRASIL, TITULO_ORIGINAL) AS titulo
            FROM obra
            WHERE COALESCE(TITULO_BRASIL, TITULO_ORIGINAL) ILIKE ?
            ORDER BY titulo
            LIMIT 20
            """,
            [f"%{q}%"],
        ).fetchall()
        return [r[0] for r in rows]
    except duckdb.CatalogException:
        return []
    finally:
        con.close()


_FILMES_QUERY_SQL = """
    WITH sess AS (
        SELECT
            b.CPB_ROE, b.DATA_EXIBICAO, b.REGISTRO_SALA, b.REGISTRO_COMPLEXO,
            b.PUBLICO, b.PUBLICO_PAGANTE, b.RENDA_TOTAL, b.TITULO_ORIGINAL, b.TITULO_BRASIL
        FROM bilheteria b
        WHERE {where_sql}
    ),
    por_dia AS (
        -- Agregação diária primeiro: dá tanto os picos (máx. salas/complexos
        -- em um mesmo dia) quanto os totais (público/sessões), numa passada
        -- só — evita fazer JOIN entre duas CTEs derivadas de `sess`, que faz
        -- o otimizador do DuckDB escolher um plano absurdamente lento aqui.
        SELECT
            CPB_ROE, DATA_EXIBICAO,
            COUNT(DISTINCT REGISTRO_SALA)     AS salas_dia,
            COUNT(DISTINCT REGISTRO_COMPLEXO) AS complexos_dia,
            COUNT(*)                          AS sessoes_dia,
            SUM(PUBLICO)                      AS publico_dia,
            SUM(PUBLICO_PAGANTE)              AS publico_pagante_dia,
            SUM(RENDA_TOTAL)                  AS renda_dia,
            ANY_VALUE(TITULO_ORIGINAL)        AS titulo_original,
            ANY_VALUE(TITULO_BRASIL)          AS titulo_brasil_raw
        FROM sess
        GROUP BY CPB_ROE, DATA_EXIBICAO
    ),
    agg AS (
        SELECT
            CPB_ROE AS codigo,
            ANY_VALUE(titulo_original)   AS titulo_original,
            ANY_VALUE(titulo_brasil_raw) AS titulo_brasil_raw,
            MIN(DATA_EXIBICAO)           AS primeira_data,
            SUM(publico_dia)             AS publico,
            SUM(publico_pagante_dia)     AS publico_pagante,
            SUM(renda_dia)               AS renda_total,
            SUM(sessoes_dia)             AS sessoes,
            COUNT(*)                     AS dias_exibicao,
            MAX(salas_dia)               AS max_salas,
            MAX(complexos_dia)           AS max_complexos
        FROM por_dia
        GROUP BY CPB_ROE
    )
    SELECT
        a.codigo, a.titulo_original, a.titulo_brasil_raw, a.primeira_data,
        a.publico, a.publico_pagante, a.renda_total,
        a.sessoes, a.dias_exibicao, a.max_salas, a.max_complexos,
        pp.paises AS pais_produtor
    FROM agg a
    LEFT JOIN (
        -- obra_pais (não obra_produtor): roe_produtor.parquet não tem coluna
        -- de país, mas roe_pais.parquet tem — cpb_pais/roe_pais cobrem os
        -- dois lados (CPB e ROE) de forma completa.
        SELECT CODIGO, string_agg(DISTINCT PAIS_ORIGEM, ' | ' ORDER BY PAIS_ORIGEM) AS paises
        FROM obra_pais
        WHERE PAIS_ORIGEM IS NOT NULL AND PAIS_ORIGEM != ''
        GROUP BY CODIGO
    ) pp ON pp.CODIGO = a.codigo
    ORDER BY a.publico DESC
"""


def _query_filmes_uncached(con: duckdb.DuckDBPyConnection, where_sql: str, params: list) -> list[dict]:
    """Executa a query de bilheteria agregada por obra e faz o pós-
    processamento em Python (tipo CPB/ROE, ano-cine, público médio) — ver
    nota no SQL acima sobre por que essas colunas não são calculadas lá."""
    rows = execute_with_timeout(
        con, _FILMES_QUERY_SQL.format(where_sql=where_sql), params
    ).fetchall()
    out = []
    for (codigo, titulo_original, titulo_brasil_raw, primeira_data, publico, publico_pagante,
         renda_total, sessoes, dias_exibicao, max_salas, max_complexos, pais_produtor) in rows:
        out.append({
            "codigo": codigo,
            "tipoRegistro": classify_registration(codigo),
            "tituloBrasil": titulo_brasil_raw or titulo_original,
            "tituloOriginal": titulo_original,
            "paisProdutor": pais_produtor,
            "ano1aExibicao": cinema_year(primeira_data),
            "publicoPagante": publico_pagante,
            "publico": publico,
            "rendaTotal": renda_total,
            # PMI (Preço Médio de Ingresso) agregado = renda / público pagante,
            # não a média simples do PMI por sessão — pondera pelo público de
            # cada sessão em vez de dar o mesmo peso a sessões pequenas e cheias.
            "pmi": round(renda_total / publico_pagante, 2) if publico_pagante else None,
            "sessoesRealizadas": sessoes,
            "diasExibicao": dias_exibicao,
            "publicoMedioSessao": round(publico / sessoes, 1) if sessoes else None,
            "maxSalasOcupadas": max_salas,
            "maxComplexosOcupados": max_complexos,
        })
    return out


def _query_filmes(con: duckdb.DuckDBPyConnection, where_sql: str, params: list) -> list[dict]:
    key = ("films", where_sql, tuple(params))
    return ANALYTICS_CACHE.get_or_set(
        key, lambda: _query_filmes_uncached(con, where_sql, params)
    )


_FILMES_FILTER_DEFAULTS = dict(
    anos=[], semanaInicio=None, semanaFim=None, cpbRoe="", tituloBrasileiro="", tituloOriginal="", paisOrigem=[],
    nacionalidade=[], tipoObra=[], subtipoObra=[],
    registroSala="", grupoExibidor=[], municipioSala=[], ufSala=[],
    nomeDiretor="", nomeProdutor="", cnpjRequerente="", nomeRequerente="",
    municipioRequerente=[], ufRequerente=[],
)

_FILMES_SEM_FILTRO_CACHE: list = []


def _load_filmes_sem_filtro() -> list:
    """Pré-computa a tabela da aba Filmes sem nenhum filtro (visão inicial),
    já que essa consulta varre a bilheteria inteira (~37M linhas) e pode
    levar de 15 a 50s — rápido demais pra rodar a cada request, rápido o
    bastante pra rodar uma vez no boot."""
    con = connect_ancine()
    try:
        where_sql, params = _ancine_filmes_where(_FILMES_FILTER_DEFAULTS)
        return _query_filmes(con, where_sql, params)
    except duckdb.CatalogException:
        return []
    finally:
        con.close()


@app.get("/api/ancine/filmes")
def api_ancine_filmes(
    anos: list[int] = Query(default=[]),
    semanaInicio: int | None = None,
    semanaFim: int | None = None,
    cpbRoe: str = "",
    tituloBrasileiro: str = "",
    tituloOriginal: str = "",
    paisOrigem: list[str] = Query(default=[]),
    nacionalidade: list[str] = Query(default=[]),
    tipoObra: list[str] = Query(default=[]),
    subtipoObra: list[str] = Query(default=[]),
    registroSala: str = "",
    grupoExibidor: list[str] = Query(default=[]),
    municipioSala: list[str] = Query(default=[]),
    ufSala: list[str] = Query(default=[]),
    nomeDiretor: str = "",
    nomeProdutor: str = "",
    cnpjRequerente: str = "",
    nomeRequerente: str = "",
    municipioRequerente: list[str] = Query(default=[]),
    ufRequerente: list[str] = Query(default=[]),
):
    """Tabela da aba Filmes: uma linha por obra (CPB ou ROE), agregada a
    partir das sessões de bilheteria que casam com os filtros da sidebar."""
    filters = dict(
        anos=anos, semanaInicio=semanaInicio, semanaFim=semanaFim, cpbRoe=cpbRoe,
        tituloBrasileiro=tituloBrasileiro, tituloOriginal=tituloOriginal, paisOrigem=paisOrigem,
        nacionalidade=nacionalidade, tipoObra=tipoObra, subtipoObra=subtipoObra,
        registroSala=registroSala, grupoExibidor=grupoExibidor, municipioSala=municipioSala, ufSala=ufSala,
        nomeDiretor=nomeDiretor, nomeProdutor=nomeProdutor,
        cnpjRequerente=cnpjRequerente, nomeRequerente=nomeRequerente,
        municipioRequerente=municipioRequerente, ufRequerente=ufRequerente,
    )
    if filters == _FILMES_FILTER_DEFAULTS:
        return _FILMES_SEM_FILTRO_CACHE

    where_sql, params = _ancine_filmes_where(filters)
    con = connect_ancine()
    try:
        return _query_filmes(con, where_sql, params)
    except duckdb.CatalogException:
        # data/ancine/ ainda não está completo neste ambiente
        return []
    finally:
        con.close()


@app.get("/api/ancine/periodo-exibido")
def api_ancine_periodo_exibido(
    anos: list[int] = Query(default=[]),
    semanaInicio: int | None = None,
    semanaFim: int | None = None,
    cpbRoe: str = "",
    tituloBrasileiro: str = "",
    tituloOriginal: str = "",
    paisOrigem: list[str] = Query(default=[]),
    nacionalidade: list[str] = Query(default=[]),
    tipoObra: list[str] = Query(default=[]),
    subtipoObra: list[str] = Query(default=[]),
    registroSala: str = "",
    grupoExibidor: list[str] = Query(default=[]),
    municipioSala: list[str] = Query(default=[]),
    ufSala: list[str] = Query(default=[]),
    nomeDiretor: str = "",
    nomeProdutor: str = "",
    cnpjRequerente: str = "",
    nomeRequerente: str = "",
    municipioRequerente: list[str] = Query(default=[]),
    ufRequerente: list[str] = Query(default=[]),
):
    """Período (data mín/máx de exibição) coberto pelas sessões que casam com
    os filtros da sidebar — mostrado no header, em todas as abas."""
    filters = dict(
        anos=anos, semanaInicio=semanaInicio, semanaFim=semanaFim, cpbRoe=cpbRoe,
        tituloBrasileiro=tituloBrasileiro, tituloOriginal=tituloOriginal, paisOrigem=paisOrigem,
        nacionalidade=nacionalidade, tipoObra=tipoObra, subtipoObra=subtipoObra,
        registroSala=registroSala, grupoExibidor=grupoExibidor, municipioSala=municipioSala, ufSala=ufSala,
        nomeDiretor=nomeDiretor, nomeProdutor=nomeProdutor,
        cnpjRequerente=cnpjRequerente, nomeRequerente=nomeRequerente,
        municipioRequerente=municipioRequerente, ufRequerente=ufRequerente,
    )
    where_sql, params = _ancine_filmes_where(filters)
    con = connect_ancine()
    try:
        data_min, data_max = con.execute(
            f"SELECT MIN(b.DATA_EXIBICAO), MAX(b.DATA_EXIBICAO) FROM bilheteria b WHERE {where_sql}", params
        ).fetchone()
        return {
            "dataMin": data_min.strftime("%d/%m/%Y") if data_min else None,
            "dataMax": data_max.strftime("%d/%m/%Y") if data_max else None,
        }
    except duckdb.CatalogException:
        return {"dataMin": None, "dataMax": None}
    finally:
        con.close()


_BILHETERIA_POR_TIPO_DEFAULTS = {
    "publico": 0, "publicoPagante": 0, "rendaTotal": 0, "pmi": None,
    "sessoes": 0, "titulosDistintos": 0,
}
_TICKET_TYPES = ("inteira", "meia", "promocional", "cortesia")
_BILHETERIA_POR_TICKET_DEFAULTS = {"publico": 0, "rendaTotal": 0, "pmi": None}
_BILHETERIA_RESUMO_DEFAULTS = {
    "publico": 0, "publicoPagante": 0, "rendaTotal": 0, "pmi": None,
    "diasExibicao": 0, "sessoes": 0, "titulosDistintos": 0, "salasDistintas": 0,
    "porTipo": {"CPB": dict(_BILHETERIA_POR_TIPO_DEFAULTS), "ROE": dict(_BILHETERIA_POR_TIPO_DEFAULTS)},
    "porTipoIngresso": {t: dict(_BILHETERIA_POR_TICKET_DEFAULTS) for t in _TICKET_TYPES},
}


def _query_bilheteria_resumo_uncached(con: duckdb.DuckDBPyConnection, where_sql: str, params: list) -> dict:
    try:
        # Agrupado por tipo (CPB/ROE) — dá tanto os totais gerais (soma dos
        # dois) quanto o detalhamento Brasileiro/Estrangeiro exibido embaixo
        # de cada indicador. Também traz, na mesma passada, as 4 colunas de
        # tipo de ingresso (inteira/meia/promocional/cortesia) — ortogonais
        # a CPB/ROE, por isso são somadas através dos grupos, não por grupo.
        # DIAS_EXIBICAO/SALAS_DISTINTAS ficam de fora de ambos os
        # detalhamentos porque não são decomponíveis: a mesma sala/dia pode
        # ter sessões dos dois lados — somar os grupos infla o total.
        rows = execute_with_timeout(con, f"""
            SELECT
                tipo_registro(b.CPB_ROE)          AS tipo,
                SUM(b.PUBLICO)                    AS publico,
                SUM(b.PUBLICO_PAGANTE)            AS publico_pagante,
                SUM(b.RENDA_TOTAL)                AS renda_total,
                COUNT(*)                          AS sessoes,
                COUNT(DISTINCT b.CPB_ROE)          AS titulos_distintos,
                SUM(b.PUBLICO_INTEIRA)            AS publico_inteira,
                SUM(b.PUBLICO_MEIA)               AS publico_meia,
                SUM(b.PUBLICO_PROMOCIONAL)        AS publico_promocional,
                SUM(b.PUBLICO_CORTESIA)           AS publico_cortesia,
                SUM(b.RENDA_INTEIRA)              AS renda_inteira,
                SUM(b.RENDA_MEIA)                 AS renda_meia,
                SUM(b.RENDA_PROMOCIONAL)          AS renda_promocional,
                SUM(b.RENDA_CORTESIA)             AS renda_cortesia
            FROM bilheteria b
            WHERE {where_sql}
            GROUP BY 1
        """, params).fetchall()
        gerais = execute_with_timeout(con, f"""
            SELECT COUNT(DISTINCT b.DATA_EXIBICAO), COUNT(DISTINCT b.REGISTRO_SALA)
            FROM bilheteria b
            WHERE {where_sql}
        """, params).fetchone()
    except duckdb.CatalogException:
        # data/ancine/ingresso_hive ainda não existe neste ambiente
        return dict(_BILHETERIA_RESUMO_DEFAULTS)

    por_tipo = {"CPB": dict(_BILHETERIA_POR_TIPO_DEFAULTS), "ROE": dict(_BILHETERIA_POR_TIPO_DEFAULTS)}
    ticket_publico = dict.fromkeys(_TICKET_TYPES, 0)
    ticket_renda = dict.fromkeys(_TICKET_TYPES, 0)
    publico = publico_pagante = renda_total = sessoes = titulos_distintos = 0
    for (tipo, t_publico, t_publico_pagante, t_renda, t_sessoes, t_titulos,
         t_pub_inteira, t_pub_meia, t_pub_promocional, t_pub_cortesia,
         t_renda_inteira, t_renda_meia, t_renda_promocional, t_renda_cortesia) in rows:
        t_publico = t_publico or 0
        t_publico_pagante = t_publico_pagante or 0
        t_renda = t_renda or 0
        t_sessoes = t_sessoes or 0
        t_titulos = t_titulos or 0
        if tipo in por_tipo:
            por_tipo[tipo] = {
                "publico": t_publico,
                "publicoPagante": t_publico_pagante,
                "rendaTotal": t_renda,
                "pmi": round(t_renda / t_publico_pagante, 2) if t_publico_pagante else None,
                "sessoes": t_sessoes,
                "titulosDistintos": t_titulos,
            }
        publico += t_publico
        publico_pagante += t_publico_pagante
        renda_total += t_renda
        sessoes += t_sessoes
        titulos_distintos += t_titulos

        ticket_publico["inteira"] += t_pub_inteira or 0
        ticket_publico["meia"] += t_pub_meia or 0
        ticket_publico["promocional"] += t_pub_promocional or 0
        ticket_publico["cortesia"] += t_pub_cortesia or 0
        ticket_renda["inteira"] += t_renda_inteira or 0
        ticket_renda["meia"] += t_renda_meia or 0
        ticket_renda["promocional"] += t_renda_promocional or 0
        ticket_renda["cortesia"] += t_renda_cortesia or 0

    # Cortesia é entrada gratuita por definição — qualquer valor não-zero na
    # soma (a base tem uns poucos centavos de ruído/estorno em ~36M linhas)
    # é artefato de dado, não renda real. Força para 0.
    ticket_renda["cortesia"] = 0.0

    por_tipo_ingresso = {
        t: {
            "publico": ticket_publico[t],
            "rendaTotal": ticket_renda[t],
            "pmi": round(ticket_renda[t] / ticket_publico[t], 2) if ticket_publico[t] else None,
        }
        for t in _TICKET_TYPES
    }

    dias_exibicao, salas_distintas = gerais if gerais else (0, 0)
    return {
        "publico": publico,
        "publicoPagante": publico_pagante,
        "rendaTotal": renda_total,
        # PMI (Preço Médio de Ingresso) agregado = renda / público pagante,
        # ponderado pelo público de cada sessão (mesma lógica da aba Filmes).
        "pmi": round(renda_total / publico_pagante, 2) if publico_pagante else None,
        "diasExibicao": dias_exibicao or 0,
        "sessoes": sessoes,
        "titulosDistintos": titulos_distintos,
        "salasDistintas": salas_distintas or 0,
        "porTipo": por_tipo,
        "porTipoIngresso": por_tipo_ingresso,
    }


def _query_bilheteria_resumo(con, where_sql: str, params: list) -> dict:
    key = ("summary", where_sql, tuple(params))
    return ANALYTICS_CACHE.get_or_set(
        key, lambda: _query_bilheteria_resumo_uncached(con, where_sql, params)
    )


_BILHETERIA_RESUMO_CACHE: dict = dict(_BILHETERIA_RESUMO_DEFAULTS)


@app.get("/api/ancine/bilheteria-resumo")
def api_ancine_bilheteria_resumo(
    anos: list[int] = Query(default=[]),
    semanaInicio: int | None = None,
    semanaFim: int | None = None,
    cpbRoe: str = "",
    tituloBrasileiro: str = "",
    tituloOriginal: str = "",
    paisOrigem: list[str] = Query(default=[]),
    nacionalidade: list[str] = Query(default=[]),
    tipoObra: list[str] = Query(default=[]),
    subtipoObra: list[str] = Query(default=[]),
    registroSala: str = "",
    grupoExibidor: list[str] = Query(default=[]),
    municipioSala: list[str] = Query(default=[]),
    ufSala: list[str] = Query(default=[]),
    nomeDiretor: str = "",
    nomeProdutor: str = "",
    cnpjRequerente: str = "",
    nomeRequerente: str = "",
    municipioRequerente: list[str] = Query(default=[]),
    ufRequerente: list[str] = Query(default=[]),
):
    """Indicadores da aba Bilheteria: público, dias de exibição, sessões,
    títulos e salas distintas — sobre as sessões que casam com os filtros
    da sidebar. Sem filtro, vem do cache pré-computado no boot (ver
    _load_all_data)."""
    filters = dict(
        anos=anos, semanaInicio=semanaInicio, semanaFim=semanaFim, cpbRoe=cpbRoe,
        tituloBrasileiro=tituloBrasileiro, tituloOriginal=tituloOriginal, paisOrigem=paisOrigem,
        nacionalidade=nacionalidade, tipoObra=tipoObra, subtipoObra=subtipoObra,
        registroSala=registroSala, grupoExibidor=grupoExibidor, municipioSala=municipioSala, ufSala=ufSala,
        nomeDiretor=nomeDiretor, nomeProdutor=nomeProdutor,
        cnpjRequerente=cnpjRequerente, nomeRequerente=nomeRequerente,
        municipioRequerente=municipioRequerente, ufRequerente=ufRequerente,
    )
    if filters == _FILMES_FILTER_DEFAULTS:
        return _BILHETERIA_RESUMO_CACHE

    where_sql, params = _ancine_filmes_where(filters)
    con = connect_ancine()
    try:
        return _query_bilheteria_resumo(con, where_sql, params)
    finally:
        con.close()


def _query_bilheteria_grafico_uncached(con: duckdb.DuckDBPyConnection, where_sql: str, params: list) -> dict:
    try:
        # Agrupa por data (não por ano_cine) — aplicar a macro ano_cine por
        # linha num GROUP BY sobre a `bilheteria` inteira gera um plano muito
        # lento no DuckDB; agregando por data primeiro (poucos milhares de
        # linhas no resultado) e mapeando para ano_cine em Python depois é
        # muito mais rápido (ver _ano_cine_py).
        rows = execute_with_timeout(con, f"""
            SELECT b.DATA_EXIBICAO AS data, tipo_registro(b.CPB_ROE) AS tipo,
                   SUM(b.PUBLICO) AS publico, SUM(b.RENDA_TOTAL) AS renda, COUNT(*) AS sessoes,
                   SUM(b.PUBLICO_INTEIRA) AS publico_inteira, SUM(b.PUBLICO_MEIA) AS publico_meia,
                   SUM(b.PUBLICO_PROMOCIONAL) AS publico_promocional, SUM(b.PUBLICO_CORTESIA) AS publico_cortesia,
                   SUM(b.RENDA_INTEIRA) AS renda_inteira, SUM(b.RENDA_MEIA) AS renda_meia,
                   SUM(b.RENDA_PROMOCIONAL) AS renda_promocional, SUM(b.RENDA_CORTESIA) AS renda_cortesia
            FROM bilheteria b
            WHERE {where_sql}
            GROUP BY 1, 2
        """, params).fetchall()
    except duckdb.CatalogException:
        # data/ancine/ingresso_hive ainda não existe neste ambiente
        return {"porAno": []}

    por_ano: dict[int, dict] = {}
    for (data, tipo, publico, renda, sessoes, pub_inteira, pub_meia, pub_promocional, pub_cortesia,
         renda_inteira, renda_meia, renda_promocional, renda_cortesia) in rows:
        ano = cinema_year(data)
        d = por_ano.setdefault(ano, {
            "ano": ano, "publicoCpb": 0, "publicoRoe": 0,
            "rendaCpb": 0, "rendaRoe": 0, "sessoesCpb": 0, "sessoesRoe": 0,
            "publicoInteira": 0, "publicoMeia": 0, "publicoPromocional": 0, "publicoCortesia": 0,
            "rendaInteira": 0, "rendaMeia": 0, "rendaPromocional": 0, "rendaCortesia": 0,
        })
        if tipo == "CPB":
            d["publicoCpb"] += publico or 0
            d["rendaCpb"] += renda or 0
            d["sessoesCpb"] += sessoes or 0
        elif tipo == "ROE":
            d["publicoRoe"] += publico or 0
            d["rendaRoe"] += renda or 0
            d["sessoesRoe"] += sessoes or 0

        # Tipo de ingresso é ortogonal a CPB/ROE — soma através dos dois grupos.
        d["publicoInteira"] += pub_inteira or 0
        d["publicoMeia"] += pub_meia or 0
        d["publicoPromocional"] += pub_promocional or 0
        d["publicoCortesia"] += pub_cortesia or 0
        d["rendaInteira"] += renda_inteira or 0
        d["rendaMeia"] += renda_meia or 0
        d["rendaPromocional"] += renda_promocional or 0
        d["rendaCortesia"] += renda_cortesia or 0

    return {"porAno": sorted(por_ano.values(), key=lambda d: d["ano"])}


def _query_bilheteria_grafico(con, where_sql: str, params: list) -> dict:
    key = ("chart", where_sql, tuple(params))
    return ANALYTICS_CACHE.get_or_set(
        key, lambda: _query_bilheteria_grafico_uncached(con, where_sql, params)
    )


_BILHETERIA_GRAFICO_CACHE: dict = {"porAno": []}


@app.get("/api/ancine/bilheteria-grafico")
def api_ancine_bilheteria_grafico(
    anos: list[int] = Query(default=[]),
    semanaInicio: int | None = None,
    semanaFim: int | None = None,
    cpbRoe: str = "",
    tituloBrasileiro: str = "",
    tituloOriginal: str = "",
    paisOrigem: list[str] = Query(default=[]),
    nacionalidade: list[str] = Query(default=[]),
    tipoObra: list[str] = Query(default=[]),
    subtipoObra: list[str] = Query(default=[]),
    registroSala: str = "",
    grupoExibidor: list[str] = Query(default=[]),
    municipioSala: list[str] = Query(default=[]),
    ufSala: list[str] = Query(default=[]),
    nomeDiretor: str = "",
    nomeProdutor: str = "",
    cnpjRequerente: str = "",
    nomeRequerente: str = "",
    municipioRequerente: list[str] = Query(default=[]),
    ufRequerente: list[str] = Query(default=[]),
):
    """Público e sessões por ano-cine × CPB/ROE, para os 3 gráficos da aba
    Bilheteria (barras empilhadas por ano + as 2 pizzas de participação).
    Sem filtro, vem do cache pré-computado no boot (ver _load_all_data)."""
    filters = dict(
        anos=anos, semanaInicio=semanaInicio, semanaFim=semanaFim, cpbRoe=cpbRoe,
        tituloBrasileiro=tituloBrasileiro, tituloOriginal=tituloOriginal, paisOrigem=paisOrigem,
        nacionalidade=nacionalidade, tipoObra=tipoObra, subtipoObra=subtipoObra,
        registroSala=registroSala, grupoExibidor=grupoExibidor, municipioSala=municipioSala, ufSala=ufSala,
        nomeDiretor=nomeDiretor, nomeProdutor=nomeProdutor,
        cnpjRequerente=cnpjRequerente, nomeRequerente=nomeRequerente,
        municipioRequerente=municipioRequerente, ufRequerente=ufRequerente,
    )
    if filters == _FILMES_FILTER_DEFAULTS:
        return _BILHETERIA_GRAFICO_CACHE

    where_sql, params = _ancine_filmes_where(filters)
    con = connect_ancine()
    try:
        return _query_bilheteria_grafico(con, where_sql, params)
    finally:
        con.close()


def _query_bilheteria_semanal_uncached(con: duckdb.DuckDBPyConnection, where_sql: str, params: list) -> dict:
    try:
        # Agrupa por data (não por ano_cine/semana_cine) pelo mesmo motivo do
        # endpoint bilheteria-grafico acima — ver _ano_cine_py/_semana_cine_py.
        rows = execute_with_timeout(con, f"""
            SELECT b.DATA_EXIBICAO AS data, SUM(b.PUBLICO) AS publico,
                   SUM(b.PUBLICO_INTEIRA) AS publico_inteira, SUM(b.PUBLICO_MEIA) AS publico_meia,
                   SUM(b.PUBLICO_PROMOCIONAL) AS publico_promocional, SUM(b.PUBLICO_CORTESIA) AS publico_cortesia,
                   SUM(b.RENDA_INTEIRA) AS renda_inteira, SUM(b.RENDA_MEIA) AS renda_meia,
                   SUM(b.RENDA_PROMOCIONAL) AS renda_promocional
            FROM bilheteria b
            WHERE {where_sql}
            GROUP BY 1
        """, params).fetchall()
    except duckdb.CatalogException:
        # data/ancine/ingresso_hive ainda não existe neste ambiente
        return {"porSemana": []}

    agregado: dict[tuple[int, int], dict] = {}
    for (data, publico, pub_inteira, pub_meia, pub_promocional, pub_cortesia,
         renda_inteira, renda_meia, renda_promocional) in rows:
        chave = (cinema_year(data), cinema_week(data))
        d = agregado.setdefault(chave, {
            "publico": 0, "publicoInteira": 0, "publicoMeia": 0, "publicoPromocional": 0, "publicoCortesia": 0,
            "rendaInteira": 0, "rendaMeia": 0, "rendaPromocional": 0,
        })
        d["publico"] += publico or 0
        d["publicoInteira"] += pub_inteira or 0
        d["publicoMeia"] += pub_meia or 0
        d["publicoPromocional"] += pub_promocional or 0
        d["publicoCortesia"] += pub_cortesia or 0
        d["rendaInteira"] += renda_inteira or 0
        d["rendaMeia"] += renda_meia or 0
        d["rendaPromocional"] += renda_promocional or 0

    return {"porSemana": [
        dict(ano=ano, semana=semana, **valores)
        for (ano, semana), valores in sorted(agregado.items())
    ]}


def _query_bilheteria_semanal(con, where_sql: str, params: list) -> dict:
    key = ("weekly", where_sql, tuple(params))
    return ANALYTICS_CACHE.get_or_set(
        key, lambda: _query_bilheteria_semanal_uncached(con, where_sql, params)
    )


_BILHETERIA_SEMANAL_CACHE: dict = {"porSemana": []}


@app.get("/api/ancine/bilheteria-semanal")
def api_ancine_bilheteria_semanal(
    anos: list[int] = Query(default=[]),
    semanaInicio: int | None = None,
    semanaFim: int | None = None,
    cpbRoe: str = "",
    tituloBrasileiro: str = "",
    tituloOriginal: str = "",
    paisOrigem: list[str] = Query(default=[]),
    nacionalidade: list[str] = Query(default=[]),
    tipoObra: list[str] = Query(default=[]),
    subtipoObra: list[str] = Query(default=[]),
    registroSala: str = "",
    grupoExibidor: list[str] = Query(default=[]),
    municipioSala: list[str] = Query(default=[]),
    ufSala: list[str] = Query(default=[]),
    nomeDiretor: str = "",
    nomeProdutor: str = "",
    cnpjRequerente: str = "",
    nomeRequerente: str = "",
    municipioRequerente: list[str] = Query(default=[]),
    ufRequerente: list[str] = Query(default=[]),
):
    """Público por semana cinematográfica (1..53), uma série por ano-cine —
    para o gráfico de linhas da aba Bilheteria. Sem filtro, vem do cache
    pré-computado no boot (ver _load_all_data)."""
    filters = dict(
        anos=anos, semanaInicio=semanaInicio, semanaFim=semanaFim, cpbRoe=cpbRoe,
        tituloBrasileiro=tituloBrasileiro, tituloOriginal=tituloOriginal, paisOrigem=paisOrigem,
        nacionalidade=nacionalidade, tipoObra=tipoObra, subtipoObra=subtipoObra,
        registroSala=registroSala, grupoExibidor=grupoExibidor, municipioSala=municipioSala, ufSala=ufSala,
        nomeDiretor=nomeDiretor, nomeProdutor=nomeProdutor,
        cnpjRequerente=cnpjRequerente, nomeRequerente=nomeRequerente,
        municipioRequerente=municipioRequerente, ufRequerente=ufRequerente,
    )
    if filters == _FILMES_FILTER_DEFAULTS:
        return _BILHETERIA_SEMANAL_CACHE

    where_sql, params = _ancine_filmes_where(filters)
    con = connect_ancine()
    try:
        return _query_bilheteria_semanal(con, where_sql, params)
    finally:
        con.close()


_PESSOA_QUERY_SQL = """
    WITH sess AS MATERIALIZED (
        SELECT b.CPB_ROE, b.DATA_EXIBICAO, b.PUBLICO, b.PUBLICO_PAGANTE, b.RENDA_TOTAL
        FROM bilheteria b
        WHERE {where_sql}
    ),
    pessoa_titulo AS ({pessoa_titulo_sql}),
    -- Pré-agrega por título ANTES de juntar com pessoa_titulo — uma obra pode
    -- ter várias pessoas (diretor/produtor/requerente), então juntar direto
    -- com `sess` infla o número de linhas (cada sessão se repete uma vez por
    -- pessoa da obra) antes de agregar, o que é caro num join grande. Pré-
    -- agregando por CPB_ROE primeiro, o join final é pequeno (nº de títulos ×
    -- pessoas por título, não nº de sessões × pessoas por título).
    titulo_agg AS (
        SELECT CPB_ROE, SUM(PUBLICO) AS publico, SUM(PUBLICO_PAGANTE) AS publico_pagante,
               SUM(RENDA_TOTAL) AS renda, COUNT(*) AS sessoes
        FROM sess
        GROUP BY CPB_ROE
    ),
    -- dias_exibicao é COUNT(DISTINCT data) por pessoa através de todos os
    -- títulos dela — não dá pra pré-somar por título (a mesma data pode
    -- aparecer em títulos diferentes da mesma pessoa), mas dá pra deduplicar
    -- (título, data) antes do join, que já é bem menor que `sess` inteira.
    titulo_datas AS (
        SELECT DISTINCT CPB_ROE, DATA_EXIBICAO FROM sess
    ),
    pessoa_agg AS (
        SELECT pt.pessoa,
               COUNT(*)                AS qtd_titulos,
               SUM(ta.publico)         AS publico_total,
               SUM(ta.publico_pagante) AS publico_pagante,
               SUM(ta.renda)           AS renda_total,
               SUM(ta.sessoes)         AS sessoes
        FROM pessoa_titulo pt
        JOIN titulo_agg ta ON ta.CPB_ROE = pt.CODIGO
        GROUP BY pt.pessoa
    ),
    pessoa_dias AS (
        SELECT pt.pessoa, COUNT(DISTINCT td.DATA_EXIBICAO) AS dias_exibicao
        FROM pessoa_titulo pt
        JOIN titulo_datas td ON td.CPB_ROE = pt.CODIGO
        GROUP BY pt.pessoa
    )
    SELECT pa.pessoa, pa.qtd_titulos, pa.publico_total, pa.publico_pagante, pa.renda_total,
           pa.sessoes, pd.dias_exibicao
    FROM pessoa_agg pa
    JOIN pessoa_dias pd ON pd.pessoa = pa.pessoa
    ORDER BY pa.publico_total DESC
"""


def _query_pessoa_agregada_uncached(con: duckdb.DuckDBPyConnection, where_sql: str, params: list, pessoa_titulo_sql: str) -> list[dict]:
    """Agrega bilheteria por pessoa/empresa (diretor, produtor ou requerente) —
    `pessoa_titulo_sql` é uma query que retorna (pessoa, CODIGO), uma linha por
    obra em que essa pessoa aparece (uma obra pode ter várias pessoas, então
    uma sessão pode contar para mais de uma linha do resultado — esperado)."""
    sql = _PESSOA_QUERY_SQL.format(where_sql=where_sql, pessoa_titulo_sql=pessoa_titulo_sql)
    rows = execute_with_timeout(con, sql, params).fetchall()
    out = []
    for pessoa, qtd, publico, publico_pagante, renda_total, sessoes, dias in rows:
        publico = publico or 0
        publico_pagante = publico_pagante or 0
        renda_total = renda_total or 0
        sessoes = sessoes or 0
        out.append({
            "nome": pessoa,
            "qtdTitulos": qtd,
            "publicoPagante": publico_pagante,
            "publicoTotal": publico,
            "rendaTotal": renda_total,
            # PMI (Preço Médio de Ingresso) agregado = renda / público pagante,
            # ponderado pelo público de cada sessão (mesma lógica da aba Filmes).
            "pmi": round(renda_total / publico_pagante, 2) if publico_pagante else None,
            "sessoes": sessoes,
            "diasExibicao": dias or 0,
            "publicoMedioTitulo": round(publico / qtd, 1) if qtd else None,
            "sessoesMediaTitulo": round(sessoes / qtd, 1) if qtd else None,
        })
    return out


def _query_pessoa_agregada(con, where_sql: str, params: list, person_sql: str) -> list[dict]:
    key = ("people", person_sql, where_sql, tuple(params))
    return ANALYTICS_CACHE.get_or_set(
        key,
        lambda: _query_pessoa_agregada_uncached(con, where_sql, params, person_sql),
    )


_DIRETORES_CACHE: list = []
_PRODUTORES_CACHE: list = []
_REQUERENTES_CACHE: list = []
_PAISES_CACHE: list = []


@app.get("/api/ancine/diretores")
def api_ancine_diretores(
    anos: list[int] = Query(default=[]),
    semanaInicio: int | None = None,
    semanaFim: int | None = None,
    cpbRoe: str = "",
    tituloBrasileiro: str = "",
    tituloOriginal: str = "",
    paisOrigem: list[str] = Query(default=[]),
    nacionalidade: list[str] = Query(default=[]),
    tipoObra: list[str] = Query(default=[]),
    subtipoObra: list[str] = Query(default=[]),
    registroSala: str = "",
    grupoExibidor: list[str] = Query(default=[]),
    municipioSala: list[str] = Query(default=[]),
    ufSala: list[str] = Query(default=[]),
    nomeDiretor: str = "",
    nomeProdutor: str = "",
    cnpjRequerente: str = "",
    nomeRequerente: str = "",
    municipioRequerente: list[str] = Query(default=[]),
    ufRequerente: list[str] = Query(default=[]),
):
    """Tabela da aba Diretores: uma linha por diretor, agregada a partir das
    sessões de bilheteria dos títulos que dirigiu. Sem filtro, vem do cache
    pré-computado no boot (ver _load_all_data)."""
    filters = dict(
        anos=anos, semanaInicio=semanaInicio, semanaFim=semanaFim, cpbRoe=cpbRoe,
        tituloBrasileiro=tituloBrasileiro, tituloOriginal=tituloOriginal, paisOrigem=paisOrigem,
        nacionalidade=nacionalidade, tipoObra=tipoObra, subtipoObra=subtipoObra,
        registroSala=registroSala, grupoExibidor=grupoExibidor, municipioSala=municipioSala, ufSala=ufSala,
        nomeDiretor=nomeDiretor, nomeProdutor=nomeProdutor,
        cnpjRequerente=cnpjRequerente, nomeRequerente=nomeRequerente,
        municipioRequerente=municipioRequerente, ufRequerente=ufRequerente,
    )
    if filters == _FILMES_FILTER_DEFAULTS:
        return _DIRETORES_CACHE

    where_sql, params = _ancine_filmes_where(filters)
    con = connect_ancine()
    try:
        return _query_pessoa_agregada(con, where_sql, params,
            "SELECT DISTINCT DIRETOR AS pessoa, CODIGO FROM obra_diretor WHERE DIRETOR IS NOT NULL AND DIRETOR != ''")
    except duckdb.CatalogException:
        return []
    finally:
        con.close()


@app.get("/api/ancine/produtores")
def api_ancine_produtores(
    anos: list[int] = Query(default=[]),
    semanaInicio: int | None = None,
    semanaFim: int | None = None,
    cpbRoe: str = "",
    tituloBrasileiro: str = "",
    tituloOriginal: str = "",
    paisOrigem: list[str] = Query(default=[]),
    nacionalidade: list[str] = Query(default=[]),
    tipoObra: list[str] = Query(default=[]),
    subtipoObra: list[str] = Query(default=[]),
    registroSala: str = "",
    grupoExibidor: list[str] = Query(default=[]),
    municipioSala: list[str] = Query(default=[]),
    ufSala: list[str] = Query(default=[]),
    nomeDiretor: str = "",
    nomeProdutor: str = "",
    cnpjRequerente: str = "",
    nomeRequerente: str = "",
    municipioRequerente: list[str] = Query(default=[]),
    ufRequerente: list[str] = Query(default=[]),
):
    """Tabela da aba Produtores: uma linha por produtor, agregada a partir das
    sessões de bilheteria dos títulos que produziu. Sem filtro, vem do cache
    pré-computado no boot (ver _load_all_data)."""
    filters = dict(
        anos=anos, semanaInicio=semanaInicio, semanaFim=semanaFim, cpbRoe=cpbRoe,
        tituloBrasileiro=tituloBrasileiro, tituloOriginal=tituloOriginal, paisOrigem=paisOrigem,
        nacionalidade=nacionalidade, tipoObra=tipoObra, subtipoObra=subtipoObra,
        registroSala=registroSala, grupoExibidor=grupoExibidor, municipioSala=municipioSala, ufSala=ufSala,
        nomeDiretor=nomeDiretor, nomeProdutor=nomeProdutor,
        cnpjRequerente=cnpjRequerente, nomeRequerente=nomeRequerente,
        municipioRequerente=municipioRequerente, ufRequerente=ufRequerente,
    )
    if filters == _FILMES_FILTER_DEFAULTS:
        return _PRODUTORES_CACHE

    where_sql, params = _ancine_filmes_where(filters)
    con = connect_ancine()
    try:
        return _query_pessoa_agregada(con, where_sql, params,
            "SELECT DISTINCT PRODUTOR AS pessoa, CODIGO FROM obra_produtor WHERE PRODUTOR IS NOT NULL AND PRODUTOR != ''")
    except duckdb.CatalogException:
        return []
    finally:
        con.close()


@app.get("/api/ancine/requerentes")
def api_ancine_requerentes(
    anos: list[int] = Query(default=[]),
    semanaInicio: int | None = None,
    semanaFim: int | None = None,
    cpbRoe: str = "",
    tituloBrasileiro: str = "",
    tituloOriginal: str = "",
    paisOrigem: list[str] = Query(default=[]),
    nacionalidade: list[str] = Query(default=[]),
    tipoObra: list[str] = Query(default=[]),
    subtipoObra: list[str] = Query(default=[]),
    registroSala: str = "",
    grupoExibidor: list[str] = Query(default=[]),
    municipioSala: list[str] = Query(default=[]),
    ufSala: list[str] = Query(default=[]),
    nomeDiretor: str = "",
    nomeProdutor: str = "",
    cnpjRequerente: str = "",
    nomeRequerente: str = "",
    municipioRequerente: list[str] = Query(default=[]),
    ufRequerente: list[str] = Query(default=[]),
):
    """Tabela da aba Requerente: uma linha por requerente (empresa que
    registrou a obra na Ancine), agregada a partir das sessões de bilheteria
    dos títulos que requereu. Sem filtro, vem do cache pré-computado no boot
    (ver _load_all_data)."""
    filters = dict(
        anos=anos, semanaInicio=semanaInicio, semanaFim=semanaFim, cpbRoe=cpbRoe,
        tituloBrasileiro=tituloBrasileiro, tituloOriginal=tituloOriginal, paisOrigem=paisOrigem,
        nacionalidade=nacionalidade, tipoObra=tipoObra, subtipoObra=subtipoObra,
        registroSala=registroSala, grupoExibidor=grupoExibidor, municipioSala=municipioSala, ufSala=ufSala,
        nomeDiretor=nomeDiretor, nomeProdutor=nomeProdutor,
        cnpjRequerente=cnpjRequerente, nomeRequerente=nomeRequerente,
        municipioRequerente=municipioRequerente, ufRequerente=ufRequerente,
    )
    if filters == _FILMES_FILTER_DEFAULTS:
        return _REQUERENTES_CACHE

    where_sql, params = _ancine_filmes_where(filters)
    con = connect_ancine()
    try:
        return _query_pessoa_agregada(con, where_sql, params,
            "SELECT DISTINCT REQUERENTE AS pessoa, CODIGO FROM obra WHERE REQUERENTE IS NOT NULL AND REQUERENTE != ''")
    except duckdb.CatalogException:
        return []
    finally:
        con.close()


@app.get("/api/ancine/paises")
def api_ancine_paises(
    anos: list[int] = Query(default=[]),
    semanaInicio: int | None = None,
    semanaFim: int | None = None,
    cpbRoe: str = "",
    tituloBrasileiro: str = "",
    tituloOriginal: str = "",
    paisOrigem: list[str] = Query(default=[]),
    nacionalidade: list[str] = Query(default=[]),
    tipoObra: list[str] = Query(default=[]),
    subtipoObra: list[str] = Query(default=[]),
    registroSala: str = "",
    grupoExibidor: list[str] = Query(default=[]),
    municipioSala: list[str] = Query(default=[]),
    ufSala: list[str] = Query(default=[]),
    nomeDiretor: str = "",
    nomeProdutor: str = "",
    cnpjRequerente: str = "",
    nomeRequerente: str = "",
    municipioRequerente: list[str] = Query(default=[]),
    ufRequerente: list[str] = Query(default=[]),
):
    """Aba Países: uma linha por país produtor (PAIS_ORIGEM em obra_pais),
    agregada a partir das sessões de bilheteria dos títulos daquele país.
    Sem filtro, vem do cache pré-computado no boot (ver _load_all_data)."""
    filters = dict(
        anos=anos, semanaInicio=semanaInicio, semanaFim=semanaFim, cpbRoe=cpbRoe,
        tituloBrasileiro=tituloBrasileiro, tituloOriginal=tituloOriginal, paisOrigem=paisOrigem,
        nacionalidade=nacionalidade, tipoObra=tipoObra, subtipoObra=subtipoObra,
        registroSala=registroSala, grupoExibidor=grupoExibidor, municipioSala=municipioSala, ufSala=ufSala,
        nomeDiretor=nomeDiretor, nomeProdutor=nomeProdutor,
        cnpjRequerente=cnpjRequerente, nomeRequerente=nomeRequerente,
        municipioRequerente=municipioRequerente, ufRequerente=ufRequerente,
    )
    if filters == _FILMES_FILTER_DEFAULTS:
        return _PAISES_CACHE

    where_sql, params = _ancine_filmes_where(filters)
    con = connect_ancine()
    try:
        return _query_pessoa_agregada(con, where_sql, params,
            "SELECT DISTINCT PAIS_ORIGEM AS pessoa, CODIGO FROM obra_pais WHERE PAIS_ORIGEM IS NOT NULL AND PAIS_ORIGEM != ''")
    except duckdb.CatalogException:
        return []
    finally:
        con.close()


@app.get("/api/ancine/filme-detalhe/{codigo}")
def api_ancine_filme_detalhe(codigo: str):
    """Detalhes do filme para o painel lateral das abas Filme/Diretor/Produtor.

    Sempre retorna o cadastro Ancine (CPB ou ROE — todo título de bilheteria
    tem um dos dois) em `ancine`. Se houver correspondência no IMDb (via
    data/ancine/ancine_cpb.parquet ou ancine_roe.parquet, coluna imdbID),
    também retorna Movie/Crew Detail em `imdb` (sem selos de avaliação); caso
    contrário `imdb` é null."""
    tipo = classify_registration(codigo)
    con = _new_filme_detalhe_db()
    try:
        ancine = None
        if tipo == "CPB":
            row = con.execute(
                "SELECT TITULO_ORIGINAL, TIPO_OBRA, DURACAO_TOTAL_MINUTOS, ANO_PRODUCAO_INICIAL, REQUERENTE "
                "FROM cpb WHERE CPB = ?", [codigo],
            ).fetchone()
            if row:
                titulo_original, tipo_obra, duracao, ano_producao, requerente = row
                ancine = {
                    "codigo": codigo, "tipoRegistro": "CPB",
                    "titulo": _clean(titulo_original),
                    "tipoObra": _clean(tipo_obra),
                    "duracao": f"{int(duracao)} min" if duracao is not None else "",
                    "anoProducao": int(ano_producao) if ano_producao is not None else None,
                    "requerente": _clean(requerente),
                }
        elif tipo == "ROE":
            row = con.execute(
                "SELECT TITULO_BRASIL, TITULO_ORIGINAL, TIPO_OBRA, DURACAO_TOTAL_MINUTOS, ANO_PRODUCAO_INICIAL, REQUERENTE "
                "FROM roe WHERE ROE = ?", [codigo],
            ).fetchone()
            if row:
                titulo_brasil, titulo_original, tipo_obra, duracao, ano_producao, requerente = row
                ancine = {
                    "codigo": codigo, "tipoRegistro": "ROE",
                    "titulo": _clean(titulo_brasil) or _clean(titulo_original),
                    "tipoObra": _clean(tipo_obra),
                    "duracao": f"{int(duracao)} min" if duracao is not None else "",
                    "anoProducao": int(ano_producao) if ano_producao is not None else None,
                    "requerente": _clean(requerente),
                }

        if tipo == "CPB":
            r = con.execute("SELECT imdbID FROM ancine_cpb WHERE CPB = ?", [codigo]).fetchone()
        elif tipo == "ROE":
            r = con.execute("SELECT imdbID FROM ancine_roe WHERE ROE = ?", [codigo]).fetchone()
        else:
            r = None
        imdb_id = _clean(r[0]) if r else ""
        if not imdb_id:
            return {"ancine": ancine, "imdb": None}

        m = con.execute(
            "SELECT TITLE, YEAR, RELEASED, RUNTIME, COUNTRY, LANGUAGE, GENRE, DIRECTOR, WRITER, "
            "ACTORS, PLOT, POSTER, AWARDS "
            "FROM movie_imdb WHERE IMDBID = ?", [imdb_id],
        ).fetchone()
        if not m:
            return {"ancine": ancine, "imdb": None}
        (title, year, released, runtime, country, language, genre, director, writer,
         actors, plot, poster, awards) = m

        def _people(person_table: str, role_table: str, id_col: str) -> list[dict]:
            # DIRECTORID/WRITERID e NCONST são o mesmo namespace de ID de pessoa
            # do IMDb (nm...) — quando a pessoa também está em output_cast (nem
            # sempre, já que ali só cobre quem tem crédito de elenco), pega a
            # foto de lá.
            rows = con.execute(
                f"SELECT p.NAME, p.GENDER, p.RACE, p.NATIONALITY, p.ETHNICITY, p.RELIGION, o.PRIMARYIMAGEURL "
                f"FROM {person_table} p JOIN {role_table} r ON p.{id_col} = r.{id_col} "
                f"LEFT JOIN output_cast o ON o.NCONST = p.{id_col} "
                f"WHERE r.IMDBID = ?", [imdb_id],
            ).fetchall()
            out = []
            for name, gender, race, nationality, ethnicity, religion, photo in rows:
                name = _clean(name)
                if not name:
                    continue
                entry: dict = {"name": name}
                gender = _norm_gender(gender)
                if gender:
                    entry["gender"] = gender
                for k, v in (("race", race), ("nationality", nationality),
                             ("ethnicity", ethnicity), ("religion", religion)):
                    v = _clean(v)
                    if v:
                        entry[k] = v
                photo = _clean(photo)
                if photo:
                    entry["photo"] = photo
                out.append(entry)
            return out

        directors = _people("director", "movie_director", "DIRECTORID")
        writers = _people("writer", "movie_writer", "WRITERID")

        cast_rows = con.execute(
            "SELECT c.NCONST, o.DISPLAYNAME, c.CATEGORY, c.JOB, c.CHARACTERS, o.PRIMARYIMAGEURL, "
            "o.BIRTHDATE, o.BIRTHLOCATION, o.BIOGRAPHY, o.GENDER "
            "FROM movie_cast c LEFT JOIN output_cast o ON o.NCONST = c.NCONST "
            "WHERE c.IMDBID = ? AND c.CATEGORY NOT IN ('director', 'writer') "
            "ORDER BY c.ORDERING", [imdb_id],
        ).fetchall()

        # Uma pessoa pode ter várias linhas em movie_cast para o mesmo filme
        # (personagens/categorias diferentes) — agrupa por NCONST, juntando
        # categorias/funções/personagens distintos numa única entrada.
        cast_by_person: dict = {}
        cast_order: list = []
        for nconst, name, category, job, characters, photo, birthdate, birthlocation, biography, gender in cast_rows:
            name = _clean(name)
            if not name:
                continue
            key = nconst or name
            if key not in cast_by_person:
                cast_by_person[key] = {
                    "name": name, "categories": [], "jobs": [], "characters": [],
                    "photo": _clean(photo), "born": ", ".join(x for x in [_clean(birthdate), _clean(birthlocation)] if x),
                    "biography": _clean(biography), "gender": _norm_gender(gender),
                }
                cast_order.append(key)
            entry = cast_by_person[key]
            category = _clean(category)
            if category and category not in entry["categories"]:
                entry["categories"].append(category)
            job = _clean(job)
            if job and job not in entry["jobs"]:
                entry["jobs"].append(job)
            for ch in _chars_to_list(characters):
                if ch not in entry["characters"]:
                    entry["characters"].append(ch)

        cast = []
        for key in cast_order:
            p = cast_by_person[key]
            entry = {"name": p["name"]}
            if p["categories"]:
                entry["category"] = ", ".join(p["categories"])
            if p["jobs"]:
                entry["job"] = ", ".join(p["jobs"])
            if p["characters"]:
                entry["characters"] = ", ".join(p["characters"])
            if p["photo"]:
                entry["photo"] = p["photo"]
            if p["born"]:
                entry["born"] = p["born"]
            if p["biography"]:
                entry["biography"] = p["biography"]
            if p["gender"]:
                entry["gender"] = p["gender"]
            cast.append(entry)

        year_str = ""
        if year is not None:
            year_str = str(int(year))

        imdb = {
            "imdbId": imdb_id,
            "title": _clean(title),
            "year": year_str,
            "released": released.strftime("%d/%m/%Y") if released else "",
            "runtime": _clean(runtime),
            "country": _clean(country),
            "language": _clean(language),
            "genre": _clean(genre),
            "director": _clean(director),
            "writer": _clean(writer),
            "cast": _clean(actors),
            "plot": _clean(plot),
            "poster": _clean(poster),
            "awards": _clean(awards),
            "crew": {"directors": directors, "writers": writers, "cast": cast},
        }
        return {"ancine": ancine, "imdb": imdb}
    except duckdb.CatalogException:
        return {"ancine": None, "imdb": None}
    finally:
        con.close()


_SALAS_QUERY_SQL = """
    WITH sess AS (
        SELECT b.REGISTRO_SALA, b.CPB_ROE, b.PUBLICO, b.PUBLICO_PAGANTE, b.RENDA_TOTAL
        FROM bilheteria b
        WHERE {where_sql}
    ),
    agg AS (
        SELECT
            REGISTRO_SALA,
            COUNT(DISTINCT CPB_ROE) AS qtd_titulos,
            SUM(PUBLICO)            AS publico_total,
            SUM(PUBLICO_PAGANTE)    AS publico_pagante,
            SUM(RENDA_TOTAL)        AS renda_total,
            COUNT(*)                AS sessoes
        FROM sess
        GROUP BY REGISTRO_SALA
    ),
    sala_dedup AS (
        -- salaexibicao.parquet tem uns poucos REGISTRO_SALA duplicados — fica só a 1ª linha
        SELECT * FROM salaexibicao
        QUALIFY ROW_NUMBER() OVER (PARTITION BY REGISTRO_SALA ORDER BY REGISTRO_SALA) = 1
    )
    SELECT
        a.REGISTRO_SALA,
        s.NOME_EXIBIDOR,
        s.NOME_COMPLEXO, s.REGISTRO_COMPLEXO,
        s.NOME_SALA,
        a.qtd_titulos, a.publico_total, a.publico_pagante, a.renda_total, a.sessoes
    FROM agg a
    LEFT JOIN sala_dedup s ON s.REGISTRO_SALA = a.REGISTRO_SALA
    ORDER BY a.publico_total DESC
"""


def _query_salas_uncached(con: duckdb.DuckDBPyConnection, where_sql: str, params: list) -> list[dict]:
    try:
        sql = _SALAS_QUERY_SQL.format(where_sql=where_sql)
        rows = execute_with_timeout(con, sql, params).fetchall()
    except duckdb.CatalogException:
        return []

    out = []
    for (registro_sala, exibidor, complexo, registro_complexo, sala, qtd,
         publico, publico_pagante, renda_total, sessoes) in rows:
        publico = publico or 0
        publico_pagante = publico_pagante or 0
        renda_total = renda_total or 0
        sessoes = sessoes or 0
        out.append({
            "registroSala": registro_sala,
            "exibidor": exibidor,
            "complexo": complexo,
            "registroComplexo": registro_complexo,
            "sala": sala,
            "qtdTitulos": qtd,
            "publicoPagante": publico_pagante,
            "publicoTotal": publico,
            "rendaTotal": renda_total,
            "pmi": round(renda_total / publico_pagante, 2) if publico_pagante else None,
            "sessoes": sessoes,
            "publicoMedioSessao": round(publico / sessoes, 1) if sessoes else None,
        })
    return out


def _query_salas(con, where_sql: str, params: list) -> list[dict]:
    key = ("theaters", where_sql, tuple(params))
    return ANALYTICS_CACHE.get_or_set(
        key, lambda: _query_salas_uncached(con, where_sql, params)
    )


_SALAS_CACHE: list = []


def _query_mapa_uf_uncached(con: duckdb.DuckDBPyConnection, where_sql: str, params: list) -> list[dict]:
    """Agrega bilheteria por UF da sala de exibição (salaexibicao.UF_COMPLEXO,
    via bilheteria.UF_SALA_COMPLEXO) — mapa do Brasil da aba Mapa."""
    try:
        rows = execute_with_timeout(con, f"""
            SELECT b.UF_SALA_COMPLEXO AS uf,
                   SUM(b.PUBLICO) AS publico,
                   SUM(b.PUBLICO_PAGANTE) AS publico_pagante,
                   SUM(b.RENDA_TOTAL) AS renda_total,
                   COUNT(*) AS sessoes
            FROM bilheteria b
            WHERE {where_sql} AND b.UF_SALA_COMPLEXO IS NOT NULL
            GROUP BY 1
        """, params).fetchall()
    except duckdb.CatalogException:
        return []

    out = []
    for uf, publico, publico_pagante, renda_total, sessoes in rows:
        publico_pagante = publico_pagante or 0
        renda_total = renda_total or 0
        out.append({
            "uf": uf,
            "publico": publico or 0,
            "rendaTotal": renda_total,
            "sessoes": sessoes or 0,
            "pmi": round(renda_total / publico_pagante, 2) if publico_pagante else None,
        })
    return out


def _query_mapa_uf(con, where_sql: str, params: list) -> list[dict]:
    key = ("mapa-uf", where_sql, tuple(params))
    return ANALYTICS_CACHE.get_or_set(
        key, lambda: _query_mapa_uf_uncached(con, where_sql, params)
    )


_MAPA_UF_CACHE: list = []


def _query_mapa_municipios_uncached(
    con: duckdb.DuckDBPyConnection, where_sql: str, params: list, uf: str
) -> list[dict]:
    """Mesma agregação de _query_mapa_uf_uncached, restrita a uma UF e
    detalhada por município — drill-down ao clicar num estado no mapa."""
    try:
        rows = execute_with_timeout(con, f"""
            SELECT b.MUNICIPIO_SALA_COMPLEXO AS municipio,
                   SUM(b.PUBLICO) AS publico,
                   SUM(b.PUBLICO_PAGANTE) AS publico_pagante,
                   SUM(b.RENDA_TOTAL) AS renda_total,
                   COUNT(*) AS sessoes
            FROM bilheteria b
            WHERE {where_sql} AND b.UF_SALA_COMPLEXO = ? AND b.MUNICIPIO_SALA_COMPLEXO IS NOT NULL
            GROUP BY 1
        """, [*params, uf]).fetchall()
    except duckdb.CatalogException:
        return []

    out = []
    for municipio, publico, publico_pagante, renda_total, sessoes in rows:
        publico_pagante = publico_pagante or 0
        renda_total = renda_total or 0
        out.append({
            "municipio": municipio,
            "publico": publico or 0,
            "rendaTotal": renda_total,
            "sessoes": sessoes or 0,
            "pmi": round(renda_total / publico_pagante, 2) if publico_pagante else None,
        })
    return out


def _load_ancine_sem_filtro_caches() -> None:
    """Pré-computa, uma vez no boot, a visão 'sem filtro' (estado inicial da
    sidebar) de cada aba que consulta `bilheteria` — os endpoints servem
    esse resultado instantaneamente via cache quando os filtros da sidebar
    estão todos nos valores padrão (ver `if filters == _FILMES_FILTER_DEFAULTS`
    em cada endpoint), evitando reprocessar a bilheteria inteira (~37M linhas)
    a cada carga da página."""
    global _BILHETERIA_RESUMO_CACHE, _BILHETERIA_GRAFICO_CACHE, _BILHETERIA_SEMANAL_CACHE
    global _DIRETORES_CACHE, _PRODUTORES_CACHE, _REQUERENTES_CACHE, _PAISES_CACHE, _SALAS_CACHE, _MAPA_UF_CACHE
    con = connect_ancine()
    try:
        where_sql, params = _ancine_filmes_where(_FILMES_FILTER_DEFAULTS)
        _BILHETERIA_RESUMO_CACHE = _query_bilheteria_resumo(con, where_sql, params)
        _BILHETERIA_GRAFICO_CACHE = _query_bilheteria_grafico(con, where_sql, params)
        _BILHETERIA_SEMANAL_CACHE = _query_bilheteria_semanal(con, where_sql, params)
        _DIRETORES_CACHE = _query_pessoa_agregada(con, where_sql, params,
            "SELECT DISTINCT DIRETOR AS pessoa, CODIGO FROM obra_diretor WHERE DIRETOR IS NOT NULL AND DIRETOR != ''")
        _PRODUTORES_CACHE = _query_pessoa_agregada(con, where_sql, params,
            "SELECT DISTINCT PRODUTOR AS pessoa, CODIGO FROM obra_produtor WHERE PRODUTOR IS NOT NULL AND PRODUTOR != ''")
        _REQUERENTES_CACHE = _query_pessoa_agregada(con, where_sql, params,
            "SELECT DISTINCT REQUERENTE AS pessoa, CODIGO FROM obra WHERE REQUERENTE IS NOT NULL AND REQUERENTE != ''")
        _PAISES_CACHE = _query_pessoa_agregada(con, where_sql, params,
            "SELECT DISTINCT PAIS_ORIGEM AS pessoa, CODIGO FROM obra_pais WHERE PAIS_ORIGEM IS NOT NULL AND PAIS_ORIGEM != ''")
        _SALAS_CACHE = _query_salas(con, where_sql, params)
        _MAPA_UF_CACHE = _query_mapa_uf(con, where_sql, params)
    except duckdb.CatalogException:
        # data/ancine/ ainda não está completo neste ambiente — caches ficam
        # nos valores default (vazios) definidos acima dos endpoints
        pass
    finally:
        con.close()


@app.get("/api/ancine/salas")
def api_ancine_salas(
    anos: list[int] = Query(default=[]),
    semanaInicio: int | None = None,
    semanaFim: int | None = None,
    cpbRoe: str = "",
    tituloBrasileiro: str = "",
    tituloOriginal: str = "",
    paisOrigem: list[str] = Query(default=[]),
    nacionalidade: list[str] = Query(default=[]),
    tipoObra: list[str] = Query(default=[]),
    subtipoObra: list[str] = Query(default=[]),
    registroSala: str = "",
    grupoExibidor: list[str] = Query(default=[]),
    municipioSala: list[str] = Query(default=[]),
    ufSala: list[str] = Query(default=[]),
    nomeDiretor: str = "",
    nomeProdutor: str = "",
    cnpjRequerente: str = "",
    nomeRequerente: str = "",
    municipioRequerente: list[str] = Query(default=[]),
    ufRequerente: list[str] = Query(default=[]),
):
    """Aba Exibidor: uma linha por sala (REGISTRO_SALA), agregada a partir das
    sessões de bilheteria realizadas naquela sala, com o nome do exibidor/
    complexo/sala vindos de salaexibicao.parquet. Sem filtro, vem do cache
    pré-computado no boot (ver _load_all_data)."""
    filters = dict(
        anos=anos, semanaInicio=semanaInicio, semanaFim=semanaFim, cpbRoe=cpbRoe,
        tituloBrasileiro=tituloBrasileiro, tituloOriginal=tituloOriginal, paisOrigem=paisOrigem,
        nacionalidade=nacionalidade, tipoObra=tipoObra, subtipoObra=subtipoObra,
        registroSala=registroSala, grupoExibidor=grupoExibidor, municipioSala=municipioSala, ufSala=ufSala,
        nomeDiretor=nomeDiretor, nomeProdutor=nomeProdutor,
        cnpjRequerente=cnpjRequerente, nomeRequerente=nomeRequerente,
        municipioRequerente=municipioRequerente, ufRequerente=ufRequerente,
    )
    if filters == _FILMES_FILTER_DEFAULTS:
        return _SALAS_CACHE

    where_sql, params = _ancine_filmes_where(filters)
    con = connect_ancine()
    try:
        return _query_salas(con, where_sql, params)
    finally:
        con.close()


@app.get("/api/ancine/mapa-uf")
def api_ancine_mapa_uf(
    anos: list[int] = Query(default=[]),
    semanaInicio: int | None = None,
    semanaFim: int | None = None,
    cpbRoe: str = "",
    tituloBrasileiro: str = "",
    tituloOriginal: str = "",
    paisOrigem: list[str] = Query(default=[]),
    nacionalidade: list[str] = Query(default=[]),
    tipoObra: list[str] = Query(default=[]),
    subtipoObra: list[str] = Query(default=[]),
    registroSala: str = "",
    grupoExibidor: list[str] = Query(default=[]),
    municipioSala: list[str] = Query(default=[]),
    ufSala: list[str] = Query(default=[]),
    nomeDiretor: str = "",
    nomeProdutor: str = "",
    cnpjRequerente: str = "",
    nomeRequerente: str = "",
    municipioRequerente: list[str] = Query(default=[]),
    ufRequerente: list[str] = Query(default=[]),
):
    """Aba Mapa: público/renda/sessões/PMI por UF da sala de exibição — uma
    linha por UF. Sem filtro, vem do cache pré-computado no boot."""
    filters = dict(
        anos=anos, semanaInicio=semanaInicio, semanaFim=semanaFim, cpbRoe=cpbRoe,
        tituloBrasileiro=tituloBrasileiro, tituloOriginal=tituloOriginal, paisOrigem=paisOrigem,
        nacionalidade=nacionalidade, tipoObra=tipoObra, subtipoObra=subtipoObra,
        registroSala=registroSala, grupoExibidor=grupoExibidor, municipioSala=municipioSala, ufSala=ufSala,
        nomeDiretor=nomeDiretor, nomeProdutor=nomeProdutor,
        cnpjRequerente=cnpjRequerente, nomeRequerente=nomeRequerente,
        municipioRequerente=municipioRequerente, ufRequerente=ufRequerente,
    )
    if filters == _FILMES_FILTER_DEFAULTS:
        return _MAPA_UF_CACHE

    where_sql, params = _ancine_filmes_where(filters)
    con = connect_ancine()
    try:
        return _query_mapa_uf(con, where_sql, params)
    finally:
        con.close()


@app.get("/api/ancine/mapa-municipios")
def api_ancine_mapa_municipios(
    uf: str,
    anos: list[int] = Query(default=[]),
    semanaInicio: int | None = None,
    semanaFim: int | None = None,
    cpbRoe: str = "",
    tituloBrasileiro: str = "",
    tituloOriginal: str = "",
    paisOrigem: list[str] = Query(default=[]),
    nacionalidade: list[str] = Query(default=[]),
    tipoObra: list[str] = Query(default=[]),
    subtipoObra: list[str] = Query(default=[]),
    registroSala: str = "",
    grupoExibidor: list[str] = Query(default=[]),
    municipioSala: list[str] = Query(default=[]),
    ufSala: list[str] = Query(default=[]),
    nomeDiretor: str = "",
    nomeProdutor: str = "",
    cnpjRequerente: str = "",
    nomeRequerente: str = "",
    municipioRequerente: list[str] = Query(default=[]),
    ufRequerente: list[str] = Query(default=[]),
):
    """Drill-down da aba Mapa: público/renda/sessões/PMI por município,
    dentro de uma UF — carregado sob demanda ao clicar num estado."""
    filters = dict(
        anos=anos, semanaInicio=semanaInicio, semanaFim=semanaFim, cpbRoe=cpbRoe,
        tituloBrasileiro=tituloBrasileiro, tituloOriginal=tituloOriginal, paisOrigem=paisOrigem,
        nacionalidade=nacionalidade, tipoObra=tipoObra, subtipoObra=subtipoObra,
        registroSala=registroSala, grupoExibidor=grupoExibidor, municipioSala=municipioSala, ufSala=ufSala,
        nomeDiretor=nomeDiretor, nomeProdutor=nomeProdutor,
        cnpjRequerente=cnpjRequerente, nomeRequerente=nomeRequerente,
        municipioRequerente=municipioRequerente, ufRequerente=ufRequerente,
    )
    where_sql, params = _ancine_filmes_where(filters)
    con = connect_ancine()
    try:
        return _query_mapa_municipios_uncached(con, where_sql, params, uf)
    finally:
        con.close()


@app.get("/api/ancine/sala-detalhe/{registro_sala}")
def api_ancine_sala_detalhe(registro_sala: int):
    """Detalhes cadastrais da sala (data/ancine/salaexibicao.parquet) para o
    painel lateral da aba Exibidor — grupo exibidor, exibidor, complexo, sala
    e assentos/acessibilidade."""
    con = connect_ancine()
    try:
        row = con.execute(
            "SELECT * FROM salaexibicao WHERE REGISTRO_SALA = ? LIMIT 1", [registro_sala]
        ).fetchone()
        if not row:
            return {"found": False}
        cols = [d[0] for d in con.description]
        r = dict(zip(cols, row))

        def c(key):
            return _clean(r.get(key))

        def d(key):
            v = r.get(key)
            return v.strftime("%d/%m/%Y") if v else None

        grupo = c("NOME_GRUPO_EXIBIDOR")
        if grupo == "NÃO PERTENCE A NENHUM GRUPO EXIBIDOR":
            grupo = ""

        return {
            "found": True,
            "grupoExibidor": grupo or None,
            "exibidor": {
                "nome": c("NOME_EXIBIDOR"),
                "registro": r.get("REGISTRO_EXIBIDOR"),
                "cnpj": c("CNPJ_EXIBIDOR"),
                "situacao": c("SITUACAO_EXIBIDOR"),
            },
            "complexo": {
                "nome": c("NOME_COMPLEXO"),
                "registro": r.get("REGISTRO_COMPLEXO"),
                "situacao": c("SITUACAO_COMPLEXO"),
                "dataSituacao": d("DATA_SITUACAO_COMPLEXO"),
                "site": c("PAGINA_ELETRONICA_COMPLEXO"),
                "endereco": c("ENDERECO_COMPLEXO"),
                "numero": c("NUMERO_ENDERECO_COMPLEXO"),
                "complemento": c("COMPLEMENTO_COMPLEXO"),
                "bairro": c("BAIRRO_COMPLEXO"),
                "municipio": c("MUNICIPIO_COMPLEXO"),
                "uf": c("UF_COMPLEXO"),
                "cep": c("CEP_COMPLEXO"),
                "itinerante": c("COMPLEXO_ITINERANTE"),
                "operacaoUsual": c("OPERACAO_USUAL"),
            },
            "sala": {
                "nome": c("NOME_SALA"),
                "registro": r.get("REGISTRO_SALA"),
                "cnpj": c("CNPJ_SALA"),
                "situacao": c("SITUACAO_SALA"),
                "dataSituacao": d("DATA_SITUACAO_SALA"),
                "inicioFuncionamento": d("DATA_INICIO_FUNCIONAMENTO_SALA"),
            },
            "assentos": {
                "total": r.get("ASSENTOS_SALA"),
                "cadeirantes": r.get("ASSENTOS_CADEIRANTES"),
                "mobilidadeReduzida": r.get("ASSENTOS_MOBILIDADE_REDUZIDA"),
                "obesidade": r.get("ASSENTOS_OBESIDADE"),
                "acessoAssentosRampa": c("ACESSO_ASSENTOS_COM_RAMPA"),
                "acessoSalaRampa": c("ACESSO_SALA_COM_RAMPA"),
                "banheirosAcessiveis": c("BANHEIROS_ACESSIVEIS"),
            },
        }
    except duckdb.CatalogException:
        return {"found": False}
    finally:
        con.close()


# Protect pages and APIs; expose only public frontend directories.
install_auth(app)


@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
def dashboard_page():
    return FileResponse(ROOT / "index.html")


for directory in ("css", "js", "static"):
    app.mount(f"/{directory}", StaticFiles(directory=ROOT / directory), name=directory)
