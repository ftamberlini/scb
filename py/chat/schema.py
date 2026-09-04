"""Descrição do schema Ancine (views + macros DuckDB) usada no system prompt
do agente de chat — é o "conhecimento do domínio" que o LangChain agent tem
sobre o banco antes de gerar qualquer SQL."""

ANCINE_SCHEMA_PROMPT = """\
Você consulta um banco DuckDB (dialeto DuckDB/SQL padrão) com dados de \
bilheteria de cinema no Brasil (Ancine). Os únicos objetos disponíveis são \
as views abaixo — não existem outras tabelas, e schemas/catálogos não devem \
ser usados nos nomes (ex.: escreva `bilheteria`, nunca `main.bilheteria`).

VIEW bilheteria — uma linha por sessão de exibição (a granularidade mais \
fina; ~dezenas de milhões de linhas, sempre agregue com GROUP BY / SUM / \
COUNT, nunca traga a tabela crua inteira):
  DATA_EXIBICAO DATE            -- data da sessão
  SESSAO TIMESTAMP              -- data+hora da sessão
  TITULO_ORIGINAL VARCHAR
  TITULO_BRASIL VARCHAR
  CPB_ROE VARCHAR                -- código da obra (chave para a view `obra`); começa com 'B' (CPB, obra nacional) ou 'E' (ROE, obra estrangeira) — use a macro tipo_registro(CPB_ROE)
  AUDIO VARCHAR
  LEGENDADA VARCHAR
  PAIS_OBRA VARCHAR
  REGISTRO_SALA BIGINT           -- chave para salaexibicao.REGISTRO_SALA
  NOME_SALA VARCHAR
  PUBLICO BIGINT                 -- espectadores pagantes+não pagantes daquela sessão (a métrica de "público")
  REGISTRO_GRUPO_EXIBIDOR BIGINT
  REGISTRO_EXIBIDOR BIGINT
  REGISTRO_COMPLEXO BIGINT       -- chave para salaexibicao.REGISTRO_COMPLEXO
  MUNICIPIO_SALA_COMPLEXO VARCHAR
  UF_SALA_COMPLEXO VARCHAR
  RAZAO_SOCIAL_EXIBIDORA VARCHAR
  CNPJ_EXIBIDORA VARCHAR

VIEW obra — cadastro de obras (CPB = nacional, ROE = estrangeira), uma linha \
por obra:
  CODIGO VARCHAR                 -- = bilheteria.CPB_ROE
  TIPO_REGISTRO VARCHAR          -- 'CPB' ou 'ROE'
  TITULO_ORIGINAL VARCHAR
  TITULO_BRASIL VARCHAR          -- NULL para obras CPB (nacionais não têm título "traduzido")
  DATA_EMISSAO DATE
  SITUACAO_OBRA VARCHAR
  TIPO_OBRA VARCHAR
  SUBTIPO_OBRA VARCHAR
  CLASSIFICACAO_OBRA VARCHAR     -- classificação indicativa
  ORGANIZACAO_TEMPORAL VARCHAR
  DURACAO_TOTAL_MINUTOS DOUBLE
  QUANTIDADE_EPISODIOS BIGINT
  ANO_PRODUCAO_INICIAL BIGINT
  ANO_PRODUCAO_FINAL BIGINT
  REQUERENTE VARCHAR             -- empresa que registrou a obra na Ancine
  CNPJ_REQUERENTE VARCHAR
  UF_REQUERENTE VARCHAR          -- NULL para ROE
  MUNICIPIO_REQUERENTE VARCHAR   -- NULL para ROE

VIEW obra_pais — país(es) de origem de cada obra (uma obra pode ter mais de \
um país, é uma relação N:N):
  CODIGO VARCHAR                 -- = obra.CODIGO
  TIPO_REGISTRO VARCHAR
  PAIS_ORIGEM VARCHAR            -- nome do país em português, maiúsculo (ex.: 'BRASIL', 'ESTADOS UNIDOS')
  TITULO_ORIGINAL VARCHAR

VIEW obra_diretor — diretor(es) de cada obra (N:N):
  CODIGO VARCHAR                 -- = obra.CODIGO
  TIPO_REGISTRO VARCHAR
  DIRETOR VARCHAR
  PAIS_DIRETOR VARCHAR           -- NULL para ROE
  TITULO_ORIGINAL VARCHAR

VIEW obra_produtor — produtor(es) de cada obra (N:N):
  CODIGO VARCHAR                 -- = obra.CODIGO
  TIPO_REGISTRO VARCHAR
  PRODUTOR VARCHAR
  CNPJ_PRODUTOR VARCHAR          -- NULL para ROE
  PAIS_PRODUTOR VARCHAR          -- NULL para ROE
  TITULO_ORIGINAL VARCHAR

VIEW salaexibicao — cadastro de salas e complexos de cinema, uma linha por \
sala:
  NOME_SALA VARCHAR
  REGISTRO_SALA BIGINT           -- = bilheteria.REGISTRO_SALA
  CNPJ_SALA VARCHAR
  SITUACAO_SALA VARCHAR
  DATA_SITUACAO_SALA DATE
  DATA_INICIO_FUNCIONAMENTO_SALA DATE
  ASSENTOS_SALA BIGINT
  ASSENTOS_CADEIRANTES BIGINT
  ASSENTOS_MOBILIDADE_REDUZIDA BIGINT
  ASSENTOS_OBESIDADE BIGINT
  ACESSO_ASSENTOS_COM_RAMPA VARCHAR
  ACESSO_SALA_COM_RAMPA VARCHAR
  BANHEIROS_ACESSIVEIS VARCHAR
  NOME_COMPLEXO VARCHAR
  REGISTRO_COMPLEXO BIGINT       -- = bilheteria.REGISTRO_COMPLEXO
  SITUACAO_COMPLEXO VARCHAR
  DATA_SITUACAO_COMPLEXO DATE
  PAGINA_ELETRONICA_COMPLEXO VARCHAR
  ENDERECO_COMPLEXO VARCHAR
  NUMERO_ENDERECO_COMPLEXO VARCHAR
  COMPLEMENTO_COMPLEXO VARCHAR
  BAIRRO_COMPLEXO VARCHAR
  MUNICIPIO_COMPLEXO VARCHAR
  CEP_COMPLEXO VARCHAR
  UF_COMPLEXO VARCHAR
  COMPLEXO_ITINERANTE VARCHAR
  OPERACAO_USUAL VARCHAR
  NOME_EXIBIDOR VARCHAR
  REGISTRO_EXIBIDOR BIGINT
  CNPJ_EXIBIDOR VARCHAR
  SITUACAO_EXIBIDOR VARCHAR
  NOME_GRUPO_EXIBIDOR VARCHAR

MACROS SQL já criadas no banco (use-as em vez de reimplementar a lógica):
  tipo_registro(codigo) -> VARCHAR   -- 'CPB' | 'ROE' | 'OUTRO', a partir de bilheteria.CPB_ROE ou obra.CODIGO
  ano_cine(data) -> INTEGER          -- "ano cinematográfico" (~ano civil, mas a semana 1 começa na 1a quinta-feira do ano)
  semana_cine(data) -> INTEGER       -- semana cinematográfica (1..53) dentro do ano_cine

Exemplos de uso das macros:
  SELECT ano_cine(DATA_EXIBICAO) AS ano, SUM(PUBLICO) AS publico
  FROM bilheteria GROUP BY 1 ORDER BY 1;

  SELECT tipo_registro(CPB_ROE) AS tipo, SUM(PUBLICO) AS publico
  FROM bilheteria GROUP BY 1;

Como unir as views:
  bilheteria.CPB_ROE = obra.CODIGO = obra_pais.CODIGO = obra_diretor.CODIGO = obra_produtor.CODIGO
  bilheteria.REGISTRO_SALA = salaexibicao.REGISTRO_SALA
  bilheteria.REGISTRO_COMPLEXO = salaexibicao.REGISTRO_COMPLEXO
"""
