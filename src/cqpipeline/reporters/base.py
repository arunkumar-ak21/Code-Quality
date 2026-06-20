"""
Abstract base class for report generators.
"""

from __future__ import annotations

import abc
from pathlib import Path

from cqpipeline.core.models import PipelineReport


class BaseReporter(abc.ABC):
    """Base class for report generators."""

    @abc.abstractmethod
    def generate(self, report: PipelineReport, output_path: Path | None = None) -> str:
        """
        Generate a report from the pipeline results.

        Args:
            report: The pipeline report to render.
            output_path: Optional path to write the report to.

        Returns:
            The rendered report as a string.
        """
        ...
