"""
Abstract base class for all scanner modules.

Every scanner in the pipeline implements this interface. The design enables:
- Pluggable scanners: add new scanners without modifying the orchestrator
- Consistent interface: all scanners produce ScanResult objects
- Tool isolation: each scanner wraps its own external tool(s)
- Graceful degradation: scanners skip cleanly if their tools aren't installed
"""

from __future__ import annotations

import abc
from pathlib import Path
from typing import Any

from cqpipeline.core.constants import ScannerCategory, Severity
from cqpipeline.core.models import Finding, ScanResult
from cqpipeline.utils.file_utils import filter_files_by_language, matches_glob_pattern
from cqpipeline.utils.logger import get_logger
from cqpipeline.utils.process import check_tool_available

logger = get_logger(__name__)


class BaseScanner(abc.ABC):
    """
    Abstract base class for pipeline scanners.

    Subclasses must implement:
        - name: scanner identifier
        - category: scanner category enum
        - scan(): the actual scanning logic
    """

    def __init__(
        self,
        config: dict,
        project_root: Path,
        allowlist: dict | None = None,
    ) -> None:
        self.config = config
        self.project_root = project_root
        self.allowlist = allowlist or {}

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique name identifier for this scanner."""
        ...

    @property
    @abc.abstractmethod
    def category(self) -> ScannerCategory:
        """Category this scanner belongs to."""
        ...

    @property
    def supported_languages(self) -> list[str]:
        """Languages this scanner supports. Empty = all languages."""
        return []

    @property
    def required_tools(self) -> list[str]:
        """External tools required by this scanner."""
        return []

    def check_prerequisites(self) -> tuple[bool, str]:
        """
        Check if all prerequisites are met for this scanner.

        Returns:
            Tuple of (available, reason).
        """
        for tool in self.required_tools:
            if not check_tool_available(tool):
                return False, f"Tool '{tool}' is not installed"
        return True, ""

    async def scan(self, files: list[Path]) -> ScanResult:
        """
        Execute the scanner on the given files.

        This method handles common pre/post-processing:
        1. Checks prerequisites
        2. Filters files by supported languages
        3. Calls _execute() (implemented by subclasses)
        4. Applies allowlist filtering
        5. Returns the final ScanResult
        """
        # Check prerequisites
        available, reason = self.check_prerequisites()
        if not available:
            logger.warning("Scanner '%s' skipped: %s", self.name, reason)
            return ScanResult(
                scanner_name=self.name,
                category=self.category,
                skipped=True,
                skip_reason=reason,
            )

        # Filter files by supported languages
        if self.supported_languages:
            files = filter_files_by_language(files, self.supported_languages)

        if not files:
            return ScanResult(
                scanner_name=self.name,
                category=self.category,
                success=True,
                files_scanned=0,
            )

        # Execute the actual scan
        result = await self._execute(files)
        result.files_scanned = len(files)

        # Apply allowlist filtering
        result.findings = self._apply_allowlist(result.findings)

        return result

    @abc.abstractmethod
    async def _execute(self, files: list[Path]) -> ScanResult:
        """
        Execute the actual scanning logic.

        Subclasses implement this method with their specific tool invocations.
        """
        ...

    def _apply_allowlist(self, findings: list[Finding]) -> list[Finding]:
        """Filter findings against the allowlist to remove false positives."""
        if not self.allowlist:
            return findings

        filtered: list[Finding] = []
        allowlisted_files = {
            entry["path"] for entry in self.allowlist.get("files", [])
        }
        allowlisted_patterns = {
            entry["pattern"] for entry in self.allowlist.get("patterns", [])
        }
        allowlisted_rules = {
            entry["rule_id"]
            for entry in self.allowlist.get("rules", [])
        }
        path_patterns = self.allowlist.get("path_patterns", [])

        # Scanner-specific allowlist entries
        scanner_allowlist = [
            entry
            for entry in self.allowlist.get("findings", [])
            if entry.get("scanner") == self.name
        ]
        scanner_rule_files = {
            (entry["rule_id"], entry.get("file", ""))
            for entry in scanner_allowlist
        }

        for finding in findings:
            # Check file allowlist
            if finding.file_path in allowlisted_files:
                logger.debug(
                    "Allowlisted (file): %s in %s",
                    finding.rule_id,
                    finding.file_path,
                )
                continue

            # Check pattern allowlist
            if finding.code_snippet in allowlisted_patterns:
                logger.debug("Allowlisted (pattern): %s", finding.code_snippet[:50])
                continue

            # Check rule allowlist
            if finding.rule_id in allowlisted_rules:
                logger.debug("Allowlisted (rule): %s", finding.rule_id)
                continue

            # Check path pattern allowlist
            if matches_glob_pattern(finding.file_path, path_patterns):
                logger.debug(
                    "Allowlisted (path pattern): %s", finding.file_path
                )
                continue

            # Check scanner-specific allowlist
            allowlisted = False
            for rule_id, file_pattern in scanner_rule_files:
                if finding.rule_id == rule_id:
                    if not file_pattern or matches_glob_pattern(
                        finding.file_path, [file_pattern]
                    ):
                        allowlisted = True
                        break
            if allowlisted:
                logger.debug(
                    "Allowlisted (scanner-specific): %s in %s",
                    finding.rule_id,
                    finding.file_path,
                )
                continue

            filtered.append(finding)

        removed_count = len(findings) - len(filtered)
        if removed_count > 0:
            logger.info(
                "Allowlist removed %d findings from scanner '%s'",
                removed_count,
                self.name,
            )

        return filtered

    @staticmethod
    def _map_severity(severity_str: str) -> Severity:
        """Map common severity strings from various tools to our Severity enum."""
        mapping = {
            # Common mappings
            "critical": Severity.CRITICAL,
            "error": Severity.HIGH,
            "high": Severity.HIGH,
            "warning": Severity.MEDIUM,
            "medium": Severity.MEDIUM,
            "warn": Severity.MEDIUM,
            "low": Severity.LOW,
            "info": Severity.INFO,
            "note": Severity.INFO,
            "convention": Severity.INFO,
            "refactor": Severity.LOW,
            # Bandit-specific
            "HIGH": Severity.HIGH,
            "MEDIUM": Severity.MEDIUM,
            "LOW": Severity.LOW,
        }
        return mapping.get(severity_str.lower(), Severity.MEDIUM)
