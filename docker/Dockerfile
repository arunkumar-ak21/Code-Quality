# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ src/
COPY config/ config/

RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir ".[scanners-linux]"

ENTRYPOINT ["cq-pipeline"]
CMD ["scan", "--all", "--format", "all"]
