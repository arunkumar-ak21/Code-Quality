"""Tests for the Configuration Loader."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cqpipeline.core.config import PipelineConfigLoader, _apply_env_overrides


def test_load_default_config(project_root: Path) -> None:
    """Test loading config from a project directory."""
    loader = PipelineConfigLoader(project_root=project_root)
    config = loader.load()

    assert "pipeline" in config
    assert "scanners" in config
    assert config["pipeline"]["name"] == "Test Pipeline"


def test_load_quality_gates(project_root: Path) -> None:
    """Test loading quality gates config."""
    loader = PipelineConfigLoader(project_root=project_root)
    config = loader.load()

    assert "quality_gates" in config
    gates = config["quality_gates"]
    assert "severity_actions" in gates
    assert gates["severity_actions"]["critical"] == "block"


def test_env_override() -> None:
    """Test environment variable overrides."""
    config = {
        "pipeline": {"timeout": 120, "log_level": "INFO"},
    }

    os.environ["CQ_PIPELINE__TIMEOUT"] = "300"
    try:
        result = _apply_env_overrides(config)
        assert result["pipeline"]["timeout"] == 300
    finally:
        del os.environ["CQ_PIPELINE__TIMEOUT"]


def test_load_allowlist(project_root: Path) -> None:
    """Test loading the allowlist config."""
    loader = PipelineConfigLoader(project_root=project_root)
    allowlist = loader.load_allowlist()

    assert "files" in allowlist
    assert "patterns" in allowlist
    assert "path_patterns" in allowlist


def test_missing_config_uses_defaults(tmp_path: Path) -> None:
    """Test that missing config files fall back to defaults."""
    loader = PipelineConfigLoader(project_root=tmp_path)
    config = loader.load()

    assert "pipeline" in config
    assert config["pipeline"]["timeout"] == 120  # Default
