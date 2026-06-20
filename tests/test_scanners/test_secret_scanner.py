"""Tests for the Secret Scanner module."""

from __future__ import annotations

from pathlib import Path

import pytest

from cqpipeline.core.constants import ScannerCategory, Severity
from cqpipeline.scanners.secret_scanner import SecretScanner


@pytest.fixture
def secret_scanner(project_root: Path) -> SecretScanner:
    """Create a SecretScanner with custom patterns enabled."""
    return SecretScanner(
        config={
            "enabled": True,
            "timeout": 10,
            "tools": {
                "gitleaks": {"enabled": False},
                "detect_secrets": {"enabled": False},
                "trufflehog": {"enabled": False},
            },
        },
        project_root=project_root,
        allowlist={},
    )


@pytest.mark.asyncio
async def test_custom_pattern_detection(
    secret_scanner: SecretScanner,
    file_with_secrets: Path,
    project_root: Path,
) -> None:
    """Test that custom regex patterns detect secrets."""
    # Create secret patterns config
    patterns_dir = project_root / "config"
    patterns_dir.mkdir(exist_ok=True)
    (patterns_dir / "secret-patterns.yaml").write_text("""
patterns:
  - id: aws-access-key
    description: AWS Access Key ID
    regex: '(AKIA[0-9A-Z]{16})'
    severity: critical
    keywords: [AKIA]
  - id: db-connection-string
    description: Database Connection String
    regex: 'postgres://[^\\s"]+:[^\\s"]+@[^\\s"]+'
    severity: critical
    keywords: ['://']
entropy:
  enabled: false
""")

    result = await secret_scanner.scan([file_with_secrets])
    assert result.success
    assert result.category == ScannerCategory.SECRETS

    # Should detect the AWS key and DB connection string
    assert len(result.findings) >= 1

    # Check severities
    for finding in result.findings:
        assert finding.severity in (Severity.CRITICAL, Severity.HIGH)


@pytest.mark.asyncio
async def test_clean_file_no_secrets(
    secret_scanner: SecretScanner,
    sample_python_file: Path,
) -> None:
    """Test that a clean file produces no secret findings."""
    result = await secret_scanner.scan([sample_python_file])
    assert result.success
    assert len(result.findings) == 0


@pytest.mark.asyncio
async def test_scanner_properties(secret_scanner: SecretScanner) -> None:
    """Test scanner metadata."""
    assert secret_scanner.name == "secrets"
    assert secret_scanner.category == ScannerCategory.SECRETS
