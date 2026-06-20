"""Pydantic schemas for scan-related API operations."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ─── Finding Schemas ──────────────────────────────────────────────────

class FindingCreate(BaseModel):
    scanner: str
    category: str
    severity: str
    rule_id: str = ""
    title: str = ""
    message: str = ""
    file_path: str = ""
    line_number: int = 0
    column_number: int = 0
    code_snippet: str = ""
    suggestion: str = ""
    cwe_id: str = ""
    cve_id: str = ""


class FindingResponse(BaseModel):
    id: str
    scan_id: str
    scanner: str
    category: str
    severity: str
    rule_id: str
    title: str
    message: str
    file_path: str
    line_number: int
    column_number: int
    code_snippet: str
    suggestion: str
    cwe_id: str
    cve_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Scan Schemas ─────────────────────────────────────────────────────

class ScanCreate(BaseModel):
    """Schema for submitting scan results."""
    project_name: str = Field(description="Project/repository name")
    commit_sha: str = ""
    branch: str = ""
    author: str = ""
    scan_mode: str = "staged"
    verdict: str = Field(description="pass, fail, warn, error")
    duration_seconds: float = 0.0
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    files_scanned: int = 0
    findings: list[FindingCreate] = Field(default_factory=list)


class ScanResponse(BaseModel):
    id: str
    project_id: Optional[str] = None
    commit_sha: str
    branch: str
    author: str
    scan_mode: str
    verdict: str
    duration_seconds: float
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int
    files_scanned: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ScanDetailResponse(ScanResponse):
    findings: list[FindingResponse] = Field(default_factory=list)


class ScanListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    scans: list[ScanResponse]


# ─── Project Schemas ──────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    repo_url: str = ""
    description: str = ""


class ProjectResponse(BaseModel):
    id: str
    name: str
    repo_url: str
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Metrics Schemas ──────────────────────────────────────────────────

class MetricsSummary(BaseModel):
    total_scans: int = 0
    total_findings: int = 0
    pass_rate: float = 0.0
    avg_duration: float = 0.0
    most_common_severity: str = ""
    top_scanners: list[dict] = Field(default_factory=list)


class TrendPoint(BaseModel):
    date: str
    total_findings: int
    critical: int
    high: int
    pass_rate: float
