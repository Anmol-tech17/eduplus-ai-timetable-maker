"""
backend/app/api/v1/timetable.py
EduPlus AI Timetable Maker — Timetable Generation, Approval & Lifecycle Endpoints (RBAC Protected)

Endpoints
---------
POST   /timetable/generate                   — Generate a timetable (Admin, Coordinator)
POST   /timetable/validate                   — Validate an existing version (Admin, Coordinator)
GET    /timetable/versions                   — List versions (role & dept isolated; Teacher/Student published only)
GET    /timetable/versions/{id}              — Get a version with sessions (role, dept & entity isolated)
POST   /timetable/versions/{id}/submit       — Submit candidate for approval (Admin, Coordinator)
POST   /timetable/versions/{id}/approve      — Approve submitted candidate (Approver: Admin or authorized Coordinator)
POST   /timetable/versions/{id}/reject       — Reject submitted candidate with optional reason (Approver)
POST   /timetable/versions/{id}/publish      — Publish an approved version (Approver; blocks hard violations, archives prior)
GET    /timetable/compare                    — Compare two versions (Admin, Coordinator)
POST   /timetable/repair                     — Localised repair (Admin, Coordinator)
GET    /timetable/runs/{id}                  — Get generation run status/details (Admin, Coordinator)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional, Set

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from backend.app.api.deps import (
    assert_department_access,
    get_current_user,
    get_db,
    require_approver,
    require_roles,
)
from backend.app.core.logging import logger
from backend.app.engine.comparator import compare_versions
from backend.app.engine.input_builder import SchedulingInputBuilder
from backend.app.engine.persistence import persist_generation_result
from backend.app.engine.solver import run_solver
from backend.app.engine.types import (
    ScheduledSessionInfo,
    SlotKey,
    ViolationLevel,
)
from backend.app.engine.validator import validate_timetable
from backend.app.models.academic import Batch
from backend.app.models.faculty import Teacher
from backend.app.models.security import UserAccount
from backend.app.models.timetable import (
    GenerationRun,
    ScheduledSession,
    TimetableVersion,
    Violation,
)
from backend.app.schemas.timetable import (
    ApprovalActionRequest,
    ComparisonResponse,
    GenerationRequest,
    GenerationResponse,
    RepairRequest,
    SessionDiffOut,
    SessionOut,
    TimetableVersionDetail,
    TimetableVersionOut,
    ValidateVersionRequest,
    ViolationOut,
)
from backend.app.services.audit import record_audit_event
from backend.app.services.job_runner import generation_job_manager

router = APIRouter(prefix="/timetable", tags=["Timetable"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _version_to_out(version: TimetableVersion, db: Session) -> TimetableVersionOut:
    session_count = (
        db.query(ScheduledSession)
        .filter(ScheduledSession.timetable_version_id == version.id)
        .count()
    )
    hard_viol = (
        db.query(Violation)
        .filter(Violation.timetable_version_id == version.id, Violation.rule_level == "A")
        .count()
    )
    return TimetableVersionOut(
        id=version.id,
        department_id=version.department_id,
        version_number=version.version_number,
        status=version.status,
        label=version.label,
        academic_year_code=version.academic_year_code,
        semester=version.semester,
        is_repair=version.is_repair,
        submitted_by=version.submitted_by,
        submitted_at=version.submitted_at,
        approved_by=version.approved_by,
        approved_at=version.approved_at,
        approval_comment=version.approval_comment,
        published_by=version.published_by,
        published_at=version.published_at,
        created_at=version.created_at,
        total_sessions=session_count,
        hard_violations=hard_viol,
    )


def _count_hard_violations(version: TimetableVersion, db: Session) -> int:
    return (
        db.query(Violation)
        .filter(Violation.timetable_version_id == version.id, Violation.rule_level == "A")
        .count()
    )


def _resolve_teacher_id(user: UserAccount, db: Session) -> Optional[str]:
    if user.linked_entity_id:
        return str(user.linked_entity_id)
    teacher = db.query(Teacher).filter(Teacher.email == user.email).first()
    return str(teacher.id) if teacher else None


def _resolve_student_allowed_groups(user: UserAccount, db: Session) -> Set[str]:
    allowed: Set[str] = set()
    if user.linked_entity_id:
        div_id = user.linked_entity_id
        allowed.add(str(div_id))
        batches = db.query(Batch).filter(Batch.division_id == div_id).all()
        for b in batches:
            allowed.add(str(b.id))
    return allowed


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

@router.post("/generate", response_model=GenerationResponse, status_code=status.HTTP_202_ACCEPTED)
def generate_timetable(
    payload: GenerationRequest,
    request: Request,
    current_user: UserAccount = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    """
    Generate a new timetable for the given department/academic-year scope.
    Allowed: Admin, Coordinator (own department only).
    """
    assert_department_access(current_user, payload.department_id)

    dept_id = str(payload.department_id)
    ay_ids = [str(x) for x in payload.academic_year_ids] if payload.academic_year_ids else None

    # Build input
    try:
        builder = SchedulingInputBuilder(db)
        scheduling_input = builder.build(dept_id, ay_ids)
    except Exception as exc:
        logger.error(f"Input build failed: {exc}", exc_info=True)
        raise HTTPException(status_code=400, detail="Failed to build scheduling input.")

    if not scheduling_input.assignments:
        raise HTTPException(
            status_code=422,
            detail=(
                "No teaching assignments found for the specified scope. "
                "Create teaching assignments and session requirements first."
            ),
        )

    logger.info(
        f"Starting generation for dept={dept_id}, "
        f"assignments={len(scheduling_input.assignments)}, "
        f"rooms={len(scheduling_input.rooms)}, "
        f"time_limit={payload.time_limit_seconds}s"
    )

    # Apply user-confirmed AI / coordinator constraints
    if payload.confirmed_constraints:
        logger.info(f"Applying {len(payload.confirmed_constraints)} confirmed constraints to scheduling input")
        active_days = [wd.day_name for wd in scheduling_input.working_days if wd.is_active]
        for c in payload.confirmed_constraints:
            cat = c.get("category")
            target_id = c.get("target_id")
            slot_indices = c.get("slot_indices", [])
            day_names = c.get("day_names", []) or active_days

            if cat == "teacher_unavailability" and target_id:
                for teacher in scheduling_input.teachers:
                    if teacher.id == target_id:
                        for d_name in day_names:
                            for s_idx in slot_indices:
                                key = SlotKey(day_name=d_name, slot_index=s_idx)
                                if key not in teacher.unavailable_slots:
                                    teacher.unavailable_slots.append(key)

            elif cat == "teacher_preference" and target_id:
                for teacher in scheduling_input.teachers:
                    if teacher.id == target_id:
                        for d_name in day_names:
                            for s_idx in slot_indices:
                                key = SlotKey(day_name=d_name, slot_index=s_idx)
                                if key not in teacher.preferred_slots:
                                    teacher.preferred_slots.append(key)

            elif cat == "practical_block":
                for d_name in day_names:
                    if d_name not in scheduling_input.blocked_practical_days:
                        scheduling_input.blocked_practical_days.append(d_name)

            elif cat == "gap_minimization":
                scheduling_input.gap_penalty_weight = 6

    # Solve
    solver_result = run_solver(scheduling_input, time_limit_seconds=payload.time_limit_seconds)
    logger.info(f"Solver finished: {solver_result.status.value} in {solver_result.solver_time_ms}ms")

    # Validate (independent deterministic check)
    violations = []
    if solver_result.sessions:
        violations = validate_timetable(
            solver_result.sessions,
            scheduling_input,
            check_soft=payload.check_soft_constraints,
        )

    hard_count = sum(1 for v in violations if v.level == ViolationLevel.A)
    soft_count = sum(1 for v in violations if v.level != ViolationLevel.A)

    # Persist + audit log
    try:
        version = persist_generation_result(
            db=db,
            scheduling_input=scheduling_input,
            solver_result=solver_result,
            violations=violations,
            department_id=dept_id,
            label=payload.label,
            academic_year_code=payload.academic_year_code,
            semester=payload.semester,
        )
        if payload.confirmed_constraints:
            record_audit_event(
                db=db,
                action="AI_CONSTRAINTS_CONFIRMED",
                entity_type="TIMETABLE_VERSION",
                user_id=current_user.id,
                entity_id=version.id if version else None,
                payload={
                    "department_id": dept_id,
                    "constraints_count": len(payload.confirmed_constraints),
                    "categories": [c.get("category") for c in payload.confirmed_constraints],
                },
                request=request,
            )
        record_audit_event(
            db=db,
            action="TIMETABLE_GENERATE",
            entity_type="TIMETABLE_VERSION",
            user_id=current_user.id,
            entity_id=version.id if version else None,
            payload={
                "department_id": dept_id,
                "label": payload.label,
                "solver_status": solver_result.status.value,
                "total_sessions": len(solver_result.sessions),
                "hard_violations": hard_count,
            },
            request=request,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Persistence failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to persist generation result.")

    return GenerationResponse(
        status=solver_result.status.value,
        version_id=str(version.id) if version else None,
        version_status=version.status if version else None,
        solver_time_ms=solver_result.solver_time_ms,
        objective_value=solver_result.objective_value,
        num_conflicts=solver_result.num_conflicts,
        total_sessions=len(solver_result.sessions),
        hard_violations=hard_count,
        soft_violations=soft_count,
        diagnostic_notes=solver_result.diagnostic_notes,
        sessions=[_session_to_out(s) for s in solver_result.sessions],
        violations=[_violation_to_out(v) for v in violations],
    )


# ---------------------------------------------------------------------------
# Validate existing version
# ---------------------------------------------------------------------------

@router.post("/validate", response_model=GenerationResponse)
def validate_version(
    payload: ValidateVersionRequest,
    current_user: UserAccount = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    """Re-validate an existing timetable version and return updated violation list."""
    version = db.query(TimetableVersion).filter(
        TimetableVersion.id == payload.version_id
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="Timetable version not found.")

    assert_department_access(current_user, version.department_id)

    dept_id = str(version.department_id)
    builder = SchedulingInputBuilder(db)
    scheduling_input = builder.build(dept_id)

    db_sessions = (
        db.query(ScheduledSession)
        .filter(ScheduledSession.timetable_version_id == payload.version_id)
        .all()
    )

    assigned_ta_ids = {str(s.teaching_assignment_id) for s in db_sessions}
    if assigned_ta_ids:
        scheduling_input.assignments = [
            a for a in scheduling_input.assignments if a.id in assigned_ta_ids
        ]

    slot_uuid_map = {}
    from backend.app.models.scheduling import TimeSlot
    for ts in db.query(TimeSlot).all():
        slot_uuid_map[str(ts.id)] = ts.slot_index

    session_infos = [
        ScheduledSessionInfo(
            assignment_id=str(s.teaching_assignment_id),
            teacher_id=str(s.teacher_id),
            subject_id=str(s.teaching_assignment_id),
            subject_name="",
            room_id=str(s.room_id),
            day_name=s.day_name,
            slot_index=slot_uuid_map.get(str(s.time_slot_id), 0),
            session_type=s.session_type,
            target_group_type=s.target_group_type,
            target_group_id=str(s.target_group_id),
            duration_slots=1,
            is_frozen=s.is_frozen,
        )
        for s in db_sessions
    ]

    violations = validate_timetable(session_infos, scheduling_input, check_soft=payload.check_soft)
    hard_count = sum(1 for v in violations if v.level == ViolationLevel.A)
    soft_count = sum(1 for v in violations if v.level != ViolationLevel.A)

    return GenerationResponse(
        status="REVALIDATED",
        version_id=str(payload.version_id),
        version_status=version.status,
        solver_time_ms=0,
        total_sessions=len(session_infos),
        hard_violations=hard_count,
        soft_violations=soft_count,
        violations=[_violation_to_out(v) for v in violations],
    )


# ---------------------------------------------------------------------------
# Version list (Role & Institutional Scope Isolated)
# ---------------------------------------------------------------------------

@router.get("/versions", response_model=List[TimetableVersionOut])
def list_versions(
    department_id: Optional[uuid.UUID] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=20, le=100),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List timetable versions with strict RBAC & data isolation:
    - Student & Teacher: strictly published versions within their own department.
    - Coordinator: all statuses within their own department.
    - Admin: all departments and statuses.
    """
    if department_id:
        assert_department_access(current_user, department_id)

    q = db.query(TimetableVersion)

    if current_user.role in ("teacher", "student"):
        if status_filter and status_filter != "published":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only published timetables are visible to teachers and students.",
            )
        q = q.filter(TimetableVersion.status == "published")
        if current_user.department_id:
            q = q.filter(TimetableVersion.department_id == current_user.department_id)
    elif current_user.role == "coordinator":
        if current_user.department_id:
            q = q.filter(TimetableVersion.department_id == current_user.department_id)
        if status_filter:
            q = q.filter(TimetableVersion.status == status_filter)
    else:
        if department_id:
            q = q.filter(TimetableVersion.department_id == department_id)
        if status_filter:
            q = q.filter(TimetableVersion.status == status_filter)

    versions = q.order_by(TimetableVersion.created_at.desc()).limit(limit).all()
    return [_version_to_out(v, db) for v in versions]


# ---------------------------------------------------------------------------
# Version detail (Role, Department & Entity Isolated)
# ---------------------------------------------------------------------------

@router.get("/versions/{version_id}", response_model=TimetableVersionDetail)
def get_version(
    version_id: uuid.UUID,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a timetable version with sessions.
    Enforces:
    - Teachers & Students cannot view unpublished versions (403 Forbidden).
    - Non-admins cannot view versions outside their department (403 Forbidden).
    - Teachers receive ONLY their own teaching sessions (and no internal violations).
    - Students receive ONLY sessions for their division & its batches (and no internal violations).
    """
    version = db.query(TimetableVersion).filter(TimetableVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Timetable version not found.")

    assert_department_access(current_user, version.department_id)

    if current_user.role in ("teacher", "student") and version.status != "published":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: unpublished timetable versions are restricted to administrators and coordinators.",
        )

    db_sessions = (
        db.query(ScheduledSession)
        .filter(ScheduledSession.timetable_version_id == version_id)
        .all()
    )

    # Apply entity-level institutional isolation
    if current_user.role == "teacher":
        teacher_id_str = _resolve_teacher_id(current_user, db)
        if teacher_id_str:
            db_sessions = [s for s in db_sessions if str(s.teacher_id) == teacher_id_str]
        else:
            db_sessions = []
        db_violations = []
    elif current_user.role == "student":
        allowed_groups = _resolve_student_allowed_groups(current_user, db)
        if allowed_groups:
            db_sessions = [s for s in db_sessions if str(s.target_group_id) in allowed_groups]
        else:
            db_sessions = []
        db_violations = []
    else:
        db_violations = (
            db.query(Violation)
            .filter(Violation.timetable_version_id == version_id)
            .all()
        )

    slot_uuid_map = {}
    from backend.app.models.scheduling import TimeSlot
    for ts in db.query(TimeSlot).all():
        slot_uuid_map[str(ts.id)] = ts.slot_index

    sessions_out = [
        SessionOut(
            assignment_id=str(s.teaching_assignment_id),
            teacher_id=str(s.teacher_id),
            subject_id=str(s.teaching_assignment.subject_id if s.teaching_assignment else s.teaching_assignment_id),
            room_id=str(s.room_id),
            day_name=s.day_name,
            slot_index=slot_uuid_map.get(str(s.time_slot_id), 0),
            session_type=s.session_type,
            target_group_type=s.target_group_type,
            target_group_id=str(s.target_group_id),
            duration_slots=1,
            is_frozen=s.is_frozen,
            subject_name=s.teaching_assignment.subject.name if s.teaching_assignment and s.teaching_assignment.subject else None,
            subject_code=s.teaching_assignment.subject.code if s.teaching_assignment and s.teaching_assignment.subject else None,
            teacher_name=s.teacher.name if s.teacher else None,
            room_name=s.room.name if s.room else None,
        )
        for s in db_sessions
    ]
    violations_out = [
        ViolationOut(
            rule_id=v.rule_id,
            level=v.rule_level,
            severity=v.severity,
            description=v.description,
            affected_session_ids=v.affected_session_ids or [],
            affected_entity_ids=v.affected_entity_ids or [],
        )
        for v in db_violations
    ]

    return TimetableVersionDetail(
        id=version.id,
        department_id=version.department_id,
        version_number=version.version_number,
        status=version.status,
        label=version.label,
        academic_year_code=version.academic_year_code,
        semester=version.semester,
        is_repair=version.is_repair,
        submitted_by=version.submitted_by,
        submitted_at=version.submitted_at,
        approved_by=version.approved_by,
        approved_at=version.approved_at,
        approval_comment=version.approval_comment,
        published_by=version.published_by,
        published_at=version.published_at,
        created_at=version.created_at,
        total_sessions=len(sessions_out),
        hard_violations=sum(1 for v in db_violations if v.rule_level == "A"),
        sessions=sessions_out,
        violations=violations_out,
    )


# ---------------------------------------------------------------------------
# Controlled Approval & Publication Workflow
# ---------------------------------------------------------------------------

@router.post("/versions/{version_id}/submit", response_model=TimetableVersionOut)
def submit_version_for_approval(
    version_id: uuid.UUID,
    request: Request,
    payload: Optional[ApprovalActionRequest] = Body(default=None),
    current_user: UserAccount = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    """
    Step 1 of controlled publication: Coordinator or Admin submits a validated
    candidate version for approval. Blocks submission if hard violations exist.
    """
    version = db.query(TimetableVersion).filter(TimetableVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Timetable version not found.")

    assert_department_access(current_user, version.department_id)

    if version.status not in ("candidate", "rejected", "draft"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot submit version with status '{version.status}' for approval.",
        )

    hard_count = _count_hard_violations(version, db)
    if hard_count > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot submit timetable for approval: {hard_count} Level A hard violation(s) must be resolved first.",
        )

    version.status = "pending_approval"
    version.submitted_by = current_user.id
    version.submitted_at = datetime.utcnow()
    if payload and payload.comment:
        version.approval_comment = payload.comment

    record_audit_event(
        db=db,
        action="TIMETABLE_SUBMIT",
        entity_type="TIMETABLE_VERSION",
        user_id=current_user.id,
        entity_id=version.id,
        payload={
            "version_number": version.version_number,
            "label": version.label,
            "comment": payload.comment if payload else None,
        },
        request=request,
    )
    db.commit()
    db.refresh(version)
    return _version_to_out(version, db)


@router.post("/versions/{version_id}/approve", response_model=TimetableVersionOut)
def approve_version(
    version_id: uuid.UUID,
    request: Request,
    payload: Optional[ApprovalActionRequest] = Body(default=None),
    current_user: UserAccount = Depends(require_approver),
    db: Session = Depends(get_db),
):
    """
    Step 2 of controlled publication: Authorized approver (Admin or Coordinator
    with can_approve_timetable=True) approves a pending candidate version.
    """
    version = db.query(TimetableVersion).filter(TimetableVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Timetable version not found.")

    assert_department_access(current_user, version.department_id)

    if version.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only versions in 'pending_approval' status can be approved (current: '{version.status}').",
        )

    hard_count = _count_hard_violations(version, db)
    if hard_count > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot approve timetable with {hard_count} Level A hard violation(s).",
        )

    version.status = "approved"
    version.approved_by = current_user.id
    version.approved_at = datetime.utcnow()
    version.approval_comment = payload.comment if payload and payload.comment else None

    record_audit_event(
        db=db,
        action="TIMETABLE_APPROVE",
        entity_type="TIMETABLE_VERSION",
        user_id=current_user.id,
        entity_id=version.id,
        payload={
            "version_number": version.version_number,
            "label": version.label,
            "comment": version.approval_comment,
        },
        request=request,
    )
    db.commit()
    db.refresh(version)
    return _version_to_out(version, db)


@router.post("/versions/{version_id}/reject", response_model=TimetableVersionOut)
def reject_version(
    version_id: uuid.UUID,
    request: Request,
    payload: Optional[ApprovalActionRequest] = Body(default=None),
    current_user: UserAccount = Depends(require_approver),
    db: Session = Depends(get_db),
):
    """
    Reject a pending timetable candidate with an optional reason.
    Authorized approver only.
    """
    version = db.query(TimetableVersion).filter(TimetableVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Timetable version not found.")

    assert_department_access(current_user, version.department_id)

    if version.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only versions in 'pending_approval' status can be rejected (current: '{version.status}').",
        )

    version.status = "rejected"
    version.approved_by = current_user.id
    version.approved_at = datetime.utcnow()
    version.approval_comment = payload.comment if payload and payload.comment else "Rejected by approver."

    record_audit_event(
        db=db,
        action="TIMETABLE_REJECT",
        entity_type="TIMETABLE_VERSION",
        user_id=current_user.id,
        entity_id=version.id,
        payload={
            "version_number": version.version_number,
            "label": version.label,
            "reason": version.approval_comment,
        },
        request=request,
    )
    db.commit()
    db.refresh(version)
    return _version_to_out(version, db)


@router.post("/versions/{version_id}/publish", response_model=TimetableVersionOut)
def publish_version(
    version_id: uuid.UUID,
    request: Request,
    current_user: UserAccount = Depends(require_approver),
    db: Session = Depends(get_db),
):
    """
    Step 3 of controlled publication: Publish an APPROVED timetable version.
    Enforces:
    - Authorized approver only (Admin or Coordinator with can_approve_timetable=True).
    - Version must be in 'approved' status (prevents unapproved or duplicate publication).
    - Zero Level A hard violations.
    - Preserves previous published versions by archiving them rather than deleting.
    - Records publisher, approver, and timestamp in DB and audit log.
    """
    version = db.query(TimetableVersion).filter(TimetableVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Timetable version not found.")

    assert_department_access(current_user, version.department_id)

    if version.status == "published":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Timetable version is already published.",
        )

    if version.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Timetable version must be approved before publication "
                f"(current status: '{version.status}'). Submit for approval and obtain approval first."
            ),
        )

    # Hard violation gate (final authoritative check)
    hard_count = _count_hard_violations(version, db)
    if hard_count > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Publication blocked: {hard_count} Level A hard violation(s) detected.",
        )

    # Archive any currently published versions for the same scope (preserving history)
    prior_published = (
        db.query(TimetableVersion)
        .filter(
            TimetableVersion.department_id == version.department_id,
            TimetableVersion.academic_year_code == version.academic_year_code,
            TimetableVersion.semester == version.semester,
            TimetableVersion.status == "published",
            TimetableVersion.id != version.id,
        )
        .all()
    )
    archived_ids = []
    for old_ver in prior_published:
        old_ver.status = "archived"
        archived_ids.append(str(old_ver.id))

    version.status = "published"
    version.published_at = datetime.utcnow()
    version.published_by = current_user.id

    record_audit_event(
        db=db,
        action="TIMETABLE_PUBLISH",
        entity_type="TIMETABLE_VERSION",
        user_id=current_user.id,
        entity_id=version.id,
        payload={
            "version_number": version.version_number,
            "label": version.label,
            "approved_by": str(version.approved_by) if version.approved_by else None,
            "approved_at": version.approved_at.isoformat() if version.approved_at else None,
            "archived_previous_versions": archived_ids,
        },
        request=request,
    )
    db.commit()
    db.refresh(version)
    return _version_to_out(version, db)


# ---------------------------------------------------------------------------
# Compare two versions
# ---------------------------------------------------------------------------

@router.get("/compare", response_model=ComparisonResponse)
def compare_timetable_versions(
    version_a: uuid.UUID = Query(...),
    version_b: uuid.UUID = Query(...),
    include_diffs: bool = Query(default=True),
    current_user: UserAccount = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    """Compare two timetable versions and return a structured diff (Admin & Coordinator only)."""
    for vid in (version_a, version_b):
        v = db.query(TimetableVersion).filter(TimetableVersion.id == vid).first()
        if v:
            assert_department_access(current_user, v.department_id)

    comparison = compare_versions(db, str(version_a), str(version_b))
    diffs = []
    if include_diffs:
        all_diffs = comparison.added + comparison.removed + comparison.moved
        diffs = [
            SessionDiffOut(
                change_type=d.change_type,
                assignment_id=d.assignment_id,
                session_type=d.session_type,
                teacher_id=d.teacher_id,
                day_a=d.day_a,
                slot_a=d.slot_a,
                room_a=d.room_a,
                day_b=d.day_b,
                slot_b=d.slot_b,
                room_b=d.room_b,
            )
            for d in all_diffs
        ]
    return ComparisonResponse(
        **comparison.summary,
        diffs=diffs,
    )


# ---------------------------------------------------------------------------
# Repair
# ---------------------------------------------------------------------------

@router.post("/repair", response_model=GenerationResponse, status_code=status.HTTP_202_ACCEPTED)
def repair_timetable(
    payload: RepairRequest,
    request: Request,
    current_user: UserAccount = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    """
    Localised repair: keep frozen sessions from source_version fixed,
    re-schedule only the specified (or all unfrozen) assignments.
    Allowed: Admin, Coordinator (own department only).
    """
    source = db.query(TimetableVersion).filter(
        TimetableVersion.id == payload.source_version_id
    ).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source timetable version not found.")

    assert_department_access(current_user, source.department_id)

    dept_id = str(source.department_id)
    builder = SchedulingInputBuilder(db)
    scheduling_input = builder.build(dept_id)

    db_sessions = (
        db.query(ScheduledSession)
        .filter(ScheduledSession.timetable_version_id == payload.source_version_id)
        .all()
    )
    affected_ids = {str(x) for x in payload.affected_assignment_ids} if payload.affected_assignment_ids else None

    slot_uuid_map = {}
    from backend.app.models.scheduling import TimeSlot
    for ts in db.query(TimeSlot).all():
        slot_uuid_map[str(ts.id)] = ts.slot_index

    pinned = []
    for s in db_sessions:
        aid = str(s.teaching_assignment_id)
        is_affected = affected_ids is None or aid in affected_ids
        if not is_affected or s.is_frozen:
            pinned.append(ScheduledSessionInfo(
                assignment_id=aid,
                teacher_id=str(s.teacher_id),
                subject_id=aid,
                subject_name="",
                room_id=str(s.room_id),
                day_name=s.day_name,
                slot_index=slot_uuid_map.get(str(s.time_slot_id), 0),
                session_type=s.session_type,
                target_group_type=s.target_group_type,
                target_group_id=str(s.target_group_id),
                duration_slots=1,
                is_frozen=True,
            ))

    pinned_aids = {p.assignment_id for p in pinned}
    free_assignments = [a for a in scheduling_input.assignments if a.id not in pinned_aids]
    if not free_assignments:
        raise HTTPException(
            status_code=422,
            detail="All assignments are pinned or no affected assignments specified.",
        )
    scheduling_input.assignments = free_assignments

    solver_result = run_solver(
        scheduling_input,
        time_limit_seconds=payload.time_limit_seconds,
        pinned_sessions=pinned,
    )

    violations = []
    if solver_result.sessions:
        scheduling_input.assignments = builder.build(dept_id).assignments
        violations = validate_timetable(solver_result.sessions, scheduling_input)

    hard_count = sum(1 for v in violations if v.level == ViolationLevel.A)
    soft_count = sum(1 for v in violations if v.level != ViolationLevel.A)

    try:
        version = persist_generation_result(
            db=db,
            scheduling_input=scheduling_input,
            solver_result=solver_result,
            violations=violations,
            department_id=dept_id,
            label=payload.label,
            parent_version_id=str(payload.source_version_id),
            is_repair=True,
        )
        record_audit_event(
            db=db,
            action="TIMETABLE_REPAIR",
            entity_type="TIMETABLE_VERSION",
            user_id=current_user.id,
            entity_id=version.id if version else None,
            payload={
                "source_version_id": str(payload.source_version_id),
                "label": payload.label,
                "solver_status": solver_result.status.value,
                "hard_violations": hard_count,
            },
            request=request,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to persist repair: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to persist repair result.")

    return GenerationResponse(
        status=solver_result.status.value,
        version_id=str(version.id) if version else None,
        version_status=version.status if version else None,
        solver_time_ms=solver_result.solver_time_ms,
        total_sessions=len(solver_result.sessions),
        hard_violations=hard_count,
        soft_violations=soft_count,
        diagnostic_notes=solver_result.diagnostic_notes,
        sessions=[_session_to_out(s) for s in solver_result.sessions],
        violations=[_violation_to_out(v) for v in violations],
    )


# ---------------------------------------------------------------------------
# Asynchronous Background Generation (Non-Blocking)
# ---------------------------------------------------------------------------

@router.post("/generate/async", status_code=status.HTTP_202_ACCEPTED)
def generate_timetable_async(
    payload: GenerationRequest,
    current_user: UserAccount = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    """
    Enqueue a non-blocking background CP-SAT timetable generation job.
    Prevents duplicate concurrent runs for the same department (409 Conflict).
    Clients poll GET /api/v1/timetable/runs/{run_id} for progress and resulting version_id.
    """
    assert_department_access(current_user, payload.department_id)
    dept_id = str(payload.department_id)
    ay_ids = [str(x) for x in payload.academic_year_ids] if payload.academic_year_ids else None

    try:
        run = generation_job_manager.submit_generation_job(
            db=db,
            department_id=dept_id,
            academic_year_ids=ay_ids,
            label=payload.label,
            academic_year_code=payload.academic_year_code,
            semester=payload.semester,
            time_limit_seconds=payload.time_limit_seconds,
            check_soft_constraints=payload.check_soft_constraints,
            confirmed_constraints=payload.confirmed_constraints,
            actor_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    return {
        "run_id": str(run.id),
        "status": run.status,
        "poll_url": f"/api/v1/timetable/runs/{run.id}",
        "started_at": run.started_at,
        "message": "Timetable generation job queued on background solver worker.",
    }


# ---------------------------------------------------------------------------
# Generation run status
# ---------------------------------------------------------------------------

@router.get("/runs/{run_id}")
def get_generation_run(
    run_id: uuid.UUID,
    current_user: UserAccount = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    """Get generation run metadata, progress status, solver diagnostics, and resulting version_id."""
    run = db.query(GenerationRun).filter(GenerationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Generation run not found.")

    # Enforce department scope if snapshot or version specifies a department
    if run.input_snapshot and isinstance(run.input_snapshot.data, dict):
        snap_dept = run.input_snapshot.data.get("department_id")
        if snap_dept:
            try:
                assert_department_access(current_user, uuid.UUID(str(snap_dept)))
            except ValueError:
                pass

    linked_version = (
        db.query(TimetableVersion)
        .filter(TimetableVersion.generation_run_id == run.id)
        .order_by(TimetableVersion.created_at.desc())
        .first()
    )
    if linked_version:
        assert_department_access(current_user, linked_version.department_id)

    return {
        "id": str(run.id),
        "status": run.status,
        "solver_status": run.solver_status,
        "solver_time_ms": run.solver_time_ms,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "notes": run.notes,
        "version_id": str(linked_version.id) if linked_version else None,
        "version_status": linked_version.status if linked_version else None,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _session_to_out(s: ScheduledSessionInfo) -> SessionOut:
    return SessionOut(
        assignment_id=s.assignment_id,
        teacher_id=s.teacher_id,
        subject_id=s.subject_id,
        room_id=s.room_id,
        day_name=s.day_name,
        slot_index=s.slot_index,
        session_type=s.session_type,
        target_group_type=s.target_group_type,
        target_group_id=s.target_group_id,
        duration_slots=s.duration_slots,
        is_frozen=s.is_frozen,
        subject_name=getattr(s, "subject_name", None),
        subject_code=getattr(s, "subject_code", None),
        teacher_name=getattr(s, "teacher_name", None),
        room_name=getattr(s, "room_name", None),
    )


def _violation_to_out(v) -> ViolationOut:
    return ViolationOut(
        rule_id=v.rule_id,
        level=v.level.value if hasattr(v.level, "value") else v.level,
        severity=v.severity,
        description=v.description,
        affected_session_ids=v.affected_session_ids,
        affected_entity_ids=v.affected_entity_ids,
        suggestion=getattr(v, "suggestion", None),
    )
