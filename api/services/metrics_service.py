"""
Metrics Service — business logic for metrics and analytics.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.scan import Finding, Scan


class MetricsService:
    """Service for computing aggregate metrics and trends."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_summary(self) -> dict:
        """Get overall security posture summary."""
        # Total scans
        total_result = await self.db.execute(
            select(func.count()).select_from(Scan)
        )
        total_scans = total_result.scalar() or 0

        # Total findings
        findings_result = await self.db.execute(
            select(func.coalesce(func.sum(Scan.total_findings), 0))
        )
        total_findings = findings_result.scalar() or 0

        # Pass rate
        pass_result = await self.db.execute(
            select(func.count()).select_from(Scan).where(Scan.verdict == "pass")
        )
        pass_count = pass_result.scalar() or 0
        pass_rate = (pass_count / total_scans * 100) if total_scans > 0 else 0.0

        # Average duration
        avg_result = await self.db.execute(
            select(func.coalesce(func.avg(Scan.duration_seconds), 0.0))
        )
        avg_duration = avg_result.scalar() or 0.0

        # Top scanners
        top_result = await self.db.execute(
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
            for row in top_result.all()
        ]

        return {
            "total_scans": total_scans,
            "total_findings": total_findings,
            "pass_rate": round(pass_rate, 1),
            "avg_duration": round(float(avg_duration), 2),
            "most_common_severity": "",
            "top_scanners": top_scanners,
        }

    async def get_trends(self, days: int = 30) -> list[dict]:
        """Get finding trends over the specified number of days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(
            select(
                func.date(Scan.created_at).label("date"),
                func.sum(Scan.total_findings).label("total"),
                func.sum(Scan.critical_count).label("critical"),
                func.sum(Scan.high_count).label("high"),
                func.count(Scan.id).label("scan_count"),
                func.sum(
                    case((Scan.verdict == "pass", 1), else_=0)
                ).label("pass_count"),
            )
            .where(Scan.created_at >= cutoff)
            .group_by(func.date(Scan.created_at))
            .order_by(func.date(Scan.created_at))
        )

        trends = []
        for row in result.all():
            scan_count = row[4] or 1
            trends.append({
                "date": str(row[0]),
                "total_findings": row[1] or 0,
                "critical": row[2] or 0,
                "high": row[3] or 0,
                "pass_rate": round((row[5] or 0) / scan_count * 100, 1),
            })

        return trends

    async def get_top_issues(self, limit: int = 10) -> list[dict]:
        """Get the most common findings across all scans."""
        result = await self.db.execute(
            select(
                Finding.rule_id,
                Finding.scanner,
                Finding.severity,
                Finding.title,
                func.count(Finding.id).label("count"),
            )
            .group_by(Finding.rule_id, Finding.scanner, Finding.severity, Finding.title)
            .order_by(func.count(Finding.id).desc())
            .limit(limit)
        )

        return [
            {
                "rule_id": row[0],
                "scanner": row[1],
                "severity": row[2],
                "title": row[3],
                "count": row[4],
            }
            for row in result.all()
        ]
