"""
HTML Reporter — generates a self-contained HTML dashboard report.

Uses Jinja2 templating to produce a styled, interactive HTML report
that can be opened in any browser. Includes:
- Severity distribution summary
- Findings table with filtering
- Scanner summary cards
- Git metadata
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Template

from cqpipeline.core.constants import Severity, Verdict
from cqpipeline.core.models import PipelineReport
from cqpipeline.reporters.base import BaseReporter
from cqpipeline.utils.logger import get_logger

logger = get_logger(__name__)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CQ Pipeline Report — {{ report.branch or 'N/A' }}</title>
    <style>
        :root {
            --bg: #0d1117; --surface: #161b22; --border: #30363d;
            --text: #e6edf3; --text-muted: #8b949e;
            --critical: #f85149; --high: #f0883e; --medium: #d29922;
            --low: #58a6ff; --info: #8b949e;
            --pass: #3fb950; --fail: #f85149; --warn: #d29922;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: var(--bg); color: var(--text); line-height: 1.6; padding: 2rem; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { font-size: 1.8rem; margin-bottom: 0.5rem; }
        h2 { font-size: 1.3rem; margin: 2rem 0 1rem; color: var(--text-muted); }

        .verdict-banner {
            padding: 1.5rem 2rem; border-radius: 12px; text-align: center;
            font-size: 1.5rem; font-weight: bold; margin: 1.5rem 0;
        }
        .verdict-pass { background: rgba(63,185,80,0.15); border: 1px solid var(--pass); color: var(--pass); }
        .verdict-fail { background: rgba(248,81,73,0.15); border: 1px solid var(--fail); color: var(--fail); }
        .verdict-warn { background: rgba(210,153,34,0.15); border: 1px solid var(--warn); color: var(--warn); }

        .meta-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                     gap: 1rem; margin: 1.5rem 0; }
        .meta-card { background: var(--surface); border: 1px solid var(--border);
                     border-radius: 8px; padding: 1rem; }
        .meta-card .label { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; }
        .meta-card .value { font-size: 1.4rem; font-weight: bold; margin-top: 0.3rem; }

        .severity-bar { display: flex; height: 8px; border-radius: 4px; overflow: hidden; margin: 1rem 0; }
        .severity-bar span { display: block; }
        .sev-critical { background: var(--critical); }
        .sev-high { background: var(--high); }
        .sev-medium { background: var(--medium); }
        .sev-low { background: var(--low); }
        .sev-info { background: var(--info); }

        table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
        th { background: var(--surface); color: var(--text-muted); text-align: left;
             padding: 0.75rem 1rem; font-size: 0.85rem; text-transform: uppercase;
             border-bottom: 2px solid var(--border); }
        td { padding: 0.6rem 1rem; border-bottom: 1px solid var(--border);
             font-size: 0.9rem; vertical-align: top; }
        tr:hover td { background: rgba(110,118,129,0.08); }

        .badge { display: inline-block; padding: 2px 8px; border-radius: 12px;
                 font-size: 0.75rem; font-weight: 600; }
        .badge-critical { background: rgba(248,81,73,0.2); color: var(--critical); }
        .badge-high { background: rgba(240,136,62,0.2); color: var(--high); }
        .badge-medium { background: rgba(210,153,34,0.2); color: var(--medium); }
        .badge-low { background: rgba(88,166,255,0.2); color: var(--low); }
        .badge-info { background: rgba(139,148,158,0.2); color: var(--info); }

        .scanner-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                        gap: 1rem; margin: 1rem 0; }
        .scanner-card { background: var(--surface); border: 1px solid var(--border);
                        border-radius: 8px; padding: 1.2rem; }
        .scanner-card h3 { font-size: 1rem; margin-bottom: 0.5rem; }
        .scanner-card .count { font-size: 2rem; font-weight: bold; }

        .filter-bar { display: flex; gap: 0.5rem; margin: 1rem 0; flex-wrap: wrap; }
        .filter-btn { background: var(--surface); border: 1px solid var(--border);
                      color: var(--text); padding: 0.4rem 1rem; border-radius: 20px;
                      cursor: pointer; font-size: 0.85rem; }
        .filter-btn.active { background: var(--low); color: var(--bg); border-color: var(--low); }
        .filter-btn:hover { border-color: var(--text-muted); }

        footer { margin-top: 3rem; text-align: center; color: var(--text-muted); font-size: 0.8rem; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ Code Quality Pipeline Report</h1>

        <div class="verdict-banner verdict-{{ report.verdict.value }}">
            {% if report.verdict.value == 'pass' %}✅ PIPELINE PASSED
            {% elif report.verdict.value == 'fail' %}❌ PIPELINE FAILED — Commit Blocked
            {% elif report.verdict.value == 'warn' %}⚠️ PIPELINE WARNING
            {% else %}💥 PIPELINE ERROR{% endif %}
        </div>

        <div class="meta-grid">
            <div class="meta-card">
                <div class="label">Branch</div>
                <div class="value">{{ report.branch or 'N/A' }}</div>
            </div>
            <div class="meta-card">
                <div class="label">Commit</div>
                <div class="value">{{ report.commit_sha[:8] if report.commit_sha else 'N/A' }}</div>
            </div>
            <div class="meta-card">
                <div class="label">Duration</div>
                <div class="value">{{ "%.1f"|format(report.duration_seconds) }}s</div>
            </div>
            <div class="meta-card">
                <div class="label">Files Scanned</div>
                <div class="value">{{ report.files_scanned }}</div>
            </div>
            <div class="meta-card">
                <div class="label">Total Findings</div>
                <div class="value" style="color: {% if report.total_findings > 0 %}var(--warn){% else %}var(--pass){% endif %}">
                    {{ report.total_findings }}
                </div>
            </div>
            <div class="meta-card">
                <div class="label">Author</div>
                <div class="value">{{ report.author or 'N/A' }}</div>
            </div>
        </div>

        {% if report.total_findings > 0 %}
        <h2>Severity Distribution</h2>
        {% set total = report.total_findings or 1 %}
        <div class="severity-bar">
            {% if report.critical_count %}<span class="sev-critical" style="width:{{ (report.critical_count/total*100)|round }}%"></span>{% endif %}
            {% if report.high_count %}<span class="sev-high" style="width:{{ (report.high_count/total*100)|round }}%"></span>{% endif %}
            {% if report.medium_count %}<span class="sev-medium" style="width:{{ (report.medium_count/total*100)|round }}%"></span>{% endif %}
            {% if report.low_count %}<span class="sev-low" style="width:{{ (report.low_count/total*100)|round }}%"></span>{% endif %}
            {% if report.info_count %}<span class="sev-info" style="width:{{ (report.info_count/total*100)|round }}%"></span>{% endif %}
        </div>
        <div style="display:flex; gap:1.5rem; font-size:0.85rem; color:var(--text-muted);">
            <span>🔴 Critical: {{ report.critical_count }}</span>
            <span>🟠 High: {{ report.high_count }}</span>
            <span>🟡 Medium: {{ report.medium_count }}</span>
            <span>🔵 Low: {{ report.low_count }}</span>
            <span>⚪ Info: {{ report.info_count }}</span>
        </div>
        {% endif %}

        <h2>Scanner Results</h2>
        <div class="scanner-grid">
            {% for result in report.scan_results %}
            <div class="scanner-card">
                <h3>{{ result.scanner_name | capitalize }}</h3>
                <div class="count" style="color: {% if result.finding_count == 0 %}var(--pass){% elif result.critical_count > 0 %}var(--critical){% else %}var(--warn){% endif %}">
                    {{ result.finding_count }}
                </div>
                <div style="font-size:0.85rem; color:var(--text-muted); margin-top:0.3rem;">
                    {% if result.skipped %}⏭️ Skipped: {{ result.skip_reason }}
                    {% elif not result.success %}❌ Error: {{ result.error_message[:50] }}
                    {% else %}✅ {{ result.duration_seconds }}s — {{ result.files_scanned }} files
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>

        {% if report.all_findings %}
        <h2>Findings ({{ report.total_findings }})</h2>
        <table>
            <thead>
                <tr>
                    <th>Severity</th>
                    <th>Scanner</th>
                    <th>Rule</th>
                    <th>Message</th>
                    <th>Location</th>
                </tr>
            </thead>
            <tbody>
                {% for finding in report.all_findings[:100] %}
                <tr>
                    <td><span class="badge badge-{{ finding.severity.value }}">{{ finding.severity.value | upper }}</span></td>
                    <td>{{ finding.scanner }}</td>
                    <td style="font-family:monospace; font-size:0.8rem;">{{ finding.rule_id }}</td>
                    <td>{{ finding.message[:120] }}</td>
                    <td style="font-family:monospace; font-size:0.8rem;">
                        {% if finding.file_path %}{{ finding.file_path }}{% if finding.line_number %}:{{ finding.line_number }}{% endif %}{% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% if report.total_findings > 100 %}
        <p style="color:var(--text-muted); text-align:center;">Showing first 100 of {{ report.total_findings }} findings</p>
        {% endif %}
        {% endif %}

        {% if report.gate_results %}
        <h2>Quality Gates</h2>
        <table>
            <thead><tr><th>Gate</th><th>Result</th><th>Details</th></tr></thead>
            <tbody>
                {% for gate in report.gate_results %}
                <tr>
                    <td>{{ gate.gate_name }}</td>
                    <td>{% if gate.passed %}<span style="color:var(--pass)">✓ PASS</span>
                        {% else %}<span style="color:var(--fail)">✗ BLOCK</span>{% endif %}</td>
                    <td>{{ gate.message }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% endif %}

        <footer>
            Generated by CQ Pipeline v1.0.0 at {{ report.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC') }}
        </footer>
    </div>
</body>
</html>"""


class HTMLReporter(BaseReporter):
    """Generates self-contained HTML dashboard reports."""

    def generate(self, report: PipelineReport, output_path: Path | None = None) -> str:
        """Generate an HTML report."""
        template = Template(HTML_TEMPLATE)
        html = template.render(report=report)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html, encoding="utf-8")
            logger.info("HTML report written to %s", output_path)

        return html
