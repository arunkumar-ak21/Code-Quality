"""
Terminal Reporter — Rich, color-coded terminal output.

Uses the `rich` library to render beautiful, scannable terminal output
with severity-colored findings, summary tables, and progress indicators.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cqpipeline.core.constants import Severity, Verdict
from cqpipeline.core.models import PipelineReport
from cqpipeline.reporters.base import BaseReporter

# Severity → color/emoji mapping
SEVERITY_STYLES = {
    Severity.CRITICAL: ("bold red", "🔴"),
    Severity.HIGH: ("red", "🟠"),
    Severity.MEDIUM: ("yellow", "🟡"),
    Severity.LOW: ("blue", "🔵"),
    Severity.INFO: ("dim", "⚪"),
}

VERDICT_STYLES = {
    Verdict.PASS: ("bold green", "✅ PASSED"),
    Verdict.FAIL: ("bold red", "❌ FAILED"),
    Verdict.WARN: ("bold yellow", "⚠️  WARNING"),
    Verdict.ERROR: ("bold red", "💥 ERROR"),
}


class TerminalReporter(BaseReporter):
    """Renders pipeline reports as colored terminal output."""

    def __init__(self) -> None:
        self.console = Console(stderr=True)

    def generate(self, report: PipelineReport, output_path: Path | None = None) -> str:
        """Render the report to the terminal."""
        self._render_header(report)
        self._render_scanner_summary(report)
        self._render_findings(report)
        self._render_gate_results(report)
        self._render_verdict(report)
        return ""

    def _render_header(self, report: PipelineReport) -> None:
        """Render the report header."""
        self.console.print()
        self.console.rule("[bold cyan]Code Quality Pipeline Report[/]")
        self.console.print(
            f"  Branch: [cyan]{report.branch or 'unknown'}[/]  "
            f"Commit: [cyan]{report.commit_sha[:8] if report.commit_sha else 'N/A'}[/]  "
            f"Duration: [cyan]{report.duration_seconds:.1f}s[/]  "
            f"Files: [cyan]{report.files_scanned}[/]"
        )
        self.console.print()

    def _render_scanner_summary(self, report: PipelineReport) -> None:
        """Render a summary table of scanner results."""
        table = Table(
            title="Scanner Summary",
            show_header=True,
            header_style="bold cyan",
            border_style="dim",
        )
        table.add_column("Scanner", style="white", min_width=15)
        table.add_column("Status", justify="center", min_width=8)
        table.add_column("Findings", justify="right", min_width=10)
        table.add_column("Critical", justify="right", min_width=8)
        table.add_column("High", justify="right", min_width=6)
        table.add_column("Medium", justify="right", min_width=8)
        table.add_column("Duration", justify="right", min_width=8)

        for result in report.scan_results:
            if result.skipped:
                status = "[dim]SKIP[/]"
            elif result.success:
                status = "[green]✓ OK[/]" if result.finding_count == 0 else "[yellow]⚠ WARN[/]"
            else:
                status = "[red]✗ ERR[/]"

            critical = f"[red]{result.critical_count}[/]" if result.critical_count > 0 else "0"
            high = f"[red]{result.high_count}[/]" if result.high_count > 0 else "0"
            medium = f"[yellow]{result.medium_count}[/]" if result.medium_count > 0 else "0"

            table.add_row(
                result.scanner_name,
                status,
                str(result.finding_count),
                critical,
                high,
                medium,
                f"{result.duration_seconds:.1f}s",
            )

        self.console.print(table)
        self.console.print()

    def _render_findings(self, report: PipelineReport) -> None:
        """Render individual findings grouped by severity."""
        findings = report.all_findings
        if not findings:
            self.console.print("[green]  No findings — code looks clean! 🎉[/]")
            self.console.print()
            return

        # Show top findings (limit to avoid flooding terminal)
        max_display = 25
        displayed = 0

        for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM]:
            severity_findings = [f for f in findings if f.severity == severity]
            if not severity_findings:
                continue

            style, emoji = SEVERITY_STYLES[severity]

            for finding in severity_findings:
                if displayed >= max_display:
                    remaining = len(findings) - displayed
                    self.console.print(
                        f"\n  [dim]... and {remaining} more findings "
                        f"(see full report for details)[/]"
                    )
                    self.console.print()
                    return

                location = ""
                if finding.file_path:
                    location = f"[dim]{finding.file_path}"
                    if finding.line_number:
                        location += f":{finding.line_number}"
                    location += "[/]"

                self.console.print(
                    f"  {emoji} [{style}]{severity.value.upper():>8}[/] "
                    f"[white]{finding.title}[/]"
                )
                if finding.message and finding.message != finding.title:
                    self.console.print(f"           {finding.message[:100]}")
                if location:
                    self.console.print(f"           {location}")
                if finding.suggestion:
                    self.console.print(
                        f"           [green]→ {finding.suggestion}[/]"
                    )
                displayed += 1

        self.console.print()

    def _render_gate_results(self, report: PipelineReport) -> None:
        """Render quality gate results."""
        if not report.gate_results:
            return

        table = Table(
            title="Quality Gates",
            show_header=True,
            header_style="bold cyan",
            border_style="dim",
        )
        table.add_column("Gate", style="white", min_width=20)
        table.add_column("Result", justify="center", min_width=10)
        table.add_column("Details", min_width=40)

        for gate in report.gate_results:
            if gate.passed:
                result_str = "[green]✓ PASS[/]"
            else:
                result_str = "[red]✗ BLOCK[/]"

            table.add_row(gate.gate_name, result_str, gate.message)

        self.console.print(table)
        self.console.print()

    def _render_verdict(self, report: PipelineReport) -> None:
        """Render the final verdict banner."""
        style, text = VERDICT_STYLES.get(
            report.verdict, ("bold white", "UNKNOWN")
        )

        # Summary line
        summary = (
            f"Findings: {report.total_findings} total "
            f"({report.critical_count}C / {report.high_count}H / "
            f"{report.medium_count}M / {report.low_count}L)"
        )

        verdict_panel = Panel(
            f"[{style}]{text}[/]\n\n{summary}",
            border_style=style.replace("bold ", ""),
            title="Pipeline Verdict",
            title_align="center",
            padding=(1, 4),
        )

        self.console.print(verdict_panel)

        if report.blocking_reasons:
            self.console.print("[red]Blocking reasons:[/]")
            for reason in report.blocking_reasons:
                self.console.print(f"  • {reason}")

        self.console.print()
