# Phase 4 — flesh out as needed (e.g. multi-stage build, non-root user).
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY config ./config

RUN pip install --no-cache-dir -e .

EXPOSE 8000
CMD ["uvicorn", "forecaster.serving.app:app", "--host", "0.0.0.0", "--port", "8000"]
