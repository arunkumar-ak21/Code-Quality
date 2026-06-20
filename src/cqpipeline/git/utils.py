"""
Git utility functions for the CQ Pipeline.

Provides functions to:
- Get list of staged files
- Get git metadata (commit, branch, author)
- Check if we're in a git repository
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from cqpipeline.utils.logger import get_logger

logger = get_logger(__name__)


def is_git_repo(path: Path) -> bool:
    """Check if the given path is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_staged_files(project_root: Path) -> list[str]:
    """
    Get list of staged files (files added to the git index).

    Uses: git diff --cached --name-only --diff-filter=ACMR
      A = Added, C = Copied, M = Modified, R = Renamed

    Returns relative paths from the project root.
    """
    if not is_git_repo(project_root):
        logger.warning("Not a git repository: %s", project_root)
        return []

    try:
        result = subprocess.run(
            [
                "git", "diff", "--cached", "--name-only",
                "--diff-filter=ACMR",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            logger.warning("git diff failed: %s", result.stderr.strip())
            return []

        files = [
            f.strip()
            for f in result.stdout.strip().splitlines()
            if f.strip()
        ]

        logger.debug("Found %d staged files", len(files))
        return files

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("Failed to get staged files: %s", e)
        return []


def get_git_metadata(project_root: Path) -> dict[str, str]:
    """
    Get git metadata for the current state.

    Returns dict with: commit_sha, branch, author, repository
    """
    metadata: dict[str, str] = {
        "commit_sha": "",
        "branch": "",
        "author": "",
        "repository": str(project_root),
    }

    if not is_git_repo(project_root):
        return metadata

    try:
        # Get current commit SHA
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            metadata["commit_sha"] = result.stdout.strip()

        # Get current branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            metadata["branch"] = result.stdout.strip()

        # Get author
        result = subprocess.run(
            ["git", "config", "user.name"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            metadata["author"] = result.stdout.strip()

        # Get remote URL as repository name
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            metadata["repository"] = result.stdout.strip()

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.debug("Failed to get git metadata: %s", e)

    return metadata


def get_changed_files_vs_branch(
    project_root: Path,
    base_branch: str = "main",
) -> list[str]:
    """
    Get files changed compared to a base branch (for CI/CD diff scanning).

    Used in PR pipelines to scan only the changes in the PR.
    """
    if not is_git_repo(project_root):
        return []

    try:
        result = subprocess.run(
            [
                "git", "diff", "--name-only",
                "--diff-filter=ACMR",
                f"origin/{base_branch}...HEAD",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            logger.warning("git diff vs %s failed: %s", base_branch, result.stderr)
            return []

        return [f.strip() for f in result.stdout.strip().splitlines() if f.strip()]

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("Failed to get changed files: %s", e)
        return []
