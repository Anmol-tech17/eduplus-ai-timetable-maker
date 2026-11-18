"""
backend/app/api/v1/users.py
EduPlus AI Timetable Maker — Admin User Management & Audit Log Endpoints

Endpoints:
- GET  /api/v1/users           (Admin only)
- POST /api/v1/users           (Admin only)
- PUT  /api/v1/users/{user_id} (Admin only)
- GET  /api/v1/audit-logs      (Admin only, immutable read-only)
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, require_roles
from backend.app.core.security import get_password_hash
from backend.app.models.academic import Department
from backend.app.models.security import AuditLog, UserAccount
from backend.app.schemas.common import PaginatedResponse, PaginationMeta
from backend.app.schemas.security import (
    AuditLogOut,
    UserCreateRequest,
    UserOut,
    UserUpdateRequest,
)
from backend.app.services.audit import record_audit_event

router = APIRouter(tags=["Users & Audit"])


# ---------------------------------------------------------------------------
# User Management (Admin Only)
# ---------------------------------------------------------------------------

@router.get("/users", response_model=PaginatedResponse[UserOut])
def list_users(
    role: Optional[str] = Query(default=None),
    department_id: Optional[UUID] = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: UserAccount = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """List institutional user accounts (Admin only)."""
    q = db.query(UserAccount)
    if role:
        q = q.filter(UserAccount.role == role)
    if department_id:
        q = q.filter(UserAccount.department_id == department_id)

    total = q.count()
    items = q.order_by(UserAccount.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return PaginatedResponse(
        items=items,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total_records=total,
            total_pages=total_pages,
        ),
    )


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    request: Request,
    current_user: UserAccount = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Create a new institutional user account with hashed password (Admin only)."""
    normalized_email = payload.email.strip().lower()
    if db.query(UserAccount).filter(UserAccount.email == normalized_email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{normalized_email}' already exists.",
        )

    if payload.department_id:
        dept = db.query(Department).filter(Department.id == payload.department_id).first()
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Specified department not found.",
            )

    user = UserAccount(
        email=normalized_email,
        full_name=payload.full_name,
        password_hash=get_password_hash(payload.password),
        role=payload.role,
        department_id=payload.department_id or current_user.department_id,
        linked_entity_id=payload.linked_entity_id,
        can_approve_timetable=True if payload.role == "admin" else payload.can_approve_timetable,
        is_active=payload.is_active,
    )
    db.add(user)
    try:
        db.flush()
        record_audit_event(
            db=db,
            action="USER_CREATED",
            entity_type="USER_ACCOUNT",
            user_id=current_user.id,
            entity_id=user.id,
            payload={
                "email": user.email,
                "role": user.role,
                "department_id": str(user.department_id) if user.department_id else None,
                "can_approve_timetable": user.can_approve_timetable,
            },
            request=request,
        )
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict creating user account.",
        )
    return user


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: UUID,
    payload: UserUpdateRequest,
    request: Request,
    current_user: UserAccount = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Update user role, approval permissions, active status, or metadata (Admin only)."""
    target = db.query(UserAccount).filter(UserAccount.id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    # Guard against self-lockout
    if target.id == current_user.id:
        if payload.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Administrators cannot deactivate their own account.",
            )
        if payload.role is not None and payload.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Administrators cannot demote their own role.",
            )

    old_role = target.role
    changes = {}

    if payload.full_name is not None:
        target.full_name = payload.full_name
        changes["full_name"] = payload.full_name
    if payload.role is not None and payload.role != target.role:
        target.role = payload.role
        changes["role"] = {"from": old_role, "to": payload.role}
        if payload.role == "admin":
            target.can_approve_timetable = True
        elif payload.can_approve_timetable is None and payload.role != "coordinator":
            target.can_approve_timetable = False
    if payload.department_id is not None:
        dept = db.query(Department).filter(Department.id == payload.department_id).first()
        if not dept:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found.")
        target.department_id = payload.department_id
        changes["department_id"] = str(payload.department_id)
    if payload.linked_entity_id is not None:
        target.linked_entity_id = payload.linked_entity_id
        changes["linked_entity_id"] = str(payload.linked_entity_id)
    if payload.can_approve_timetable is not None:
        target.can_approve_timetable = payload.can_approve_timetable
        changes["can_approve_timetable"] = payload.can_approve_timetable
    if payload.is_active is not None:
        target.is_active = payload.is_active
        changes["is_active"] = payload.is_active
    if payload.password is not None:
        target.password_hash = get_password_hash(payload.password)
        changes["password_reset"] = True

    action = "USER_ROLE_CHANGED" if "role" in changes else "USER_UPDATED"
    record_audit_event(
        db=db,
        action=action,
        entity_type="USER_ACCOUNT",
        user_id=current_user.id,
        entity_id=target.id,
        payload={"target_email": target.email, "changes": changes},
        request=request,
    )
    db.commit()
    db.refresh(target)
    return target


# ---------------------------------------------------------------------------
# Audit Logs (Admin Only, Read-Only)
# ---------------------------------------------------------------------------

@router.get("/audit-logs", response_model=PaginatedResponse[AuditLogOut])
def list_audit_logs(
    action: Optional[str] = Query(default=None),
    entity_type: Optional[str] = Query(default=None),
    user_id: Optional[UUID] = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: UserAccount = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Retrieve immutable security and operational audit logs (Admin only)."""
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)

    total = q.count()
    logs = q.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    items: List[AuditLogOut] = []
    for log in logs:
        items.append(AuditLogOut(
            id=log.id,
            user_id=log.user_id,
            actor_email=log.user.email if log.user else None,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            payload=log.payload,
            ip_address=log.ip_address,
            created_at=log.created_at,
        ))

    return PaginatedResponse(
        items=items,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total_records=total,
            total_pages=total_pages,
        ),
    )
