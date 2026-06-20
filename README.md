# 🛡️ CQ Pipeline — Enterprise DevSecOps Quality Gate

**Enterprise-grade automated pre-commit security & code quality pipeline system.**

CQ Pipeline acts as the **first gate** in your CI/CD pipeline — automatically scanning code for security vulnerabilities, leaked secrets, linting issues, and code quality problems **before commits reach your repository**.

---

## 🏗️ Architecture

```
Developer writes code
         ↓
   git commit / push
         ↓
┌─────────────────────────┐
│   CQ Pipeline Engine    │
│                         │
│  ┌─────────────────┐    │
│  │ Secret Scanner  │    │  Gitleaks + detect-secrets + TruffleHog
│  │ Lint Scanner    │    │  Ruff + Black + Pylint
│  │ SAST Scanner    │    │  Semgrep + Bandit
│  │ Dep Scanner     │    │  pip-audit + Safety
│  │ Quality Scanner │    │  Radon + AST analysis
│  │ File Scanner    │    │  .env, large files, debug stmts
│  │ Type Checker    │    │  MyPy
│  └─────────────────┘    │
│           ↓              │
│  ┌─────────────────┐    │
│  │ Quality Gates   │    │  Configurable thresholds
│  └─────────────────┘    │
│           ↓              │
│  ┌─────────────────┐    │
│  │ Report Engine   │    │  Terminal + JSON + HTML
│  └─────────────────┘    │
└─────────────────────────┘
         ↓
  ✅ Allow  or  ❌ Block
```

## ⚡ Quick Start

### 1. Install
```bash
# Clone and install
git clone <your-repo-url>
cd Code-Quality

# One-command install
bash scripts/install.sh

# Or manual install
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[all]"
```

### 2. Install Git Hooks
```bash
cq-pipeline install-hooks
```

### 3. Scan
```bash
# Scan staged files (pre-commit mode)
cq-pipeline scan --staged

# Scan entire project
cq-pipeline scan --all

# Generate HTML report
cq-pipeline scan --all --format html
```

### 4. That's it!
Now every `git commit` will automatically run security and quality checks. If critical issues are found, the commit is **blocked**.

---

## 📋 Features

| Feature | Tools | Description |
|---------|-------|-------------|
| 🔐 Secret Detection | Gitleaks, detect-secrets, TruffleHog | AWS keys, API tokens, passwords, private keys |
| 📝 Linting | Ruff, Black, Pylint | Code style, formatting, deep analysis |
| 🛡️ SAST | Semgrep, Bandit | SQL injection, command injection, eval(), exec() |
| 📦 Dependencies | pip-audit, Safety | CVE scanning, vulnerable packages |
| 📊 Code Quality | Radon, AST analysis | Cyclomatic complexity, function length |
| 📁 File Checks | Built-in | .env files, large files, debug statements |
| ✅ Type Checking | MyPy | Static type analysis |

## 🔧 Configuration

All configuration lives in `config/`:

| File | Purpose |
|------|---------|
| `config/pipeline.yaml` | Main pipeline config (scanners, timeouts, parallelism) |
| `config/quality-gates.yaml` | Pass/fail thresholds |
| `config/secret-patterns.yaml` | Custom regex patterns for secret detection |
| `config/allowlist.yaml` | False positive suppressions |
| `config/language-profiles/` | Per-language scanner configs |

### Environment Variable Overrides

Any config can be overridden via `CQ_` prefixed environment variables:

```bash
# Override pipeline timeout
export CQ_PIPELINE__TIMEOUT=300

# Disable a scanner
export CQ_SCANNERS__LINTING__ENABLED=false
```

## 🐳 Docker

```bash
# Build the scanner image
make docker-build

# Run a scan via Docker
make docker-scan

# Start the full stack (API + PostgreSQL + SonarQube)
make docker-up

# Start with SonarQube
docker compose -f docker/docker-compose.yaml --profile sonarqube up -d
```

## 🔄 CI/CD Integration

### GitHub Actions
The `.github/workflows/security-scan.yaml` workflow:
- Runs on every PR to main/develop
- Posts scan summary as a PR comment
- Blocks merge on critical/high findings
- Uploads JSON/HTML reports as artifacts

### GitLab CI
The `.gitlab-ci.yml` pipeline:
- Runs secret scan, pipeline scan, and dependency audit
- Generates reports as CI artifacts

## 📊 FastAPI Dashboard

```bash
# Start the API
make api

# Or with Docker
make docker-up

# API docs
open http://localhost:8000/docs
```

### API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/scans` | Submit scan results |
| GET | `/api/v1/scans` | List scans (paginated) |
| GET | `/api/v1/scans/{id}` | Get scan details + findings |
| GET | `/api/v1/metrics/summary` | Security posture summary |
| GET | `/api/v1/metrics/health` | Health check |

## 🧪 Testing

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test
pytest tests/test_scanners/test_file_scanner.py -v
```

## 📁 Project Structure

```
Code-Quality/
├── config/                 # Configuration files
├── src/cqpipeline/         # Main Python package
│   ├── core/               # Engine, config, models
│   ├── scanners/           # Scanner modules (pluggable)
│   ├── gates/              # Quality gate evaluation
│   ├── reporters/          # Report generators
│   ├── git/                # Git hook management
│   └── utils/              # Logging, subprocess, file ops
├── api/                    # FastAPI dashboard backend
├── docker/                 # Docker infrastructure
├── scripts/                # Automation scripts
├── tests/                  # Test suite
├── .github/workflows/      # GitHub Actions
└── .gitlab-ci.yml          # GitLab CI
```

## 🔌 Extending

### Add a Custom Scanner

1. Create a new file in `src/cqpipeline/scanners/`
2. Implement the `BaseScanner` interface:

```python
from cqpipeline.scanners.base import BaseScanner
from cqpipeline.core.constants import ScannerCategory
from cqpipeline.core.models import ScanResult

class MyScanner(BaseScanner):
    @property
    def name(self) -> str:
        return "my_scanner"

    @property
    def category(self) -> ScannerCategory:
        return ScannerCategory.SAST

    async def _execute(self, files: list[Path]) -> ScanResult:
        # Your scanning logic here
        ...
```

3. Register it in `src/cqpipeline/core/orchestrator.py`:
```python
SCANNER_REGISTRY["my_scanner"] = MyScanner
```

4. Add config in `config/pipeline.yaml`:
```yaml
scanners:
  my_scanner:
    enabled: true
    timeout: 30
```

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
