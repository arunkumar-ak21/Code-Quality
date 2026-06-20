"""
Metrics API routes — aggregated statistics and trends.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.scan import Finding, Scan
from api.schemas.scan import MetricsSummary

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/summary", response_model=MetricsSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get overall security posture summary."""
    # Total scans
    total_scans_result = await db.execute(select(func.count()).select_from(Scan))
    total_scans = total_scans_result.scalar() or 0

    # Total findings
    total_findings_result = await db.execute(
        select(func.sum(Scan.total_findings)).select_from(Scan)
    )
    total_findings = total_findings_result.scalar() or 0

    # Pass rate
    pass_count_result = await db.execute(
        select(func.count()).select_from(Scan).where(Scan.verdict == "pass")
    )
    pass_count = pass_count_result.scalar() or 0
    pass_rate = (pass_count / total_scans * 100) if total_scans > 0 else 0.0

    # Average duration
    avg_duration_result = await db.execute(
        select(func.avg(Scan.duration_seconds)).select_from(Scan)
    )
    avg_duration = avg_duration_result.scalar() or 0.0

    # Top scanners by finding count
    top_scanners_result = await db.execute(
        select(
            Finding.scanner,
            func.count(Finding.id).label("count"),
        )
        .group_by(Finding.scanner)
        .order_by(func.count(Finding.id).desc())
        .limit(5)
    )
    top_scanners = [
        {"scanner": row[0], "count": row[1]}
        for row in top_scanners_result.all()
    ]

    return {
        "total_scans": total_scans,
        "total_findings": total_findings,
        "pass_rate": round(pass_rate, 1),
        "avg_duration": round(avg_duration, 2),
        "most_common_severity": "high",  # Simplified
        "top_scanners": top_scanners,
    }


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "service": "cq-pipeline-api"}
