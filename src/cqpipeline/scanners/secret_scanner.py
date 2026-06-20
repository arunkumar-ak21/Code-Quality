"""
Secret Detection Scanner — Defense-in-depth with multiple tools.

Integrates:
- Gitleaks: Fast regex-based secret detection (primary)
- detect-secrets: Entropy-based + regex detection (secondary)
- TruffleHog: Git history scanning (CI/CD mode only)

Each tool has different strengths:
- Gitleaks: Best regex patterns, fastest, excellent for pre-commit
- detect-secrets: Entropy analysis catches secrets that regex misses
- TruffleHog: Scans full git history for rotated/removed secrets
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from cqpipeline.core.constants import ScannerCategory, Severity
from cqpipeline.core.models import Finding, ScanResult
from cqpipeline.scanners.base import BaseScanner
from cqpipeline.utils.logger import get_logger
from cqpipeline.utils.process import check_tool_available, run_process

logger = get_logger(__name__)


class SecretScanner(BaseScanner):
    """Multi-tool secret detection scanner."""

    @property
    def name(self) -> str:
        return "secrets"

    @property
    def category(self) -> ScannerCategory:
        return ScannerCategory.SECRETS

    @property
    def required_tools(self) -> list[str]:
        # Don't require all tools — we gracefully skip missing ones
        return []

    async def _execute(self, files: list[Path]) -> ScanResult:
        """Run all enabled secret detection tools and merge results."""
        all_findings: list[Finding] = []
        tools_config = self.config.get("tools", {})

        # 1. Gitleaks
        if tools_config.get("gitleaks", {}).get("enabled", True):
            if check_tool_available("gitleaks"):
                findings = await self._run_gitleaks(files)
                all_findings.extend(findings)
            else:
                logger.warning("Gitleaks not installed — skipping")

        # 2. detect-secrets
        if tools_config.get("detect_secrets", {}).get("enabled", True):
            if check_tool_available("detect-secrets"):
                findings = await self._run_detect_secrets(files)
                all_findings.extend(findings)
            else:
                logger.warning("detect-secrets not installed — skipping")

        # 3. TruffleHog (CI/CD only — slow for pre-commit)
        if tools_config.get("trufflehog", {}).get("enabled", False):
            if check_tool_available("trufflehog"):
                findings = await self._run_trufflehog()
                all_findings.extend(findings)
            else:
                logger.warning("TruffleHog not installed — skipping")

        # 4. Custom pattern matching (always runs — no external tool needed)
        custom_findings = await self._run_custom_patterns(files)
        all_findings.extend(custom_findings)

        # Deduplicate findings
        all_findings = self._deduplicate(all_findings)

        return ScanResult(
            scanner_name=self.name,
            category=self.category,
            success=True,
            findings=all_findings,
        )

    async def _run_gitleaks(self, files: list[Path]) -> list[Finding]:
        """Run Gitleaks on the project directory."""
        findings: list[Finding] = []

        cmd = [
            "gitleaks",
            "detect",
            "--source", str(self.project_root),
            "--report-format", "json",
            "--report-path", "/dev/stdout",
            "--no-git",  # Scan files, not git history
            "--verbose",
        ]

        # Add custom config if specified
        config_path = self.config.get("tools", {}).get("gitleaks", {}).get("config_path", "")
        if config_path:
            cmd.extend(["--config", config_path])

        result = await run_process(
            cmd,
            cwd=self.project_root,
            timeout=self.config.get("timeout", 30),
            scanner_name="gitleaks",
        )

        # Gitleaks exit code 1 means leaks found (not an error)
        if result.stdout.strip():
            try:
                leaks = json.loads(result.stdout)
                if isinstance(leaks, list):
                    for leak in leaks:
                        findings.append(
                            Finding(
                                scanner="gitleaks",
                                category=ScannerCategory.SECRETS,
                                severity=Severity.CRITICAL,
                                rule_id=leak.get("RuleID", "unknown"),
                                title=f"Secret Detected: {leak.get('Description', 'Unknown')}",
                                message=leak.get("Description", "Potential secret detected"),
                                file_path=leak.get("File", ""),
                                line_number=leak.get("StartLine", 0),
                                code_snippet=leak.get("Match", "")[:100],  # Truncate
                                metadata={
                                    "entropy": leak.get("Entropy", 0),
                                    "commit": leak.get("Commit", ""),
                                    "author": leak.get("Author", ""),
                                },
                            )
                        )
            except json.JSONDecodeError:
                logger.warning("Failed to parse Gitleaks output")

        logger.info("Gitleaks found %d secrets", len(findings))
        return findings

    async def _run_detect_secrets(self, files: list[Path]) -> list[Finding]:
        """Run detect-secrets for entropy-based detection."""
        findings: list[Finding] = []

        # Create a file list for detect-secrets
        file_list = [str(f) for f in files if f.exists()]
        if not file_list:
            return findings

        cmd = [
            "detect-secrets",
            "scan",
            "--list-all-plugins",
        ]

        # Run scan on the project
        scan_cmd = [
            "detect-secrets",
            "scan",
            str(self.project_root),
        ]

        result = await run_process(
            scan_cmd,
            cwd=self.project_root,
            timeout=self.config.get("timeout", 30),
            scanner_name="detect-secrets",
        )

        if result.stdout.strip():
            try:
                scan_results = json.loads(result.stdout)
                results_dict = scan_results.get("results", {})
                for file_path, secrets in results_dict.items():
                    for secret in secrets:
                        findings.append(
                            Finding(
                                scanner="detect-secrets",
                                category=ScannerCategory.SECRETS,
                                severity=Severity.CRITICAL,
                                rule_id=secret.get("type", "unknown"),
                                title=f"Secret Detected ({secret.get('type', 'unknown')})",
                                message=f"Potential {secret.get('type', 'secret')} detected",
                                file_path=file_path,
                                line_number=secret.get("line_number", 0),
                                metadata={
                                    "hashed_secret": secret.get("hashed_secret", ""),
                                    "is_verified": secret.get("is_verified", False),
                                },
                            )
                        )
            except json.JSONDecodeError:
                logger.warning("Failed to parse detect-secrets output")

        logger.info("detect-secrets found %d secrets", len(findings))
        return findings

    async def _run_trufflehog(self) -> list[Finding]:
        """Run TruffleHog for git history scanning."""
        findings: list[Finding] = []

        cmd = [
            "trufflehog",
            "filesystem",
            str(self.project_root),
            "--json",
            "--no-update",
        ]

        result = await run_process(
            cmd,
            cwd=self.project_root,
            timeout=self.config.get("timeout", 60),
            scanner_name="trufflehog",
        )

        if result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                try:
                    finding_data = json.loads(line)
                    source_meta = finding_data.get("SourceMetadata", {}).get("Data", {})
                    findings.append(
                        Finding(
                            scanner="trufflehog",
                            category=ScannerCategory.SECRETS,
                            severity=Severity.CRITICAL,
                            rule_id=finding_data.get("DetectorName", "unknown"),
                            title=f"Secret in History: {finding_data.get('DetectorName', '')}",
                            message=f"Secret detected by {finding_data.get('DetectorName', 'unknown')}",
                            file_path=source_meta.get("Filesystem", {}).get("file", ""),
                            line_number=source_meta.get("Filesystem", {}).get("line", 0),
                            metadata={
                                "verified": finding_data.get("Verified", False),
                                "detector_type": finding_data.get("DetectorType", ""),
                            },
                        )
                    )
                except json.JSONDecodeError:
                    continue

        logger.info("TruffleHog found %d secrets", len(findings))
        return findings

    async def _run_custom_patterns(self, files: list[Path]) -> list[Finding]:
        """Run custom regex-based secret detection on file contents."""
        findings: list[Finding] = []

        # Load custom patterns from config
        try:
            from cqpipeline.core.config import PipelineConfigLoader
            loader = PipelineConfigLoader(project_root=self.project_root)
            patterns_config = loader.load_secret_patterns()
        except Exception:
            patterns_config = {"patterns": []}

        patterns = patterns_config.get("patterns", [])
        if not patterns:
            return findings

        for file_path in files:
            if not file_path.exists() or not file_path.is_file():
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            for pattern_def in patterns:
                regex = pattern_def.get("regex", "")
                if not regex:
                    continue

                try:
                    matches = re.finditer(regex, content)
                    for match in matches:
                        line_num = content[:match.start()].count("\n") + 1
                        rel_path = str(file_path.relative_to(self.project_root))

                        findings.append(
                            Finding(
                                scanner="custom-patterns",
                                category=ScannerCategory.SECRETS,
                                severity=self._map_severity(
                                    pattern_def.get("severity", "high")
                                ),
                                rule_id=pattern_def.get("id", "custom"),
                                title=pattern_def.get("description", "Custom pattern match"),
                                message=pattern_def.get("description", "Custom secret pattern detected"),
                                file_path=rel_path,
                                line_number=line_num,
                                code_snippet=match.group(0)[:50] + "..." if len(match.group(0)) > 50 else match.group(0),
                            )
                        )
                except re.error as e:
                    logger.warning("Invalid regex pattern '%s': %s", pattern_def.get("id"), e)

        logger.info("Custom patterns found %d secrets", len(findings))
        return findings

    def _deduplicate(self, findings: list[Finding]) -> list[Finding]:
        """Remove duplicate findings from multiple tools detecting the same secret."""
        seen: set[tuple[str, int, str]] = set()
        unique: list[Finding] = []

        for finding in findings:
            key = (finding.file_path, finding.line_number, finding.rule_id)
            if key not in seen:
                seen.add(key)
                unique.append(finding)

        removed = len(findings) - len(unique)
        if removed > 0:
            logger.debug("Deduplicated %d findings", removed)

        return unique
