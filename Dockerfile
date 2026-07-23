# Phase 4 — flesh out as needed (e.g. multi-stage build, non-root user).
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY config ./config

RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "forecaster.serving.app:app", "--host", "0.0.0.0", "--port", "8000"]
