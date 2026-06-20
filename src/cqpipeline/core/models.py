"""
Pydantic data models — the data contract between all pipeline components.

Every scanner produces `Finding` objects. The orchestrator collects them into
`ScanResult` objects. The quality gate evaluates the aggregate and produces
a `PipelineReport` with a final `Verdict`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from cqpipeline.core.constants import (
    GateAction,
    ScanMode,
    ScannerCategory,
    Severity,
    Verdict,
)


# ─── Finding ──────────────────────────────────────────────────────────

class Finding(BaseModel):
    """A single issue detected by a scanner."""

    id: UUID = Field(default_factory=uuid4)
    scanner: str = Field(description="Scanner that produced this finding (e.g., 'gitleaks')")
    category: ScannerCategory = Field(description="Category of the scanner")
    severity: Severity = Field(description="Severity of the finding")
    rule_id: str = Field(default="", description="Rule/check ID (e.g., 'B101', 'CWE-78')")
    title: str = Field(default="", description="Short title for the finding")
    message: str = Field(description="Human-readable description of the finding")
    file_path: str = Field(default="", description="Relative file path where issue was found")
    line_number: int = Field(default=0, description="Line number (1-indexed)")
    column_number: int = Field(default=0, description="Column number (1-indexed)")
    code_snippet: str = Field(default="", description="Relevant code snippet")
    suggestion: str = Field(default="", description="Suggested fix or remediation")
    cwe_id: str = Field(default="", description="CWE identifier if applicable")
    cvss_score: float | None = Field(default=None, description="CVSS score for CVEs")
    cve_id: str = Field(default="", description="CVE identifier if applicable")
    metadata: dict = Field(default_factory=dict, description="Additional scanner-specific data")

    model_config = {"ser_json_bytes": "utf8"}


# ─── Scan Result ──────────────────────────────────────────────────────

class ScanResult(BaseModel):
    """Result from a single scanner's execution."""

    scanner_name: str = Field(description="Name of the scanner")
    category: ScannerCategory = Field(description="Scanner category")
    success: bool = Field(default=True, description="Whether the scanner ran successfully")
    error_message: str = Field(default="", description="Error message if scanner failed")
    findings: list[Finding] = Field(default_factory=list, description="List of findings")
    duration_seconds: float = Field(default=0.0, description="Execution time in seconds")
    files_scanned: int = Field(default=0, description="Number of files scanned")
    tool_version: str = Field(default="", description="Version of the external tool used")
    skipped: bool = Field(default=False, description="Whether the scanner was skipped")
    skip_reason: str = Field(default="", description="Reason for skipping")

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.HIGH)

    @property
    def medium_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.MEDIUM)

    @property
    def low_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.LOW)

    def has_blocking_findings(self, blocking_severities: set[Severity] | None = None) -> bool:
        """Check if this result contains findings that should block the commit."""
        if blocking_severities is None:
            blocking_severities = {Severity.CRITICAL, Severity.HIGH}
        return any(f.severity in blocking_severities for f in self.findings)


# ─── Gate Result ──────────────────────────────────────────────────────

class GateResult(BaseModel):
    """Result from a quality gate evaluation."""

    gate_name: str = Field(description="Name of the gate policy")
    passed: bool = Field(description="Whether the gate passed")
    action: GateAction = Field(description="Action taken: block, warn, info, ignore")
    message: str = Field(default="", description="Explanation of the gate result")
    details: list[str] = Field(default_factory=list, description="Detailed reasons")


# ─── Pipeline Report ─────────────────────────────────────────────────

class PipelineReport(BaseModel):
    """Complete report from a pipeline run — the final output."""

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    verdict: Verdict = Field(description="Final pipeline verdict")
    scan_mode: ScanMode = Field(description="What was scanned")

    # Git metadata
    commit_sha: str = Field(default="", description="Git commit SHA")
    branch: str = Field(default="", description="Git branch name")
    author: str = Field(default="", description="Git author")
    repository: str = Field(default="", description="Repository name/path")

    # Results
    scan_results: list[ScanResult] = Field(default_factory=list)
    gate_results: list[GateResult] = Field(default_factory=list)

    # Aggregates
    total_findings: int = Field(default=0)
    critical_count: int = Field(default=0)
    high_count: int = Field(default=0)
    medium_count: int = Field(default=0)
    low_count: int = Field(default=0)
    info_count: int = Field(default=0)

    # Timing
    duration_seconds: float = Field(default=0.0)
    files_scanned: int = Field(default=0)

    # Blocking reasons
    blocking_reasons: list[str] = Field(default_factory=list)

    model_config = {"ser_json_bytes": "utf8"}

    def compute_aggregates(self) -> None:
        """Recompute aggregate counts from scan results."""
        self.total_findings = 0
        self.critical_count = 0
        self.high_count = 0
        self.medium_count = 0
        self.low_count = 0
        self.info_count = 0
        self.files_scanned = 0

        for result in self.scan_results:
            self.total_findings += result.finding_count
            self.critical_count += result.critical_count
            self.high_count += result.high_count
            self.medium_count += result.medium_count
            self.low_count += result.low_count
            self.info_count += sum(
                1 for f in result.findings if f.severity == Severity.INFO
            )
            self.files_scanned += result.files_scanned

    @property
    def all_findings(self) -> list[Finding]:
        """Flatten all findings from all scan results."""
        findings: list[Finding] = []
        for result in self.scan_results:
            findings.extend(result.findings)
        return sorted(findings, key=lambda f: f.severity.weight, reverse=True)


# ─── Scanner Configuration Models ────────────────────────────────────

class ScannerConfig(BaseModel):
    """Configuration for a single scanner."""

    enabled: bool = True
    timeout: int = 60
    extra_args: list[str] = Field(default_factory=list)
    config_path: str = ""


class PipelineConfig(BaseModel):
    """Top-level pipeline configuration model."""

    name: str = "Code Quality Pipeline"
    version: str = "1.0.0"
    timeout: int = 120
    parallel_workers: int = 4
    fail_on_scanner_error: bool = False
    default_scan_mode: ScanMode = ScanMode.STAGED
    report_dir: str = "reports"
    log_level: str = "INFO"


class FileToScan(BaseModel):
    """Represents a file to be scanned with its metadata."""

    path: Path
    language: str = ""
    size_bytes: int = 0
    is_new: bool = False

    model_config = {"arbitrary_types_allowed": True}
