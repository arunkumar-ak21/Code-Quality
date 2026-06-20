"""
Configuration loader with layered resolution: defaults → YAML files → environment variables.

Supports the CQ_ prefix for environment variable overrides, e.g.:
  CQ_PIPELINE__TIMEOUT=180  →  pipeline.timeout = 180
  CQ_SCANNERS__SECRETS__ENABLED=false  →  scanners.secrets.enabled = false
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from cqpipeline.core.constants import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_GATES_PATH,
)
from cqpipeline.core.exceptions import ConfigurationError
from cqpipeline.utils.logger import get_logger

logger = get_logger(__name__)


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override dict into base dict."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _apply_env_overrides(config: dict, prefix: str = "CQ") -> dict:
    """
    Apply environment variable overrides to config.

    Environment variables follow the pattern:
      CQ_<SECTION>__<KEY>=<VALUE>

    Double underscores (__) denote nesting levels.
    Example: CQ_PIPELINE__TIMEOUT=180
    """
    env_prefix = f"{prefix}_"
    for env_key, env_value in os.environ.items():
        if not env_key.startswith(env_prefix):
            continue

        # Strip prefix and split on double underscore for nesting
        path_str = env_key[len(env_prefix):]
        path_parts = [p.lower() for p in path_str.split("__")]

        if not path_parts:
            continue

        # Navigate to the correct nesting level
        current = config
        for part in path_parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Set the value with type coercion
        final_key = path_parts[-1]
        current[final_key] = _coerce_value(env_value)

    return config


def _coerce_value(value: str) -> Any:
    """Coerce string environment variable values to appropriate Python types."""
    # Boolean
    if value.lower() in ("true", "yes", "1", "on"):
        return True
    if value.lower() in ("false", "no", "0", "off"):
        return False

    # Integer
    try:
        return int(value)
    except ValueError:
        pass

    # Float
    try:
        return float(value)
    except ValueError:
        pass

    return value


class PipelineConfigLoader:
    """
    Loads and merges pipeline configuration from multiple sources.

    Resolution order (later sources override earlier):
    1. Built-in defaults
    2. Project config file (config/pipeline.yaml)
    3. Quality gates config (config/quality-gates.yaml)
    4. Environment variables (CQ_ prefix)
    """

    def __init__(
        self,
        project_root: Path | None = None,
        config_path: str | None = None,
        gates_path: str | None = None,
    ) -> None:
        self.project_root = project_root or Path.cwd()
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.gates_path = gates_path or DEFAULT_GATES_PATH
        self._config: dict = {}
        self._gates: dict = {}

    def load(self) -> dict:
        """Load and merge all configuration sources."""
        # 1. Load pipeline config
        config_file = self.project_root / self.config_path
        if config_file.exists():
            self._config = self._load_yaml(config_file)
            logger.info("Loaded pipeline config from %s", config_file)
        else:
            logger.warning(
                "Pipeline config not found at %s — using defaults", config_file
            )
            self._config = self._get_defaults()

        # 2. Load quality gates config
        gates_file = self.project_root / self.gates_path
        if gates_file.exists():
            self._gates = self._load_yaml(gates_file)
            self._config["quality_gates"] = self._gates
            logger.info("Loaded quality gates from %s", gates_file)
        else:
            logger.warning("Quality gates config not found at %s", gates_file)

        # 3. Apply environment variable overrides
        self._config = _apply_env_overrides(self._config)

        return self._config

    def load_secret_patterns(self) -> dict:
        """Load custom secret detection patterns."""
        patterns_file = self.project_root / "config" / "secret-patterns.yaml"
        if patterns_file.exists():
            return self._load_yaml(patterns_file)
        return {"patterns": [], "entropy": {"enabled": False}}

    def load_allowlist(self) -> dict:
        """Load the false positive allowlist."""
        allowlist_file = self.project_root / "config" / "allowlist.yaml"
        if allowlist_file.exists():
            return self._load_yaml(allowlist_file)
        return {"files": [], "patterns": [], "rules": [], "path_patterns": [], "findings": []}

    def load_language_profile(self, language: str) -> dict:
        """Load language-specific configuration."""
        profile_file = self.project_root / "config" / "language-profiles" / f"{language}.yaml"
        if profile_file.exists():
            return self._load_yaml(profile_file)
        return {}

    @property
    def config(self) -> dict:
        """Get the loaded configuration (call load() first)."""
        if not self._config:
            self.load()
        return self._config

    @property
    def gates(self) -> dict:
        """Get the quality gates configuration."""
        return self._gates

    @staticmethod
    def _load_yaml(path: Path) -> dict:
        """Load and parse a YAML file."""
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data is None:
                    return {}
                if not isinstance(data, dict):
                    raise ConfigurationError(
                        f"Expected YAML mapping in {path}, got {type(data).__name__}",
                        config_path=str(path),
                    )
                return data
        except yaml.YAMLError as e:
            raise ConfigurationError(
                f"Invalid YAML in {path}: {e}",
                config_path=str(path),
            ) from e
        except OSError as e:
            raise ConfigurationError(
                f"Cannot read config file {path}: {e}",
                config_path=str(path),
            ) from e

    @staticmethod
    def _get_defaults() -> dict:
        """Return built-in default configuration."""
        return {
            "pipeline": {
                "name": "Code Quality Pipeline",
                "version": "1.0.0",
                "timeout": 120,
                "parallel_workers": 4,
                "fail_on_scanner_error": False,
                "default_scan_mode": "staged",
                "report_dir": "reports",
                "log_level": "INFO",
            },
            "scanners": {
                "secrets": {"enabled": True, "timeout": 30},
                "linting": {"enabled": True, "timeout": 60},
                "sast": {"enabled": True, "timeout": 60},
                "dependencies": {"enabled": True, "timeout": 60},
                "quality": {"enabled": True, "timeout": 30},
                "files": {"enabled": True, "timeout": 10},
                "type_checking": {"enabled": False, "timeout": 60},
            },
        }


def get_scanner_config(config: dict, scanner_name: str) -> dict:
    """Extract configuration for a specific scanner from the full config."""
    scanners_config = config.get("scanners", {})
    return scanners_config.get(scanner_name, {"enabled": False})


def get_pipeline_config(config: dict) -> dict:
    """Extract pipeline-level configuration."""
    return config.get("pipeline", {})


def get_gate_config(config: dict) -> dict:
    """Extract quality gate configuration."""
    return config.get("quality_gates", {})
