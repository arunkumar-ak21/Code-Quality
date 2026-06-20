"""Baseline support for separating old technical debt from new findings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from cqpipeline.core.models import Finding, PipelineReport

DEFAULT_BASELINE_FILE = ".cq-baseline.json"


@dataclass(frozen=True)
class BaselineResult:
    new_count: int
    existing_count: int
    ignored_count: int


class FindingBaseline:
    """Loads and applies a finding fingerprint baseline.

    The baseline file format is intentionally simple:
    {
      "version": 1,
      "fingerprints": ["..."]
    }
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.fingerprints: set[str] = set()

    def load(self) -> "FindingBaseline":
        if not self.path.exists():
            self.fingerprints = set()
            return self
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            raw = data.get("fingerprints", []) if isinstance(data, dict) else []
            self.fingerprints = {str(item) for item in raw if item}
        except Exception:
            self.fingerprints = set()
        return self

    def apply(self, report: PipelineReport, *, suppress_existing: bool = False) -> BaselineResult:
        new_count = 0
        existing_count = 0
        ignored_count = 0

        for result in report.scan_results:
            retained: list[Finding] = []
            for finding in result.findings:
                fingerprint = finding.ensure_fingerprint()
                if fingerprint in self.fingerprints:
                    finding.baseline_state = "existing"
                    existing_count += 1
                    if suppress_existing:
                        ignored_count += 1
                        continue
                else:
                    finding.baseline_state = "new"
                    new_count += 1
                retained.append(finding)
            result.findings = retained

        report.compute_aggregates()
        report.blocking_reasons.append(
            f"Baseline: {new_count} new, {existing_count} existing, {ignored_count} suppressed findings."
        )
        return BaselineResult(new_count, existing_count, ignored_count)

    @staticmethod
    def write_from_report(report: PipelineReport, path: Path) -> None:
        fingerprints = sorted({finding.ensure_fingerprint() for finding in report.all_findings})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"version": 1, "fingerprints": fingerprints}, indent=2),
            encoding="utf-8",
        )
