"""
backend/app/engine/persistence.py
EduPlus AI Timetable Maker — Timetable Generation Persistence

Saves a SolverResult to the database using existing tables:
  - input_snapshots
  - generation_runs
  - timetable_versions
  - scheduled_sessions
  - violations

All writes happen inside a single database transaction. If any step
fails the entire operation is rolled back — no partial timetable is
ever persisted.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.app.engine.types import (
    ScheduledSessionInfo,
    SchedulingInput,
    SolverResult,
    SolverStatus,
    ViolationRecord,
    ViolationLevel,
)
from backend.app.models.timetable import (
    GenerationRun,
    InputSnapshot,
    ScheduledSession,
    TimetableVersion,
    Violation,
)


def persist_generation_result(
    db: Session,
    scheduling_input: SchedulingInput,
    solver_result: SolverResult,
    violations: List[ViolationRecord],
    department_id: str,
    label: str,
    academic_year_code: str = "2026-27",
    semester: int = 1,
    parent_version_id: Optional[str] = None,
    is_repair: bool = False,
) -> Optional[TimetableVersion]:
    """
    Persist a complete generation result atomically.

    Returns the saved TimetableVersion on success, or None if the solver
    produced no usable sessions (infeasible / timeout).

    The caller is responsible for committing or rolling back the session;
    this function only adds objects to the session.
    """
    # 1. Build input snapshot
    snapshot_data = _build_snapshot_data(scheduling_input)
    snapshot_json = json.dumps(snapshot_data, sort_keys=True, default=str)
    checksum = hashlib.sha256(snapshot_json.encode()).hexdigest()

    snapshot = InputSnapshot(
        id=uuid.uuid4(),
        data=snapshot_data,
        checksum=checksum,
        created_at=datetime.utcnow(),
    )
    db.add(snapshot)
    db.flush()   # get snapshot.id before referencing it

    # 2. Generation run record
    gen_run = GenerationRun(
        id=uuid.uuid4(),
        input_snapshot_id=snapshot.id,
        status=_map_status(solver_result.status),
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
        solver_time_ms=solver_result.solver_time_ms,
        solver_status=solver_result.status.value,
        notes=solver_result.diagnostic_notes[:2000] if solver_result.diagnostic_notes else None,
    )
    db.add(gen_run)
    db.flush()

    # 3. If no solution, stop here — return None so API can report clearly
    if solver_result.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
        return None

    # 4. Determine timetable version status
    has_hard_violations = any(v.level == ViolationLevel.A for v in violations)
    version_status = "draft" if has_hard_violations else "candidate"

    # 5. TimetableVersion
    version = TimetableVersion(
        id=uuid.uuid4(),
        generation_run_id=gen_run.id,
        parent_version_id=uuid.UUID(parent_version_id) if parent_version_id else None,
        department_id=uuid.UUID(department_id),
        version_number=_next_version_number(db, department_id),
        status=version_status,
        label=label,
        academic_year_code=academic_year_code,
        semester=semester,
        is_repair=is_repair,
        created_at=datetime.utcnow(),
    )
    db.add(version)
    db.flush()

    # 6. Scheduled sessions
    for session_info in solver_result.sessions:
        ss = ScheduledSession(
            id=uuid.uuid4(),
            timetable_version_id=version.id,
            teaching_assignment_id=uuid.UUID(session_info.assignment_id),
            teacher_id=uuid.UUID(session_info.teacher_id),
            room_id=uuid.UUID(session_info.room_id),
            day_name=session_info.day_name,
            time_slot_id=_resolve_time_slot_id(scheduling_input, session_info.slot_index),
            session_type=session_info.session_type,
            target_group_type=session_info.target_group_type,
            target_group_id=uuid.UUID(session_info.target_group_id),
            is_frozen=session_info.is_frozen,
            created_at=datetime.utcnow(),
        )
        db.add(ss)

    # 7. Violations
    for viol in violations:
        v = Violation(
            id=uuid.uuid4(),
            timetable_version_id=version.id,
            rule_id=viol.rule_id,
            rule_level=viol.level.value,
            severity=viol.severity,
            description=viol.description,
            affected_session_ids=viol.affected_session_ids,
            affected_entity_ids=viol.affected_entity_ids,
            created_at=datetime.utcnow(),
        )
        db.add(v)

    db.flush()
    return version


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _map_status(status: SolverStatus) -> str:
    return {
        SolverStatus.OPTIMAL: "completed",
        SolverStatus.FEASIBLE: "completed",
        SolverStatus.INFEASIBLE: "infeasible",
        SolverStatus.TIMEOUT: "timeout",
        SolverStatus.UNKNOWN: "failed",
        SolverStatus.ERROR: "failed",
    }.get(status, "failed")


def _build_snapshot_data(inp: SchedulingInput) -> dict:
    """Lightweight snapshot of the scheduling input for reproducibility."""
    return {
        "department_id": inp.department_id,
        "academic_year_ids": inp.academic_year_ids,
        "num_teachers": len(inp.teachers),
        "num_rooms": len(inp.rooms),
        "num_divisions": len(inp.divisions),
        "num_batches": len(inp.batches),
        "num_assignments": len(inp.assignments),
        "num_working_days": len(inp.working_days),
        "num_time_slots": len(inp.time_slots),
        "assignments": [
            {
                "id": a.id,
                "subject_id": a.subject_id,
                "teacher_id": a.teacher_id,
                "division_id": a.division_id,
                "batch_id": a.batch_id,
                "session_type": a.session_type,
                "weekly_count": a.weekly_count,
                "duration_slots": a.duration_slots,
            }
            for a in inp.assignments
        ],
    }


def _next_version_number(db: Session, department_id: str) -> int:
    from sqlalchemy import func
    result = (
        db.query(func.max(TimetableVersion.version_number))
        .filter(TimetableVersion.department_id == uuid.UUID(department_id))
        .scalar()
    )
    return (result or 0) + 1


def _resolve_time_slot_id(inp: SchedulingInput, slot_index: int) -> uuid.UUID:
    for ts in inp.time_slots:
        if ts.slot_index == slot_index:
            return uuid.UUID(ts.id)
    raise ValueError(f"Time slot index {slot_index} not found in scheduling input.")

