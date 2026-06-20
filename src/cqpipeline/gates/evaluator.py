"""
Quality Gate Evaluator — the decision engine for pass/fail/warn.

Evaluates scan results against configurable thresholds defined in
quality-gates.yaml. Each policy returns a GateResult that includes
whether it passed, what action to take, and an explanation.

The evaluator aggregates all policy results to determine the final verdict.
"""

from __future__ import annotations

from cqpipeline.core.constants import GateAction, ScannerCategory, Severity
from cqpipeline.core.models import Finding, GateResult, ScanResult
from cqpipeline.utils.logger import get_logger

logger = get_logger(__name__)


class QualityGateEvaluator:
    """
    Evaluates scan results against quality gate thresholds.

    Usage:
        evaluator = QualityGateEvaluator(gates_config)
        gate_results = evaluator.evaluate(scan_results)
    """

    def __init__(self, config: dict) -> None:
        self.config = config
        self.severity_actions = config.get("severity_actions", {
            "critical": "block",
            "high": "block",
            "medium": "warn",
            "low": "info",
            "info": "ignore",
        })
        self.max_findings = config.get("max_findings", {})

    def evaluate(self, scan_results: list[ScanResult]) -> list[GateResult]:
        """Evaluate all quality gate policies against scan results."""
        gate_results: list[GateResult] = []

        # Collect all findings
        all_findings: list[Finding] = []
        for result in scan_results:
            all_findings.extend(result.findings)

        # 1. Severity-based gate
        gate_results.append(self._evaluate_severity_gate(all_findings))

        # 2. Finding count gate
        gate_results.append(self._evaluate_count_gate(all_findings))

        # 3. Secret detection gate
        secret_findings = [
            f for f in all_findings if f.category == ScannerCategory.SECRETS
        ]
        if secret_findings:
            gate_results.append(self._evaluate_secret_gate(secret_findings))

        # 4. SAST gate
        sast_findings = [
            f for f in all_findings if f.category == ScannerCategory.SAST
        ]
        if sast_findings:
            gate_results.append(self._evaluate_sast_gate(sast_findings))

        # 5. Dependency gate
        dep_findings = [
            f for f in all_findings if f.category == ScannerCategory.DEPENDENCIES
        ]
        if dep_findings:
            gate_results.append(self._evaluate_dependency_gate(dep_findings))

        # 6. Linting gate
        lint_findings = [
            f for f in all_findings if f.category == ScannerCategory.LINTING
        ]
        if lint_findings:
            gate_results.append(self._evaluate_linting_gate(lint_findings))

        # 7. File gate
        file_findings = [
            f for f in all_findings if f.category == ScannerCategory.FILES
        ]
        if file_findings:
            gate_results.append(self._evaluate_file_gate(file_findings))

        # Log summary
        blocked = [gr for gr in gate_results if not gr.passed]
        warnings = [gr for gr in gate_results if gr.action == GateAction.WARN]
        logger.info(
            "Quality gates: %d passed, %d blocked, %d warnings",
            len(gate_results) - len(blocked),
            len(blocked),
            len(warnings),
        )

        return gate_results

    def _evaluate_severity_gate(self, findings: list[Finding]) -> GateResult:
        """Evaluate findings based on severity thresholds."""
        blocking_findings: list[str] = []
        warning_findings: list[str] = []

        severity_counts = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 0,
            Severity.MEDIUM: 0,
            Severity.LOW: 0,
            Severity.INFO: 0,
        }

        for finding in findings:
            severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1

        for severity, count in severity_counts.items():
            if count == 0:
                continue

            action_str = self.severity_actions.get(severity.value, "info")
            if action_str == "block":
                blocking_findings.append(
                    f"{count} {severity.value.upper()} finding(s)"
                )
            elif action_str == "warn":
                warning_findings.append(
                    f"{count} {severity.value.upper()} finding(s)"
                )

        if blocking_findings:
            return GateResult(
                gate_name="Severity Gate",
                passed=False,
                action=GateAction.BLOCK,
                message=f"Blocked: {', '.join(blocking_findings)}",
                details=blocking_findings,
            )
        elif warning_findings:
            return GateResult(
                gate_name="Severity Gate",
                passed=True,
                action=GateAction.WARN,
                message=f"Warnings: {', '.join(warning_findings)}",
                details=warning_findings,
            )
        else:
            return GateResult(
                gate_name="Severity Gate",
                passed=True,
                action=GateAction.INFO,
                message="All severity checks passed",
            )

    def _evaluate_count_gate(self, findings: list[Finding]) -> GateResult:
        """Evaluate total finding counts against maximums."""
        max_total = self.max_findings.get("total", 50)
        max_critical = self.max_findings.get("critical", 0)
        max_high = self.max_findings.get("high", 0)

        critical_count = sum(1 for f in findings if f.severity == Severity.CRITICAL)
        high_count = sum(1 for f in findings if f.severity == Severity.HIGH)
        total = len(findings)

        violations: list[str] = []

        if max_critical >= 0 and critical_count > max_critical:
            violations.append(
                f"Critical findings: {critical_count} (max: {max_critical})"
            )
        if max_high >= 0 and high_count > max_high:
            violations.append(
                f"High findings: {high_count} (max: {max_high})"
            )
        if max_total >= 0 and total > max_total:
            violations.append(
                f"Total findings: {total} (max: {max_total})"
            )

        if violations:
            return GateResult(
                gate_name="Finding Count Gate",
                passed=False,
                action=GateAction.BLOCK,
                message=f"Exceeded limits: {'; '.join(violations)}",
                details=violations,
            )

        return GateResult(
            gate_name="Finding Count Gate",
            passed=True,
            action=GateAction.INFO,
            message=f"Finding counts within limits (total: {total})",
        )

    def _evaluate_secret_gate(self, findings: list[Finding]) -> GateResult:
        """Zero tolerance for secrets."""
        secrets_config = self.config.get("secrets", {})
        max_secrets = secrets_config.get("max_secrets", 0)

        if len(findings) > max_secrets:
            details = [
                f"  • {f.title} in {f.file_path}:{f.line_number}"
                for f in findings[:10]  # Show first 10
            ]
            return GateResult(
                gate_name="Secret Detection Gate",
                passed=False,
                action=GateAction.BLOCK,
                message=f"🔐 {len(findings)} secret(s) detected — commit BLOCKED",
                details=details,
            )

        return GateResult(
            gate_name="Secret Detection Gate",
            passed=True,
            action=GateAction.INFO,
            message="No secrets detected",
        )

    def _evaluate_sast_gate(self, findings: list[Finding]) -> GateResult:
        """Evaluate SAST findings against security policies."""
        sast_config = self.config.get("sast", {})
        block_on_cwe = set(sast_config.get("block_on_cwe", []))

        blocking_cwes: list[str] = []
        for finding in findings:
            if finding.cwe_id:
                # Check each CWE in the finding
                for cwe in finding.cwe_id.split(","):
                    cwe = cwe.strip()
                    if cwe in block_on_cwe:
                        blocking_cwes.append(
                            f"{cwe}: {finding.message[:60]} ({finding.file_path})"
                        )

        # Also block on HIGH/CRITICAL SAST findings
        high_sast = [
            f for f in findings
            if f.severity in (Severity.CRITICAL, Severity.HIGH)
        ]

        if blocking_cwes or high_sast:
            details = blocking_cwes[:5]
            if high_sast:
                details.extend([
                    f"  • {f.title} in {f.file_path}:{f.line_number}"
                    for f in high_sast[:5]
                ])
            return GateResult(
                gate_name="SAST Gate",
                passed=False,
                action=GateAction.BLOCK,
                message=f"🛡️ {len(blocking_cwes) + len(high_sast)} security issue(s) detected",
                details=details,
            )

        return GateResult(
            gate_name="SAST Gate",
            passed=True,
            action=GateAction.WARN if findings else GateAction.INFO,
            message=f"SAST check: {len(findings)} finding(s)" if findings else "No SAST issues",
        )

    def _evaluate_dependency_gate(self, findings: list[Finding]) -> GateResult:
        """Evaluate dependency vulnerability findings."""
        dep_config = self.config.get("dependencies", {})
        max_vuln = dep_config.get("max_vulnerable_deps", 0)

        critical_deps = [
            f for f in findings if f.severity in (Severity.CRITICAL, Severity.HIGH)
        ]

        if len(critical_deps) > max_vuln:
            details = [
                f"  • {f.message[:80]}" for f in critical_deps[:10]
            ]
            return GateResult(
                gate_name="Dependency Gate",
                passed=False,
                action=GateAction.BLOCK,
                message=f"📦 {len(critical_deps)} vulnerable dependency(ies) detected",
                details=details,
            )

        if findings:
            return GateResult(
                gate_name="Dependency Gate",
                passed=True,
                action=GateAction.WARN,
                message=f"Dependency check: {len(findings)} issue(s) (non-blocking)",
            )

        return GateResult(
            gate_name="Dependency Gate",
            passed=True,
            action=GateAction.INFO,
            message="No dependency vulnerabilities",
        )

    def _evaluate_linting_gate(self, findings: list[Finding]) -> GateResult:
        """Evaluate linting results against thresholds."""
        lint_config = self.config.get("linting", {})
        max_errors = lint_config.get("max_lint_errors", 10)

        error_findings = [
            f for f in findings if f.severity in (Severity.HIGH, Severity.CRITICAL)
        ]

        if max_errors >= 0 and len(error_findings) > max_errors:
            return GateResult(
                gate_name="Linting Gate",
                passed=False,
                action=GateAction.BLOCK,
                message=f"📝 {len(error_findings)} lint errors (max: {max_errors})",
                details=[
                    f"  • {f.rule_id}: {f.message[:60]} ({f.file_path}:{f.line_number})"
                    for f in error_findings[:10]
                ],
            )

        return GateResult(
            gate_name="Linting Gate",
            passed=True,
            action=GateAction.WARN if findings else GateAction.INFO,
            message=f"Linting: {len(findings)} finding(s)" if findings else "Linting passed",
        )

    def _evaluate_file_gate(self, findings: list[Finding]) -> GateResult:
        """Evaluate file-level findings (.env, large files, etc.)."""
        critical_files = [
            f for f in findings if f.severity in (Severity.CRITICAL, Severity.HIGH)
        ]

        if critical_files:
            details = [
                f"  • {f.title}: {f.file_path}" for f in critical_files
            ]
            return GateResult(
                gate_name="File Gate",
                passed=False,
                action=GateAction.BLOCK,
                message=f"📁 {len(critical_files)} blocked file(s) detected",
                details=details,
            )

        return GateResult(
            gate_name="File Gate",
            passed=True,
            action=GateAction.INFO,
            message="File checks passed",
        )
