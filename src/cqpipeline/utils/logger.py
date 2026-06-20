"""
Structured logging configuration for the CQ Pipeline.

Provides JSON-formatted structured logging for production use and
human-readable colored output for development/terminal use.
"""

from __future__ import annotations

import logging
import sys
from typing import Any


class ColorFormatter(logging.Formatter):
    """Human-readable colored log formatter for terminal output."""

    COLORS = {
        logging.DEBUG: "\033[36m",      # Cyan
        logging.INFO: "\033[32m",       # Green
        logging.WARNING: "\033[33m",    # Yellow
        logging.ERROR: "\033[31m",      # Red
        logging.CRITICAL: "\033[1;31m", # Bold Red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, self.RESET)
        record.levelname = f"{color}{record.levelname:<8}{self.RESET}"
        return super().format(record)


def setup_logging(level: str = "INFO", json_format: bool = False) -> None:
    """
    Configure the root logger for the CQ Pipeline.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
        json_format: If True, output JSON-structured logs (for CI/CD).
    """
    root_logger = logging.getLogger("cqpipeline")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)

    if json_format:
        formatter = logging.Formatter(
            '{"timestamp":"%(asctime)s","level":"%(levelname)s",'
            '"logger":"%(name)s","message":"%(message)s"}'
        )
    else:
        formatter = ColorFormatter(
            "%(asctime)s %(levelname)s %(name)s — %(message)s",
            datefmt="%H:%M:%S",
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given module name.

    Always use this instead of logging.getLogger() directly to ensure
    all pipeline loggers share the cqpipeline namespace.
    """
    if not name.startswith("cqpipeline"):
        name = f"cqpipeline.{name}"
    return logging.getLogger(name)
