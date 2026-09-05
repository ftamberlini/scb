# Bilheteria BR — Cinema no Brasil

Painel web para explorar dados de bilheteria do cinema brasileiro (fonte ANCINE), com filtros por filme, diretor, produtor, requerente, sala de exibição e país, além de um assistente de busca com IA que responde perguntas em linguagem natural sobre os dados.

## O que o app faz

- Exibe estatísticas de público, dias de exibição e outros indicadores de bilheteria.
- Permite navegar os dados por diferentes recortes (filmes, diretores, produtores, salas de exibição, países).
- Oferece um chat com IA que converte perguntas em linguagem natural em consultas SQL (NL2SQL) sobre a base de dados.
- Suporta modo claro/escuro.

## Como funciona

- **Frontend**: HTML/CSS/JS estático (`index.html`, `css/`, `js/`), sem framework.
- **Backend**: API em FastAPI (`app/server.py`) que consulta arquivos Parquet via DuckDB (sem banco de dados externo em produção).
- **Dados**: arquivos Parquet em `data/ancine` (bilheteria ANCINE) e `data/imdb` (metadados de filmes).
- **Chat com IA**: módulo `app/chat/` usa provedores configuráveis para converter perguntas em SQL e responder com base nos resultados.

## Rodando localmente

```bash
uv sync
uv run uvicorn app.server:app --reload
```

Acesse `http://localhost:8000`.

Os arquivos Parquet grandes não são versionados. Consulte
[`data/README.md`](data/README.md) para preparar os dados ou configurar
`ANCINE_DATA_DIR` e `DATA_DIR`.

## Qualidade

```bash
uv run ruff check app tests
uv run pytest
```

O GitHub Actions executa lint, testes e um build Docker em cada push e pull
request. O código interno usa nomes em inglês; nomes de campos e rotas da API
em português são preservados por compatibilidade com a interface e com o
vocabulário oficial da ANCINE.

## Configuração operacional

Copie `.env.example` para `.env` e configure apenas os provedores de IA que
serão oferecidos. Modelos sem credencial não aparecem no seletor. Os limites
de concorrência, timeout, cache e rate limit também podem ser ajustados nesse
arquivo.

- `/health/live`: processo ativo.
- `/health/ready`: dados carregados e aplicação pronta.
- `/health`: alias compatível da verificação de prontidão.
- `/metrics`: estado, contadores, latência média e tamanho do cache.

Os filtros e a aba ativa são gravados na URL, permitindo compartilhar uma
análise. As tabelas e resultados do chat oferecem exportação CSV. D3,
TopoJSON e o mapa mundial são servidos localmente com versões fixas.

## Deploy

O projeto inclui um `Dockerfile` e scripts em `deploy/` para publicar a aplicação em um servidor/contêiner.
