"""
backend/app/main.py
EduPlus AI Timetable Maker — FastAPI Application Entry Point
Includes production configuration validation, request-ID correlation,
structured request logging, security headers, and startup orphan-job recovery.
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.v1.router import api_v1_router
from backend.app.core.config import settings, validate_production_config
from backend.app.core.logging import logger, request_id_ctx
from backend.app.db.session import SessionLocal
from backend.app.services.job_runner import generation_job_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Fail fast if production environment has insecure/missing configuration
    config_errors = validate_production_config(settings)
    if config_errors:
        for err in config_errors:
            logger.error(f"Configuration validation error: {err}")
        raise RuntimeError("Invalid production configuration: " + "; ".join(config_errors))

    # 2. Recover any orphaned 'running' generation runs left by a previous crash
    db = SessionLocal()
    try:
        generation_job_manager.recover_orphaned_runs(db)
    except Exception as exc:
        logger.warning(f"Startup orphan-run recovery skipped: {type(exc).__name__}")
    finally:
        db.close()

    logger.info(
        f"Starting {settings.PROJECT_NAME} v{settings.VERSION} "
        f"[env={settings.ENVIRONMENT}, docs={'on' if settings.ENABLE_DOCS else 'off'}]"
    )
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}")


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="EduPlus AI Timetable Maker — Academic Scheduling Platform API",
        docs_url="/docs" if settings.ENABLE_DOCS else None,
        redoc_url="/redoc" if settings.ENABLE_DOCS else None,
        openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
        lifespan=lifespan,
    )

    # Configure CORS with explicit origins (no wildcard '*' with credentials)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-CSRF-Token", "X-Request-ID"],
    )

    # Request ID correlation, structured access logging & security headers middleware
    @app.middleware("http")
    async def observability_and_security_middleware(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token_ctx = request_id_ctx.set(req_id)
        t0 = time.monotonic()
        try:
            response = await call_next(request)
            elapsed_ms = int((time.monotonic() - t0) * 1000)

            response.headers["X-Request-ID"] = req_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            if request.url.path.startswith(f"{settings.API_V1_PREFIX}/auth"):
                response.headers["Cache-Control"] = "no-store"

            logger.info(
                f"{request.method} {request.url.path} -> {response.status_code} ({elapsed_ms}ms)"
            )
            return response
        finally:
            request_id_ctx.reset(token_ctx)

    # Global Exception Handler (never leaks internal stack/SQL details)
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        req_id = request_id_ctx.get()
        logger.error(f"Unhandled error processing {request.method} {request.url.path}: {type(exc).__name__}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "request_id": req_id,
                "message": "An internal server error occurred.",
                "detail": "Internal server error. Please contact an administrator if the issue persists.",
            },
        )

    # Root endpoint
    @app.get("/", tags=["Root"])
    def root():
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "health": f"{settings.API_V1_PREFIX}/health",
            "readiness": f"{settings.API_V1_PREFIX}/health/ready",
        }

    # Register API v1
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()
