# Architecture Documentation

## System Architecture

The CQ Pipeline follows a **three-layer security strategy**:

| Layer | Placement | Purpose | Speed |
|-------|-----------|---------|-------|
| **Local** | Pre-commit hooks | Immediate developer feedback, block secrets | < 10s |
| **CI/CD** | PR/Merge Request | Enforcement, deeper analysis, dependency scan | < 5min |
| **Full** | Scheduled/On-demand | Complete audit, history scan, compliance | < 30min |

## Component Architecture

```
┌──────────────────────────────────────────────────┐
│                   CLI / Git Hook                  │
│              (src/cqpipeline/cli.py)              │
└──────────────────┬───────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────┐
│              Pipeline Orchestrator                │
│          (src/cqpipeline/core/orchestrator.py)    │
│                                                   │
│  • Loads configuration                            │
│  • Discovers enabled scanners                     │
│  • Runs scanners in parallel (asyncio)            │
│  • Collects results                               │
│  • Evaluates quality gates                        │
│  • Generates reports                              │
└──┬──────┬──────┬──────┬──────┬──────┬──────┬─────┘
   │      │      │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼      ▼      ▼
┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐
│ SEC ││LINT ││SAST ││ DEP ││QUAL ││FILE ││TYPE │
│     ││     ││     ││     ││     ││     ││     │
│Gitleak│Ruff │Semgr.│pip-  │Radon │.env  │MyPy │
│detect│Black │Bandit│audit │AST   │size  │     │
│Truff.│Pylint│     │Safety│      │debug │     │
└─────┘└─────┘└─────┘└─────┘└─────┘└─────┘└─────┘
   │      │      │      │      │      │      │
   └──────┴──────┴──────┴──────┼──────┴──────┘
                               │
                   ┌───────────▼───────────┐
                   │   Quality Gate Engine  │
                   │  (gates/evaluator.py)  │
                   └───────────┬───────────┘
                               │
                   ┌───────────▼───────────┐
                   │   Report Generators    │
                   │  Terminal / JSON / HTML │
                   └───────────────────────┘
```

## Data Flow

1. **Input**: Git staged files (pre-commit) or all project files
2. **Configuration**: Loaded from YAML configs with env var overrides
3. **Scanning**: All enabled scanners run in parallel via `asyncio.gather()`
4. **Normalization**: Each scanner's output is normalized to `Finding` objects
5. **Gate Evaluation**: Findings are evaluated against configurable thresholds
6. **Reporting**: Results are rendered as terminal output, JSON, or HTML
7. **Verdict**: PASS (exit 0) or FAIL (exit 1) — controls git commit/push

## Design Principles

- **Plugin Architecture**: New scanners implement `BaseScanner` — no orchestrator changes needed
- **Defense in Depth**: Multiple tools for the same category (e.g., 3 secret scanners)
- **Fail Open**: If a scanner tool isn't installed, skip with warning (don't block the developer)
- **Configurable Policies**: Everything is tunable via YAML config + env vars
- **Allowlisting**: Proper false-positive management with audit trail
- **Parallel Execution**: Scanners run concurrently for speed
- **Structured Logging**: JSON logs for observability, colored logs for developers

## Technology Choices

| Choice | Why |
|--------|-----|
| **Ruff over Flake8** | 100x faster, single tool replaces Flake8+isort+pyupgrade |
| **asyncio over threading** | Better concurrency model for I/O-bound subprocess calls |
| **Pydantic models** | Type-safe data contracts, automatic JSON serialization |
| **Click CLI** | Composable subcommands, type validation, help generation |
| **Rich terminal** | Beautiful output increases developer adoption |
| **Jinja2 HTML** | Self-contained reports without frontend build tooling |
| **SQLAlchemy async** | Works with PostgreSQL (prod) and SQLite (dev) |
