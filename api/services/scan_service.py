"""
Scan Service — business logic for scan operations.

Decouples business logic from API route handlers for testability.
"""

from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.scan import Finding, Project, Scan
from api.schemas.scan import ScanCreate


class ScanService:
    """Service layer for scan-related operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_scan(self, scan_data: ScanCreate) -> Scan:
        """Create a scan record with its findings."""
        # Get or create project
        project = await self._get_or_create_project(scan_data.project_name)

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
        self.db.add(scan)
        await self.db.flush()

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
            self.db.add(finding)

        await self.db.commit()
        await self.db.refresh(scan)
        return scan

    async def get_scan(self, scan_id: str) -> Scan | None:
        """Get a scan by ID."""
        result = await self.db.execute(
            select(Scan).where(Scan.id == scan_id)
        )
        return result.scalar_one_or_none()

    async def list_scans(
        self,
        page: int = 1,
        page_size: int = 20,
        verdict: str | None = None,
        branch: str | None = None,
    ) -> tuple[list[Scan], int]:
        """List scans with pagination and filtering."""
        query = select(Scan).order_by(Scan.created_at.desc())
        count_query = select(func.count()).select_from(Scan)

        if verdict:
            query = query.where(Scan.verdict == verdict)
            count_query = count_query.where(Scan.verdict == verdict)
        if branch:
            query = query.where(Scan.branch == branch)
            count_query = count_query.where(Scan.branch == branch)

        # Total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginate
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        result = await self.db.execute(query)
        scans = list(result.scalars().all())

        return scans, total

    async def _get_or_create_project(self, name: str) -> Project:
        """Get an existing project or create a new one."""
        result = await self.db.execute(
            select(Project).where(Project.name == name)
        )
        project = result.scalar_one_or_none()

        if not project:
            project = Project(name=name)
            self.db.add(project)
            await self.db.flush()

        return project
