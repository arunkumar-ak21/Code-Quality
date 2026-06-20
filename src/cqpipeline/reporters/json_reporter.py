"""
JSON Reporter — structured JSON output for machine consumption.

Produces a complete JSON document with all scan results, findings,
gate evaluations, and metadata. Used for:
- CI/CD artifact uploads
- API submission to the dashboard
- Integration with other tools
- Historical archiving
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from cqpipeline.core.models import PipelineReport
from cqpipeline.reporters.base import BaseReporter
from cqpipeline.utils.logger import get_logger

logger = get_logger(__name__)


class JSONReporter(BaseReporter):
    """Generates structured JSON reports."""

    def generate(self, report: PipelineReport, output_path: Path | None = None) -> str:
        """Generate a JSON report."""
        report_dict = report.model_dump(mode="json")

        json_str = json.dumps(report_dict, indent=2, default=str)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json_str, encoding="utf-8")
            logger.info("JSON report written to %s", output_path)

        return json_str
