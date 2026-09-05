-- DDL gerada a partir de data/ancine/bilheteria_2014.parquet (248 linhas)
CREATE TABLE bilheteria_2014 (
    "DATA_EXIBICAO"           DATE,
    "SESSAO"                  TIMESTAMP,
    "TITULO_ORIGINAL"         VARCHAR,
    "TITULO_BRASIL"           VARCHAR,
    "CPB_ROE"                 VARCHAR,
    "AUDIO"                   VARCHAR,
    "LEGENDADA"               VARCHAR,
    "PAIS_OBRA"               VARCHAR,
    "REGISTRO_SALA"           BIGINT,
    "NOME_SALA"               VARCHAR,
    "PUBLICO"                 BIGINT,
    "REGISTRO_GRUPO_EXIBIDOR" BIGINT,
    "REGISTRO_EXIBIDOR"       BIGINT,
    "REGISTRO_COMPLEXO"       BIGINT,
    "MUNICIPIO_SALA_COMPLEXO" VARCHAR,
    "UF_SALA_COMPLEXO"        VARCHAR,
    "RAZAO_SOCIAL_EXIBIDORA"  VARCHAR,
    "CNPJ_EXIBIDORA"          VARCHAR
);
