"""Compiler/build scanner for syntax and build failures.

This scanner is intentionally conservative: it never builds network-heavy projects by
itself unless a language manifest exists and the command is available. It produces
findings instead of crashing so CI reports remain readable.
"""

from __future__ import annotations

import json
from pathlib import Path

from cqpipeline.core.constants import ScannerCategory, Severity
from cqpipeline.core.models import Finding, ScanResult
from cqpipeline.scanners.base import BaseScanner
from cqpipeline.utils.file_utils import get_relative_path
from cqpipeline.utils.process import check_tool_available, run_process


class CompilerScanner(BaseScanner):
    @property
    def name(self) -> str:
        return "compiler"

    @property
    def category(self) -> ScannerCategory:
        return ScannerCategory.COMPILER

    @property
    def supported_languages(self) -> list[str]:
        # Manifest/language aware; do not pre-filter only one extension.
        return []

    async def _execute(self, files: list[Path]) -> ScanResult:
        findings: list[Finding] = []
        scanned = 0

        py_files = [path for path in files if path.suffix == ".py" and path.exists()]
        if py_files:
            scanned += len(py_files)
            findings.extend(await self._compile_python(py_files))

        package_json = self.project_root / "package.json"
        if package_json.exists():
            scanned += 1
            findings.extend(await self._check_node_build(package_json))

        go_mod = self.project_root / "go.mod"
        if go_mod.exists():
            scanned += 1
            findings.extend(await self._check_go(go_mod))

        pom = self.project_root / "pom.xml"
        gradle = self.project_root / "build.gradle"
        if pom.exists() or gradle.exists():
            scanned += 1
            findings.extend(await self._check_java(pom if pom.exists() else gradle))

        return ScanResult(
            scanner_name=self.name,
            category=self.category,
            success=True,
            findings=findings,
            files_scanned=scanned,
        )

    async def _compile_python(self, py_files: list[Path]) -> list[Finding]:
        findings: list[Finding] = []
        for path in py_files:
            result = await run_process(
                ["python", "-m", "py_compile", str(path)],
                cwd=self.project_root,
                timeout=self.config.get("timeout", 60),
                scanner_name="python-compile",
            )
            if result.exit_code != 0:
                rel = get_relative_path(path, self.project_root)
                message = (result.stderr or result.stdout or "Python compilation failed").strip()
                findings.append(
                    Finding(
                        scanner="python-compile",
                        category=ScannerCategory.COMPILER,
                        severity=Severity.HIGH,
                        rule_id="PY-COMPILE-ERROR",
                        title="Python syntax/compile error",
                        message=message[:2000],
                        file_path=rel,
                        suggestion="Fix the syntax error so the file can be imported/compiled.",
                    )
                )
        return findings

    async def _check_node_build(self, package_json: Path) -> list[Finding]:
        if not check_tool_available("npm"):
            return []
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except Exception:
            return []
        scripts = data.get("scripts") or {}
        if "build" not in scripts and "test" not in scripts:
            return []
        cmd = ["npm", "run", "build"] if "build" in scripts else ["npm", "test", "--", "--watch=false"]
        result = await run_process(cmd, cwd=self.project_root, timeout=self.config.get("timeout", 120), scanner_name="node-build")
        if result.exit_code == 0:
            return []
        return [Finding(
            scanner="node-build",
            category=ScannerCategory.COMPILER,
            severity=Severity.HIGH,
            rule_id="NODE-BUILD-FAILED",
            title="Node build/test failed",
            message=((result.stderr or result.stdout or "Node build/test failed").strip())[:2000],
            file_path="package.json",
            suggestion="Run the same npm command locally and fix the build/test failure.",
        )]

    async def _check_go(self, manifest: Path) -> list[Finding]:
        if not check_tool_available("go"):
            return []
        result = await run_process(["go", "test", "./..."], cwd=self.project_root, timeout=self.config.get("timeout", 120), scanner_name="go-test")
        if result.exit_code == 0:
            return []
        return [Finding(
            scanner="go-test",
            category=ScannerCategory.COMPILER,
            severity=Severity.HIGH,
            rule_id="GO-TEST-FAILED",
            title="Go tests/build failed",
            message=((result.stderr or result.stdout or "go test failed").strip())[:2000],
            file_path=get_relative_path(manifest, self.project_root),
            suggestion="Run go test ./... locally and fix the failure.",
        )]

    async def _check_java(self, manifest: Path) -> list[Finding]:
        if manifest.name == "pom.xml" and check_tool_available("mvn"):
            cmd = ["mvn", "-q", "test"]
        elif check_tool_available("gradle"):
            cmd = ["gradle", "test", "--no-daemon"]
        else:
            return []
        result = await run_process(cmd, cwd=self.project_root, timeout=self.config.get("timeout", 180), scanner_name="java-build")
        if result.exit_code == 0:
            return []
        return [Finding(
            scanner="java-build",
            category=ScannerCategory.COMPILER,
            severity=Severity.HIGH,
            rule_id="JAVA-BUILD-FAILED",
            title="Java build/test failed",
            message=((result.stderr or result.stdout or "Java build/test failed").strip())[:2000],
            file_path=get_relative_path(manifest, self.project_root),
            suggestion="Run the same build command locally and fix the failure.",
        )]
