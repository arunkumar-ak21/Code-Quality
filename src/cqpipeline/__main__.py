"""Allow running the package as a module: python -m cqpipeline."""

import os
import sys

# Fix Windows terminal encoding for emoji/unicode output
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from cqpipeline.cli import cli

if __name__ == "__main__":
    cli()

