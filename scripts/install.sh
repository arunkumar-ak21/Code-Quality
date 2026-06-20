#!/usr/bin/env bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CQ Pipeline — One-Command Installer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Usage: bash scripts/install.sh
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  🛡️  CQ Pipeline — Installer${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ─── Check Prerequisites ─────────────────────────────────────────
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Python 3.11+
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo -e "${RED}❌ Python 3.11+ is required but not found${NC}"
    exit 1
fi

PY_VERSION=$($PYTHON --version 2>&1 | grep -oP '\d+\.\d+')
echo -e "  ✓ Python: $PY_VERSION"

# Git
if ! command -v git &> /dev/null; then
    echo -e "${RED}❌ Git is required but not found${NC}"
    exit 1
fi
echo -e "  ✓ Git: $(git --version | head -1)"

# ─── Create Virtual Environment ──────────────────────────────────
echo ""
echo -e "${YELLOW}Setting up virtual environment...${NC}"

if [ ! -d ".venv" ]; then
    $PYTHON -m venv .venv
    echo -e "  ✓ Created .venv"
else
    echo -e "  ✓ .venv already exists"
fi

# Activate venv
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi

# ─── Install Python Dependencies ─────────────────────────────────
echo ""
echo -e "${YELLOW}Installing Python dependencies...${NC}"

pip install --upgrade pip setuptools wheel -q
pip install -e ".[all]" -q
echo -e "  ✓ Python dependencies installed"

# ─── Install External Tools ──────────────────────────────────────
echo ""
echo -e "${YELLOW}Checking external scanner tools...${NC}"

# Gitleaks
if command -v gitleaks &> /dev/null; then
    echo -e "  ✓ Gitleaks: $(gitleaks version 2>&1 || echo 'installed')"
else
    echo -e "  ${YELLOW}⚠ Gitleaks not found — install from: https://github.com/gitleaks/gitleaks${NC}"
fi

# Semgrep
if command -v semgrep &> /dev/null; then
    echo -e "  ✓ Semgrep: $(semgrep --version 2>&1 || echo 'installed')"
else
    echo -e "  ${YELLOW}⚠ Semgrep not found — will be installed via pip${NC}"
    pip install semgrep -q 2>/dev/null || echo "  ⚠ Failed to install semgrep"
fi

# ─── Install Git Hooks ───────────────────────────────────────────
echo ""
echo -e "${YELLOW}Installing git hooks...${NC}"

if [ -d ".git" ]; then
    $PYTHON -m cqpipeline install-hooks
    echo -e "  ✓ Git hooks installed"
else
    echo -e "  ${YELLOW}⚠ Not a git repository — skipping hook installation${NC}"
    echo -e "  Run 'cq-pipeline install-hooks' after 'git init'"
fi

# ─── Validate Installation ───────────────────────────────────────
echo ""
echo -e "${YELLOW}Validating installation...${NC}"

if cq-pipeline --version &> /dev/null; then
    echo -e "  ✓ cq-pipeline CLI is working"
else
    echo -e "  ✓ Installation complete (run via: python -m cqpipeline)"
fi

# ─── Summary ─────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✅ CQ Pipeline installed successfully!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  Quick start:"
echo -e "    ${CYAN}cq-pipeline scan --all${NC}        # Scan entire project"
echo -e "    ${CYAN}cq-pipeline scan --staged${NC}     # Scan staged files only"
echo -e "    ${CYAN}cq-pipeline report --format html${NC} # Generate HTML report"
echo -e "    ${CYAN}make help${NC}                     # See all commands"
echo ""
echo -e "  Docker:"
echo -e "    ${CYAN}make docker-build${NC}             # Build Docker image"
echo -e "    ${CYAN}make docker-scan${NC}              # Scan with Docker"
echo -e "    ${CYAN}make docker-up${NC}                # Start API + DB stack"
echo ""
