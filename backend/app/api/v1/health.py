"""
backend/app/api/v1/health.py
EduPlus AI Timetable Maker — Liveness & Readiness Diagnostic Endpoints
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.core.config import settings
from backend.app.services.job_runner import generation_job_manager

router = APIRouter(tags=["Health"])


@router.get("/health", status_code=status.HTTP_200_OK)
def check_health(db: Session = Depends(get_db)):
    """Liveness and basic database connectivity check."""
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
    }


@router.get("/health/ready")
def check_readiness(response: Response, db: Session = Depends(get_db)):
    """
    Production readiness probe verifying:
    - PostgreSQL query connectivity
    - Core schema accessibility
    - Background solver worker pool health
    Returns HTTP 200 when ready, or HTTP 503 if any critical dependency is unavailable.
    """
    checks = {"database": "ok", "schema": "ok", "worker_pool": "ok"}
    ready = True

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        checks["database"] = "unavailable"
        ready = False

    if ready:
        try:
            db.execute(text("SELECT COUNT(*) FROM departments"))
        except Exception:
            checks["schema"] = "not_initialized"
            ready = False

    worker_health = generation_job_manager.get_health()
    if worker_health.get("status") != "healthy":
        checks["worker_pool"] = "degraded"
        ready = False

    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "ready": ready,
        "status": "ready" if ready else "not_ready",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "checks": checks,
        "workers": worker_health,
    }
