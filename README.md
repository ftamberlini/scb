# Bilheteria BR — Cinema no Brasil

Painel web para explorar dados de bilheteria do cinema brasileiro (fonte ANCINE), com filtros por filme, diretor, produtor, requerente, sala de exibição e país, além de um assistente de busca com IA que responde perguntas em linguagem natural sobre os dados.

## O que o app faz

- Exibe estatísticas de público, dias de exibição e outros indicadores de bilheteria.
- Permite navegar os dados por diferentes recortes (filmes, diretores, produtores, salas de exibição, países).
- Oferece um chat com IA que converte perguntas em linguagem natural em consultas SQL (NL2SQL) sobre a base de dados.
- Suporta modo claro/escuro.

## Como funciona

- **Frontend**: HTML/CSS/JS estático (`index.html`, `css/`, `js/`), sem framework.
- **Backend**: API em FastAPI (`py/server.py`) que consulta arquivos Parquet via DuckDB (sem banco de dados externo em produção).
- **Dados**: arquivos Parquet em `data/ancine` (bilheteria ANCINE) e `data/imdb` (metadados de filmes).
- **Chat com IA**: módulo `py/chat/` usa a API da Anthropic para converter perguntas em SQL e responder com base nos resultados.

## Rodando localmente

```bash
uv sync
uv run uvicorn py.server:app --reload
```

Acesse `http://localhost:8000`.

## Deploy

O projeto inclui um `Dockerfile` e scripts em `deploy/` para publicar a aplicação em um servidor/contêiner.
