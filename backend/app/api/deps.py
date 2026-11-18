"""
backend/app/api/deps.py
EduPlus AI Timetable Maker — Shared API, Authentication & RBAC Dependencies
"""

from __future__ import annotations

import uuid
from typing import Callable, Iterable, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.core.security import decode_access_token, token_revocation_store
from backend.app.db.session import get_db
from backend.app.models.security import UserAccount

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> UserAccount:
    """
    Validate Bearer JWT access token, check server-side revocation,
    verify active UserAccount, and return the authenticated user.
    """
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jti = payload.get("jti")
    if not jti or token_revocation_store.is_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = uuid.UUID(str(payload.get("sub")))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(UserAccount).filter(UserAccount.id == user_uuid).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    # Attach non-persistent token metadata for logout revocation
    user._token_jti = jti  # type: ignore[attr-defined]
    user._token_exp = float(payload.get("exp", 0))  # type: ignore[attr-defined]
    return user


def require_roles(*allowed_roles: str) -> Callable[[UserAccount], UserAccount]:
    """Dependency factory enforcing that the authenticated user has one of allowed_roles."""
    allowed_set = set(allowed_roles)

    def _checker(current_user: UserAccount = Depends(get_current_user)) -> UserAccount:
        if current_user.role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return current_user

    return _checker


def can_user_approve_timetable(user: UserAccount) -> bool:
    """Admins can always approve/publish; Coordinators can if explicitly granted permission."""
    if user.role == "admin":
        return True
    if user.role == "coordinator" and bool(user.can_approve_timetable):
        return True
    return False


def require_approver(current_user: UserAccount = Depends(get_current_user)) -> UserAccount:
    """Enforce that the caller is authorized to approve/reject/publish timetables."""
    if not can_user_approve_timetable(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to approve or publish timetables.",
        )
    return current_user


def assert_department_access(user: UserAccount, department_id: Optional[uuid.UUID]) -> None:
    """
    Enforce institutional department scope isolation.
    Admins can manage all institutional departments; non-admin roles are strictly
    isolated to their assigned department_id.
    """
    if user.role == "admin":
        return
    if department_id is None:
        return
    if user.department_id is None or str(user.department_id) != str(department_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: resource belongs to a different institutional department.",
        )


__all__ = [
    "get_db",
    "get_current_user",
    "require_roles",
    "require_approver",
    "can_user_approve_timetable",
    "assert_department_access",
]
