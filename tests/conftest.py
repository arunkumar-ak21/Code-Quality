"""Shared test fixtures for the CQ Pipeline test suite."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Create a temporary project directory with basic structure."""
    # Create config directory
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create minimal pipeline config
    (config_dir / "pipeline.yaml").write_text("""
pipeline:
  name: Test Pipeline
  timeout: 30
  parallel_workers: 2
  fail_on_scanner_error: false
  default_scan_mode: all
  report_dir: reports
  log_level: WARNING

scanners:
  secrets:
    enabled: true
    timeout: 10
    tools:
      gitleaks: {enabled: false}
      detect_secrets: {enabled: false}
      trufflehog: {enabled: false}
  linting:
    enabled: false
  sast:
    enabled: false
  dependencies:
    enabled: false
  quality:
    enabled: false
  files:
    enabled: true
    timeout: 10
  type_checking:
    enabled: false
""")

    # Create quality gates config
    (config_dir / "quality-gates.yaml").write_text("""
severity_actions:
  critical: block
  high: block
  medium: warn
  low: info
  info: ignore
max_findings:
  critical: 0
  high: 0
  medium: 20
  low: -1
  total: 50
secrets:
  max_secrets: 0
""")

    # Create empty allowlist
    (config_dir / "allowlist.yaml").write_text("""
files: []
patterns: []
rules: []
path_patterns: []
findings: []
""")

    # Create secret patterns
    (config_dir / "secret-patterns.yaml").write_text("""
patterns: []
entropy:
  enabled: false
""")

    return tmp_path


@pytest.fixture
def sample_python_file(project_root: Path) -> Path:
    """Create a sample Python file for scanning."""
    py_file = project_root / "sample.py"
    py_file.write_text('''
def hello():
    """A simple function."""
    name = "world"
    return f"Hello, {name}!"

def calculate(x, y):
    """Calculate the sum."""
    return x + y

if __name__ == "__main__":
    print(hello())
''')
    return py_file


@pytest.fixture
def file_with_secrets(project_root: Path) -> Path:
    """Create a file with intentional fake secrets for testing."""
    secret_file = project_root / "bad_config.py"
    secret_file.write_text('''
# WARNING: These are FAKE secrets for testing only!
AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
DATABASE_URL = "postgres://admin:supersecretpassword@db.example.com:5432/mydb"
API_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
''')
    return secret_file


@pytest.fixture
def file_with_env(project_root: Path) -> Path:
    """Create an .env file for testing detection."""
    env_file = project_root / ".env"
    env_file.write_text('''
SECRET_KEY=my-secret-key
DATABASE_URL=postgres://user:pass@localhost/db
DEBUG=true
''')
    return env_file


@pytest.fixture
def file_with_debug(project_root: Path) -> Path:
    """Create a file with debug statements."""
    debug_file = project_root / "debug_code.py"
    debug_file.write_text('''
def process_data(data):
    print("Debug: processing data")
    breakpoint()
    result = data * 2
    import pdb; pdb.set_trace()
    return result
''')
    return debug_file


@pytest.fixture
def large_file(project_root: Path) -> Path:
    """Create a file exceeding the size limit."""
    large = project_root / "large_file.bin"
    large.write_bytes(b"x" * (3 * 1024 * 1024))  # 3MB
    return large
