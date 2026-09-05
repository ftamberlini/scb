-- DDL gerada a partir de data/ancine/cpb.parquet (62,897 linhas)
CREATE TABLE cpb (
    "TITULO_ORIGINAL"             VARCHAR,
    "CPB"                         VARCHAR,
    "DATA_EMISSAO_CPB"            DATE,
    "SITUACAO_OBRA"               VARCHAR,
    "TIPO_OBRA"                   VARCHAR,
    "SUBTIPO_OBRA"                VARCHAR,
    "CLASSIFICACAO_OBRA"          VARCHAR,
    "ORGANIZACAO_TEMPORAL"        VARCHAR,
    "DURACAO_TOTAL_MINUTOS"       DOUBLE,
    "QUANTIDADE_EPISODIOS"        BIGINT,
    "ANO_PRODUCAO_INICIAL"        BIGINT,
    "ANO_PRODUCAO_FINAL"          BIGINT,
    "SEGMENTO_DESTINACAO_INICIAL" VARCHAR,
    "COPRODUCAO_INTERNACIONAL"    VARCHAR,
    "REQUERENTE"                  VARCHAR,
    "CNPJ_REQUERENTE"             VARCHAR,
    "UF_REQUERENTE"               VARCHAR,
    "MUNICIPIO_REQUERENTE"        VARCHAR
);
