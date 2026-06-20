#!/usr/bin/env bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CQ Pipeline — Manual Scan Runner
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Usage:
#   bash scripts/run-scan.sh                    # Staged files
#   bash scripts/run-scan.sh --all              # Full project
#   bash scripts/run-scan.sh --format html      # HTML report
#   bash scripts/run-scan.sh --docker           # Docker mode
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -euo pipefail

MODE="--staged"
FORMAT="terminal"
DOCKER=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --all) MODE="--all"; shift ;;
        --staged) MODE="--staged"; shift ;;
        --format) FORMAT="$2"; shift 2 ;;
        --docker) DOCKER=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [ "$DOCKER" = true ]; then
    echo "🐳 Running scan in Docker container..."
    docker run --rm \
        -v "$(pwd):/workspace" \
        -w /workspace \
        cq-pipeline:latest \
        scan $MODE --format "$FORMAT"
else
    echo "🛡️ Running CQ Pipeline scan..."
    if command -v cq-pipeline &> /dev/null; then
        cq-pipeline scan $MODE --format "$FORMAT"
    else
        python -m cqpipeline scan $MODE --format "$FORMAT"
    fi
fi

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Scan passed!"
elif [ $EXIT_CODE -eq 1 ]; then
    echo "❌ Scan failed — quality gate blocked"
else
    echo "⚠️ Scan completed with warnings (exit code: $EXIT_CODE)"
fi

exit $EXIT_CODE
