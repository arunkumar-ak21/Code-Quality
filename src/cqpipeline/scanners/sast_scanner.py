"""
SAST Scanner — Static Application Security Testing.

Integrates:
- Semgrep: Multi-language SAST with community and custom rules
- Bandit: Python-specific security linter

Why both tools:
- Semgrep has the broadest rule coverage (OWASP Top 10, custom rules)
  and supports many languages with the same engine
- Bandit is purpose-built for Python and catches Python-unique issues
  like pickle deserialization, yaml.load without Loader, exec/eval
"""

from __future__ import annotations

import json
from pathlib import Path

from cqpipeline.core.constants import ScannerCategory, Severity
from cqpipeline.core.models import Finding, ScanResult
from cqpipeline.scanners.base import BaseScanner
from cqpipeline.utils.logger import get_logger
from cqpipeline.utils.process import check_tool_available, run_process

logger = get_logger(__name__)


class SASTScanner(BaseScanner):
    """Multi-tool SAST scanner for security vulnerability detection."""

    @property
    def name(self) -> str:
        return "sast"

    @property
    def category(self) -> ScannerCategory:
        return ScannerCategory.SAST

    async def _execute(self, files: list[Path]) -> ScanResult:
        """Run SAST tools and merge results."""
        all_findings: list[Finding] = []
        tools_config = self.config.get("tools", {})

        # 1. Semgrep
        if tools_config.get("semgrep", {}).get("enabled", True):
            if check_tool_available("semgrep"):
                findings = await self._run_semgrep(files)
                all_findings.extend(findings)
            else:
                logger.warning("Semgrep not installed — skipping")

        # 2. Bandit (Python-specific)
        if tools_config.get("bandit", {}).get("enabled", True):
            if check_tool_available("bandit"):
                py_files = [f for f in files if f.suffix in (".py", ".pyw")]
                if py_files:
                    findings = await self._run_bandit(py_files)
                    all_findings.extend(findings)
            else:
                logger.warning("Bandit not installed — skipping")

        return ScanResult(
            scanner_name=self.name,
            category=self.category,
            success=True,
            findings=all_findings,
        )

    async def _run_semgrep(self, files: list[Path]) -> list[Finding]:
        """Run Semgrep with community rules."""
        findings: list[Finding] = []
        tools_config = self.config.get("tools", {}).get("semgrep", {})

        config = tools_config.get("config", "auto")
        cmd = [
            "semgrep",
            "scan",
            "--config", config,
            "--json",
            "--quiet",
            "--no-git-ignore",
        ]

        # Add custom rules directory if specified
        custom_rules = tools_config.get("custom_rules_dir", "")
        if custom_rules:
            cmd.extend(["--config", custom_rules])

        # Add target files
        cmd.append(str(self.project_root))

        result = await run_process(
            cmd,
            cwd=self.project_root,
            timeout=self.config.get("timeout", 60),
            scanner_name="semgrep",
        )

        if result.stdout.strip():
            try:
                output = json.loads(result.stdout)
                results = output.get("results", [])

                for r in results:
                    extra = r.get("extra", {})
                    metadata = extra.get("metadata", {})
                    severity_str = extra.get("severity", "WARNING")

                    findings.append(
                        Finding(
                            scanner="semgrep",
                            category=ScannerCategory.SAST,
                            severity=self._map_semgrep_severity(severity_str),
                            rule_id=r.get("check_id", ""),
                            title=r.get("check_id", "").split(".")[-1],
                            message=extra.get("message", "Security issue detected"),
                            file_path=r.get("path", ""),
                            line_number=r.get("start", {}).get("line", 0),
                            column_number=r.get("start", {}).get("col", 0),
                            code_snippet=extra.get("lines", ""),
                            cwe_id=", ".join(metadata.get("cwe", [])) if metadata.get("cwe") else "",
                            suggestion=extra.get("fix", ""),
                            metadata={
                                "confidence": metadata.get("confidence", ""),
                                "impact": metadata.get("impact", ""),
                                "references": metadata.get("references", []),
                                "owasp": metadata.get("owasp", []),
                            },
                        )
                    )
            except json.JSONDecodeError:
                logger.warning("Failed to parse Semgrep output")

        logger.info("Semgrep found %d issues", len(findings))
        return findings

    async def _run_bandit(self, files: list[Path]) -> list[Finding]:
        """Run Bandit on Python files."""
        findings: list[Finding] = []
        tools_config = self.config.get("tools", {}).get("bandit", {})

        severity_level = tools_config.get("severity_level", "medium")
        confidence_level = tools_config.get("confidence_level", "medium")

        file_args = [str(f) for f in files]

        cmd = [
            "bandit",
            "-f", "json",
            "--severity-level", severity_level,
            "--confidence-level", confidence_level,
        ] + file_args

        result = await run_process(
            cmd,
            cwd=self.project_root,
            timeout=self.config.get("timeout", 60),
            scanner_name="bandit",
        )

        # Bandit exit code 1 means issues found
        if result.stdout.strip():
            try:
                output = json.loads(result.stdout)
                results = output.get("results", [])

                for r in results:
                    findings.append(
                        Finding(
                            scanner="bandit",
                            category=ScannerCategory.SAST,
                            severity=self._map_severity(
                                r.get("issue_severity", "MEDIUM")
                            ),
                            rule_id=r.get("test_id", ""),
                            title=r.get("test_name", ""),
                            message=r.get("issue_text", ""),
                            file_path=r.get("filename", ""),
                            line_number=r.get("line_number", 0),
                            column_number=r.get("col_offset", 0),
                            code_snippet=r.get("code", ""),
                            cwe_id=r.get("issue_cwe", {}).get("id", "") if r.get("issue_cwe") else "",
                            metadata={
                                "confidence": r.get("issue_confidence", ""),
                                "more_info": r.get("more_info", ""),
                                "line_range": r.get("line_range", []),
                            },
                        )
                    )
            except json.JSONDecodeError:
                logger.warning("Failed to parse Bandit output")

        logger.info("Bandit found %d issues", len(findings))
        return findings

    @staticmethod
    def _map_semgrep_severity(severity: str) -> Severity:
        """Map Semgrep severity to our Severity enum."""
        mapping = {
            "ERROR": Severity.HIGH,
            "WARNING": Severity.MEDIUM,
            "INFO": Severity.LOW,
        }
        return mapping.get(severity.upper(), Severity.MEDIUM)
