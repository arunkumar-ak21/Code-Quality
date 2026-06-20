"""
Quality Scanner — Code complexity and maintainability analysis.

Integrates:
- Radon: Cyclomatic complexity + maintainability index analysis
- Custom AST-based function length analyzer

Why complexity matters:
- High cyclomatic complexity correlates with bugs (McCabe, 1976)
- Long functions are harder to test, review, and maintain
- Maintainability index predicts how hard code is to change
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from cqpipeline.core.constants import ScannerCategory, Severity
from cqpipeline.core.models import Finding, ScanResult
from cqpipeline.scanners.base import BaseScanner
from cqpipeline.utils.file_utils import get_relative_path, read_file_safe
from cqpipeline.utils.logger import get_logger
from cqpipeline.utils.process import check_tool_available, run_process

logger = get_logger(__name__)


class QualityScanner(BaseScanner):
    """Code quality analyzer using Radon and custom AST analysis."""

    @property
    def name(self) -> str:
        return "quality"

    @property
    def category(self) -> ScannerCategory:
        return ScannerCategory.QUALITY

    @property
    def supported_languages(self) -> list[str]:
        return ["python"]

    async def _execute(self, files: list[Path]) -> ScanResult:
        """Run quality analysis tools."""
        all_findings: list[Finding] = []
        tools_config = self.config.get("tools", {})

        py_files = [f for f in files if f.suffix in (".py", ".pyw")]
        if not py_files:
            return ScanResult(
                scanner_name=self.name,
                category=self.category,
                success=True,
            )

        # 1. Radon complexity analysis
        if tools_config.get("radon", {}).get("enabled", True):
            if check_tool_available("radon"):
                findings = await self._run_radon_complexity(py_files)
                all_findings.extend(findings)

                mi_findings = await self._run_radon_maintainability(py_files)
                all_findings.extend(mi_findings)
            else:
                logger.warning("Radon not installed — skipping")

        # 2. Custom function length analysis (no external tool needed)
        length_findings = self._analyze_function_lengths(py_files)
        all_findings.extend(length_findings)

        return ScanResult(
            scanner_name=self.name,
            category=self.category,
            success=True,
            findings=all_findings,
        )

    async def _run_radon_complexity(self, files: list[Path]) -> list[Finding]:
        """Run Radon cyclomatic complexity analysis."""
        findings: list[Finding] = []
        file_args = [str(f) for f in files]

        cmd = ["radon", "cc", "--json", "--min", "C"] + file_args

        result = await run_process(
            cmd,
            cwd=self.project_root,
            timeout=self.config.get("timeout", 30),
            scanner_name="radon",
        )

        if result.stdout.strip():
            try:
                output = json.loads(result.stdout)
                for file_path, blocks in output.items():
                    for block in blocks:
                        complexity = block.get("complexity", 0)
                        rank = block.get("rank", "A")
                        severity = self._complexity_to_severity(rank)

                        findings.append(
                            Finding(
                                scanner="radon",
                                category=ScannerCategory.QUALITY,
                                severity=severity,
                                rule_id=f"CC-{rank}",
                                title=f"High Complexity ({rank}): {block.get('name', '')}",
                                message=(
                                    f"Function '{block.get('name', '')}' has cyclomatic "
                                    f"complexity of {complexity} (rank {rank})"
                                ),
                                file_path=file_path,
                                line_number=block.get("lineno", 0),
                                suggestion=f"Consider refactoring to reduce complexity below 15",
                                metadata={
                                    "complexity": complexity,
                                    "rank": rank,
                                    "type": block.get("type", ""),
                                    "classname": block.get("classname", ""),
                                },
                            )
                        )
            except json.JSONDecodeError:
                logger.warning("Failed to parse Radon CC output")

        logger.info("Radon CC found %d complex functions", len(findings))
        return findings

    async def _run_radon_maintainability(self, files: list[Path]) -> list[Finding]:
        """Run Radon maintainability index analysis."""
        findings: list[Finding] = []
        file_args = [str(f) for f in files]

        cmd = ["radon", "mi", "--json"] + file_args

        result = await run_process(
            cmd,
            cwd=self.project_root,
            timeout=self.config.get("timeout", 30),
            scanner_name="radon",
        )

        if result.stdout.strip():
            try:
                output = json.loads(result.stdout)
                for file_path, mi_data in output.items():
                    # mi_data can be a dict with 'mi' and 'rank' or just the score
                    if isinstance(mi_data, dict):
                        mi_score = mi_data.get("mi", 100)
                        rank = mi_data.get("rank", "A")
                    else:
                        mi_score = mi_data
                        rank = "A" if mi_score >= 20 else "B" if mi_score >= 10 else "C"

                    # Only report files with low maintainability
                    if isinstance(mi_score, (int, float)) and mi_score < 20:
                        findings.append(
                            Finding(
                                scanner="radon",
                                category=ScannerCategory.QUALITY,
                                severity=Severity.MEDIUM if mi_score >= 10 else Severity.HIGH,
                                rule_id=f"MI-{rank}",
                                title=f"Low Maintainability: {Path(file_path).name}",
                                message=(
                                    f"File '{file_path}' has maintainability index of "
                                    f"{mi_score:.1f} (rank {rank}). Target: >= 20"
                                ),
                                file_path=file_path,
                                suggestion="Simplify code, reduce complexity, add documentation",
                                metadata={"mi_score": mi_score, "rank": rank},
                            )
                        )
            except json.JSONDecodeError:
                logger.warning("Failed to parse Radon MI output")

        logger.info("Radon MI found %d low-maintainability files", len(findings))
        return findings

    def _analyze_function_lengths(self, files: list[Path]) -> list[Finding]:
        """Analyze function/method lengths using Python AST."""
        findings: list[Finding] = []
        max_lines = 100  # Default threshold

        for file_path in files:
            content = read_file_safe(file_path)
            if not content:
                continue

            try:
                tree = ast.parse(content, filename=str(file_path))
            except SyntaxError:
                continue

            rel_path = get_relative_path(file_path, self.project_root)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Calculate function length
                    if hasattr(node, "end_lineno") and node.end_lineno:
                        func_lines = node.end_lineno - node.lineno + 1
                    else:
                        # Estimate from body
                        func_lines = len(ast.dump(node).splitlines())

                    if func_lines > max_lines:
                        # Determine parent class name
                        class_name = ""
                        for parent in ast.walk(tree):
                            if isinstance(parent, ast.ClassDef):
                                for child in ast.iter_child_nodes(parent):
                                    if child is node:
                                        class_name = parent.name
                                        break

                        func_name = (
                            f"{class_name}.{node.name}"
                            if class_name
                            else node.name
                        )

                        findings.append(
                            Finding(
                                scanner="function-length",
                                category=ScannerCategory.QUALITY,
                                severity=Severity.MEDIUM,
                                rule_id="FUNC-LENGTH",
                                title=f"Long Function: {func_name}",
                                message=(
                                    f"Function '{func_name}' is {func_lines} lines long "
                                    f"(max: {max_lines})"
                                ),
                                file_path=rel_path,
                                line_number=node.lineno,
                                suggestion="Consider breaking this function into smaller, focused functions",
                                metadata={
                                    "function_name": node.name,
                                    "lines": func_lines,
                                    "max_lines": max_lines,
                                },
                            )
                        )

        logger.info("Function length check found %d long functions", len(findings))
        return findings

    @staticmethod
    def _complexity_to_severity(rank: str) -> Severity:
        """Map Radon complexity rank to Severity."""
        mapping = {
            "A": Severity.INFO,     # 1-5: simple
            "B": Severity.INFO,     # 6-10: well structured
            "C": Severity.LOW,      # 11-20: slightly complex
            "D": Severity.MEDIUM,   # 21-30: more complex
            "E": Severity.HIGH,     # 31-40: complex
            "F": Severity.CRITICAL, # 41+: very complex
        }
        return mapping.get(rank.upper(), Severity.MEDIUM)
