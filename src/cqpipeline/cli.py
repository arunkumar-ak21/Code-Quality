"""
CLI — Command-line interface for the CQ Pipeline.

Provides the `cq-pipeline` command with subcommands:
  - scan: Run the pipeline (--staged, --all, --files)
  - install-hooks: Install git hooks
  - report: Generate report from latest scan
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import click

from cqpipeline.core.baseline import DEFAULT_BASELINE_FILE, FindingBaseline
from cqpipeline.core.constants import ExitCode, ScanMode, Verdict
from cqpipeline.core.orchestrator import run_pipeline_sync
from cqpipeline.reporters.html_reporter import HTMLReporter
from cqpipeline.reporters.json_reporter import JSONReporter
from cqpipeline.reporters.sarif_reporter import SARIFReporter
from cqpipeline.reporters.terminal_reporter import TerminalReporter
from cqpipeline.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


@click.group()
@click.version_option(version="1.0.0", prog_name="cq-pipeline")
def cli() -> None:
    """🛡️ CQ Pipeline — Enterprise DevSecOps Security & Quality Gate."""


@cli.command()
@click.option("--staged", is_flag=True, default=False, help="Scan only staged files (pre-commit)")
@click.option("--all", "scan_all", is_flag=True, default=False, help="Scan entire project")
@click.option("--files", multiple=True, help="Scan specific files")
@click.option("--format", "output_format", type=click.Choice(["terminal", "json", "html", "sarif", "all"]),
              default="terminal", help="Output format")
@click.option("--config", "config_path", default=None, help="Path to pipeline config")
@click.option("--gates", "gates_path", default=None, help="Path to quality gates config")
@click.option("--project", "project_root", default=None, help="Project root directory")
@click.option("--log-level", default="INFO", help="Log level (DEBUG/INFO/WARNING/ERROR)")
@click.option("--json-log", is_flag=True, default=False, help="Output logs as JSON (for CI/CD)")
@click.option("--baseline", "baseline_path", default=None, help="Path to .cq-baseline.json for existing findings")
@click.option("--suppress-baseline", is_flag=True, default=False, help="Suppress baseline findings from the gate/report")
@click.option("--update-baseline", is_flag=True, default=False, help="Write/update baseline from current findings after the scan")
def scan(
    staged: bool,
    scan_all: bool,
    files: tuple[str, ...],
    output_format: str,
    config_path: str | None,
    gates_path: str | None,
    project_root: str | None,
    log_level: str,
    json_log: bool,
    baseline_path: str | None,
    suppress_baseline: bool,
    update_baseline: bool,
) -> None:
    """Run the security and quality pipeline scan."""
    setup_logging(level=log_level, json_format=json_log)

    # Determine scan mode
    if files:
        scan_mode = ScanMode.FILES
        file_list = list(files)
    elif scan_all:
        scan_mode = ScanMode.ALL
        file_list = None
    else:
        scan_mode = ScanMode.STAGED
        file_list = None

    root = Path(project_root) if project_root else Path.cwd()

    try:
        # Run the pipeline
        report = run_pipeline_sync(
            project_root=root,
            scan_mode=scan_mode,
            files=file_list,
            config_path=config_path,
            gates_path=gates_path,
        )

        baseline_file = Path(baseline_path) if baseline_path else root / DEFAULT_BASELINE_FILE
        if baseline_file.exists():
            FindingBaseline(baseline_file).load().apply(report, suppress_existing=suppress_baseline)

        if update_baseline:
            FindingBaseline.write_from_report(report, baseline_file)
            click.echo(f"🧭 Baseline updated: {baseline_file}", err=True)

        # Generate reports
        if output_format in ("terminal", "all"):
            terminal_reporter = TerminalReporter()
            terminal_reporter.generate(report)

        if output_format in ("json", "all"):
            json_reporter = JSONReporter()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_path = root / "reports" / f"scan_{timestamp}.json"
            json_reporter.generate(report, output_path=json_path)
            if output_format == "json":
                click.echo(json_reporter.generate(report))

        if output_format in ("html", "all"):
            html_reporter = HTMLReporter()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            html_path = root / "reports" / f"scan_{timestamp}.html"
            html_reporter.generate(report, output_path=html_path)
            click.echo(f"📄 HTML report: {html_path}", err=True)

        if output_format in ("sarif", "all"):
            sarif_reporter = SARIFReporter()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            sarif_path = root / "reports" / f"scan_{timestamp}.sarif"
            sarif_reporter.generate(report, output_path=sarif_path)
            click.echo(f"📄 SARIF report: {sarif_path}", err=True)

        # Exit based on verdict
        if report.verdict == Verdict.FAIL:
            sys.exit(ExitCode.QUALITY_GATE_FAILED)
        elif report.verdict == Verdict.ERROR:
            sys.exit(ExitCode.SCANNER_ERROR)
        else:
            sys.exit(ExitCode.SUCCESS)

    except Exception as e:
        logger.error("Pipeline error: %s", e, exc_info=True)
        click.echo(f"💥 Pipeline error: {e}", err=True)
        sys.exit(ExitCode.INTERNAL_ERROR)


@cli.command("install-hooks")
@click.option("--project", "project_root", default=None, help="Project root directory")
def install_hooks_cmd(project_root: str | None) -> None:
    """Install git pre-commit and pre-push hooks."""
    from cqpipeline.git.hooks import install_hooks

    root = Path(project_root) if project_root else Path.cwd()

    try:
        install_hooks(root)
        click.echo("✅ Git hooks installed successfully!")
        click.echo("   Pre-commit hook will run on: git commit")
        click.echo("   Pre-push hook will run on: git push")
    except Exception as e:
        click.echo(f"❌ Failed to install hooks: {e}", err=True)
        sys.exit(1)


@cli.command("remove-hooks")
@click.option("--project", "project_root", default=None, help="Project root directory")
def remove_hooks_cmd(project_root: str | None) -> None:
    """Remove CQ Pipeline git hooks."""
    from cqpipeline.git.hooks import remove_hooks

    root = Path(project_root) if project_root else Path.cwd()

    try:
        remove_hooks(root)
        click.echo("✅ Git hooks removed successfully!")
    except Exception as e:
        click.echo(f"❌ Failed to remove hooks: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--format", "output_format", type=click.Choice(["html", "json"]),
              default="html", help="Report format")
@click.option("--project", "project_root", default=None, help="Project root directory")
def report(output_format: str, project_root: str | None) -> None:
    """Generate a report from the latest scan results."""
    root = Path(project_root) if project_root else Path.cwd()

    # Run a fresh scan for the report
    setup_logging(level="WARNING")

    try:
        pipeline_report = run_pipeline_sync(
            project_root=root,
            scan_mode=ScanMode.ALL,
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if output_format == "html":
            reporter = HTMLReporter()
            out_path = root / "reports" / f"report_{timestamp}.html"
            reporter.generate(pipeline_report, output_path=out_path)
            click.echo(f"📄 HTML report generated: {out_path}")

        elif output_format == "json":
            reporter = JSONReporter()
            out_path = root / "reports" / f"report_{timestamp}.json"
            reporter.generate(pipeline_report, output_path=out_path)
            click.echo(f"📄 JSON report generated: {out_path}")

    except Exception as e:
        click.echo(f"❌ Report generation failed: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
