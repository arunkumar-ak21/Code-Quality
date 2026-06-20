from cqpipeline.core.constants import ScanMode, ScannerCategory, Severity, Verdict
from cqpipeline.core.models import Finding, PipelineReport, ScanResult
from cqpipeline.reporters.sarif_reporter import SARIFReporter


def test_sarif_reporter_generates_valid_shape():
    finding = Finding(
        scanner="unit",
        category=ScannerCategory.LINTING,
        severity=Severity.HIGH,
        rule_id="UNIT001",
        title="Unit finding",
        message="A test finding",
        file_path="x.py",
        line_number=1,
    )
    report = PipelineReport(
        verdict=Verdict.FAIL,
        scan_mode=ScanMode.ALL,
        scan_results=[ScanResult(scanner_name="unit", category=ScannerCategory.LINTING, findings=[finding])],
    )
    report.compute_aggregates()
    text = SARIFReporter().generate(report)
    assert '"version": "2.1.0"' in text
    assert "UNIT001" in text
