"""
backend/app/engine/input_builder.py
EduPlus AI Timetable Maker — Scheduling Input Builder

Reads live database rows and constructs a normalised SchedulingInput
ready for the validator and CP-SAT solver.

Usage
-----
    from backend.app.engine.input_builder import SchedulingInputBuilder
    inp = SchedulingInputBuilder(db).build(department_id, academic_year_ids)
"""

from __future__ import annotations

from typing import List, Optional
from sqlalchemy.orm import Session

from backend.app.models.academic import Department, AcademicYear, Division, Batch
from backend.app.models.faculty import Teacher, TeacherAvailability
from backend.app.models.room import Room
from backend.app.models.scheduling import (
    TimeSlot, WorkingDay, TeachingAssignment, SessionRequirement,
)
from backend.app.engine.types import (
    BatchInfo,
    DivisionInfo,
    RoomInfo,
    SchedulingInput,
    SlotKey,
    TeacherInfo,
    TeachingAssignmentInfo,
    TimeSlotInfo,
    WorkingDayInfo,
)


class SchedulingInputBuilder:
    """Constructs a SchedulingInput from the live database for a given scope."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def build(
        self,
        department_id: str,
        academic_year_ids: Optional[List[str]] = None,
    ) -> SchedulingInput:
        """
        Build a normalised SchedulingInput.

        Parameters
        ----------
        department_id:
            UUID of the department to generate for.
        academic_year_ids:
            Restrict to specific academic years within that department.
            If None, all years for the department are included.
        """
        db = self.db

        # Time slots and working days (global/department)
        time_slots = db.query(TimeSlot).order_by(TimeSlot.slot_index).all()
        working_days = (
            db.query(WorkingDay)
            .filter(WorkingDay.department_id == department_id, WorkingDay.is_active == True)
            .order_by(WorkingDay.day_index)
            .all()
        )

        # Teachers
        teachers_db = (
            db.query(Teacher)
            .filter(Teacher.department_id == department_id)
            .all()
        )
        teachers = []
        for t in teachers_db:
            unavail = [
                SlotKey(day_name=av.day_name, slot_index=self._slot_index(av.time_slot_id, time_slots))
                for av in t.availabilities
                if av.availability_type == "unavailable"
            ]
            preferred = [
                SlotKey(day_name=av.day_name, slot_index=self._slot_index(av.time_slot_id, time_slots))
                for av in t.availabilities
                if av.availability_type == "preferred"
            ]
            teachers.append(TeacherInfo(
                id=str(t.id),
                name=t.name,
                short_name=t.short_name,
                department_id=str(t.department_id),
                weekly_workload_cap=t.weekly_workload_cap,
                unavailable_slots=unavail,
                preferred_slots=preferred,
            ))

        # Rooms
        rooms_db = db.query(Room).filter(Room.department_id == department_id).all()
        rooms = [
            RoomInfo(
                id=str(r.id),
                name=r.name,
                type=r.type,
                capacity=r.capacity,
                capabilities=[c.capability for c in r.capabilities],
            )
            for r in rooms_db
        ]

        # Academic years scope
        ay_query = db.query(AcademicYear).filter(AcademicYear.department_id == department_id)
        if academic_year_ids:
            ay_query = ay_query.filter(AcademicYear.id.in_(academic_year_ids))
        academic_years = ay_query.all()
        ay_ids = [str(ay.id) for ay in academic_years]

        # Divisions
        divs_db = (
            db.query(Division)
            .filter(Division.academic_year_id.in_(ay_ids))
            .all()
        )
        batches_db = (
            db.query(Batch)
            .filter(Batch.division_id.in_([str(d.id) for d in divs_db]))
            .all()
        )
        batches_by_div = {}
        for b in batches_db:
            batches_by_div.setdefault(str(b.division_id), []).append(str(b.id))

        divisions = [
            DivisionInfo(
                id=str(d.id),
                name=d.name,
                academic_year_id=str(d.academic_year_id),
                strength=d.strength,
                batch_ids=batches_by_div.get(str(d.id), []),
            )
            for d in divs_db
        ]
        batches = [
            BatchInfo(
                id=str(b.id),
                name=b.name,
                division_id=str(b.division_id),
                capacity=b.capacity,
            )
            for b in batches_db
        ]

        # Teaching assignments and session requirements
        div_ids = [str(d.id) for d in divs_db]
        assignments_db = (
            db.query(TeachingAssignment)
            .filter(TeachingAssignment.division_id.in_(div_ids))
            .all()
        )
        assignments = []
        for a in assignments_db:
            req = (
                db.query(SessionRequirement)
                .filter(SessionRequirement.teaching_assignment_id == a.id)
                .first()
            )
            if req is None:
                # Default: 3 lectures of 1 hour each
                weekly_count = 3
                duration_slots = 1
            else:
                weekly_count = req.weekly_count
                duration_slots = req.duration_hours  # 1 or 2

            assignments.append(TeachingAssignmentInfo(
                id=str(a.id),
                subject_id=str(a.subject_id),
                division_id=str(a.division_id),
                teacher_id=str(a.teacher_id),
                session_type=a.session_type,
                batch_id=str(a.batch_id) if a.batch_id else None,
                enrollment_group_id=str(a.enrollment_group_id) if a.enrollment_group_id else None,
                weekly_count=weekly_count,
                duration_slots=duration_slots,
            ))

        return SchedulingInput(
            department_id=department_id,
            academic_year_ids=ay_ids,
            working_days=[
                WorkingDayInfo(
                    id=str(wd.id),
                    day_name=wd.day_name,
                    day_index=wd.day_index,
                    is_active=wd.is_active,
                )
                for wd in working_days
            ],
            time_slots=[
                TimeSlotInfo(
                    id=str(ts.id),
                    slot_code=ts.slot_code,
                    slot_index=ts.slot_index,
                    label=ts.label,
                )
                for ts in time_slots
            ],
            teachers=teachers,
            rooms=rooms,
            divisions=divisions,
            batches=batches,
            assignments=assignments,
        )

    @staticmethod
    def _slot_index(time_slot_id, time_slots) -> int:
        for ts in time_slots:
            if str(ts.id) == str(time_slot_id):
                return ts.slot_index
        return 0

