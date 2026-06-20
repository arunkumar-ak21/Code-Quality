"""Tests for the Dependency Scanner module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cqpipeline.core.constants import Severity
from cqpipeline.scanners.dependency_scanner import DependencyScanner
from cqpipeline.utils.process import ProcessResult


@pytest.fixture
def dependency_scanner(project_root: Path) -> DependencyScanner:
    return DependencyScanner(
        config={
            "enabled": True,
            "timeout": 10,
            "tools": {
                "pip_audit": {"enabled": True},
                "safety": {"enabled": False},
            },
        },
        project_root=project_root,
        allowlist={},
    )


@pytest.mark.asyncio
async def test_pip_audit_scans_nested_requirements(
    dependency_scanner: DependencyScanner,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nested_dir = project_root / "test-10-wrong"
    nested_dir.mkdir()
    req_file = nested_dir / "requirements.txt"
    req_file.write_text("django==1.2\nrequests==2.19.1\npyyaml==3.13\n")

    monkeypatch.setattr(
        "cqpipeline.scanners.dependency_scanner.check_tool_available",
        lambda tool: tool == "pip-audit",
    )

    async def fake_run_process(command, **kwargs):
        assert "--requirement" in command
        assert str(req_file) in command
        payload = {
            "dependencies": [
                {
                    "name": "django",
                    "version": "1.2",
                    "vulns": [
                        {
                            "id": "PYSEC-TEST-1",
                            "description": "test vulnerability",
                            "fix_versions": ["4.2.0"],
                            "aliases": ["CVE-TEST-1"],
                        }
                    ],
                }
            ]
        }
        return ProcessResult(command=command, exit_code=1, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(
        "cqpipeline.scanners.dependency_scanner.run_process",
        fake_run_process,
    )

    result = await dependency_scanner.scan([req_file])

    assert result.success
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.severity == Severity.HIGH
    assert finding.file_path == "test-10-wrong/requirements.txt"
    assert "django==1.2" in finding.message


@pytest.mark.asyncio
async def test_pip_audit_failure_does_not_pass_silently(
    dependency_scanner: DependencyScanner,
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    req_file = project_root / "requirements.txt"
    req_file.write_text("django==1.2\n")

    monkeypatch.setattr(
        "cqpipeline.scanners.dependency_scanner.check_tool_available",
        lambda tool: tool == "pip-audit",
    )

    async def fake_run_process(command, **kwargs):
        return ProcessResult(
            command=command,
            exit_code=1,
            stdout="",
            stderr="dependency resolution failed",
        )

    monkeypatch.setattr(
        "cqpipeline.scanners.dependency_scanner.run_process",
        fake_run_process,
    )

    result = await dependency_scanner.scan([req_file])

    assert result.success
    assert len(result.findings) == 1
    assert result.findings[0].rule_id == "PIP-AUDIT-FAILED"
    assert result.findings[0].severity == Severity.HIGH
