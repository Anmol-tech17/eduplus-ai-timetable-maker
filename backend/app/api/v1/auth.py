"""
backend/app/api/v1/auth.py
EduPlus AI Timetable Maker — Authentication Endpoints

Endpoints:
- POST /api/v1/auth/login
- POST /api/v1/auth/logout
- GET  /api/v1/auth/me
- POST /api/v1/auth/change-password
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.api.deps import can_user_approve_timetable, get_current_user, get_db
from backend.app.core.security import (
    create_access_token,
    get_password_hash,
    login_rate_limiter,
    token_revocation_store,
    verify_password,
)
from backend.app.models.security import UserAccount
from backend.app.schemas.security import (
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
    UserProfileOut,
)
from backend.app.services.audit import extract_client_ip, record_audit_event

router = APIRouter(prefix="/auth", tags=["Authentication"])


def resolve_user_permissions(user: UserAccount) -> List[str]:
    """Return descriptive capability flags derived from role & account config."""
    perms: List[str] = ["view_published_timetable"]
    if user.role == "admin":
        perms.extend([
            "manage_users",
            "manage_institution",
            "view_audit_logs",
            "generate_timetable",
            "validate_timetable",
            "compare_versions",
            "repair_timetable",
            "use_ai_assistant",
            "submit_for_approval",
            "approve_timetable",
            "publish_timetable",
            "review_teacher_requests",
        ])
    elif user.role == "coordinator":
        perms.extend([
            "generate_timetable",
            "validate_timetable",
            "compare_versions",
            "repair_timetable",
            "use_ai_assistant",
            "submit_for_approval",
            "review_teacher_requests",
        ])
        if user.can_approve_timetable:
            perms.extend(["approve_timetable", "publish_timetable"])
    elif user.role == "teacher":
        perms.extend([
            "view_own_timetable",
            "submit_teacher_request",
            "view_own_requests",
        ])
    elif user.role == "student":
        perms.extend([
            "view_division_timetable",
        ])
    return perms


def build_user_profile(user: UserAccount) -> UserProfileOut:
    return UserProfileOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name or user.email.split("@")[0],
        role=user.role,
        department_id=user.department_id,
        linked_entity_id=user.linked_entity_id,
        can_approve_timetable=can_user_approve_timetable(user),
        is_active=user.is_active,
        permissions=resolve_user_permissions(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Authenticate user with email & password and issue a signed JWT access token."""
    normalized_email = payload.email.strip().lower()
    client_ip = extract_client_ip(request) or "unknown"
    rate_key = f"{client_ip}:{normalized_email}"

    if not login_rate_limiter.check_allowed(rate_key):
        record_audit_event(
            db=db,
            action="AUTH_LOGIN_RATE_LIMITED",
            entity_type="USER_ACCOUNT",
            payload={"email": normalized_email},
            request=request,
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
        )

    user = db.query(UserAccount).filter(UserAccount.email == normalized_email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        login_rate_limiter.record_failure(rate_key)
        record_audit_event(
            db=db,
            action="AUTH_LOGIN_FAILURE",
            entity_type="USER_ACCOUNT",
            user_id=user.id if user else None,
            entity_id=user.id if user else None,
            payload={"email": normalized_email, "reason": "invalid_credentials"},
            request=request,
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        record_audit_event(
            db=db,
            action="AUTH_LOGIN_FAILURE",
            entity_type="USER_ACCOUNT",
            user_id=user.id,
            entity_id=user.id,
            payload={"email": normalized_email, "reason": "account_inactive"},
            request=request,
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact an administrator.",
        )

    login_rate_limiter.record_success(rate_key)
    token, _jti, expires_in = create_access_token(
        subject=str(user.id),
        role=user.role,
        email=user.email,
        department_id=str(user.department_id) if user.department_id else None,
    )

    record_audit_event(
        db=db,
        action="AUTH_LOGIN_SUCCESS",
        entity_type="USER_ACCOUNT",
        user_id=user.id,
        entity_id=user.id,
        payload={"role": user.role},
        request=request,
        commit=True,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        user=build_user_profile(user),
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    request: Request,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke the current access token immediately and record audit event."""
    jti = getattr(current_user, "_token_jti", None)
    exp = getattr(current_user, "_token_exp", None)
    if jti:
        token_revocation_store.revoke(jti, exp)

    record_audit_event(
        db=db,
        action="AUTH_LOGOUT",
        entity_type="USER_ACCOUNT",
        user_id=current_user.id,
        entity_id=current_user.id,
        payload={"role": current_user.role},
        request=request,
        commit=True,
    )
    return {"message": "Signed out successfully."}


@router.get("/me", response_model=UserProfileOut)
def get_me(current_user: UserAccount = Depends(get_current_user)):
    """Return the authenticated user's profile and active permissions."""
    return build_user_profile(current_user)


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Allow an authenticated user to change their own password."""
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    current_user.password_hash = get_password_hash(payload.new_password)
    record_audit_event(
        db=db,
        action="AUTH_PASSWORD_CHANGED",
        entity_type="USER_ACCOUNT",
        user_id=current_user.id,
        entity_id=current_user.id,
        payload={"email": current_user.email},
        request=request,
    )
    db.commit()
    return {"message": "Password updated successfully."}
