# Development Guide

## Setting Up the Development Environment

### 1. Clone and Install
```bash
git clone <repo-url>
cd Code-Quality

python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows

pip install -e ".[all]"
```

### 2. Verify Installation
```bash
cq-pipeline --version
cq-pipeline scan --help
```

---

## Project Structure

```
src/cqpipeline/
├── core/           # Engine: orchestrator, config, models, constants
├── scanners/       # Pluggable scanner modules (one per tool category)
├── gates/          # Quality gate evaluation and policies
├── reporters/      # Output generators (terminal, JSON, HTML)
├── git/            # Git integration (hooks, utils)
└── utils/          # Shared utilities (logging, subprocess, files)
```

---

## Adding a New Scanner

1. Create `src/cqpipeline/scanners/my_scanner.py`:

```python
from cqpipeline.scanners.base import BaseScanner
from cqpipeline.core.constants import ScannerCategory
from cqpipeline.core.models import Finding, ScanResult

class MyScanner(BaseScanner):
    @property
    def name(self) -> str:
        return "my_scanner"

    @property
    def category(self) -> ScannerCategory:
        return ScannerCategory.SAST

    @property
    def required_tools(self) -> list[str]:
        return ["my-tool"]  # External tool needed

    async def _execute(self, files: list[Path]) -> ScanResult:
        result = await run_process(
            ["my-tool", "--json"] + [str(f) for f in files],
            cwd=self.project_root,
            timeout=self.config.get("timeout", 60),
            scanner_name="my-tool",
        )
        findings = self._parse_output(result.stdout)
        return ScanResult(
            scanner_name=self.name,
            category=self.category,
            success=True,
            findings=findings,
        )
```

2. Register in `src/cqpipeline/core/orchestrator.py`:
```python
SCANNER_REGISTRY["my_scanner"] = MyScanner
```

3. Add config in `config/pipeline.yaml`:
```yaml
scanners:
  my_scanner:
    enabled: true
    timeout: 30
```

4. Write tests in `tests/test_scanners/test_my_scanner.py`

---

## Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=src/cqpipeline --cov-report=term-missing

# Specific test file
pytest tests/test_scanners/test_file_scanner.py -v

# Skip slow tests
pytest tests/ -v -m "not slow"
```

---

## Code Quality on the Pipeline Itself

We eat our own dogfood:

```bash
# Lint the project
ruff check src/ tests/
black --check src/ tests/

# Type check
mypy src/cqpipeline/

# Run bandit on ourselves
bandit -r src/ -f json

# Full pipeline scan
cq-pipeline scan --all
```

---

## API Development

```bash
# Start dev server with hot reload
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# View API docs
open http://localhost:8000/docs

# Test the health endpoint
curl http://localhost:8000/api/v1/metrics/health
```

### Database Migrations (if using PostgreSQL)
```bash
# Initialize Alembic (first time)
alembic init api/migrations

# Create a migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

---

## Debugging

### Increase Log Verbosity
```bash
cq-pipeline scan --all --log-level DEBUG
```

### Run a Single Scanner
```python
import asyncio
from pathlib import Path
from cqpipeline.scanners.file_scanner import FileScanner

scanner = FileScanner(
    config={"enabled": True, "timeout": 10},
    project_root=Path("."),
)
result = asyncio.run(scanner.scan([Path("my_file.py")]))
for f in result.findings:
    print(f"{f.severity.value}: {f.message}")
```

### Check Tool Availability
```python
from cqpipeline.utils.process import check_tool_available
print(check_tool_available("gitleaks"))  # True/False
print(check_tool_available("bandit"))
print(check_tool_available("ruff"))
```
