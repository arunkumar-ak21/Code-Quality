"""SQLAlchemy ORM models for scan data."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from api.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    """Represents a scanned project/repository."""

    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False, unique=True)
    repo_url = Column(String(500), default="")
    description = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    scans = relationship("Scan", back_populates="project", lazy="selectin")


class Scan(Base):
    """Represents a single pipeline scan execution."""

    __tablename__ = "scans"

    id = Column(String(36), primary_key=True, default=_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=True)
    commit_sha = Column(String(40), default="")
    branch = Column(String(255), default="")
    author = Column(String(255), default="")
    scan_mode = Column(String(20), default="staged")
    verdict = Column(String(10), nullable=False)  # pass, fail, warn, error
    duration_seconds = Column(Float, default=0.0)
    total_findings = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)
    info_count = Column(Integer, default=0)
    files_scanned = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    project = relationship("Project", back_populates="scans")
    findings = relationship("Finding", back_populates="scan", lazy="selectin")


class Finding(Base):
    """Represents a single finding from a scan."""

    __tablename__ = "findings"

    id = Column(String(36), primary_key=True, default=_uuid)
    scan_id = Column(String(36), ForeignKey("scans.id"), nullable=False)
    scanner = Column(String(50), nullable=False)
    category = Column(String(30), nullable=False)
    severity = Column(String(10), nullable=False)
    rule_id = Column(String(100), default="")
    title = Column(String(500), default="")
    message = Column(Text, default="")
    file_path = Column(String(500), default="")
    line_number = Column(Integer, default=0)
    column_number = Column(Integer, default=0)
    code_snippet = Column(Text, default="")
    suggestion = Column(Text, default="")
    cwe_id = Column(String(50), default="")
    cve_id = Column(String(50), default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    scan = relationship("Scan", back_populates="findings")
