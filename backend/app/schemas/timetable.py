"""
backend/app/schemas/timetable.py
EduPlus AI Timetable Maker — Timetable Generation Schemas (Pydantic v2)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Generation request / response
# ---------------------------------------------------------------------------

class GenerationRequest(BaseModel):
    department_id: UUID
    academic_year_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Restrict generation to specific academic years; None = all years for department.",
    )
    label: str = Field(..., description="Human-readable label for the new timetable version.")
    academic_year_code: str = Field(default="2026-27", description="Academic year string (e.g. '2026-27').")
    semester: int = Field(default=1, ge=1, le=2)
    time_limit_seconds: int = Field(default=60, ge=5, le=300)
    check_soft_constraints: bool = Field(default=True)
    confirmed_constraints: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Optional list of user-confirmed constraints from AI NLP interpretation.",
    )


class SessionOut(BaseModel):
    assignment_id: str
    teacher_id: str
    subject_id: str
    room_id: str
    day_name: str
    slot_index: int
    session_type: str
    target_group_type: str
    target_group_id: str
    duration_slots: int
    is_frozen: bool
    subject_name: Optional[str] = None
    subject_code: Optional[str] = None
    teacher_name: Optional[str] = None
    room_name: Optional[str] = None
    target_group_name: Optional[str] = None


class ViolationOut(BaseModel):
    rule_id: str
    level: str
    severity: str
    description: str
    affected_session_ids: List[str]
    affected_entity_ids: List[str]
    suggestion: Optional[str] = None


class GenerationResponse(BaseModel):
    status: str                   # 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE' | 'TIMEOUT' | 'ERROR'
    version_id: Optional[str] = None
    version_status: Optional[str] = None  # 'draft' | 'candidate'
    solver_time_ms: int
    objective_value: Optional[float] = None
    num_conflicts: Optional[int] = None
    total_sessions: int = 0
    hard_violations: int = 0
    soft_violations: int = 0
    diagnostic_notes: str = ""
    sessions: List[SessionOut] = []
    violations: List[ViolationOut] = []


# ---------------------------------------------------------------------------
# Version list / detail
# ---------------------------------------------------------------------------

class TimetableVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    department_id: UUID
    version_number: int
    status: str
    label: str
    academic_year_code: str
    semester: int
    is_repair: bool
    published_at: Optional[datetime]
    created_at: datetime
    total_sessions: Optional[int] = None
    hard_violations: Optional[int] = None


class TimetableVersionDetail(TimetableVersionOut):
    sessions: List[SessionOut] = []
    violations: List[ViolationOut] = []


# ---------------------------------------------------------------------------
# Version comparison
# ---------------------------------------------------------------------------

class SessionDiffOut(BaseModel):
    change_type: str
    assignment_id: str
    session_type: str
    teacher_id: str
    day_a: Optional[str] = None
    slot_a: Optional[str] = None
    room_a: Optional[str] = None
    day_b: Optional[str] = None
    slot_b: Optional[str] = None
    room_b: Optional[str] = None


class ComparisonResponse(BaseModel):
    version_a_id: str
    version_b_id: str
    total_sessions_a: int
    total_sessions_b: int
    added: int
    removed: int
    moved: int
    unchanged: int
    diffs: List[SessionDiffOut] = []


# ---------------------------------------------------------------------------
# Repair request
# ---------------------------------------------------------------------------

class RepairRequest(BaseModel):
    source_version_id: UUID = Field(..., description="Version to repair.")
    label: str = Field(..., description="Label for the repaired version.")
    affected_assignment_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Specific assignment IDs to re-schedule; None = full regeneration.",
    )
    time_limit_seconds: int = Field(default=60, ge=5, le=300)


# ---------------------------------------------------------------------------
# Validation-only request
# ---------------------------------------------------------------------------

class ValidateVersionRequest(BaseModel):
    version_id: UUID
    check_soft: bool = True

