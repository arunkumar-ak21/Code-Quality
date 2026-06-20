"""Tests for the Quality Gate Evaluator."""

from __future__ import annotations

import pytest

from cqpipeline.core.constants import GateAction, ScannerCategory, Severity
from cqpipeline.core.models import Finding, ScanResult
from cqpipeline.gates.evaluator import QualityGateEvaluator


@pytest.fixture
def evaluator() -> QualityGateEvaluator:
    """Create evaluator with default config."""
    config = {
        "severity_actions": {
            "critical": "block",
            "high": "block",
            "medium": "warn",
            "low": "info",
            "info": "ignore",
        },
        "max_findings": {
            "critical": 0,
            "high": 0,
            "total": 50,
        },
        "secrets": {"max_secrets": 0},
    }
    return QualityGateEvaluator(config)


def _make_finding(severity: Severity, category: ScannerCategory = ScannerCategory.SAST) -> Finding:
    """Helper to create a test finding."""
    return Finding(
        scanner="test",
        category=category,
        severity=severity,
        message=f"Test {severity.value} finding",
    )


def _make_result(
    findings: list[Finding],
    category: ScannerCategory = ScannerCategory.SAST,
) -> ScanResult:
    """Helper to create a test scan result."""
    return ScanResult(
        scanner_name="test",
        category=category,
        findings=findings,
    )


def test_pass_with_no_findings(evaluator: QualityGateEvaluator) -> None:
    """Test that no findings results in all gates passing."""
    results = [_make_result([])]
    gate_results = evaluator.evaluate(results)

    assert all(gr.passed for gr in gate_results)


def test_block_on_critical_finding(evaluator: QualityGateEvaluator) -> None:
    """Test that a critical finding blocks the gate."""
    findings = [_make_finding(Severity.CRITICAL)]
    results = [_make_result(findings)]

    gate_results = evaluator.evaluate(results)

    blocked = [gr for gr in gate_results if not gr.passed]
    assert len(blocked) >= 1
    assert any(gr.action == GateAction.BLOCK for gr in blocked)


def test_block_on_high_finding(evaluator: QualityGateEvaluator) -> None:
    """Test that a high severity finding blocks the gate."""
    findings = [_make_finding(Severity.HIGH)]
    results = [_make_result(findings)]

    gate_results = evaluator.evaluate(results)

    blocked = [gr for gr in gate_results if not gr.passed]
    assert len(blocked) >= 1


def test_warn_on_medium_finding(evaluator: QualityGateEvaluator) -> None:
    """Test that medium findings produce warnings but pass."""
    findings = [_make_finding(Severity.MEDIUM)]
    results = [_make_result(findings)]

    gate_results = evaluator.evaluate(results)

    # Severity gate should pass with warning
    severity_gate = next(
        (gr for gr in gate_results if gr.gate_name == "Severity Gate"), None
    )
    assert severity_gate is not None
    assert severity_gate.passed  # Medium = warn, not block


def test_secret_detection_always_blocks(evaluator: QualityGateEvaluator) -> None:
    """Test zero tolerance for secrets."""
    findings = [_make_finding(Severity.CRITICAL, ScannerCategory.SECRETS)]
    results = [_make_result(findings, ScannerCategory.SECRETS)]

    gate_results = evaluator.evaluate(results)

    secret_gate = next(
        (gr for gr in gate_results if gr.gate_name == "Secret Detection Gate"), None
    )
    assert secret_gate is not None
    assert not secret_gate.passed
    assert secret_gate.action == GateAction.BLOCK


def test_low_findings_pass(evaluator: QualityGateEvaluator) -> None:
    """Test that low severity findings don't block."""
    findings = [_make_finding(Severity.LOW) for _ in range(10)]
    results = [_make_result(findings)]

    gate_results = evaluator.evaluate(results)

    # Should not have any blocking gates (only severity gate with low)
    severity_gate = next(
        (gr for gr in gate_results if gr.gate_name == "Severity Gate"), None
    )
    assert severity_gate is not None
    assert severity_gate.passed
