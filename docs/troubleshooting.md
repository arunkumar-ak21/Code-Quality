# Troubleshooting Guide

## Common Issues

### Installation

| Issue | Solution |
|-------|----------|
| `semgrep` fails to install on Windows | Semgrep requires Linux/macOS. Use `pip install -e ".[scanners]"` (without semgrep) or install via WSL. |
| `cq-pipeline: command not found` | Activate your virtual environment: `source .venv/bin/activate` |
| `pip install` fails | Ensure Python 3.11+: `python --version`. Upgrade pip: `python -m pip install --upgrade pip` |

### Scanner Issues

| Issue | Solution |
|-------|----------|
| `gitleaks: command not found` | Install Gitleaks: `scoop install gitleaks` (Windows) or download from GitHub releases |
| Scanner times out | Increase timeout in `config/pipeline.yaml`: `scanners.<name>.timeout: 120` |
| Too many false positives | Add entries to `config/allowlist.yaml` with justification |
| Scanner crashes pipeline | Set `pipeline.fail_on_scanner_error: false` to skip failed scanners |

### Git Hooks

| Issue | Solution |
|-------|----------|
| Hook not executing | Check `.git/hooks/pre-commit` exists and is executable |
| Permission denied | `chmod +x .git/hooks/pre-commit` (Unix) |
| Want to skip temporarily | `git commit --no-verify` (use sparingly!) |
| Hooks slow | Reduce enabled scanners or increase `parallel_workers` |

### Docker

| Issue | Solution |
|-------|----------|
| `docker build` fails | Ensure Docker Desktop is running |
| Database connection refused | Check PostgreSQL container: `docker compose ps` |
| SonarQube won't start | Increase Docker memory: SonarQube needs 2GB+ RAM |

---

## Debug Mode

Run with maximum verbosity:
```bash
cq-pipeline scan --all --log-level DEBUG 2>debug.log
```

Check individual scanner availability:
```bash
python -c "from cqpipeline.utils.process import check_tool_available; print({t: check_tool_available(t) for t in ['gitleaks', 'bandit', 'ruff', 'black', 'pylint', 'radon', 'mypy', 'pip-audit', 'safety', 'detect-secrets', 'semgrep']})"
```

---

## Windows-Specific Issues

1. **Semgrep**: Not supported on Windows natively. Install via WSL2 or use Docker.
2. **Bash scripts**: Use Git Bash, WSL, or convert to PowerShell.
3. **File permissions**: Git hooks may need `git update-index --chmod=+x` for bash scripts.
4. **Path separators**: The pipeline handles both `/` and `\` automatically.

### Using WSL for Semgrep
```bash
# In WSL (Ubuntu)
pip install semgrep
wsl semgrep scan --config auto --json .
```

### Using Docker for Full Scanning
```bash
# Build once
docker build -f docker/Dockerfile -t cq-pipeline:latest .

# Scan any project
docker run --rm -v "$(pwd):/workspace" -w /workspace cq-pipeline:latest scan --all
```

---

## Performance Tuning

| Setting | Default | Tuning |
|---------|---------|--------|
| `parallel_workers` | 4 | Increase for more CPU cores |
| Scanner timeouts | 30-60s | Reduce for faster pre-commit |
| TruffleHog | disabled | Enable only in CI/CD (scans full history) |
| Type checking | disabled | Enable in CI/CD only |
| `scan_mode` | staged | Use `staged` for pre-commit, `all` for CI |

### Recommended Settings by Context

**Pre-commit (fast, < 10s):**
```yaml
scanners:
  secrets: { enabled: true, timeout: 10 }
  files: { enabled: true, timeout: 5 }
  linting: { enabled: true, timeout: 15, tools: { ruff: { enabled: true }, black: { enabled: true }, pylint: { enabled: false } } }
  sast: { enabled: false }
  dependencies: { enabled: false }
  quality: { enabled: false }
  type_checking: { enabled: false }
```

**CI/CD (thorough, < 5min):**
```yaml
scanners:
  secrets: { enabled: true, timeout: 30, tools: { trufflehog: { enabled: true } } }
  linting: { enabled: true, timeout: 60 }
  sast: { enabled: true, timeout: 120 }
  dependencies: { enabled: true, timeout: 60 }
  quality: { enabled: true }
  files: { enabled: true }
  type_checking: { enabled: true, timeout: 120 }
```
