# Configuration Guide

## Configuration Files

The CQ Pipeline uses a layered configuration system. Settings are resolved in this order (later overrides earlier):

1. **Built-in defaults** → hardcoded in `src/cqpipeline/core/config.py`
2. **`config/pipeline.yaml`** → project-level pipeline settings
3. **`config/quality-gates.yaml`** → pass/fail thresholds
4. **Environment variables** → `CQ_` prefixed overrides

---

## Main Pipeline Configuration

**File:** `config/pipeline.yaml`

### Pipeline Section
```yaml
pipeline:
  name: "Code Quality Pipeline"   # Display name for reports
  version: "1.0.0"
  timeout: 120                     # Global pipeline timeout (seconds)
  parallel_workers: 4              # Max concurrent scanners
  fail_on_scanner_error: false     # Fail pipeline if a scanner crashes
  default_scan_mode: "staged"      # staged | all | files
  report_dir: "reports"            # Where to save reports
  log_level: "INFO"                # DEBUG | INFO | WARNING | ERROR
```

### Scanner Configuration
```yaml
scanners:
  secrets:
    enabled: true
    timeout: 30
    tools:
      gitleaks:
        enabled: true
        config_path: ""            # Custom gitleaks.toml path
      detect_secrets:
        enabled: true
      trufflehog:
        enabled: false             # Enable in CI/CD only (slow)

  linting:
    enabled: true
    timeout: 60
    tools:
      ruff: { enabled: true }
      black: { enabled: true, check_only: true }
      pylint: { enabled: true, min_score: 8.0 }

  sast:
    enabled: true
    timeout: 60
    tools:
      semgrep:
        enabled: true
        config: "auto"             # "auto" = community rules
        custom_rules_dir: ""       # Path to org-specific rules
      bandit:
        enabled: true
        severity_level: "medium"
        confidence_level: "medium"

  dependencies:
    enabled: true
    tools:
      pip_audit: { enabled: true }
      safety: { enabled: true }

  quality:
    enabled: true
    tools:
      radon: { enabled: true }

  files:
    enabled: true
    timeout: 10

  type_checking:
    enabled: false                 # Disabled by default — slow
```

---

## Quality Gates Configuration

**File:** `config/quality-gates.yaml`

### Severity Actions
Controls what happens when findings of each severity are detected:

```yaml
severity_actions:
  critical: "block"    # block | warn | info | ignore
  high: "block"
  medium: "warn"
  low: "info"
  info: "ignore"
```

### Thresholds
```yaml
max_findings:
  critical: 0          # Zero tolerance
  high: 0              # Zero tolerance
  medium: 20           # Allow up to 20
  low: -1              # Unlimited (-1)
  total: 50            # Hard cap

quality:
  max_cyclomatic_complexity: 15
  max_function_lines: 100
  max_file_lines: 1000

files:
  max_file_size_bytes: 2097152   # 2MB
  block_env_files: true
  block_debug_statements: true
```

---

## Environment Variable Overrides

Any config value can be overridden via environment variables with the `CQ_` prefix. Nesting uses double underscores:

```bash
# Override pipeline timeout
export CQ_PIPELINE__TIMEOUT=300

# Disable a scanner
export CQ_SCANNERS__LINTING__ENABLED=false

# Change log level
export CQ_PIPELINE__LOG_LEVEL=DEBUG

# Set API key
export CQ_API_KEY=your-secret-key
```

---

## Allowlist Configuration

**File:** `config/allowlist.yaml`

Suppress false positives with required justification:

```yaml
# Exclude entire files
files:
  - path: "tests/fixtures/fake_secrets.py"
    reason: "Test fixtures with dummy secrets"
    approved_by: "security-team"

# Exclude specific patterns
patterns:
  - pattern: "AKIAIOSFODNN7EXAMPLE"
    reason: "AWS documentation example key"

# Disable specific rules globally
rules:
  - rule_id: "B101"
    reason: "assert is fine in tests"

# Exclude path patterns
path_patterns:
  - "tests/**"
  - "vendor/**"

# Scanner-specific exclusions
findings:
  - scanner: "bandit"
    rule_id: "B101"
    file: "tests/**"
    reason: "assert in test files is expected"
```

---

## Custom Secret Patterns

**File:** `config/secret-patterns.yaml`

Add organization-specific patterns beyond what Gitleaks detects:

```yaml
patterns:
  - id: "internal-api-key"
    description: "Internal API Key"
    regex: 'INTERNAL_KEY_[A-Za-z0-9]{32}'
    severity: "critical"
    keywords: ["INTERNAL_KEY_"]

entropy:
  enabled: true
  hex_threshold: 3.5
  base64_threshold: 4.5
```

---

## Language Profiles

**Directory:** `config/language-profiles/`

Per-language scanner and debug-pattern configuration. Files: `python.yaml`, `javascript.yaml`, etc.

```yaml
# python.yaml
language: python
extensions: [".py", ".pyw", ".pyi"]
debug_patterns:
  - 'print\s*\('
  - 'breakpoint\s*\('
  - 'pdb\.set_trace\s*\('
```
