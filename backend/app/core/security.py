"""
backend/app/core/security.py
EduPlus AI Timetable Maker — Password Hashing, JWT Access/Refresh Tokens,
Persistent Multi-Worker Token Revocation, Persistent Login Rate Limiting & CSRF Utilities
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from passlib.hash import pbkdf2_sha256
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.security import LoginAttempt, RevokedToken

ACCESS_COOKIE_NAME = "eduplus_access_token"
REFRESH_COOKIE_NAME = "eduplus_refresh_token"
CSRF_COOKIE_NAME = "eduplus_csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"


# ---------------------------------------------------------------------------
# Password hashing (PBKDF2-SHA256)
# ---------------------------------------------------------------------------

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the stored hash using PBKDF2-SHA256."""
    if not plain_password or not hashed_password:
        return False
    try:
        return pbkdf2_sha256.verify(plain_password, hashed_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Generates a salted password hash using PBKDF2-SHA256."""
    return pbkdf2_sha256.hash(password)


def generate_csrf_token() -> str:
    """Generate a cryptographically secure double-submit CSRF token."""
    return secrets.token_urlsafe(32)


def verify_csrf_token(cookie_token: Optional[str], header_token: Optional[str]) -> bool:
    """Constant-time comparison for double-submit CSRF validation."""
    if not cookie_token or not header_token:
        return False
    return secrets.compare_digest(cookie_token, header_token)


# ---------------------------------------------------------------------------
# JWT Access & Refresh Token Creation & Decoding
# ---------------------------------------------------------------------------

def create_access_token(
    subject: str,
    role: str,
    email: str,
    department_id: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, str, int]:
    """Create a signed HS256 JWT access token. Returns (token, jti, expires_in_seconds)."""
    now = datetime.now(timezone.utc)
    delta = expires_delta if expires_delta is not None else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = now + delta
    jti = str(uuid.uuid4())

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "email": email,
        "dept": str(department_id) if department_id else None,
        "jti": jti,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    expires_in = max(0, int(delta.total_seconds()))
    return token, jti, expires_in


def create_refresh_token(
    subject: str,
    role: str,
    email: str,
    department_id: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, str, int]:
    """Create a signed HS256 JWT refresh token. Returns (token, jti, expires_in_seconds)."""
    now = datetime.now(timezone.utc)
    delta = expires_delta if expires_delta is not None else timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    expire = now + delta
    jti = str(uuid.uuid4())

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "email": email,
        "dept": str(department_id) if department_id else None,
        "jti": jti,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    expires_in = max(0, int(delta.total_seconds()))
    return token, jti, expires_in


def decode_token(token: str, expected_type: str = "access") -> Dict[str, Any]:
    """
    Decode and validate a JWT token of expected_type ('access' or 'refresh').
    Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError on failure.
    """
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["sub", "role", "exp", "jti", "type"]},
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"Invalid token type: expected '{expected_type}'.")
    return payload


def decode_access_token(token: str) -> Dict[str, Any]:
    """Backward-compatible helper decoding an access token."""
    return decode_token(token, expected_type="access")


# ---------------------------------------------------------------------------
# Persistent Multi-Worker Token Revocation (PostgreSQL-backed)
# ---------------------------------------------------------------------------

def revoke_token_db(
    db: Session,
    jti: str,
    user_id: Optional[uuid.UUID] = None,
    token_type: str = "access",
    exp_timestamp: Optional[float] = None,
    commit: bool = False,
) -> None:
    """Persist a revoked token JTI in PostgreSQL so all workers honor revocation."""
    if not jti:
        return
    existing = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
    if existing:
        return

    if exp_timestamp is not None and exp_timestamp > 0:
        expires_at = datetime.utcfromtimestamp(exp_timestamp)
    else:
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    db.add(RevokedToken(
        jti=jti,
        user_id=user_id,
        token_type=token_type,
        expires_at=expires_at,
        revoked_at=datetime.utcnow(),
    ))
    if commit:
        db.commit()
    else:
        db.flush()


def is_token_revoked_db(db: Session, jti: str) -> bool:
    """Check whether a token JTI has been revoked in shared persistent storage."""
    if not jti:
        return True
    return db.query(RevokedToken.jti).filter(RevokedToken.jti == jti).first() is not None


def prune_expired_revoked_tokens_db(db: Session) -> int:
    """Delete expired revocation rows to keep revoked_tokens compact."""
    deleted = db.query(RevokedToken).filter(RevokedToken.expires_at < datetime.utcnow()).delete()
    db.flush()
    return deleted


# ---------------------------------------------------------------------------
# Persistent Multi-Worker Login Rate Limiter (PostgreSQL-backed)
# ---------------------------------------------------------------------------

def check_login_rate_limit_db(db: Session, rate_key: str) -> bool:
    """Return True if login attempt is permitted within the sliding window."""
    cutoff = datetime.utcnow() - timedelta(seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS)
    recent_failures = (
        db.query(LoginAttempt)
        .filter(LoginAttempt.rate_key == rate_key, LoginAttempt.attempted_at >= cutoff)
        .count()
    )
    return recent_failures < settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS


def record_login_failure_db(db: Session, rate_key: str, commit: bool = False) -> None:
    """Record a failed login attempt in shared PostgreSQL storage."""
    db.add(LoginAttempt(rate_key=rate_key, attempted_at=datetime.utcnow()))
    if commit:
        db.commit()
    else:
        db.flush()


def clear_login_failures_db(db: Session, rate_key: str, commit: bool = False) -> None:
    """Clear failed login attempts for rate_key after successful authentication."""
    db.query(LoginAttempt).filter(LoginAttempt.rate_key == rate_key).delete()
    if commit:
        db.commit()
    else:
        db.flush()


# Legacy lightweight shim kept for test fixture reset compatibility
class _CompatNoOpStore:
    def clear(self) -> None:
        pass


token_revocation_store = _CompatNoOpStore()
login_rate_limiter = _CompatNoOpStore()
