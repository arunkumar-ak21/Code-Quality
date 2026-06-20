"""
Pipeline Orchestrator — the central engine that coordinates all scanners.

The orchestrator:
1. Loads configuration
2. Discovers enabled scanners
3. Resolves files to scan based on scan mode
4. Runs scanners in parallel with timeouts
5. Collects results and passes them through quality gates
6. Generates the final PipelineReport with a PASS/FAIL/WARN verdict

This is the single entry point that the CLI, git hooks, and CI/CD all invoke.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING

from cqpipeline.core.config import PipelineConfigLoader, get_pipeline_config, get_scanner_config
from cqpipeline.core.constants import ScanMode, ScannerCategory, Severity, Verdict
from cqpipeline.core.exceptions import CQPipelineError, ScannerError
from cqpipeline.core.models import PipelineReport, ScanResult
from cqpipeline.gates.evaluator import QualityGateEvaluator
from cqpipeline.git.utils import get_git_metadata, get_staged_files
from cqpipeline.scanners.base import BaseScanner
from cqpipeline.scanners.dependency_scanner import DependencyScanner
from cqpipeline.scanners.file_scanner import FileScanner
from cqpipeline.scanners.lint_scanner import LintScanner
from cqpipeline.scanners.quality_scanner import QualityScanner
from cqpipeline.scanners.sast_scanner import SASTScanner
from cqpipeline.scanners.secret_scanner import SecretScanner
from cqpipeline.scanners.type_checker import TypeChecker
from cqpipeline.utils.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


# ─── Scanner Registry ────────────────────────────────────────────────
# Maps scanner category names (from config) to their implementation classes.

SCANNER_REGISTRY: dict[str, type[BaseScanner]] = {
    "secrets": SecretScanner,
    "linting": LintScanner,
    "sast": SASTScanner,
    "dependencies": DependencyScanner,
    "quality": QualityScanner,
    "files": FileScanner,
    "type_checking": TypeChecker,
}


class PipelineOrchestrator:
    """
    Central pipeline engine that coordinates scanning, evaluation, and reporting.

    Usage:
        orchestrator = PipelineOrchestrator(project_root=Path("."))
        report = await orchestrator.run(scan_mode=ScanMode.STAGED)
        if report.verdict == Verdict.FAIL:
            sys.exit(1)
    """

    def __init__(
        self,
        project_root: Path | None = None,
        config_path: str | None = None,
        gates_path: str | None = None,
    ) -> None:
        self.project_root = (project_root or Path.cwd()).resolve()
        self.config_loader = PipelineConfigLoader(
            project_root=self.project_root,
            config_path=config_path,
            gates_path=gates_path,
        )
        self.config: dict = {}
        self.scanners: list[BaseScanner] = []
        self.gate_evaluator: QualityGateEvaluator | None = None

    def initialize(self) -> None:
        """Load configuration and initialize scanner instances."""
        logger.info("Initializing pipeline for project: %s", self.project_root)

        # Load all configs
        self.config = self.config_loader.load()
        pipeline_cfg = get_pipeline_config(self.config)

        # Initialize scanners based on config
        self.scanners = self._discover_scanners()
        logger.info(
            "Enabled scanners: %s",
            [s.name for s in self.scanners],
        )

        # Initialize quality gate evaluator
        gates_config = self.config.get("quality_gates", {})
        self.gate_evaluator = QualityGateEvaluator(gates_config)

    def _discover_scanners(self) -> list[BaseScanner]:
        """Discover and instantiate enabled scanners from configuration."""
        scanners: list[BaseScanner] = []
        scanners_config = self.config.get("scanners", {})

        for scanner_name, scanner_class in SCANNER_REGISTRY.items():
            scanner_cfg = scanners_config.get(scanner_name, {})
            if scanner_cfg.get("enabled", False):
                try:
                    scanner = scanner_class(
                        config=scanner_cfg,
                        project_root=self.project_root,
                        allowlist=self.config_loader.load_allowlist(),
                    )
                    scanners.append(scanner)
                except Exception as e:
                    logger.warning(
                        "Failed to initialize scanner '%s': %s", scanner_name, e
                    )
                    if self.config.get("pipeline", {}).get("fail_on_scanner_error", False):
                        raise

        return scanners

    async def run(
        self,
        scan_mode: ScanMode = ScanMode.STAGED,
        files: list[str] | None = None,
    ) -> PipelineReport:
        """
        Execute the full pipeline and return the report.

        Args:
            scan_mode: What to scan (staged files, all files, specific files).
            files: Specific file list when scan_mode is FILES.

        Returns:
            PipelineReport with verdict, findings, and gate results.
        """
        start_time = time.monotonic()

        # Ensure initialized
        if not self.scanners:
            self.initialize()

        # Resolve files to scan
        file_list = self._resolve_files(scan_mode, files)
        if not file_list:
            logger.warning("No files to scan.")
            return self._create_empty_report(scan_mode, start_time)

        logger.info(
            "Scanning %d files in mode '%s'", len(file_list), scan_mode.value
        )

        # Get pipeline settings
        pipeline_cfg = get_pipeline_config(self.config)
        timeout = pipeline_cfg.get("timeout", 120)
        max_workers = pipeline_cfg.get("parallel_workers", 4)

        # Run all scanners in parallel with global timeout
        scan_results: list[ScanResult] = []
        try:
            scan_results = await asyncio.wait_for(
                self._run_scanners(file_list, max_workers),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.error("Pipeline timed out after %d seconds", timeout)
            # Return partial results with FAIL verdict
            report = self._build_report(scan_results, scan_mode, start_time)
            report.verdict = Verdict.FAIL
            report.blocking_reasons.append(
                f"Pipeline timed out after {timeout} seconds"
            )
            return report

        # Evaluate quality gates
        report = self._build_report(scan_results, scan_mode, start_time)

        if self.gate_evaluator:
            gate_results = self.gate_evaluator.evaluate(scan_results)
            report.gate_results = gate_results

            # Determine final verdict
            has_blocking = any(not gr.passed for gr in gate_results)
            has_warnings = any(
                gr.action.value == "warn" for gr in gate_results
            )

            if has_blocking:
                report.verdict = Verdict.FAIL
                report.blocking_reasons = [
                    gr.message for gr in gate_results if not gr.passed
                ]
            elif has_warnings:
                report.verdict = Verdict.WARN
            else:
                report.verdict = Verdict.PASS

        report.compute_aggregates()
        elapsed = time.monotonic() - start_time
        report.duration_seconds = round(elapsed, 2)

        logger.info(
            "Pipeline completed in %.2fs — Verdict: %s (%d findings)",
            elapsed,
            report.verdict.value.upper(),
            report.total_findings,
        )

        return report

    async def _run_scanners(
        self,
        files: list[Path],
        max_workers: int,
    ) -> list[ScanResult]:
        """Run all enabled scanners in parallel with concurrency control."""
        semaphore = asyncio.Semaphore(max_workers)

        async def _run_with_semaphore(scanner: BaseScanner) -> ScanResult:
            async with semaphore:
                return await self._run_single_scanner(scanner, files)

        tasks = [_run_with_semaphore(scanner) for scanner in self.scanners]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results, converting exceptions to error ScanResults
        scan_results: list[ScanResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                scanner = self.scanners[i]
                logger.error(
                    "Scanner '%s' raised exception: %s",
                    scanner.name,
                    result,
                )
                scan_results.append(
                    ScanResult(
                        scanner_name=scanner.name,
                        category=scanner.category,
                        success=False,
                        error_message=str(result),
                    )
                )
            else:
                scan_results.append(result)

        return scan_results

    async def _run_single_scanner(
        self,
        scanner: BaseScanner,
        files: list[Path],
    ) -> ScanResult:
        """Run a single scanner with its own timeout and error handling."""
        scanner_timeout = scanner.config.get("timeout", 60)

        try:
            logger.info("Running scanner: %s", scanner.name)
            start = time.monotonic()

            result = await asyncio.wait_for(
                scanner.scan(files),
                timeout=scanner_timeout,
            )

            elapsed = time.monotonic() - start
            result.duration_seconds = round(elapsed, 2)

            logger.info(
                "Scanner '%s' completed in %.2fs — %d findings",
                scanner.name,
                elapsed,
                result.finding_count,
            )
            return result

        except asyncio.TimeoutError:
            logger.warning(
                "Scanner '%s' timed out after %ds",
                scanner.name,
                scanner_timeout,
            )
            return ScanResult(
                scanner_name=scanner.name,
                category=scanner.category,
                success=False,
                error_message=f"Scanner timed out after {scanner_timeout}s",
            )

        except ScannerError as e:
            logger.error("Scanner '%s' error: %s", scanner.name, e)
            return ScanResult(
                scanner_name=scanner.name,
                category=scanner.category,
                success=False,
                error_message=str(e),
            )

        except Exception as e:
            logger.error(
                "Unexpected error in scanner '%s': %s",
                scanner.name,
                e,
                exc_info=True,
            )
            return ScanResult(
                scanner_name=scanner.name,
                category=scanner.category,
                success=False,
                error_message=f"Unexpected error: {e}",
            )

    def _resolve_files(
        self,
        scan_mode: ScanMode,
        files: list[str] | None = None,
    ) -> list[Path]:
        """Resolve the list of files to scan based on the scan mode."""
        if scan_mode == ScanMode.STAGED:
            staged = get_staged_files(self.project_root)
            return [self.project_root / f for f in staged]

        elif scan_mode == ScanMode.FILES:
            if not files:
                return []
            return [Path(f).resolve() for f in files]

        elif scan_mode == ScanMode.ALL:
            return self._get_all_project_files()

        else:
            logger.warning("Unknown scan mode: %s, defaulting to ALL", scan_mode)
            return self._get_all_project_files()

    def _get_all_project_files(self) -> list[Path]:
        """Get all trackable project files, respecting .gitignore patterns."""
        all_files: list[Path] = []
        ignore_dirs = {
            ".git", "__pycache__", "node_modules", ".venv", "venv",
            ".mypy_cache", ".ruff_cache", ".pytest_cache", "dist",
            "build", ".eggs", "*.egg-info", ".tox", "htmlcov",
        }

        for item in self.project_root.rglob("*"):
            if item.is_file():
                # Skip ignored directories
                parts = item.relative_to(self.project_root).parts
                if any(part in ignore_dirs for part in parts):
                    continue
                all_files.append(item)

        return all_files

    def _build_report(
        self,
        scan_results: list[ScanResult],
        scan_mode: ScanMode,
        start_time: float,
    ) -> PipelineReport:
        """Build a PipelineReport from scan results."""
        git_meta = get_git_metadata(self.project_root)

        report = PipelineReport(
            verdict=Verdict.PASS,  # Will be updated by gate evaluation
            scan_mode=scan_mode,
            commit_sha=git_meta.get("commit_sha", ""),
            branch=git_meta.get("branch", ""),
            author=git_meta.get("author", ""),
            repository=git_meta.get("repository", str(self.project_root)),
            scan_results=scan_results,
            duration_seconds=round(time.monotonic() - start_time, 2),
        )

        report.compute_aggregates()
        return report

    def _create_empty_report(
        self,
        scan_mode: ScanMode,
        start_time: float,
    ) -> PipelineReport:
        """Create an empty report when no files are found to scan."""
        git_meta = get_git_metadata(self.project_root)
        return PipelineReport(
            verdict=Verdict.PASS,
            scan_mode=scan_mode,
            commit_sha=git_meta.get("commit_sha", ""),
            branch=git_meta.get("branch", ""),
            author=git_meta.get("author", ""),
            repository=str(self.project_root),
            duration_seconds=round(time.monotonic() - start_time, 2),
        )


def run_pipeline_sync(
    project_root: Path | None = None,
    scan_mode: ScanMode = ScanMode.STAGED,
    files: list[str] | None = None,
    config_path: str | None = None,
    gates_path: str | None = None,
) -> PipelineReport:
    """
    Synchronous wrapper for running the pipeline.

    Used by CLI and git hooks that can't easily use async.
    """
    orchestrator = PipelineOrchestrator(
        project_root=project_root,
        config_path=config_path,
        gates_path=gates_path,
    )
    return asyncio.run(orchestrator.run(scan_mode=scan_mode, files=files))
