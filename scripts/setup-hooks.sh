#!/usr/bin/env bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CQ Pipeline — Git Hooks Installer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Usage: bash scripts/setup-hooks.sh
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -euo pipefail

echo "🛡️  Installing CQ Pipeline git hooks..."

# Check if in git repo
if [ ! -d ".git" ]; then
    echo "❌ Not a git repository. Run 'git init' first."
    exit 1
fi

# Use Python hook installer
if command -v cq-pipeline &> /dev/null; then
    cq-pipeline install-hooks
elif command -v python &> /dev/null; then
    python -m cqpipeline install-hooks
elif command -v python3 &> /dev/null; then
    python3 -m cqpipeline install-hooks
else
    echo "❌ Python not found. Install Python 3.11+ first."
    exit 1
fi

echo ""
echo "✅ Git hooks installed!"
echo "   Pre-commit: runs on 'git commit'"
echo "   Pre-push:   runs on 'git push'"
echo ""
echo "   To bypass:  git commit --no-verify"
echo ""
