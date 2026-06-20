.PHONY: help install install-all install-hooks scan scan-staged scan-all test lint format docker-build docker-scan api clean

# ─── Variables ───────────────────────────────────────────────────────
PYTHON := python
PIP := pip
DOCKER := docker
COMPOSE := docker compose

# ─── Help ────────────────────────────────────────────────────────────
help: ## Show this help message
	@echo "Enterprise DevSecOps Pipeline - Available Commands"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Installation ────────────────────────────────────────────────────
install: ## Install pipeline (core only)
	$(PIP) install -e .

install-all: ## Install pipeline with all extras (scanners + api + dev)
	$(PIP) install -e ".[all]"

install-hooks: ## Install git hooks into current repository
	$(PYTHON) -m cqpipeline install-hooks

# ─── Scanning ────────────────────────────────────────────────────────
scan: ## Run pipeline scan on staged files (default)
	$(PYTHON) -m cqpipeline scan --staged

scan-staged: ## Run pipeline scan on staged files
	$(PYTHON) -m cqpipeline scan --staged

scan-all: ## Run pipeline scan on entire project
	$(PYTHON) -m cqpipeline scan --all

scan-files: ## Run pipeline scan on specific files (FILES="a.py b.py")
	$(PYTHON) -m cqpipeline scan --files $(FILES)

# ─── Code Quality ────────────────────────────────────────────────────
lint: ## Run linters on project source
	ruff check src/ tests/
	black --check src/ tests/

format: ## Auto-format source code
	ruff check --fix src/ tests/
	black src/ tests/

typecheck: ## Run mypy type checking
	mypy src/cqpipeline/

# ─── Testing ─────────────────────────────────────────────────────────
test: ## Run test suite
	pytest tests/ -v --tb=short

test-cov: ## Run tests with coverage report
	pytest tests/ -v --cov=src/cqpipeline --cov-report=term-missing --cov-report=html

test-integration: ## Run integration tests
	pytest tests/ -v -m integration

# ─── Docker ──────────────────────────────────────────────────────────
docker-build: ## Build pipeline Docker image
	$(DOCKER) build -f docker/Dockerfile -t cq-pipeline:latest .

docker-scan: ## Run scan using Docker container
	$(DOCKER) run --rm -v "$$(pwd):/workspace" cq-pipeline:latest scan --all

docker-up: ## Start full stack (API + DB + SonarQube)
	$(COMPOSE) -f docker/docker-compose.yaml up -d

docker-down: ## Stop full stack
	$(COMPOSE) -f docker/docker-compose.yaml down

# ─── API ─────────────────────────────────────────────────────────────
api: ## Start FastAPI development server
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

api-prod: ## Start FastAPI production server
	gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# ─── Reports ─────────────────────────────────────────────────────────
report: ## Generate HTML report from latest scan
	$(PYTHON) -m cqpipeline report --format html

report-json: ## Generate JSON report from latest scan
	$(PYTHON) -m cqpipeline report --format json

# ─── Cleanup ─────────────────────────────────────────────────────────
clean: ## Remove build artifacts and caches
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache
	rm -rf htmlcov/ .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
