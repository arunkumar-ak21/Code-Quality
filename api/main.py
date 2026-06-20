"""
FastAPI Application — CQ Pipeline Dashboard API.

Provides REST endpoints for storing and querying scan results,
viewing metrics, and powering a future dashboard frontend.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.database import close_db, init_db
from api.routers import metrics, scans


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events — startup and shutdown."""
    # Startup: initialize database
    await init_db()
    yield
    # Shutdown: close database connections
    await close_db()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "REST API for the CQ Pipeline — Enterprise DevSecOps "
        "Security & Code Quality Platform. Submit scan results, "
        "query findings, and view metrics."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# ─── Middleware ────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────
app.include_router(scans.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")

# ─── Static Files ──────────────────────────────────────────────────
# Mount static files for the dashboard
import os
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    """Serve the SPA Dashboard at the root."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/api/v1/metrics/health",
        "error": "Dashboard UI not built yet. Create api/static/index.html."
    }

