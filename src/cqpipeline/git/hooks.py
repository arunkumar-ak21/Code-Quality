"""
Git hook management — install, update, and remove git hooks.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from cqpipeline.git.utils import is_git_repo
from cqpipeline.utils.logger import get_logger

logger = get_logger(__name__)

PRE_COMMIT_HOOK = '''#!/usr/bin/env bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CQ Pipeline — Pre-Commit Hook
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# This hook runs the Code Quality Pipeline on staged files BEFORE
# the commit is created. If any critical issues are found, the
# commit is BLOCKED (exit code 1).
#
# How it works:
# 1. Git calls this script before creating a commit
# 2. This script invokes the CQ Pipeline in --staged mode
# 3. The pipeline scans only staged files for speed
# 4. Exit code 0 = commit allowed, Exit code 1 = commit blocked
#
# To bypass (emergency only): git commit --no-verify
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -euo pipefail

echo ""
echo "🛡️  CQ Pipeline — Pre-Commit Security & Quality Scan"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if cq-pipeline is installed
if command -v cq-pipeline &> /dev/null; then
    cq-pipeline scan --staged
    EXIT_CODE=$?
elif command -v python &> /dev/null; then
    python -m cqpipeline scan --staged
    EXIT_CODE=$?
elif command -v python3 &> /dev/null; then
    python3 -m cqpipeline scan --staged
    EXIT_CODE=$?
else
    echo "⚠️  CQ Pipeline not found — skipping pre-commit checks"
    echo "   Install with: pip install -e ."
    exit 0
fi

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Commit BLOCKED — fix the issues above and try again"
    echo "   To bypass (emergency): git commit --no-verify"
    echo ""
    exit 1
fi

echo "✅ All checks passed — commit allowed"
echo ""
exit 0
'''

PRE_PUSH_HOOK = '''#!/usr/bin/env bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CQ Pipeline — Pre-Push Hook
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Runs deeper scans before pushing, including dependency audit
# and full project scan.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -euo pipefail

echo ""
echo "🛡️  CQ Pipeline — Pre-Push Security Scan"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v cq-pipeline &> /dev/null; then
    cq-pipeline scan --all
    EXIT_CODE=$?
elif command -v python &> /dev/null; then
    python -m cqpipeline scan --all
    EXIT_CODE=$?
elif command -v python3 &> /dev/null; then
    python3 -m cqpipeline scan --all
    EXIT_CODE=$?
else
    echo "⚠️  CQ Pipeline not found — skipping pre-push checks"
    exit 0
fi

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Push BLOCKED — fix the issues above and try again"
    echo "   To bypass (emergency): git push --no-verify"
    echo ""
    exit 1
fi

echo "✅ All checks passed — push allowed"
echo ""
exit 0
'''


def install_hooks(project_root: Path) -> None:
    """
    Install CQ Pipeline git hooks into the repository.

    Creates pre-commit and pre-push hooks in .git/hooks/.
    Backs up existing hooks if present.
    """
    if not is_git_repo(project_root):
        logger.error("Not a git repository: %s", project_root)
        raise RuntimeError(f"Not a git repository: {project_root}")

    hooks_dir = project_root / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    _install_hook(hooks_dir / "pre-commit", PRE_COMMIT_HOOK)
    _install_hook(hooks_dir / "pre-push", PRE_PUSH_HOOK)

    logger.info("Git hooks installed successfully in %s", hooks_dir)


def _install_hook(hook_path: Path, content: str) -> None:
    """Install a single hook, backing up existing if present."""
    if hook_path.exists():
        backup_path = hook_path.with_suffix(".backup")
        hook_path.rename(backup_path)
        logger.info("Backed up existing hook to %s", backup_path)

    hook_path.write_text(content, encoding="utf-8")

    # Make executable (Unix)
    try:
        current_mode = hook_path.stat().st_mode
        hook_path.chmod(current_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass  # Windows doesn't need chmod

    logger.info("Installed hook: %s", hook_path.name)


def remove_hooks(project_root: Path) -> None:
    """Remove CQ Pipeline git hooks."""
    hooks_dir = project_root / ".git" / "hooks"

    for hook_name in ["pre-commit", "pre-push"]:
        hook_path = hooks_dir / hook_name
        if hook_path.exists():
            # Check if it's our hook
            content = hook_path.read_text(encoding="utf-8")
            if "CQ Pipeline" in content:
                hook_path.unlink()
                logger.info("Removed hook: %s", hook_name)

                # Restore backup if exists
                backup = hook_path.with_suffix(".backup")
                if backup.exists():
                    backup.rename(hook_path)
                    logger.info("Restored backup hook: %s", hook_name)
