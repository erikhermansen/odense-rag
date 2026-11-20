# Trin 1: byg Vue-frontenden.
FROM node:22-slim AS frontend
WORKDIR /frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend ./
RUN pnpm build

# Trin 2: Python-API'et, som også serverer den byggede frontend.
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1 PYDANTIC_AI_NO_BANNER=1

# Kør som non-root-bruger.
RUN useradd --create-home --uid 1000 app
WORKDIR /app
RUN chown app:app /app
USER app

# Afhængigheder i et separat lag, så de kun geninstalleres, når lockfilen ændres.
COPY --chown=app:app pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project

COPY --chown=app:app src ./src
COPY --chown=app:app data ./data
COPY --chown=app:app --from=frontend /frontend/dist ./frontend/dist
RUN uv sync --locked

# Hent embedding-modellen ved build, så containeren starter uden netværkskald til Hugging Face.
RUN uv run python -c "from odense_rag.config import get_settings; from odense_rag.ingest.embed import get_embedder; get_embedder(get_settings().embed_model)"

EXPOSE 8000
# Bygger indekset ved opstart (få sekunder for dette korpus) og starter API'et.
CMD ["sh", "-c", "uv run odense-rag ingest && uv run uvicorn odense_rag.api:app --host 0.0.0.0 --port 8000"]
