"""
File Scanner — detects .env files, large files, debug statements, and dangerous functions.

This scanner requires NO external tools — it uses Python's built-in pathlib,
re, and ast modules. It runs instantly and catches common issues that other
scanners might miss.
"""

from __future__ import annotations

import re
from pathlib import Path

from cqpipeline.core.constants import (
    DANGEROUS_FUNCTIONS,
    DEBUG_PATTERNS,
    ScannerCategory,
    Severity,
)
from cqpipeline.core.models import Finding, ScanResult
from cqpipeline.scanners.base import BaseScanner
from cqpipeline.utils.file_utils import (
    detect_language,
    get_file_size,
    get_relative_path,
    read_file_safe,
)
from cqpipeline.utils.logger import get_logger

logger = get_logger(__name__)


class FileScanner(BaseScanner):
    """File-level scanner for .env files, large files, debug statements."""

    @property
    def name(self) -> str:
        return "files"

    @property
    def category(self) -> ScannerCategory:
        return ScannerCategory.FILES

    async def _execute(self, files: list[Path]) -> ScanResult:
        """Run all file-level checks."""
        all_findings: list[Finding] = []

        for file_path in files:
            rel_path = get_relative_path(file_path, self.project_root)

            # 1. Check for .env files
            env_findings = self._check_env_file(file_path, rel_path)
            all_findings.extend(env_findings)

            # 2. Check for large files
            size_findings = self._check_file_size(file_path, rel_path)
            all_findings.extend(size_findings)

            # 3. Check for blocked file patterns (private keys, certs)
            pattern_findings = self._check_blocked_patterns(file_path, rel_path)
            all_findings.extend(pattern_findings)

            # 4. Check for debug statements
            debug_findings = self._check_debug_statements(file_path, rel_path)
            all_findings.extend(debug_findings)

            # 5. Check for dangerous functions
            danger_findings = self._check_dangerous_functions(file_path, rel_path)
            all_findings.extend(danger_findings)

        return ScanResult(
            scanner_name=self.name,
            category=self.category,
            success=True,
            findings=all_findings,
        )

    def _check_env_file(self, file_path: Path, rel_path: str) -> list[Finding]:
        """Check if the file is a .env file that shouldn't be committed."""
        findings: list[Finding] = []
        name = file_path.name.lower()

        env_patterns = [".env", ".env.local", ".env.production", ".env.staging",
                        ".env.development", ".env.test"]

        if name in env_patterns or name.startswith(".env."):
            findings.append(
                Finding(
                    scanner="file-check",
                    category=ScannerCategory.FILES,
                    severity=Severity.CRITICAL,
                    rule_id="ENV-FILE",
                    title="Environment File Detected",
                    message=(
                        f"File '{rel_path}' appears to be an environment file "
                        f"that may contain secrets. Add it to .gitignore."
                    ),
                    file_path=rel_path,
                    suggestion="Add this file to .gitignore and use environment variables instead",
                )
            )

        return findings

    def _check_file_size(self, file_path: Path, rel_path: str) -> list[Finding]:
        """Check if a file exceeds the size limit."""
        findings: list[Finding] = []
        max_size = 2 * 1024 * 1024  # 2MB default

        size = get_file_size(file_path)
        if size > max_size:
            size_mb = size / (1024 * 1024)
            max_mb = max_size / (1024 * 1024)
            findings.append(
                Finding(
                    scanner="file-check",
                    category=ScannerCategory.FILES,
                    severity=Severity.HIGH,
                    rule_id="LARGE-FILE",
                    title="Large File Detected",
                    message=(
                        f"File '{rel_path}' is {size_mb:.1f}MB "
                        f"(max: {max_mb:.0f}MB). Consider using Git LFS."
                    ),
                    file_path=rel_path,
                    suggestion="Use Git LFS for large files or add to .gitignore",
                    metadata={"size_bytes": size, "max_bytes": max_size},
                )
            )

        return findings

    def _check_blocked_patterns(
        self, file_path: Path, rel_path: str
    ) -> list[Finding]:
        """Check if the file matches blocked patterns (private keys, certs)."""
        findings: list[Finding] = []
        blocked = [
            ("*.pem", "PEM certificate/key file"),
            ("*.key", "Private key file"),
            ("*.p12", "PKCS12 certificate"),
            ("*.pfx", "PFX certificate"),
            ("*.jks", "Java keystore"),
            ("id_rsa", "RSA private key"),
            ("id_dsa", "DSA private key"),
            ("id_ecdsa", "ECDSA private key"),
            ("id_ed25519", "Ed25519 private key"),
        ]

        name = file_path.name
        for pattern, description in blocked:
            if pattern.startswith("*"):
                if name.endswith(pattern[1:]):
                    findings.append(
                        Finding(
                            scanner="file-check",
                            category=ScannerCategory.FILES,
                            severity=Severity.CRITICAL,
                            rule_id="BLOCKED-FILE",
                            title=f"Blocked File Type: {description}",
                            message=f"File '{rel_path}' matches blocked pattern '{pattern}'",
                            file_path=rel_path,
                            suggestion=f"Remove this file and add '{pattern}' to .gitignore",
                        )
                    )
            elif name == pattern:
                findings.append(
                    Finding(
                        scanner="file-check",
                        category=ScannerCategory.FILES,
                        severity=Severity.CRITICAL,
                        rule_id="BLOCKED-FILE",
                        title=f"Blocked File: {description}",
                        message=f"File '{rel_path}' is a {description} and must not be committed",
                        file_path=rel_path,
                        suggestion=f"Remove this file and add it to .gitignore",
                    )
                )

        return findings

    def _check_debug_statements(
        self, file_path: Path, rel_path: str
    ) -> list[Finding]:
        """Check for debug statements in source files."""
        findings: list[Finding] = []
        language = detect_language(file_path)

        patterns = DEBUG_PATTERNS.get(language, [])
        if not patterns:
            return findings

        content = read_file_safe(file_path)
        if not content:
            return findings

        for line_num, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            # Skip comments
            if stripped.startswith("#") or stripped.startswith("//"):
                continue

            for pattern in patterns:
                if re.search(pattern, line):
                    findings.append(
                        Finding(
                            scanner="file-check",
                            category=ScannerCategory.FILES,
                            severity=Severity.LOW,
                            rule_id="DEBUG-STMT",
                            title="Debug Statement Found",
                            message=f"Debug statement found: {stripped[:80]}",
                            file_path=rel_path,
                            line_number=line_num,
                            code_snippet=stripped[:100],
                            suggestion="Remove debug statements before committing",
                        )
                    )
                    break  # One finding per line

        return findings

    def _check_dangerous_functions(
        self, file_path: Path, rel_path: str
    ) -> list[Finding]:
        """Check for dangerous function calls."""
        findings: list[Finding] = []
        language = detect_language(file_path)

        patterns = DANGEROUS_FUNCTIONS.get(language, [])
        if not patterns:
            return findings

        content = read_file_safe(file_path)
        if not content:
            return findings

        for line_num, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue

            for pattern in patterns:
                if re.search(pattern, line):
                    findings.append(
                        Finding(
                            scanner="file-check",
                            category=ScannerCategory.FILES,
                            severity=Severity.MEDIUM,
                            rule_id="DANGEROUS-FUNC",
                            title="Dangerous Function Call",
                            message=f"Potentially dangerous function call: {stripped[:80]}",
                            file_path=rel_path,
                            line_number=line_num,
                            code_snippet=stripped[:100],
                            suggestion="Review this function call for security implications",
                        )
                    )
                    break

        return findings
