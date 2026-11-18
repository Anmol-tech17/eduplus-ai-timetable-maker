"""
backend/app/api/v1/auth.py
EduPlus AI Timetable Maker — Multi-Worker Authentication, Refresh Rotation & Cookie/CSRF Endpoints

Endpoints:
- POST /api/v1/auth/login
- POST /api/v1/auth/refresh
- POST /api/v1/auth/logout
- GET  /api/v1/auth/me
- POST /api/v1/auth/change-password
"""

from __future__ import annotations

import uuid
from typing import List, Optional

import jwt
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from backend.app.api.deps import can_user_approve_timetable, get_current_user, get_db
from backend.app.core.config import settings
from backend.app.core.security import (
    ACCESS_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    REFRESH_COOKIE_NAME,
    check_login_rate_limit_db,
    clear_login_failures_db,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_csrf_token,
    get_password_hash,
    is_token_revoked_db,
    record_login_failure_db,
    revoke_token_db,
    verify_csrf_token,
    verify_password,
)
from backend.app.models.security import UserAccount
from backend.app.schemas.security import (
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
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


def _set_auth_cookies(
    response: Response,
    access_token: str,
    access_max_age: int,
    refresh_token: str,
    refresh_max_age: int,
) -> None:
    """Attach HttpOnly access/refresh cookies and readable double-submit CSRF cookie."""
    cookie_kwargs = {
        "secure": settings.COOKIE_SECURE,
        "samesite": settings.COOKIE_SAMESITE,
    }
    if settings.COOKIE_DOMAIN:
        cookie_kwargs["domain"] = settings.COOKIE_DOMAIN

    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=access_token,
        httponly=True,
        max_age=access_max_age,
        path="/",
        **cookie_kwargs,
    )
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        max_age=refresh_max_age,
        path=f"{settings.API_V1_PREFIX}/auth",
        **cookie_kwargs,
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=generate_csrf_token(),
        httponly=False,  # Must be readable by browser JS to echo in X-CSRF-Token header
        max_age=refresh_max_age,
        path="/",
        **cookie_kwargs,
    )


def _clear_auth_cookies(response: Response) -> None:
    cookie_kwargs = {}
    if settings.COOKIE_DOMAIN:
        cookie_kwargs["domain"] = settings.COOKIE_DOMAIN
    response.delete_cookie(key=ACCESS_COOKIE_NAME, path="/", **cookie_kwargs)
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path=f"{settings.API_V1_PREFIX}/auth", **cookie_kwargs)
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/", **cookie_kwargs)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Authenticate user with email & password.
    Enforces persistent multi-worker rate limiting, issues access + refresh tokens,
    and attaches HttpOnly/SameSite/Secure + CSRF cookies.
    """
    normalized_email = payload.email.strip().lower()
    client_ip = extract_client_ip(request) or "unknown"
    rate_key = f"{client_ip}:{normalized_email}"

    if not check_login_rate_limit_db(db, rate_key):
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
        record_login_failure_db(db, rate_key, commit=False)
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

    clear_login_failures_db(db, rate_key, commit=False)

    dept_str = str(user.department_id) if user.department_id else None
    access_token, _a_jti, access_exp = create_access_token(
        subject=str(user.id),
        role=user.role,
        email=user.email,
        department_id=dept_str,
    )
    refresh_token, _r_jti, refresh_exp = create_refresh_token(
        subject=str(user.id),
        role=user.role,
        email=user.email,
        department_id=dept_str,
    )

    _set_auth_cookies(response, access_token, access_exp, refresh_token, refresh_exp)

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
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=access_exp,
        user=build_user_profile(user),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_session(
    request: Request,
    response: Response,
    payload: Optional[RefreshTokenRequest] = Body(default=None),
    db: Session = Depends(get_db),
):
    """
    Rotate a valid refresh token (from HttpOnly cookie or JSON body) into a fresh
    access + refresh token pair. Immediately revokes the consumed refresh token in DB.
    """
    raw_refresh: Optional[str] = None
    via_cookie = False

    if payload and payload.refresh_token:
        raw_refresh = payload.refresh_token
    else:
        cookie_rt = request.cookies.get(REFRESH_COOKIE_NAME)
        if cookie_rt:
            raw_refresh = cookie_rt
            via_cookie = True

    if not raw_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required.",
        )

    if via_cookie:
        if not verify_csrf_token(request.cookies.get(CSRF_COOKIE_NAME), request.headers.get(CSRF_HEADER_NAME)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF validation failed.",
            )

    try:
        claims = decode_token(raw_refresh, expected_type="refresh")
    except jwt.ExpiredSignatureError:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired. Please sign in again.",
        )
    except jwt.InvalidTokenError:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
        )

    old_jti = claims.get("jti")
    if not old_jti or is_token_revoked_db(db, old_jti):
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked.",
        )

    try:
        user_uuid = uuid.UUID(str(claims.get("sub")))
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.")

    user = db.query(UserAccount).filter(UserAccount.id == user_uuid).first()
    if user is None or not user.is_active:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive.")

    # Rotate: revoke consumed refresh token persistently
    revoke_token_db(
        db=db,
        jti=old_jti,
        user_id=user.id,
        token_type="refresh",
        exp_timestamp=float(claims.get("exp", 0)),
        commit=False,
    )

    dept_str = str(user.department_id) if user.department_id else None
    new_access, _a_jti, access_exp = create_access_token(
        subject=str(user.id),
        role=user.role,
        email=user.email,
        department_id=dept_str,
    )
    new_refresh, _r_jti, refresh_exp = create_refresh_token(
        subject=str(user.id),
        role=user.role,
        email=user.email,
        department_id=dept_str,
    )
    _set_auth_cookies(response, new_access, access_exp, new_refresh, refresh_exp)

    record_audit_event(
        db=db,
        action="AUTH_TOKEN_REFRESH",
        entity_type="USER_ACCOUNT",
        user_id=user.id,
        entity_id=user.id,
        payload={"role": user.role},
        request=request,
        commit=True,
    )

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=access_exp,
        user=build_user_profile(user),
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    request: Request,
    response: Response,
    payload: Optional[LogoutRequest] = Body(default=None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Persistently revoke active access token (and refresh token if present) across
    all workers, clear auth cookies, and record audit event.
    """
    jti = getattr(current_user, "_token_jti", None)
    exp = getattr(current_user, "_token_exp", None)
    if jti:
        revoke_token_db(
            db=db,
            jti=jti,
            user_id=current_user.id,
            token_type="access",
            exp_timestamp=exp,
            commit=False,
        )

    # Also revoke refresh token if supplied in cookie or request body
    raw_refresh = (payload.refresh_token if payload and payload.refresh_token else None) or request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_refresh:
        try:
            r_claims = decode_token(raw_refresh, expected_type="refresh")
            r_jti = r_claims.get("jti")
            if r_jti:
                revoke_token_db(
                    db=db,
                    jti=r_jti,
                    user_id=current_user.id,
                    token_type="refresh",
                    exp_timestamp=float(r_claims.get("exp", 0)),
                    commit=False,
                )
        except jwt.InvalidTokenError:
            pass

    _clear_auth_cookies(response)

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
