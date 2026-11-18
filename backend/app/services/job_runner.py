"""
backend/app/services/job_runner.py
EduPlus AI Timetable Maker — Asynchronous Background Timetable Generation Worker Pool

Provides non-blocking CP-SAT timetable generation backed by PostgreSQL GenerationRun
persistence, per-department duplicate-job protection, clean error recovery, and health reporting.
"""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.session import SessionLocal
from backend.app.engine.input_builder import SchedulingInputBuilder
from backend.app.engine.persistence import persist_generation_result
from backend.app.engine.solver import run_solver
from backend.app.engine.types import SlotKey, SolverStatus, ViolationLevel
from backend.app.engine.validator import validate_timetable
from backend.app.models.timetable import GenerationRun, InputSnapshot, TimetableVersion
from backend.app.services.audit import record_audit_event


class GenerationJobManager:
    """Thread-pool backed background generation runner with DB persistence and dedup guards."""

    def __init__(self, max_workers: int = 2) -> None:
        self._max_workers = max(1, max_workers)
        self._executor = ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="eduplus-solver",
        )
        self._lock = threading.Lock()
        self._active_departments: Set[str] = set()
        self._active_runs: Dict[str, str] = {}  # run_id -> department_id
        self._completed_count = 0
        self._failed_count = 0

    def is_department_busy(self, department_id: str, db: Optional[Session] = None) -> bool:
        with self._lock:
            if department_id in self._active_departments:
                return True
        if db is not None:
            # Also check shared DB state across workers
            running = (
                db.query(GenerationRun)
                .join(InputSnapshot, GenerationRun.input_snapshot_id == InputSnapshot.id)
                .filter(GenerationRun.status == "running")
                .all()
            )
            for r in running:
                snap_data = r.input_snapshot.data if r.input_snapshot else {}
                if isinstance(snap_data, dict) and snap_data.get("department_id") == department_id:
                    return True
        return False

    def submit_generation_job(
        self,
        db: Session,
        department_id: str,
        academic_year_ids: Optional[List[str]],
        label: str,
        academic_year_code: str,
        semester: int,
        time_limit_seconds: int,
        check_soft_constraints: bool,
        confirmed_constraints: Optional[List[Dict[str, Any]]],
        actor_user_id: Optional[uuid.UUID],
        session_factory: Callable[[], Session] = SessionLocal,
    ) -> GenerationRun:
        """
        Persist an initial InputSnapshot & GenerationRun(status='running') and enqueue
        the CP-SAT solve on the background thread pool.
        Raises ValueError if a generation job is already active for the same department.
        """
        with self._lock:
            if department_id in self._active_departments:
                raise ValueError("A timetable generation job is already running for this department.")
            self._active_departments.add(department_id)

        try:
            if self._db_has_running_job_for_dept(db, department_id):
                with self._lock:
                    self._active_departments.discard(department_id)
                raise ValueError("A timetable generation job is already running for this department.")

            snap_payload = {
                "department_id": department_id,
                "academic_year_ids": academic_year_ids or [],
                "label": label,
                "academic_year_code": academic_year_code,
                "semester": semester,
                "confirmed_constraints_count": len(confirmed_constraints or []),
            }
            checksum = hashlib.sha256(json.dumps(snap_payload, sort_keys=True).encode()).hexdigest()
            snapshot = InputSnapshot(data=snap_payload, checksum=checksum)
            db.add(snapshot)
            db.flush()

            run = GenerationRun(
                input_snapshot_id=snapshot.id,
                status="running",
                started_at=datetime.utcnow(),
                notes="Queued for background CP-SAT execution.",
            )
            db.add(run)
            db.commit()
            db.refresh(run)

            run_id_str = str(run.id)
            with self._lock:
                self._active_runs[run_id_str] = department_id

            self._executor.submit(
                self._execute_job,
                run.id,
                department_id,
                academic_year_ids,
                label,
                academic_year_code,
                semester,
                time_limit_seconds,
                check_soft_constraints,
                confirmed_constraints,
                actor_user_id,
                session_factory,
            )
            return run
        except Exception:
            with self._lock:
                self._active_departments.discard(department_id)
            raise

    def _db_has_running_job_for_dept(self, db: Session, department_id: str) -> bool:
        running = db.query(GenerationRun).filter(GenerationRun.status == "running").all()
        for r in running:
            snap_data = r.input_snapshot.data if r.input_snapshot else {}
            if isinstance(snap_data, dict) and snap_data.get("department_id") == department_id:
                return True
        return False

    def _execute_job(
        self,
        run_id: uuid.UUID,
        department_id: str,
        academic_year_ids: Optional[List[str]],
        label: str,
        academic_year_code: str,
        semester: int,
        time_limit_seconds: int,
        check_soft_constraints: bool,
        confirmed_constraints: Optional[List[Dict[str, Any]]],
        actor_user_id: Optional[uuid.UUID],
        session_factory: Callable[[], Session],
    ) -> None:
        db = session_factory()
        run_id_str = str(run_id)
        try:
            run = db.query(GenerationRun).filter(GenerationRun.id == run_id).first()
            if run is None:
                return

            builder = SchedulingInputBuilder(db)
            scheduling_input = builder.build(department_id, academic_year_ids)
            if not scheduling_input.assignments:
                run.status = "failed"
                run.finished_at = datetime.utcnow()
                run.notes = "No teaching assignments found for the specified scope."
                db.commit()
                self._failed_count += 1
                return

            # Apply confirmed constraints
            if confirmed_constraints:
                active_days = [wd.day_name for wd in scheduling_input.working_days if wd.is_active]
                for c in confirmed_constraints:
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

            solver_result = run_solver(scheduling_input, time_limit_seconds=time_limit_seconds)
            violations = []
            if solver_result.sessions:
                violations = validate_timetable(
                    solver_result.sessions,
                    scheduling_input,
                    check_soft=check_soft_constraints,
                )

            version = persist_generation_result(
                db=db,
                scheduling_input=scheduling_input,
                solver_result=solver_result,
                violations=violations,
                department_id=department_id,
                label=label,
                academic_year_code=academic_year_code,
                semester=semester,
            )
            # Attach persisted version to our tracked GenerationRun
            if version is not None:
                version.generation_run_id = run.id

            status_map = {
                SolverStatus.OPTIMAL: "completed",
                SolverStatus.FEASIBLE: "completed",
                SolverStatus.INFEASIBLE: "infeasible",
                SolverStatus.TIMEOUT: "timeout",
            }
            run.status = status_map.get(solver_result.status, "failed")
            run.solver_status = solver_result.status.value
            run.solver_time_ms = solver_result.solver_time_ms
            run.finished_at = datetime.utcnow()
            run.notes = solver_result.diagnostic_notes

            record_audit_event(
                db=db,
                action="TIMETABLE_GENERATE_ASYNC",
                entity_type="TIMETABLE_VERSION",
                user_id=actor_user_id,
                entity_id=version.id if version else run.id,
                payload={
                    "run_id": run_id_str,
                    "department_id": department_id,
                    "solver_status": solver_result.status.value,
                    "total_sessions": len(solver_result.sessions),
                    "hard_violations": sum(1 for v in violations if v.level == ViolationLevel.A),
                },
            )
            db.commit()
            self._completed_count += 1
            logger.info(
                f"Background generation run={run_id_str} finished: {run.status} "
                f"({solver_result.status.value}) in {solver_result.solver_time_ms}ms"
            )
        except Exception as exc:
            db.rollback()
            self._failed_count += 1
            logger.error(f"Background generation run={run_id_str} failed: {type(exc).__name__}", exc_info=True)
            try:
                run = db.query(GenerationRun).filter(GenerationRun.id == run_id).first()
                if run:
                    run.status = "failed"
                    run.finished_at = datetime.utcnow()
                    run.notes = f"Worker error: {type(exc).__name__}"
                    db.commit()
            except Exception:
                db.rollback()
        finally:
            db.close()
            with self._lock:
                self._active_departments.discard(department_id)
                self._active_runs.pop(run_id_str, None)

    def recover_orphaned_runs(self, db: Session) -> int:
        """Mark any leftover 'running' jobs from a previous crashed process as 'failed'."""
        orphans = db.query(GenerationRun).filter(GenerationRun.status == "running").all()
        count = 0
        for run in orphans:
            if str(run.id) not in self._active_runs:
                run.status = "failed"
                run.finished_at = datetime.utcnow()
                run.notes = "Interrupted by server restart; safe to retry."
                count += 1
        if count > 0:
            db.commit()
            logger.warning(f"Recovered {count} orphaned generation run(s) on startup.")
        return count

    def get_health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "status": "healthy",
                "max_workers": self._max_workers,
                "active_jobs": len(self._active_runs),
                "completed_jobs": self._completed_count,
                "failed_jobs": self._failed_count,
            }


generation_job_manager = GenerationJobManager(max_workers=settings.SOLVER_MAX_WORKERS)
