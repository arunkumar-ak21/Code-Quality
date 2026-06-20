"""
Custom exception hierarchy for the CQ Pipeline.

Each exception carries structured context to enable detailed error reporting
without leaking internal details in user-facing messages.
"""

from __future__ import annotations


class CQPipelineError(Exception):
    """Base exception for all CQ Pipeline errors."""

    def __init__(self, message: str, *, details: str | None = None) -> None:
        super().__init__(message)
        self.details = details


class ConfigurationError(CQPipelineError):
    """Raised when pipeline configuration is invalid or missing."""

    def __init__(self, message: str, *, config_path: str | None = None) -> None:
        super().__init__(message, details=f"Config path: {config_path}")
        self.config_path = config_path


class ScannerError(CQPipelineError):
    """Raised when a scanner encounters an error during execution."""

    def __init__(
        self,
        message: str,
        *,
        scanner_name: str,
        exit_code: int | None = None,
        stderr: str | None = None,
    ) -> None:
        super().__init__(message, details=f"Scanner: {scanner_name}, Exit: {exit_code}")
        self.scanner_name = scanner_name
        self.exit_code = exit_code
        self.stderr = stderr


class ScannerNotFoundError(ScannerError):
    """Raised when a required external scanner tool is not installed."""

    def __init__(self, scanner_name: str, tool_name: str) -> None:
        super().__init__(
            f"Scanner tool '{tool_name}' is not installed. "
            f"Install it or disable the '{scanner_name}' scanner in config.",
            scanner_name=scanner_name,
        )
        self.tool_name = tool_name


class QualityGateError(CQPipelineError):
    """Raised when quality gate configuration is invalid."""


class TimeoutError(CQPipelineError):
    """Raised when a scanner or the pipeline exceeds its timeout."""

    def __init__(self, message: str, *, timeout_seconds: float) -> None:
        super().__init__(message, details=f"Timeout: {timeout_seconds}s")
        self.timeout_seconds = timeout_seconds


class ReportError(CQPipelineError):
    """Raised when report generation fails."""


class GitError(CQPipelineError):
    """Raised when git operations fail."""
