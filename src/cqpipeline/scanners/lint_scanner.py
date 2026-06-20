"""
Linting Scanner — code style, formatting, and quality analysis.

Integrates:
- Ruff: Ultra-fast Python linter (100x faster than Flake8)
- Black: Code formatter check
- Pylint: Deep code analysis with scoring

Why these tools:
- Ruff replaces Flake8+isort+pyupgrade in a single, fast tool
- Black enforces consistent formatting (no debates about style)
- Pylint provides deep analysis including code smells and scoring
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


class LintScanner(BaseScanner):
    """Multi-tool linting scanner for code style and quality."""

    @property
    def name(self) -> str:
        return "linting"

    @property
    def category(self) -> ScannerCategory:
        return ScannerCategory.LINTING

    @property
    def supported_languages(self) -> list[str]:
        return ["python", "javascript", "typescript"]

    async def _execute(self, files: list[Path]) -> ScanResult:
        """Run all enabled linting tools and merge results."""
        all_findings: list[Finding] = []
        tools_config = self.config.get("tools", {})

        # Get Python files
        py_files = [f for f in files if f.suffix in (".py", ".pyw", ".pyi")]
        py_args = [str(f) for f in py_files]

        # Get JS/TS files
        js_files = [f for f in files if f.suffix in (".js", ".jsx", ".mjs", ".ts", ".tsx")]
        js_args = [str(f) for f in js_files]

        if not py_files and not js_files:
            return ScanResult(
                scanner_name=self.name,
                category=self.category,
                success=True,
            )

        # 1. Ruff (fast linter)
        if py_files and tools_config.get("ruff", {}).get("enabled", True):
            if check_tool_available("ruff"):
                findings = await self._run_ruff(py_args)
                all_findings.extend(findings)
            else:
                logger.warning("Ruff not installed — skipping")

        # 2. Black (formatting check)
        if py_files and tools_config.get("black", {}).get("enabled", True):
            if check_tool_available("black"):
                findings = await self._run_black(py_args)
                all_findings.extend(findings)
            else:
                logger.warning("Black not installed — skipping")

        # 3. Pylint (deep analysis)
        if py_files and tools_config.get("pylint", {}).get("enabled", True):
            if check_tool_available("pylint"):
                findings = await self._run_pylint(py_args)
                all_findings.extend(findings)
            else:
                logger.warning("Pylint not installed — skipping")

        # 4. ESLint (JS/TS analysis)
        if js_files and tools_config.get("eslint", {}).get("enabled", True):
            if check_tool_available("eslint"):
                findings = await self._run_eslint(js_args)
                all_findings.extend(findings)
            else:
                logger.warning("ESLint not installed — skipping")

        return ScanResult(
            scanner_name=self.name,
            category=self.category,
            success=True,
            findings=all_findings,
        )

    async def _run_ruff(self, files: list[str]) -> list[Finding]:
        """Run Ruff linter with JSON output."""
        findings: list[Finding] = []

        cmd = ["ruff", "check", "--output-format", "json", "--no-fix"] + files

        result = await run_process(
            cmd,
            cwd=self.project_root,
            timeout=self.config.get("timeout", 60),
            scanner_name="ruff",
        )

        # Ruff exit code 1 means issues found
        if result.stdout.strip():
            try:
                issues = json.loads(result.stdout)
                for issue in issues:
                    # Ruff severity: all reported as errors by default
                    severity = Severity.LOW
                    code = issue.get("code", "")
                    # Security-related rules get higher severity
                    if code.startswith("S"):
                        severity = Severity.MEDIUM

                    location = issue.get("location", {})
                    findings.append(
                        Finding(
                            scanner="ruff",
                            category=ScannerCategory.LINTING,
                            severity=severity,
                            rule_id=code,
                            title=f"Ruff: {code}",
                            message=issue.get("message", ""),
                            file_path=issue.get("filename", ""),
                            line_number=location.get("row", 0),
                            column_number=location.get("column", 0),
                            suggestion=issue.get("fix", {}).get("message", "") if issue.get("fix") else "",
                        )
                    )
            except json.JSONDecodeError:
                logger.warning("Failed to parse Ruff output")

        logger.info("Ruff found %d issues", len(findings))
        return findings

    async def _run_black(self, files: list[str]) -> list[Finding]:
        """Run Black formatter check."""
        findings: list[Finding] = []

        cmd = ["black", "--check", "--diff", "--quiet"] + files

        result = await run_process(
            cmd,
            cwd=self.project_root,
            timeout=self.config.get("timeout", 60),
            scanner_name="black",
        )

        # Black exit code 1 means files would be reformatted
        if result.exit_code == 1:
            # Parse diff output to find affected files
            current_file = ""
            for line in result.stdout.splitlines():
                if line.startswith("--- "):
                    pass
                elif line.startswith("+++ "):
                    current_file = line[4:].strip()
                    if current_file.startswith("b/"):
                        current_file = current_file[2:]

            # Also check stderr for file list
            for line in result.stderr.splitlines():
                if line.strip().startswith("would reformat"):
                    file_name = line.strip().replace("would reformat ", "").strip()
                    findings.append(
                        Finding(
                            scanner="black",
                            category=ScannerCategory.LINTING,
                            severity=Severity.LOW,
                            rule_id="formatting",
                            title="Code Formatting",
                            message=f"File needs formatting: {file_name}",
                            file_path=file_name,
                            suggestion="Run 'black .' to auto-format",
                        )
                    )

            # If we didn't parse specific files, create a generic finding
            if not findings and result.exit_code == 1:
                findings.append(
                    Finding(
                        scanner="black",
                        category=ScannerCategory.LINTING,
                        severity=Severity.LOW,
                        rule_id="formatting",
                        title="Code Formatting Required",
                        message="One or more files need formatting",
                        suggestion="Run 'black .' to auto-format",
                    )
                )

        logger.info("Black found %d formatting issues", len(findings))
        return findings

    async def _run_pylint(self, files: list[str]) -> list[Finding]:
        """Run Pylint with JSON output."""
        findings: list[Finding] = []

        cmd = [
            "pylint",
            "--output-format=json",
            "--exit-zero",  # Don't fail — we'll evaluate the score ourselves
        ] + files

        result = await run_process(
            cmd,
            cwd=self.project_root,
            timeout=self.config.get("timeout", 60),
            scanner_name="pylint",
        )

        if result.stdout.strip():
            try:
                issues = json.loads(result.stdout)
                for issue in issues:
                    msg_type = issue.get("type", "convention")
                    severity = self._map_pylint_severity(msg_type)

                    findings.append(
                        Finding(
                            scanner="pylint",
                            category=ScannerCategory.LINTING,
                            severity=severity,
                            rule_id=issue.get("message-id", ""),
                            title=f"Pylint: {issue.get('symbol', '')}",
                            message=issue.get("message", ""),
                            file_path=issue.get("path", ""),
                            line_number=issue.get("line", 0),
                            column_number=issue.get("column", 0),
                            metadata={
                                "module": issue.get("module", ""),
                                "obj": issue.get("obj", ""),
                                "type": msg_type,
                            },
                        )
                    )
            except json.JSONDecodeError:
                logger.warning("Failed to parse Pylint output")

        logger.info("Pylint found %d issues", len(findings))
        return findings

    @staticmethod
    def _map_pylint_severity(msg_type: str) -> Severity:
        """Map Pylint message types to Severity enum."""
        mapping = {
            "fatal": Severity.CRITICAL,
            "error": Severity.HIGH,
            "warning": Severity.MEDIUM,
            "convention": Severity.INFO,
            "refactor": Severity.LOW,
            "information": Severity.INFO,
        }
        return mapping.get(msg_type.lower(), Severity.LOW)

    async def _run_eslint(self, files: list[str]) -> list[Finding]:
        """Run ESLint with JSON output."""
        findings: list[Finding] = []

        cmd = ["eslint", "-f", "json"] + files

        result = await run_process(
            cmd,
            cwd=self.project_root,
            timeout=self.config.get("timeout", 60),
            scanner_name="eslint",
        )

        if result.stdout.strip():
            try:
                issues = json.loads(result.stdout)
                for file_issue in issues:
                    file_path = file_issue.get("filePath", "")
                    for msg in file_issue.get("messages", []):
                        # severity: 1 is warning, 2 is error
                        severity = Severity.HIGH if msg.get("severity") == 2 else Severity.MEDIUM
                        
                        findings.append(
                            Finding(
                                scanner="eslint",
                                category=ScannerCategory.LINTING,
                                severity=severity,
                                rule_id=msg.get("ruleId") or "unknown",
                                title=f"ESLint: {msg.get('ruleId') or 'Syntax'}",
                                message=msg.get("message", ""),
                                file_path=file_path,
                                line_number=msg.get("line", 0),
                                column_number=msg.get("column", 0),
                            )
                        )
            except json.JSONDecodeError:
                logger.warning("Failed to parse ESLint output")

        logger.info("ESLint found %d issues", len(findings))
        return findings
