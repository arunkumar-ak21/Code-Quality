"""SARIF reporter for GitHub Code Scanning integration."""

from __future__ import annotations

import json
from pathlib import Path

from cqpipeline.core.constants import Severity
from cqpipeline.core.models import Finding, PipelineReport
from cqpipeline.reporters.base import BaseReporter


def _sarif_level(severity: Severity) -> str:
    if severity in {Severity.CRITICAL, Severity.HIGH}:
        return "error"
    if severity == Severity.MEDIUM:
        return "warning"
    return "note"


class SARIFReporter(BaseReporter):
    """Generate SARIF 2.1.0 output."""

    def generate(self, report: PipelineReport, output_path: Path | None = None) -> str:
        rules: dict[str, dict] = {}
        results: list[dict] = []

        for finding in report.all_findings:
            rule_id = finding.rule_id or finding.title or finding.scanner
            rules.setdefault(rule_id, {
                "id": rule_id,
                "name": finding.title or rule_id,
                "shortDescription": {"text": finding.title or rule_id},
                "fullDescription": {"text": finding.message or finding.title or rule_id},
                "help": {"text": finding.suggestion or "Review and remediate this finding."},
                "properties": {
                    "scanner": finding.scanner,
                    "category": finding.category.value if hasattr(finding.category, "value") else str(finding.category),
                    "severity": finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity),
                    "tags": [finding.scanner],
                },
            })
            location = {
                "physicalLocation": {
                    "artifactLocation": {"uri": finding.file_path or "unknown"},
                    "region": {"startLine": max(1, int(finding.line_number or 1))},
                }
            }
            if finding.column_number:
                location["physicalLocation"]["region"]["startColumn"] = max(1, int(finding.column_number))
            results.append({
                "ruleId": rule_id,
                "level": _sarif_level(finding.severity),
                "message": {"text": finding.message or finding.title or rule_id},
                "locations": [location],
                "partialFingerprints": {"primaryLocationLineHash": finding.ensure_fingerprint()},
                "properties": {
                    "fingerprint": finding.fingerprint,
                    "baseline_state": finding.baseline_state,
                    "cve_id": finding.cve_id,
                    "cwe_id": finding.cwe_id,
                    "metadata": finding.metadata,
                },
            })

        sarif = {
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [{
                "tool": {
                    "driver": {
                        "name": "CQ Pipeline",
                        "informationUri": "https://github.com/arunkumar-ak21/Code-Quality",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
                "properties": {
                    "verdict": report.verdict.value if hasattr(report.verdict, "value") else str(report.verdict),
                    "total_findings": report.total_findings,
                    "critical": report.critical_count,
                    "high": report.high_count,
                    "medium": report.medium_count,
                    "low": report.low_count,
                },
            }],
        }
        text = json.dumps(sarif, indent=2)
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(text, encoding="utf-8")
        return text
