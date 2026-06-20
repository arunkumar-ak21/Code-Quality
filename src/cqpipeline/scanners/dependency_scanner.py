"""
Dependency Scanner — Software Composition Analysis (SCA).

Integrates:
- pip-audit: Audits Python requirements files against Python advisory data
- Safety: Optional secondary Python dependency vulnerability scanner

Important behavior:
- Scans requirements*.txt files anywhere inside the target project, not only the
  repository root. This is required for CI test folders such as
  test-10-wrong/requirements.txt.
- Never silently passes when a dependency manifest exists but the audit command
  fails before producing JSON; that is reported as a blocking finding so risky
  dependencies do not slip through as "passed".
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cqpipeline.core.constants import ScannerCategory, Severity
from cqpipeline.core.models import Finding, ScanResult
from cqpipeline.scanners.base import BaseScanner
from cqpipeline.utils.file_utils import get_relative_path
from cqpipeline.utils.logger import get_logger
from cqpipeline.utils.process import check_tool_available, run_process

logger = get_logger(__name__)


IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".eggs",
    ".tox",
    "htmlcov",
    "reports",
}


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
        # Dependency scanning is manifest-based, not source-file-language-based.
        return []

    async def _execute(self, files: list[Path]) -> ScanResult:
        """Run dependency scanning tools."""
        all_findings: list[Finding] = []
        tools_config = self.config.get("tools", {})
        requirements_files = self._discover_requirements_files()
        node_package_locks = self._discover_node_package_locks()

        if not requirements_files and not node_package_locks:
            logger.info("No supported dependency manifests found for dependency scanning")
            return ScanResult(
                scanner_name=self.name,
                category=self.category,
                success=True,
                findings=[],
            )

        # 1. pip-audit. This is the primary scanner and should catch old vulnerable
        # packages like django==1.2, requests==2.19.1, and pyyaml==3.13.
        if tools_config.get("pip_audit", {}).get("enabled", True):
            if check_tool_available("pip-audit"):
                findings = await self._run_pip_audit(requirements_files)
                all_findings.extend(findings)
            else:
                all_findings.append(
                    self._tool_missing_finding(
                        "pip-audit",
                        "pip-audit is not installed, so Python dependency vulnerabilities could not be checked.",
                    )
                )

        # 2. Safety. Optional secondary scanner. Safety can require API/auth in newer
        # versions, so failures here are reported but pip-audit remains the primary
        # dependency gate.
        if tools_config.get("safety", {}).get("enabled", True):
            if check_tool_available("safety"):
                findings = await self._run_safety(requirements_files)
                all_findings.extend(findings)
            else:
                logger.warning("Safety not installed — skipping secondary dependency scan")

        if node_package_locks and tools_config.get("npm_audit", {}).get("enabled", True):
            if check_tool_available("npm"):
                all_findings.extend(await self._run_npm_audit(node_package_locks))
            else:
                logger.warning("npm not installed — skipping npm audit")

        all_findings = self._deduplicate(all_findings)

        return ScanResult(
            scanner_name=self.name,
            category=self.category,
            success=True,
            findings=all_findings,
        )

    def _discover_requirements_files(self) -> list[Path]:
        """Find Python requirements files throughout the target repository."""
        candidates: list[Path] = []
        for path in self.project_root.rglob("requirements*.txt"):
            if not path.is_file():
                continue
            if self._is_ignored_path(path):
                continue
            candidates.append(path)
        return sorted(candidates, key=lambda item: item.relative_to(self.project_root).as_posix())

    def _is_ignored_path(self, path: Path) -> bool:
        try:
            parts = path.relative_to(self.project_root).parts
        except ValueError:
            parts = path.parts
        return any(part in IGNORED_DIRS for part in parts)


    def _discover_node_package_locks(self) -> list[Path]:
        """Find npm lockfiles throughout the target repository."""
        candidates: list[Path] = []
        for pattern in ("package-lock.json", "npm-shrinkwrap.json"):
            for path in self.project_root.rglob(pattern):
                if path.is_file() and not self._is_ignored_path(path):
                    candidates.append(path)
        return sorted(candidates, key=lambda item: item.relative_to(self.project_root).as_posix())

    async def _run_pip_audit(self, requirements_files: list[Path]) -> list[Finding]:
        """Run pip-audit against every discovered requirements file."""
        findings: list[Finding] = []

        for req_file in requirements_files:
            rel_path = get_relative_path(req_file, self.project_root)
            cmd = [
                "pip-audit",
                "--format",
                "json",
                "--progress-spinner",
                "off",
                "--requirement",
                str(req_file),
            ]

            result = await run_process(
                cmd,
                cwd=self.project_root,
                timeout=self.config.get("timeout", 60),
                scanner_name="pip-audit",
            )

            parsed_any = False
            if result.stdout.strip():
                try:
                    output = json.loads(result.stdout)
                    parsed_any = True
                    dependencies = output.get("dependencies", []) if isinstance(output, dict) else []
                    for dep in dependencies:
                        findings.extend(self._findings_from_pip_audit_dependency(dep, rel_path))
                except json.JSONDecodeError:
                    logger.warning("Failed to parse pip-audit output for %s", rel_path)

            # pip-audit exits with 1 when vulnerabilities are found, which is fine
            # because we parse stdout. But if it exits non-zero without valid JSON,
            # do not let that manifest pass silently.
            if result.exit_code != 0 and not parsed_any:
                message = (result.stderr or result.stdout or "pip-audit failed without JSON output").strip()
                findings.append(
                    Finding(
                        scanner="pip-audit",
                        category=ScannerCategory.DEPENDENCIES,
                        severity=Severity.HIGH,
                        rule_id="PIP-AUDIT-FAILED",
                        title="Dependency audit failed",
                        message=f"pip-audit could not audit {rel_path}: {message[:1000]}",
                        file_path=rel_path,
                        suggestion=(
                            "Fix the requirements file so pip-audit can resolve it, or review the dependency versions manually. "
                            "The pipeline fails closed instead of silently passing an unaudited manifest."
                        ),
                        metadata={
                            "requirements_file": rel_path,
                            "exit_code": result.exit_code,
                        },
                    )
                )

        logger.info("pip-audit found %d dependency findings", len(findings))
        return findings

    def _findings_from_pip_audit_dependency(self, dep: dict[str, Any], req_file: str) -> list[Finding]:
        findings: list[Finding] = []
        package_name = str(dep.get("name") or "")
        installed_version = str(dep.get("version") or "")

        for vuln in dep.get("vulns", []) or []:
            cve_id = str(vuln.get("id") or "")
            aliases = [str(alias) for alias in (vuln.get("aliases") or [])]
            fix_versions = [str(version) for version in (vuln.get("fix_versions") or [])]
            description = str(vuln.get("description") or "Known vulnerability detected")

            findings.append(
                Finding(
                    scanner="pip-audit",
                    category=ScannerCategory.DEPENDENCIES,
                    severity=Severity.HIGH,
                    rule_id=cve_id or "PIP-AUDIT-VULN",
                    title=f"Vulnerable dependency: {package_name}",
                    message=(
                        f"{package_name}=={installed_version} in {req_file} has vulnerability "
                        f"{cve_id or ', '.join(aliases) or 'unknown'}: {description}"
                    ),
                    file_path=req_file,
                    cve_id=cve_id,
                    suggestion=(
                        f"Upgrade to: {', '.join(fix_versions)}"
                        if fix_versions
                        else "Upgrade this dependency to a non-vulnerable version."
                    ),
                    metadata={
                        "package": package_name,
                        "installed_version": installed_version,
                        "fix_versions": fix_versions,
                        "aliases": aliases,
                        "requirements_file": req_file,
                    },
                )
            )
        return findings

    async def _run_safety(self, requirements_files: list[Path]) -> list[Finding]:
        """Run Safety against every discovered requirements file."""
        findings: list[Finding] = []

        for req_file in requirements_files:
            rel_path = get_relative_path(req_file, self.project_root)
            cmd = [
                "safety",
                "check",
                "--json",
                "--output",
                "json",
                "--file",
                str(req_file),
            ]

            result = await run_process(
                cmd,
                cwd=self.project_root,
                timeout=self.config.get("timeout", 60),
                scanner_name="safety",
            )

            if not result.stdout.strip():
                if result.exit_code != 0:
                    logger.warning("Safety failed for %s: %s", rel_path, result.stderr[:500])
                continue

            try:
                output = json.loads(result.stdout)
                vulnerabilities = self._extract_safety_vulnerabilities(output)
                for vuln in vulnerabilities:
                    finding = self._finding_from_safety_vulnerability(vuln, rel_path)
                    if finding:
                        findings.append(finding)
            except json.JSONDecodeError:
                logger.warning("Failed to parse Safety output for %s", rel_path)

        logger.info("Safety found %d dependency findings", len(findings))
        return findings

    def _extract_safety_vulnerabilities(self, output: Any) -> list[Any]:
        if isinstance(output, list):
            return output
        if not isinstance(output, dict):
            return []
        if isinstance(output.get("vulnerabilities"), list):
            return output["vulnerabilities"]
        if isinstance(output.get("issues"), list):
            return output["issues"]
        return []

    def _finding_from_safety_vulnerability(self, vuln: Any, req_file: str) -> Finding | None:
        if isinstance(vuln, list) and len(vuln) >= 5:
            return Finding(
                scanner="safety",
                category=ScannerCategory.DEPENDENCIES,
                severity=Severity.HIGH,
                rule_id=str(vuln[4]) if len(vuln) > 4 else "SAFETY-VULN",
                title=f"Vulnerable dependency: {vuln[0]}",
                message=str(vuln[3]) if len(vuln) > 3 else "Vulnerability detected",
                file_path=req_file,
                metadata={
                    "package": vuln[0],
                    "affected_versions": vuln[1] if len(vuln) > 1 else "",
                    "installed_version": vuln[2] if len(vuln) > 2 else "",
                    "requirements_file": req_file,
                },
            )

        if isinstance(vuln, dict):
            package_name = str(
                vuln.get("package_name")
                or vuln.get("package")
                or vuln.get("name")
                or ""
            )
            installed_version = str(
                vuln.get("analyzed_version")
                or vuln.get("installed_version")
                or vuln.get("version")
                or ""
            )
            return Finding(
                scanner="safety",
                category=ScannerCategory.DEPENDENCIES,
                severity=self._map_severity(str(vuln.get("severity") or "high")),
                rule_id=str(vuln.get("vulnerability_id") or vuln.get("id") or "SAFETY-VULN"),
                title=f"Vulnerable dependency: {package_name}",
                message=str(vuln.get("advisory") or vuln.get("description") or "Vulnerability detected"),
                file_path=req_file,
                cve_id=str(vuln.get("CVE") or vuln.get("cve") or ""),
                metadata={
                    "package": package_name,
                    "installed_version": installed_version,
                    "vulnerable_versions": vuln.get("vulnerable_versions", ""),
                    "requirements_file": req_file,
                },
            )

        return None

    async def _run_npm_audit(self, lockfiles: list[Path]) -> list[Finding]:
        """Run npm audit for projects that have package-lock.json."""
        findings: list[Finding] = []
        for lockfile in lockfiles:
            rel_path = get_relative_path(lockfile, self.project_root)
            cwd = lockfile.parent
            result = await run_process(
                ["npm", "audit", "--json", "--audit-level=low"],
                cwd=cwd,
                timeout=self.config.get("timeout", 60),
                scanner_name="npm-audit",
            )
            if not result.stdout.strip():
                if result.exit_code != 0:
                    findings.append(Finding(
                        scanner="npm-audit",
                        category=ScannerCategory.DEPENDENCIES,
                        severity=Severity.HIGH,
                        rule_id="NPM-AUDIT-FAILED",
                        title="npm audit failed",
                        message=((result.stderr or result.stdout or "npm audit failed without JSON output").strip())[:1000],
                        file_path=rel_path,
                        suggestion="Ensure package.json/package-lock.json are valid and run npm audit locally.",
                    ))
                continue
            try:
                output = json.loads(result.stdout)
            except json.JSONDecodeError:
                continue
            vulnerabilities = output.get("vulnerabilities") if isinstance(output, dict) else None
            if not isinstance(vulnerabilities, dict):
                continue
            for package_name, vuln in vulnerabilities.items():
                via = vuln.get("via") or []
                severity = self._map_severity(str(vuln.get("severity") or "high"))
                title = f"Vulnerable npm dependency: {package_name}"
                messages = []
                advisory_ids = []
                for item in via:
                    if isinstance(item, dict):
                        advisory_ids.append(str(item.get("source") or item.get("url") or item.get("title") or "NPM-AUDIT"))
                        messages.append(str(item.get("title") or item.get("url") or "npm advisory"))
                    else:
                        messages.append(str(item))
                findings.append(Finding(
                    scanner="npm-audit",
                    category=ScannerCategory.DEPENDENCIES,
                    severity=severity,
                    rule_id=advisory_ids[0] if advisory_ids else "NPM-AUDIT-VULN",
                    title=title,
                    message="; ".join(messages)[:2000] or title,
                    file_path=rel_path,
                    suggestion=str(vuln.get("fixAvailable") or "Run npm audit fix or upgrade the affected package."),
                    metadata={
                        "package": package_name,
                        "installed_version": str(vuln.get("range") or ""),
                        "lockfile": rel_path,
                    },
                ))
        return findings

    def _tool_missing_finding(self, tool_name: str, message: str) -> Finding:
        return Finding(
            scanner=tool_name,
            category=ScannerCategory.DEPENDENCIES,
            severity=Severity.HIGH,
            rule_id=f"{tool_name.upper()}-MISSING",
            title=f"Dependency scanner missing: {tool_name}",
            message=message,
            suggestion=(
                f"Install the scanner extras used by the workflow, for example: "
                f"pip install -e '.[scanners-linux]'"
            ),
        )

    def _deduplicate(self, findings: list[Finding]) -> list[Finding]:
        """Remove duplicate vulnerability findings across tools."""
        seen: set[str] = set()
        unique: list[Finding] = []

        for finding in findings:
            package = str(finding.metadata.get("package", "")).lower()
            version = str(finding.metadata.get("installed_version", ""))
            req_file = str(finding.metadata.get("requirements_file", finding.file_path or ""))
            vuln_id = finding.cve_id or finding.rule_id or finding.title
            key = f"{req_file}:{package}:{version}:{vuln_id}"
            if key not in seen:
                seen.add(key)
                unique.append(finding)

        return unique

    @staticmethod
    def _map_severity(value: str) -> Severity:
        normalized = str(value or "").strip().lower()
        if normalized in {"critical", "crit"}:
            return Severity.CRITICAL
        if normalized in {"high", "important"}:
            return Severity.HIGH
        if normalized in {"medium", "moderate", "moderate severity"}:
            return Severity.MEDIUM
        if normalized in {"low", "minor"}:
            return Severity.LOW
        return Severity.HIGH
