"""
API Configuration — settings loaded from environment variables.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class APISettings(BaseSettings):
    """API configuration loaded from environment variables."""

    # App
    app_name: str = "CQ Pipeline Dashboard"
    app_version: str = "1.0.0"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./cqpipeline.db"
    # For PostgreSQL: "postgresql+asyncpg://user:pass@localhost:5432/cqpipeline"

    # Security
    api_key: str = ""  # Set via CQ_API_KEY env var
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Rate limiting
    rate_limit: str = "100/minute"

    model_config = {
        "env_prefix": "CQ_",
        "env_file": ".env",
        "case_sensitive": False,
    }


settings = APISettings()
