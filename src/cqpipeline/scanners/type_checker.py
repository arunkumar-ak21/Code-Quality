"""
Type Checker Scanner — MyPy integration for static type checking.

MyPy catches type errors at analysis time that would otherwise become
runtime errors. It's particularly valuable for:
- Catching None-related bugs
- Ensuring API contracts are respected
- Validating function signatures
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


class TypeChecker(BaseScanner):
    """MyPy-based static type checker."""

    @property
    def name(self) -> str:
        return "type_checking"

    @property
    def category(self) -> ScannerCategory:
        return ScannerCategory.TYPE_CHECKING

    @property
    def supported_languages(self) -> list[str]:
        return ["python"]

    @property
    def required_tools(self) -> list[str]:
        return ["mypy"]

    async def _execute(self, files: list[Path]) -> ScanResult:
        """Run MyPy type checking."""
        py_files = [f for f in files if f.suffix in (".py", ".pyw")]
        if not py_files:
            return ScanResult(
                scanner_name=self.name,
                category=self.category,
                success=True,
            )

        findings = await self._run_mypy(py_files)

        return ScanResult(
            scanner_name=self.name,
            category=self.category,
            success=True,
            findings=findings,
        )

    async def _run_mypy(self, files: list[Path]) -> list[Finding]:
        """Run MyPy on the given files."""
        findings: list[Finding] = []
        tools_config = self.config.get("tools", {}).get("mypy", {})

        file_args = [str(f) for f in files]

        cmd = [
            "mypy",
            "--no-error-summary",
            "--show-column-numbers",
            "--no-pretty",
        ]

        if tools_config.get("strict", False):
            cmd.append("--strict")

        cmd.extend(file_args)

        result = await run_process(
            cmd,
            cwd=self.project_root,
            timeout=self.config.get("timeout", 60),
            scanner_name="mypy",
        )

        # Parse MyPy text output (file:line:col: severity: message)
        for line in result.stdout.splitlines():
            if ": error:" in line or ": warning:" in line or ": note:" in line:
                parsed = self._parse_mypy_line(line)
                if parsed:
                    findings.append(parsed)

        logger.info("MyPy found %d type errors", len(findings))
        return findings

    def _parse_mypy_line(self, line: str) -> Finding | None:
        """Parse a single MyPy output line into a Finding."""
        try:
            # Format: file:line:col: severity: message  [error-code]
            parts = line.split(":", 3)
            if len(parts) < 4:
                return None

            file_path = parts[0].strip()
            line_number = int(parts[1].strip()) if parts[1].strip().isdigit() else 0

            # The rest contains severity and message
            rest = parts[3].strip() if len(parts) > 3 else parts[2].strip()

            severity = Severity.MEDIUM
            if "error:" in rest:
                severity = Severity.HIGH
                message = rest.split("error:", 1)[1].strip()
            elif "warning:" in rest:
                severity = Severity.MEDIUM
                message = rest.split("warning:", 1)[1].strip()
            elif "note:" in rest:
                severity = Severity.INFO
                message = rest.split("note:", 1)[1].strip()
            else:
                message = rest

            # Extract error code (e.g., [assignment])
            rule_id = ""
            if message.endswith("]") and "[" in message:
                bracket_start = message.rfind("[")
                rule_id = message[bracket_start + 1 : -1]
                message = message[:bracket_start].strip()

            column = int(parts[2].strip()) if len(parts) > 3 and parts[2].strip().isdigit() else 0

            return Finding(
                scanner="mypy",
                category=ScannerCategory.TYPE_CHECKING,
                severity=severity,
                rule_id=rule_id,
                title=f"Type Error: {rule_id}" if rule_id else "Type Error",
                message=message,
                file_path=file_path,
                line_number=line_number,
                column_number=column,
            )

        except (ValueError, IndexError) as e:
            logger.debug("Failed to parse MyPy line: %s (%s)", line, e)
            return None
