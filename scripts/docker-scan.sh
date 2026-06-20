#!/usr/bin/env bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CQ Pipeline — Docker Scan Runner
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Runs the full pipeline scan inside a Docker container.
# No local tool installation required.
#
# Usage:
#   bash scripts/docker-scan.sh                # Scan current directory
#   bash scripts/docker-scan.sh /path/to/repo  # Scan specific directory
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -euo pipefail

IMAGE_NAME="cq-pipeline:latest"
TARGET_DIR="${1:-.}"
TARGET_DIR=$(cd "$TARGET_DIR" && pwd)

echo "🐳 CQ Pipeline — Docker Scan"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Target: $TARGET_DIR"
echo "  Image:  $IMAGE_NAME"
echo ""

# Check if image exists, build if not
if ! docker image inspect "$IMAGE_NAME" &> /dev/null; then
    echo "📦 Building Docker image (first time)..."
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    docker build -f "$PROJECT_DIR/docker/Dockerfile" -t "$IMAGE_NAME" "$PROJECT_DIR"
    echo ""
fi

# Run scan
echo "🔍 Running scan..."
echo ""

docker run --rm \
    -v "$TARGET_DIR:/workspace" \
    -w /workspace \
    "$IMAGE_NAME" \
    scan --all --format terminal

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Docker scan completed — all checks passed!"
else
    echo "❌ Docker scan found issues (exit code: $EXIT_CODE)"
fi

exit $EXIT_CODE
