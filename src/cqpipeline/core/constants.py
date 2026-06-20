"""
Constants and enumerations used throughout the CQ Pipeline.

Centralizing these values prevents magic strings/numbers and ensures consistency
across all scanner modules, gates, and reporters.
"""

from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    """Finding severity levels, ordered from most to least critical."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @property
    def weight(self) -> int:
        """Numeric weight for sorting (higher = more severe)."""
        weights = {
            Severity.CRITICAL: 5,
            Severity.HIGH: 4,
            Severity.MEDIUM: 3,
            Severity.LOW: 2,
            Severity.INFO: 1,
        }
        return weights[self]

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.weight >= other.weight

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.weight > other.weight

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.weight <= other.weight

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.weight < other.weight


class Verdict(str, Enum):
    """Pipeline verdict after quality gate evaluation."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    ERROR = "error"


class ScanMode(str, Enum):
    """What files to scan."""

    STAGED = "staged"        # Only git-staged files (pre-commit)
    ALL = "all"              # Entire project
    FILES = "files"          # Specific file list
    DIFF = "diff"            # Changed files vs. base branch (CI/CD)


class ScannerCategory(str, Enum):
    """Scanner categories for classification."""

    SECRETS = "secrets"
    LINTING = "linting"
    SAST = "sast"
    DEPENDENCIES = "dependencies"
    QUALITY = "quality"
    FILES = "files"
    TYPE_CHECKING = "type_checking"
    COMPILER = "compiler"


class GateAction(str, Enum):
    """What to do when a gate threshold is breached."""

    BLOCK = "block"
    WARN = "warn"
    INFO = "info"
    IGNORE = "ignore"


# ─── Exit Codes ──────────────────────────────────────────────────────
# Standard exit codes for the pipeline CLI.

class ExitCode:
    """Process exit codes."""

    SUCCESS = 0               # All checks passed
    QUALITY_GATE_FAILED = 1   # Quality gate blocked the commit
    SCANNER_ERROR = 2         # A scanner encountered an error
    CONFIG_ERROR = 3          # Configuration error
    TIMEOUT = 4               # Pipeline timed out
    INTERNAL_ERROR = 99       # Unexpected internal error


# ─── Default Values ──────────────────────────────────────────────────

DEFAULT_TIMEOUT = 120          # seconds
DEFAULT_SCANNER_TIMEOUT = 60   # seconds
DEFAULT_PARALLEL_WORKERS = 4
DEFAULT_CONFIG_PATH = "config/pipeline.yaml"
DEFAULT_GATES_PATH = "config/quality-gates.yaml"
DEFAULT_REPORT_DIR = "reports"
DEFAULT_LOG_LEVEL = "INFO"

# ─── Supported Languages ─────────────────────────────────────────────

LANGUAGE_EXTENSIONS: dict[str, list[str]] = {
    "python": [".py", ".pyw", ".pyi"],
    "javascript": [".js", ".jsx", ".mjs"],
    "typescript": [".ts", ".tsx"],
    "go": [".go"],
    "java": [".java"],
    "ruby": [".rb"],
    "rust": [".rs"],
    "c": [".c", ".h"],
    "cpp": [".cpp", ".hpp", ".cc", ".cxx"],
    "csharp": [".cs"],
    "yaml": [".yaml", ".yml"],
    "json": [".json"],
    "toml": [".toml"],
    "shell": [".sh", ".bash"],
    "dockerfile": ["Dockerfile"],
}

# ─── Debug Statement Patterns ────────────────────────────────────────

DEBUG_PATTERNS: dict[str, list[str]] = {
    "python": [
        r"print\s*\(",
        r"pdb\.set_trace\s*\(",
        r"breakpoint\s*\(",
        r"import\s+pdb",
        r"import\s+ipdb",
    ],
    "javascript": [
        r"console\.log\s*\(",
        r"console\.debug\s*\(",
        r"debugger",
        r"alert\s*\(",
    ],
    "go": [
        r"fmt\.Println\s*\(",
        r"fmt\.Printf\s*\(",
        r"log\.Println\s*\(",
    ],
}

# ─── Dangerous Functions ─────────────────────────────────────────────
# These are checked by the SAST scanner but also listed here for the
# file scanner's quick regex-based check.

DANGEROUS_FUNCTIONS: dict[str, list[str]] = {
    "python": [
        r"eval\s*\(",
        r"exec\s*\(",
        r"__import__\s*\(",
        r"compile\s*\(",
        r"os\.system\s*\(",
        r"subprocess\.call\s*\(.*shell\s*=\s*True",
        r"pickle\.loads?\s*\(",
        r"yaml\.load\s*\(",           # without Loader= is unsafe
        r"marshal\.loads?\s*\(",
        r"shelve\.open\s*\(",
    ],
    "javascript": [
        r"eval\s*\(",
        r"Function\s*\(",
        r"setTimeout\s*\(\s*['\"]",   # string argument to setTimeout
        r"setInterval\s*\(\s*['\"]",
        r"innerHTML\s*=",
        r"document\.write\s*\(",
    ],
}
