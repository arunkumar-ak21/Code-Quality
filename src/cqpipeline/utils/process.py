"""
Subprocess runner for executing external scanner tools.

Provides async subprocess execution with:
- Configurable timeouts
- stdout/stderr capture
- JSON output parsing
- Graceful error handling
- Tool availability checking
"""

from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from cqpipeline.core.exceptions import ScannerError, ScannerNotFoundError
from cqpipeline.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessResult:
    """Result from an external process execution."""

    command: list[str]
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False

    @property
    def success(self) -> bool:
        """Check if the process exited successfully."""
        return self.exit_code == 0

    def json_output(self) -> dict | list:
        """Parse stdout as JSON. Returns empty dict on failure."""
        if not self.stdout.strip():
            return {}
        try:
            return json.loads(self.stdout)
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse JSON output: %s", e)
            return {}


def check_tool_available(tool_name: str) -> bool:
    """Check if an external tool is available on PATH."""
    return shutil.which(tool_name) is not None


def require_tool(tool_name: str, scanner_name: str) -> str:
    """
    Require that an external tool is available, raising if not found.

    Returns the full path to the tool.
    """
    tool_path = shutil.which(tool_name)
    if tool_path is None:
        raise ScannerNotFoundError(scanner_name=scanner_name, tool_name=tool_name)
    return tool_path


async def run_process(
    command: list[str],
    cwd: Path | None = None,
    timeout: int = 60,
    env: dict | None = None,
    stdin_data: str | None = None,
    scanner_name: str = "unknown",
) -> ProcessResult:
    """
    Execute an external process asynchronously.

    Args:
        command: Command and arguments to execute.
        cwd: Working directory for the command.
        timeout: Maximum execution time in seconds.
        env: Additional environment variables.
        stdin_data: Data to send to process stdin.
        scanner_name: Name of the scanner (for error messages).

    Returns:
        ProcessResult with exit code, stdout, and stderr.
    """
    cmd_str = " ".join(command[:3])  # Log first 3 args only
    logger.debug("Executing: %s (timeout=%ds)", cmd_str, timeout)

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE if stdin_data else None,
            env=env,
        )

        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(
                input=stdin_data.encode() if stdin_data else None
            ),
            timeout=timeout,
        )

        return ProcessResult(
            command=command,
            exit_code=process.returncode or 0,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
        )

    except asyncio.TimeoutError:
        logger.warning("Process timed out: %s", cmd_str)
        try:
            process.kill()
            await process.wait()
        except Exception:
            pass
        return ProcessResult(
            command=command,
            exit_code=-1,
            timed_out=True,
            stderr=f"Process timed out after {timeout}s",
        )

    except FileNotFoundError:
        raise ScannerNotFoundError(
            scanner_name=scanner_name,
            tool_name=command[0],
        )

    except Exception as e:
        raise ScannerError(
            f"Failed to execute {cmd_str}: {e}",
            scanner_name=scanner_name,
        ) from e
