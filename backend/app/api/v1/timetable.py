"""
backend/app/api/v1/timetable.py
EduPlus AI Timetable Maker — Timetable Generation & Lifecycle Endpoints

Endpoints
---------
POST   /timetable/generate          — Generate a timetable
POST   /timetable/validate          — Validate an existing version
GET    /timetable/versions          — List versions for a department
GET    /timetable/versions/{id}     — Get a version with sessions
GET    /timetable/compare           — Compare two versions
POST   /timetable/repair            — Localised repair
GET    /timetable/runs/{id}         — Get generation run status/details
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.core.logging import logger
from backend.app.engine.comparator import compare_versions
from backend.app.engine.input_builder import SchedulingInputBuilder
from backend.app.engine.persistence import persist_generation_result
from backend.app.engine.solver import run_solver
from backend.app.engine.types import (
    ScheduledSessionInfo,
    SolverStatus,
    ViolationLevel,
)
from backend.app.engine.validator import validate_timetable
from backend.app.models.timetable import (
    GenerationRun,
    ScheduledSession,
    TimetableVersion,
    Violation,
)
from backend.app.schemas.timetable import (
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

router = APIRouter(prefix="/timetable", tags=["Timetable"])


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

@router.post("/generate", response_model=GenerationResponse, status_code=status.HTTP_202_ACCEPTED)
def generate_timetable(request: GenerationRequest, db: Session = Depends(get_db)):
    """
    Generate a new timetable for the given department/academic-year scope.

    1. Builds normalised scheduling input from the database.
    2. Runs the CP-SAT solver.
    3. Validates the result with the independent validator.
    4. Persists the generation run, version, sessions, and violations.
    5. Returns the full result.
    """
    dept_id = str(request.department_id)
    ay_ids = [str(x) for x in request.academic_year_ids] if request.academic_year_ids else None

    # Build input
    try:
        builder = SchedulingInputBuilder(db)
        scheduling_input = builder.build(dept_id, ay_ids)
    except Exception as exc:
        logger.error(f"Input build failed: {exc}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to build scheduling input: {exc}")

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
        f"time_limit={request.time_limit_seconds}s"
    )

    # Solve
    solver_result = run_solver(scheduling_input, time_limit_seconds=request.time_limit_seconds)
    logger.info(f"Solver finished: {solver_result.status.value} in {solver_result.solver_time_ms}ms")

    # Validate (even if solver reports OPTIMAL — independent check)
    violations = []
    if solver_result.sessions:
        violations = validate_timetable(
            solver_result.sessions,
            scheduling_input,
            check_soft=request.check_soft_constraints,
        )

    # Persist
    try:
        version = persist_generation_result(
            db=db,
            scheduling_input=scheduling_input,
            solver_result=solver_result,
            violations=violations,
            department_id=dept_id,
            label=request.label,
            academic_year_code=request.academic_year_code,
            semester=request.semester,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Persistence failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to persist generation result: {exc}")

    hard_count = sum(1 for v in violations if v.level == ViolationLevel.A)
    soft_count = sum(1 for v in violations if v.level != ViolationLevel.A)

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
def validate_version(request: ValidateVersionRequest, db: Session = Depends(get_db)):
    """Re-validate an existing timetable version and return updated violation list."""
    version = db.query(TimetableVersion).filter(
        TimetableVersion.id == request.version_id
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="Timetable version not found.")

    dept_id = str(version.department_id)
    builder = SchedulingInputBuilder(db)
    scheduling_input = builder.build(dept_id)

    # Load persisted sessions back into ScheduledSessionInfo
    db_sessions = (
        db.query(ScheduledSession)
        .filter(ScheduledSession.timetable_version_id == request.version_id)
        .all()
    )
    # Map time_slot_id -> slot_index
    slot_index_map = {ts.id: ts.slot_index for ts in scheduling_input.time_slots
                      if hasattr(ts, 'id')}
    # Rebuild from DB (we stored slot by time_slot_id UUID)
    slot_uuid_map = {}
    from backend.app.models.scheduling import TimeSlot
    for ts in db.query(TimeSlot).all():
        slot_uuid_map[str(ts.id)] = ts.slot_index

    session_infos = [
        ScheduledSessionInfo(
            assignment_id=str(s.teaching_assignment_id),
            teacher_id=str(s.teacher_id),
            subject_id=str(s.teaching_assignment_id),  # proxied
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

    violations = validate_timetable(session_infos, scheduling_input, check_soft=request.check_soft)
    hard_count = sum(1 for v in violations if v.level == ViolationLevel.A)
    soft_count = sum(1 for v in violations if v.level != ViolationLevel.A)

    return GenerationResponse(
        status="REVALIDATED",
        version_id=str(request.version_id),
        version_status=version.status,
        solver_time_ms=0,
        total_sessions=len(session_infos),
        hard_violations=hard_count,
        soft_violations=soft_count,
        violations=[_violation_to_out(v) for v in violations],
    )


# ---------------------------------------------------------------------------
# Version list
# ---------------------------------------------------------------------------

@router.get("/versions", response_model=List[TimetableVersionOut])
def list_versions(
    department_id: Optional[uuid.UUID] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
):
    """List timetable versions, optionally filtered by department and status."""
    q = db.query(TimetableVersion)
    if department_id:
        q = q.filter(TimetableVersion.department_id == department_id)
    if status:
        q = q.filter(TimetableVersion.status == status)
    q = q.order_by(TimetableVersion.created_at.desc()).limit(limit)
    versions = q.all()

    result = []
    for v in versions:
        session_count = (
            db.query(ScheduledSession)
            .filter(ScheduledSession.timetable_version_id == v.id)
            .count()
        )
        hard_viol = (
            db.query(Violation)
            .filter(Violation.timetable_version_id == v.id, Violation.rule_level == "A")
            .count()
        )
        out = TimetableVersionOut(
            id=v.id,
            department_id=v.department_id,
            version_number=v.version_number,
            status=v.status,
            label=v.label,
            academic_year_code=v.academic_year_code,
            semester=v.semester,
            is_repair=v.is_repair,
            published_at=v.published_at,
            created_at=v.created_at,
            total_sessions=session_count,
            hard_violations=hard_viol,
        )
        result.append(out)
    return result


# ---------------------------------------------------------------------------
# Version detail
# ---------------------------------------------------------------------------

@router.get("/versions/{version_id}", response_model=TimetableVersionDetail)
def get_version(version_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get a timetable version with full session and violation detail."""
    version = db.query(TimetableVersion).filter(TimetableVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Timetable version not found.")

    db_sessions = (
        db.query(ScheduledSession)
        .filter(ScheduledSession.timetable_version_id == version_id)
        .all()
    )
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
            subject_id=str(s.teaching_assignment_id),
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
        published_at=version.published_at,
        created_at=version.created_at,
        total_sessions=len(sessions_out),
        hard_violations=sum(1 for v in db_violations if v.rule_level == "A"),
        sessions=sessions_out,
        violations=violations_out,
    )


# ---------------------------------------------------------------------------
# Compare two versions
# ---------------------------------------------------------------------------

@router.get("/compare", response_model=ComparisonResponse)
def compare_timetable_versions(
    version_a: uuid.UUID = Query(...),
    version_b: uuid.UUID = Query(...),
    include_diffs: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """Compare two timetable versions and return a structured diff."""
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
def repair_timetable(request: RepairRequest, db: Session = Depends(get_db)):
    """
    Localised repair: keep frozen sessions from source_version fixed,
    re-schedule only the specified (or all unfrozen) assignments.
    """
    source = db.query(TimetableVersion).filter(
        TimetableVersion.id == request.source_version_id
    ).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source timetable version not found.")

    dept_id = str(source.department_id)
    builder = SchedulingInputBuilder(db)
    scheduling_input = builder.build(dept_id)

    # Load pinned sessions from DB (is_frozen=True, or those NOT in affected_assignment_ids)
    db_sessions = (
        db.query(ScheduledSession)
        .filter(ScheduledSession.timetable_version_id == request.source_version_id)
        .all()
    )
    affected_ids = {str(x) for x in request.affected_assignment_ids} if request.affected_assignment_ids else None

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

    # Remove pinned assignments from the input (solver only sees free assignments)
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
        time_limit_seconds=request.time_limit_seconds,
        pinned_sessions=pinned,
    )

    violations = []
    if solver_result.sessions:
        # Validate the full repaired timetable (free + pinned)
        scheduling_input.assignments = builder.build(dept_id).assignments  # restore all
        violations = validate_timetable(solver_result.sessions, scheduling_input)

    try:
        version = persist_generation_result(
            db=db,
            scheduling_input=scheduling_input,
            solver_result=solver_result,
            violations=violations,
            department_id=dept_id,
            label=request.label,
            parent_version_id=str(request.source_version_id),
            is_repair=True,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to persist repair: {exc}")

    hard_count = sum(1 for v in violations if v.level == ViolationLevel.A)
    soft_count = sum(1 for v in violations if v.level != ViolationLevel.A)

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
# Generation run status
# ---------------------------------------------------------------------------

@router.get("/runs/{run_id}")
def get_generation_run(run_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get generation run metadata and solver diagnostics."""
    run = db.query(GenerationRun).filter(GenerationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Generation run not found.")
    return {
        "id": str(run.id),
        "status": run.status,
        "solver_status": run.solver_status,
        "solver_time_ms": run.solver_time_ms,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "notes": run.notes,
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

