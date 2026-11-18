"""
backend/app/schemas/security.py
EduPlus AI Timetable Maker — Authentication, User Management, Audit & Teacher Request Schemas
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

RoleType = Literal["admin", "coordinator", "teacher", "student"]
TeacherRequestType = Literal["availability", "reschedule", "substitution", "cancellation"]
TeacherRequestStatus = Literal["pending", "approved", "rejected"]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class UserProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: Optional[str] = None
    role: str
    department_id: Optional[UUID] = None
    linked_entity_id: Optional[UUID] = None
    can_approve_timetable: bool = False
    is_active: bool = True
    permissions: List[str] = Field(default_factory=list)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfileOut


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


# ---------------------------------------------------------------------------
# User Management (Admin)
# ---------------------------------------------------------------------------

class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=128)
    role: RoleType
    department_id: Optional[UUID] = None
    linked_entity_id: Optional[UUID] = None
    can_approve_timetable: bool = False
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=128)
    role: Optional[RoleType] = None
    department_id: Optional[UUID] = None
    linked_entity_id: Optional[UUID] = None
    can_approve_timetable: Optional[bool] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: Optional[str] = None
    role: str
    department_id: Optional[UUID] = None
    linked_entity_id: Optional[UUID] = None
    can_approve_timetable: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Audit Logs (Admin Read-Only)
# ---------------------------------------------------------------------------

class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: Optional[UUID] = None
    actor_email: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[UUID] = None
    payload: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Teacher Availability & Change Requests
# ---------------------------------------------------------------------------

class TeacherRequestCreate(BaseModel):
    request_type: TeacherRequestType
    day_name: Optional[str] = Field(default=None, max_length=16)
    time_slot_code: Optional[str] = Field(default=None, max_length=16)
    reason: str = Field(..., min_length=5, max_length=1000)


class TeacherRequestReview(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: Optional[str] = Field(default=None, max_length=500)


class TeacherRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    teacher_id: UUID
    teacher_name: Optional[str] = None
    department_id: UUID
    submitted_by: Optional[UUID] = None
    request_type: str
    day_name: Optional[str] = None
    time_slot_code: Optional[str] = None
    reason: str
    status: str
    reviewed_by: Optional[UUID] = None
    review_comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime
