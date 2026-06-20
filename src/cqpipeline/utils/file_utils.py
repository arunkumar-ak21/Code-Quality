"""
File utility functions for the CQ Pipeline.

Provides file filtering, language detection, size checks, and path operations.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

from cqpipeline.core.constants import LANGUAGE_EXTENSIONS
from cqpipeline.utils.logger import get_logger

logger = get_logger(__name__)


def detect_language(file_path: Path) -> str:
    """Detect the programming language of a file by its extension."""
    suffix = file_path.suffix.lower()
    name = file_path.name

    for language, extensions in LANGUAGE_EXTENSIONS.items():
        if suffix in extensions or name in extensions:
            return language

    return "unknown"


def filter_files_by_language(
    files: list[Path],
    languages: list[str],
) -> list[Path]:
    """Filter files to only those matching the specified languages."""
    result: list[Path] = []
    for f in files:
        lang = detect_language(f)
        if lang in languages:
            result.append(f)
    return result


def filter_files_by_extensions(
    files: list[Path],
    extensions: list[str],
) -> list[Path]:
    """Filter files by their extensions."""
    ext_set = {e.lower() for e in extensions}
    return [f for f in files if f.suffix.lower() in ext_set]


def matches_glob_pattern(file_path: str, patterns: list[str]) -> bool:
    """Check if a file path matches any of the glob patterns."""
    for pattern in patterns:
        if fnmatch.fnmatch(file_path, pattern):
            return True
    return False


def get_file_size(file_path: Path) -> int:
    """Get file size in bytes, returning 0 if file doesn't exist."""
    try:
        return file_path.stat().st_size
    except OSError:
        return 0


def is_binary_file(file_path: Path) -> bool:
    """
    Heuristic check for binary files.

    Reads the first 8KB and checks for null bytes.
    """
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(8192)
            return b"\x00" in chunk
    except OSError:
        return False


def read_file_safe(file_path: Path, max_size_mb: int = 10) -> str | None:
    """
    Read a file safely with size limits.

    Returns None if the file is too large, binary, or unreadable.
    """
    try:
        size = file_path.stat().st_size
        if size > max_size_mb * 1024 * 1024:
            logger.debug("Skipping large file: %s (%d bytes)", file_path, size)
            return None

        if is_binary_file(file_path):
            logger.debug("Skipping binary file: %s", file_path)
            return None

        with open(file_path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as e:
        logger.debug("Cannot read file %s: %s", file_path, e)
        return None


def get_relative_path(file_path: Path, base_path: Path) -> str:
    """Get the relative path string from base_path to file_path."""
    try:
        return str(file_path.relative_to(base_path))
    except ValueError:
        return str(file_path)
