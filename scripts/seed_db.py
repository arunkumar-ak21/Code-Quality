#!/usr/bin/env python3
"""
Seed script to inject dummy data into the Code-Quality database for the dashboard.
"""

import asyncio
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import SessionLocal, engine
from api.models.scan import Finding, Project, Scan
from cqpipeline.core.constants import ScannerCategory, Severity, Verdict


async def clear_data(db: AsyncSession):
    await db.execute(delete(Finding))
    await db.execute(delete(Scan))
    await db.execute(delete(Project))
    await db.commit()


async def seed_data():
    async with SessionLocal() as db:
        print("Clearing existing data...")
        await clear_data(db)

        print("Creating project...")
        project = Project(name="Code-Quality-Dashboard")
        db.add(project)
        await db.flush()

        scanners = [
            ("gitleaks", ScannerCategory.SECRETS),
            ("bandit", ScannerCategory.SAST),
            ("ruff", ScannerCategory.LINTING),
            ("black", ScannerCategory.LINTING),
            ("pip_audit", ScannerCategory.DEPENDENCIES),
            ("eslint", ScannerCategory.LINTING),
        ]

        authors = ["Alice Smith", "Bob Jones", "Charlie Brown", "Diana Prince"]
        branches = ["main", "develop", "feature/auth", "fix/login-bug", "feature/dashboard"]

        now = datetime.now(timezone.utc)
        print("Creating 50 historical scans...")

        # Create 50 historical scans spanning the last 30 days
        for i in range(50):
            days_ago = 30 - int((i / 50) * 30)
            scan_time = now - timedelta(days=days_ago, hours=random.randint(1, 23))
            
            is_pass = random.random() > 0.3  # 70% pass rate
            verdict = Verdict.PASS if is_pass else random.choice([Verdict.FAIL, Verdict.WARN])
            
            # Bias more findings if it's a fail/warn
            num_findings = random.randint(0, 5) if is_pass else random.randint(3, 15)

            scan = Scan(
                id=None,  # auto-generated UUID
                project_id=project.id,
                commit_sha=f"commit-{random.randint(100000, 999999)}",
                branch=random.choice(branches),
                author=random.choice(authors),
                scan_mode="staged",
                verdict=verdict,
                duration_seconds=random.uniform(5.0, 45.0),
                total_findings=num_findings,
                critical_count=0,
                high_count=0,
                medium_count=0,
                low_count=0,
                info_count=0,
                files_scanned=random.randint(5, 100),
                created_at=scan_time,
                updated_at=scan_time,
            )
            
            db.add(scan)
            await db.flush()

            for _ in range(num_findings):
                scanner, category = random.choice(scanners)
                
                if verdict == Verdict.FAIL:
                    severity = random.choice([Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM])
                elif verdict == Verdict.WARN:
                    severity = random.choice([Severity.MEDIUM, Severity.LOW])
                else:
                    severity = random.choice([Severity.LOW, Severity.INFO])

                # Update scan counts
                if severity == Severity.CRITICAL: scan.critical_count += 1
                elif severity == Severity.HIGH: scan.high_count += 1
                elif severity == Severity.MEDIUM: scan.medium_count += 1
                elif severity == Severity.LOW: scan.low_count += 1
                elif severity == Severity.INFO: scan.info_count += 1

                finding = Finding(
                    scan_id=scan.id,
                    scanner=scanner,
                    category=category,
                    severity=severity,
                    rule_id=f"RULE-{random.randint(100, 999)}",
                    title=f"{scanner.title()} issue found",
                    message="Detailed description of the issue that needs to be fixed.",
                    file_path=f"src/components/File_{random.randint(1, 20)}.{'js' if scanner == 'eslint' else 'py'}",
                    line_number=random.randint(10, 500),
                    column_number=random.randint(1, 80),
                    code_snippet="def example_function():\n    pass # issue is here",
                    suggestion="Consider refactoring this section to adhere to best practices.",
                    created_at=scan_time,
                    updated_at=scan_time,
                )
                db.add(finding)
        
        await db.commit()
        print("Database seeded successfully with 50 scans!")

if __name__ == "__main__":
    asyncio.run(seed_data())
