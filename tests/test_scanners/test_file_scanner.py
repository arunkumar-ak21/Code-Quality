"""Tests for the File Scanner module."""

from __future__ import annotations

from pathlib import Path

import pytest

from cqpipeline.core.constants import ScannerCategory, Severity
from cqpipeline.scanners.file_scanner import FileScanner


@pytest.fixture
def file_scanner(project_root: Path) -> FileScanner:
    """Create a FileScanner instance."""
    return FileScanner(
        config={"enabled": True, "timeout": 10},
        project_root=project_root,
        allowlist={},
    )


@pytest.mark.asyncio
async def test_detect_env_file(file_scanner: FileScanner, file_with_env: Path) -> None:
    """Test that .env files are detected."""
    result = await file_scanner.scan([file_with_env])
    assert result.success
    env_findings = [f for f in result.findings if f.rule_id == "ENV-FILE"]
    assert len(env_findings) >= 1
    assert env_findings[0].severity == Severity.CRITICAL


@pytest.mark.asyncio
async def test_detect_large_file(file_scanner: FileScanner, large_file: Path) -> None:
    """Test that large files are detected."""
    result = await file_scanner.scan([large_file])
    assert result.success
    large_findings = [f for f in result.findings if f.rule_id == "LARGE-FILE"]
    assert len(large_findings) >= 1
    assert large_findings[0].severity == Severity.HIGH


@pytest.mark.asyncio
async def test_detect_debug_statements(
    file_scanner: FileScanner, file_with_debug: Path
) -> None:
    """Test that debug statements are detected."""
    result = await file_scanner.scan([file_with_debug])
    assert result.success
    debug_findings = [f for f in result.findings if f.rule_id == "DEBUG-STMT"]
    assert len(debug_findings) >= 2  # print() and breakpoint()


@pytest.mark.asyncio
async def test_detect_blocked_file_patterns(
    file_scanner: FileScanner, project_root: Path
) -> None:
    """Test that private key files are detected."""
    key_file = project_root / "id_rsa"
    key_file.write_text("fake key content")

    result = await file_scanner.scan([key_file])
    assert result.success
    blocked = [f for f in result.findings if f.rule_id == "BLOCKED-FILE"]
    assert len(blocked) >= 1
    assert blocked[0].severity == Severity.CRITICAL


@pytest.mark.asyncio
async def test_clean_file_passes(
    file_scanner: FileScanner, sample_python_file: Path
) -> None:
    """Test that a clean file produces no findings."""
    result = await file_scanner.scan([sample_python_file])
    assert result.success
    # Clean file should have minimal or no findings
    critical_findings = [
        f for f in result.findings
        if f.severity in (Severity.CRITICAL, Severity.HIGH)
    ]
    assert len(critical_findings) == 0


@pytest.mark.asyncio
async def test_scanner_metadata(file_scanner: FileScanner) -> None:
    """Test scanner metadata properties."""
    assert file_scanner.name == "files"
    assert file_scanner.category == ScannerCategory.FILES
