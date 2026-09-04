FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Instala dependências (sem copiar o código ainda → melhor cache de layers)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copia os arquivos da aplicação
COPY py/ ./py/
COPY index.html ./
COPY js/ ./js/
COPY css/ ./css/

# Dados Parquet — lidos pelo DuckDB em runtime
COPY data/ ./data/

EXPOSE 8080

CMD ["/app/.venv/bin/uvicorn", "py.server:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
