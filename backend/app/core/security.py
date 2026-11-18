"""
backend/app/core/security.py
EduPlus AI Timetable Maker — Password Hashing, JWT Access Tokens,
Token Revocation, and Authentication Rate Limiting
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Deque, Dict, Optional

import jwt
from passlib.hash import pbkdf2_sha256

from backend.app.core.config import settings


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


# ---------------------------------------------------------------------------
# JWT Access Token creation & decoding
# ---------------------------------------------------------------------------

def create_access_token(
    subject: str,
    role: str,
    email: str,
    department_id: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> tuple[str, str, int]:
    """
    Create a signed JWT access token.

    Returns (encoded_jwt, jti, expires_in_seconds).
    """
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


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT access token.
    Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError on failure.
    """
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["sub", "role", "exp", "jti", "type"]},
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Invalid token type.")
    return payload


# ---------------------------------------------------------------------------
# Server-side Token Revocation Store (Logout support)
# ---------------------------------------------------------------------------

class TokenRevocationStore:
    """Thread-safe in-memory JTI revocation list with automatic expiry pruning."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._revoked: Dict[str, float] = {}  # jti -> exp_timestamp

    def revoke(self, jti: str, exp_timestamp: Optional[float] = None) -> None:
        exp = exp_timestamp if exp_timestamp is not None else (time.time() + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
        with self._lock:
            self._prune_locked()
            self._revoked[jti] = exp

    def is_revoked(self, jti: str) -> bool:
        with self._lock:
            self._prune_locked()
            return jti in self._revoked

    def clear(self) -> None:
        with self._lock:
            self._revoked.clear()

    def _prune_locked(self) -> None:
        now = time.time()
        expired = [k for k, v in self._revoked.items() if v < now]
        for k in expired:
            del self._revoked[k]


token_revocation_store = TokenRevocationStore()


# ---------------------------------------------------------------------------
# Sliding-Window Rate Limiter for Authentication Endpoints
# ---------------------------------------------------------------------------

class LoginRateLimiter:
    """Tracks failed login attempts per key (IP / email) within a sliding window."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._attempts: Dict[str, Deque[float]] = defaultdict(deque)

    def check_allowed(self, key: str) -> bool:
        now = time.time()
        window = settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
        max_attempts = settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS
        with self._lock:
            q = self._attempts[key]
            while q and (now - q[0]) > window:
                q.popleft()
            return len(q) < max_attempts

    def record_failure(self, key: str) -> None:
        now = time.time()
        window = settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
        with self._lock:
            q = self._attempts[key]
            while q and (now - q[0]) > window:
                q.popleft()
            q.append(now)

    def record_success(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._attempts.clear()


login_rate_limiter = LoginRateLimiter()
