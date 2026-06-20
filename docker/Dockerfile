# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CQ Pipeline — Scanner Docker Image (Multi-Stage Build)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# This image contains all scanning tools for running the pipeline
# in isolated Docker environments (CI/CD or local).
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ─── Stage 1: Builder ────────────────────────────────────────────
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Gitleaks
RUN curl -sSfL https://github.com/gitleaks/gitleaks/releases/download/v8.22.1/gitleaks_8.22.1_linux_x64.tar.gz \
    | tar -xz -C /usr/local/bin/ gitleaks

WORKDIR /build
COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install ".[scanners]"

# ─── Stage 2: Runtime ────────────────────────────────────────────
FROM python:3.11-slim

# Security: run as non-root
RUN groupadd -r cqpipeline && useradd -r -g cqpipeline -m cqpipeline

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local
COPY --from=builder /usr/local/bin/gitleaks /usr/local/bin/gitleaks

# Copy application source
WORKDIR /app
COPY src/ src/
COPY config/ config/

# Install the package
RUN pip install --no-cache-dir -e .

# Switch to non-root user
USER cqpipeline

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -m cqpipeline --help || exit 1

ENTRYPOINT ["cq-pipeline"]
CMD ["scan", "--all"]
