"""
Dependency Scanner — Software Composition Analysis (SCA).

Integrates:
- pip-audit: Audits Python packages against PyPI advisory database
- Safety: Cross-references packages against the Safety vulnerability DB

Why SCA matters:
- ~80% of modern application code comes from dependencies
- A single vulnerable dependency can compromise the entire application
- CVEs in popular packages (e.g., log4j) affect millions of projects
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


class DependencyScanner(BaseScanner):
    """Dependency vulnerability scanner using pip-audit and Safety."""

    @property
    def name(self) -> str:
        return "dependencies"

    @property
    def category(self) -> ScannerCategory:
        return ScannerCategory.DEPENDENCIES

    @property
    def supported_languages(self) -> list[str]:
        # Dependency scanning is not file-based
        return []

    async def _execute(self, files: list[Path]) -> ScanResult:
        """Run dependency scanning tools."""
        all_findings: list[Finding] = []
        tools_config = self.config.get("tools", {})

        # 1. pip-audit
        if tools_config.get("pip_audit", {}).get("enabled", True):
            if check_tool_available("pip-audit"):
                findings = await self._run_pip_audit()
                all_findings.extend(findings)
            else:
                logger.warning("pip-audit not installed — skipping")

        # 2. Safety
        if tools_config.get("safety", {}).get("enabled", True):
            if check_tool_available("safety"):
                findings = await self._run_safety()
                all_findings.extend(findings)
            else:
                logger.warning("Safety not installed — skipping")

        # Deduplicate (both tools may find the same CVE)
        all_findings = self._deduplicate(all_findings)

        return ScanResult(
            scanner_name=self.name,
            category=self.category,
            success=True,
            findings=all_findings,
        )

    async def _run_pip_audit(self) -> list[Finding]:
        """Run pip-audit to check installed packages for vulnerabilities."""
        findings: list[Finding] = []

        cmd = [
            "pip-audit",
            "--format", "json",
            "--progress-spinner", "off",
        ]

        # Check for requirements file
        req_file = self.project_root / "requirements.txt"
        if req_file.exists():
            cmd.extend(["--requirement", str(req_file)])

        result = await run_process(
            cmd,
            cwd=self.project_root,
            timeout=self.config.get("timeout", 60),
            scanner_name="pip-audit",
        )

        if result.stdout.strip():
            try:
                output = json.loads(result.stdout)
                dependencies = output.get("dependencies", [])

                for dep in dependencies:
                    vulns = dep.get("vulns", [])
                    for vuln in vulns:
                        severity = self._cvss_to_severity(
                            vuln.get("fix_versions", [])
                        )
                        cve_id = vuln.get("id", "")

                        findings.append(
                            Finding(
                                scanner="pip-audit",
                                category=ScannerCategory.DEPENDENCIES,
                                severity=severity,
                                rule_id=cve_id,
                                title=f"Vulnerable dependency: {dep.get('name', '')}",
                                message=(
                                    f"{dep.get('name', '')}=={dep.get('version', '')} "
                                    f"has vulnerability {cve_id}: {vuln.get('description', '')}"
                                ),
                                cve_id=cve_id,
                                suggestion=(
                                    f"Upgrade to: {', '.join(vuln.get('fix_versions', []))}"
                                    if vuln.get("fix_versions")
                                    else "No fix available yet"
                                ),
                                metadata={
                                    "package": dep.get("name", ""),
                                    "installed_version": dep.get("version", ""),
                                    "fix_versions": vuln.get("fix_versions", []),
                                    "aliases": vuln.get("aliases", []),
                                },
                            )
                        )
            except json.JSONDecodeError:
                logger.warning("Failed to parse pip-audit output")

        logger.info("pip-audit found %d vulnerabilities", len(findings))
        return findings

    async def _run_safety(self) -> list[Finding]:
        """Run Safety to check dependencies against the Safety DB."""
        findings: list[Finding] = []

        cmd = [
            "safety",
            "check",
            "--json",
            "--output", "json",
        ]

        # Check for requirements file
        req_file = self.project_root / "requirements.txt"
        if req_file.exists():
            cmd.extend(["--file", str(req_file)])

        result = await run_process(
            cmd,
            cwd=self.project_root,
            timeout=self.config.get("timeout", 60),
            scanner_name="safety",
        )

        if result.stdout.strip():
            try:
                output = json.loads(result.stdout)
                vulnerabilities = output if isinstance(output, list) else output.get("vulnerabilities", [])

                for vuln in vulnerabilities:
                    if isinstance(vuln, list) and len(vuln) >= 5:
                        # Old Safety format: [package, affected, installed, description, id]
                        findings.append(
                            Finding(
                                scanner="safety",
                                category=ScannerCategory.DEPENDENCIES,
                                severity=Severity.HIGH,
                                rule_id=str(vuln[4]) if len(vuln) > 4 else "",
                                title=f"Vulnerable dependency: {vuln[0]}",
                                message=vuln[3] if len(vuln) > 3 else "Vulnerability detected",
                                metadata={
                                    "package": vuln[0],
                                    "affected_versions": vuln[1] if len(vuln) > 1 else "",
                                    "installed_version": vuln[2] if len(vuln) > 2 else "",
                                },
                            )
                        )
                    elif isinstance(vuln, dict):
                        # New Safety format
                        findings.append(
                            Finding(
                                scanner="safety",
                                category=ScannerCategory.DEPENDENCIES,
                                severity=self._map_severity(
                                    vuln.get("severity", "medium")
                                ),
                                rule_id=vuln.get("vulnerability_id", ""),
                                title=f"Vulnerable: {vuln.get('package_name', '')}",
                                message=vuln.get("advisory", ""),
                                cve_id=vuln.get("CVE", ""),
                                metadata={
                                    "package": vuln.get("package_name", ""),
                                    "installed_version": vuln.get("analyzed_version", ""),
                                    "vulnerable_versions": vuln.get("vulnerable_versions", ""),
                                },
                            )
                        )
            except json.JSONDecodeError:
                logger.warning("Failed to parse Safety output")

        logger.info("Safety found %d vulnerabilities", len(findings))
        return findings

    def _deduplicate(self, findings: list[Finding]) -> list[Finding]:
        """Remove duplicate vulnerability findings across tools."""
        seen: set[str] = set()
        unique: list[Finding] = []

        for finding in findings:
            # Deduplicate by CVE ID or package+rule_id
            key = finding.cve_id or f"{finding.metadata.get('package', '')}:{finding.rule_id}"
            if key and key not in seen:
                seen.add(key)
                unique.append(finding)
            elif not key:
                unique.append(finding)

        return unique

    @staticmethod
    def _cvss_to_severity(fix_versions: list[str]) -> Severity:
        """
        Map vulnerability to severity.

        Without CVSS score from pip-audit, we default to HIGH
        since all reported vulnerabilities are security-relevant.
        """
        return Severity.HIGH
