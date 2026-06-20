from pathlib import Path

import pytest

from cqpipeline.scanners.compiler_scanner import CompilerScanner


@pytest.mark.asyncio
async def test_python_compile_finding_for_broken_file(tmp_path: Path):
    bad = tmp_path / "broken.py"
    bad.write_text('def broken():\n    print("missing"\n', encoding="utf-8")
    scanner = CompilerScanner(config={"timeout": 30}, project_root=tmp_path)
    result = await scanner.scan([bad])
    assert result.findings
    assert result.findings[0].rule_id == "PY-COMPILE-ERROR"
