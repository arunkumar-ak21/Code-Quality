"""
Scan API routes — submit and query scan results.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.scan import Finding, Project, Scan
from api.schemas.scan import (
    ScanCreate,
    ScanDetailResponse,
    ScanListResponse,
    ScanResponse,
)

router = APIRouter(prefix="/scans", tags=["Scans"])


@router.post("/", response_model=ScanResponse, status_code=201)
async def create_scan(
    scan_data: ScanCreate,
    db: AsyncSession = Depends(get_db),
) -> Scan:
    """Submit scan results from a pipeline run."""
    # Get or create project
    result = await db.execute(
        select(Project).where(Project.name == scan_data.project_name)
    )
    project = result.scalar_one_or_none()

    if not project:
        project = Project(name=scan_data.project_name)
        db.add(project)
        await db.flush()

    # Create scan
    scan = Scan(
        project_id=project.id,
        commit_sha=scan_data.commit_sha,
        branch=scan_data.branch,
        author=scan_data.author,
        scan_mode=scan_data.scan_mode,
        verdict=scan_data.verdict,
        duration_seconds=scan_data.duration_seconds,
        total_findings=scan_data.total_findings,
        critical_count=scan_data.critical_count,
        high_count=scan_data.high_count,
        medium_count=scan_data.medium_count,
        low_count=scan_data.low_count,
        info_count=scan_data.info_count,
        files_scanned=scan_data.files_scanned,
    )
    db.add(scan)
    await db.flush()

    # Create findings
    for finding_data in scan_data.findings:
        finding = Finding(
            scan_id=scan.id,
            scanner=finding_data.scanner,
            category=finding_data.category,
            severity=finding_data.severity,
            rule_id=finding_data.rule_id,
            title=finding_data.title,
            message=finding_data.message,
            file_path=finding_data.file_path,
            line_number=finding_data.line_number,
            column_number=finding_data.column_number,
            code_snippet=finding_data.code_snippet,
            suggestion=finding_data.suggestion,
            cwe_id=finding_data.cwe_id,
            cve_id=finding_data.cve_id,
        )
        db.add(finding)

    await db.commit()
    await db.refresh(scan)
    return scan


@router.get("/", response_model=ScanListResponse)
async def list_scans(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    verdict: str | None = None,
    branch: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List scans with pagination and filtering."""
    query = select(Scan).order_by(Scan.created_at.desc())

    if verdict:
        query = query.where(Scan.verdict == verdict)
    if branch:
        query = query.where(Scan.branch == branch)

    # Count total
    count_query = select(func.count()).select_from(Scan)
    if verdict:
        count_query = count_query.where(Scan.verdict == verdict)
    if branch:
        count_query = count_query.where(Scan.branch == branch)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    scans = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "scans": scans,
    }


@router.get("/{scan_id}", response_model=ScanDetailResponse)
async def get_scan(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
) -> Scan:
    """Get detailed scan results including findings."""
    result = await db.execute(
        select(Scan).where(Scan.id == scan_id)
    )
    scan = result.scalar_one_or_none()

    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    return scan
