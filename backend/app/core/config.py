"""
backend/app/core/config.py
EduPlus AI Timetable Maker — Environment-Aware Application Configuration
Supports 'development', 'testing', and 'production' with startup safety validation.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

_DEFAULT_DEV_SECRET = "eduplus-dev-secret-key-for-local-testing-only-32chars"


def _parse_bool(val: Optional[str], default: bool) -> bool:
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    PROJECT_NAME: str = "EduPlus AI Timetable Maker"
    VERSION: str = "0.7.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").strip().lower()
    API_V1_PREFIX: str = os.getenv("API_V1_PREFIX", "/api/v1")

    # Security & JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", _DEFAULT_DEV_SECRET)
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = int(os.getenv("LOGIN_RATE_LIMIT_MAX_ATTEMPTS", "10"))
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "60"))

    # Cookie & CSRF Configuration (HttpOnly cookies + Double-Submit CSRF)
    COOKIE_AUTH_ENABLED: bool = _parse_bool(
        os.getenv("COOKIE_AUTH_ENABLED"),
        default=(ENVIRONMENT == "production"),
    )
    COOKIE_SECURE: bool = _parse_bool(
        os.getenv("COOKIE_SECURE"),
        default=(ENVIRONMENT == "production"),
    )
    COOKIE_SAMESITE: str = os.getenv("COOKIE_SAMESITE", "lax").strip().lower()
    COOKIE_DOMAIN: Optional[str] = os.getenv("COOKIE_DOMAIN") or None

    # Development fallbacks & OpenAPI docs
    ENABLE_DEV_FALLBACKS: bool = _parse_bool(
        os.getenv("ENABLE_DEV_FALLBACKS"),
        default=(ENVIRONMENT != "production"),
    )
    ENABLE_DOCS: bool = _parse_bool(
        os.getenv("ENABLE_DOCS"),
        default=(ENVIRONMENT != "production"),
    )

    # Database & Connection Pooling
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres@127.0.0.1:5433/eduplus_db",
    )
    TEST_DATABASE_URL: str = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg2://postgres@127.0.0.1:5433/eduplus_test_db",
    )
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "1800"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))

    # Background Solver Workers
    SOLVER_MAX_WORKERS: int = int(os.getenv("SOLVER_MAX_WORKERS", "2"))

    # CORS (explicit origins — never combine wildcard '*' with allow_credentials=True)
    ALLOWED_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000,http://127.0.0.1:3000,http://localhost:5500,http://127.0.0.1:5500,null",
        ).split(",")
        if origin.strip()
    ]

    # Server & Observability
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json" if ENVIRONMENT == "production" else "text").strip().lower()

    # AI / LLM Configuration
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")  # "auto", "gemini", "mock"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


def validate_production_config(cfg: Settings) -> List[str]:
    """
    Validate required production security and infrastructure invariants.
    Returns a list of error strings (empty if valid).
    """
    errors: List[str] = []
    if cfg.ENVIRONMENT not in ("development", "testing", "production"):
        errors.append(f"ENVIRONMENT must be 'development', 'testing', or 'production' (got '{cfg.ENVIRONMENT}').")

    if not cfg.is_production:
        return errors

    if not cfg.SECRET_KEY or cfg.SECRET_KEY == _DEFAULT_DEV_SECRET or len(cfg.SECRET_KEY) < 32:
        errors.append("Production requires a strong SECRET_KEY (>= 32 characters, not the development default).")

    if not cfg.DATABASE_URL or "eduplus_test_db" in cfg.DATABASE_URL:
        errors.append("Production requires a valid non-test DATABASE_URL.")

    if not cfg.ALLOWED_ORIGINS or any(o in ("*", "null") for o in cfg.ALLOWED_ORIGINS):
        errors.append("Production ALLOWED_ORIGINS must list explicit HTTPS origins (no '*' or 'null').")

    if cfg.COOKIE_AUTH_ENABLED and not cfg.COOKIE_SECURE:
        errors.append("Production COOKIE_AUTH_ENABLED=true requires COOKIE_SECURE=true (HTTPS).")

    if cfg.COOKIE_SAMESITE not in ("strict", "lax", "none"):
        errors.append(f"Invalid COOKIE_SAMESITE value: '{cfg.COOKIE_SAMESITE}'.")

    if cfg.ENABLE_DEV_FALLBACKS:
        errors.append("ENABLE_DEV_FALLBACKS must be false in production.")

    if cfg.LLM_PROVIDER.lower() == "gemini" and not cfg.GEMINI_API_KEY:
        errors.append("LLM_PROVIDER=gemini requires GEMINI_API_KEY to be set in production.")

    return errors


settings = Settings()
