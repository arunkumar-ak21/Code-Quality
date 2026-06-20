# Installation Guide

## Prerequisites

| Requirement | Version | Check |
|-------------|---------|-------|
| Python | 3.11+ | `python --version` |
| Git | 2.x | `git --version` |
| pip | 23+ | `pip --version` |
| Docker (optional) | 20+ | `docker --version` |

## Quick Install

```bash
# Clone the repository
git clone <your-repo-url>
cd Code-Quality

# Run the installer
bash scripts/install.sh
```

The installer will:
1. ✓ Check prerequisites
2. ✓ Create a Python virtual environment
3. ✓ Install all Python dependencies
4. ✓ Check for external scanner tools
5. ✓ Install git hooks
6. ✓ Validate the installation

## Manual Installation

### Step 1: Virtual Environment
```bash
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### Step 2: Install Python Package
```bash
# Core only (minimal)
pip install -e .

# With scanners (recommended)
pip install -e ".[scanners]"

# With API dashboard
pip install -e ".[api]"

# Everything
pip install -e ".[all]"
```

### Step 3: Install External Tools

#### Gitleaks (Secret Detection)
```bash
# macOS
brew install gitleaks

# Linux
curl -sSfL https://github.com/gitleaks/gitleaks/releases/download/v8.22.1/gitleaks_8.22.1_linux_x64.tar.gz \
  | tar -xz -C /usr/local/bin/

# Windows (via scoop)
scoop install gitleaks

# Verify
gitleaks version
```

#### Semgrep (SAST)
```bash
pip install semgrep
# or
brew install semgrep

# Verify
semgrep --version
```

#### TruffleHog (Git History Scanning — Optional)
```bash
pip install trufflehog

# Verify
trufflehog --version
```

### Step 4: Install Git Hooks
```bash
cq-pipeline install-hooks
```

### Step 5: Verify
```bash
# Check CLI
cq-pipeline --version

# Run a test scan
cq-pipeline scan --all --format terminal
```

## Docker Installation

No Python installation needed — everything runs in Docker:

```bash
# Build the scanner image
docker build -f docker/Dockerfile -t cq-pipeline:latest .

# Run a scan
docker run --rm -v "$(pwd):/workspace" -w /workspace cq-pipeline:latest scan --all

# Start the full stack (API + DB)
docker compose -f docker/docker-compose.yaml up -d
```

## Windows-Specific Notes

1. **Git Bash**: Use Git Bash or WSL2 for running bash scripts
2. **Gitleaks**: Install via `scoop install gitleaks` or download the Windows binary
3. **Semgrep**: Install via `pip install semgrep` (works on Windows)
4. **Docker Desktop**: Required for Docker-based scanning
5. **Pre-commit hooks**: The bash hooks work in Git Bash; for PowerShell, use the `pre-commit` framework instead:
   ```bash
   pip install pre-commit
   pre-commit install
   ```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `cq-pipeline: command not found` | Ensure virtual environment is activated |
| `gitleaks: command not found` | Install Gitleaks or disable in config |
| Scanner timeout | Increase timeout in `config/pipeline.yaml` |
| False positive flood | Add entries to `config/allowlist.yaml` |
| Permission denied on hooks | `chmod +x .git/hooks/pre-commit` |
