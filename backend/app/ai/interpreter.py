"""
backend/app/ai/interpreter.py
EduPlus AI Timetable Maker — Database-Grounded Natural Language Constraint Interpreter

Gounds user scheduling instructions against active PostgreSQL entities
(Teachers, Working Days, Time Slots, Academic Years, Divisions) before
invoking the LLM provider. Ensures zero entity hallucinations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.app.ai.provider import get_llm_provider
from backend.app.ai.schemas import (
    InterpretationResponse,
)
from backend.app.models.academic import AcademicYear, Department, Division, Subject
from backend.app.models.faculty import Teacher
from backend.app.models.room import Room
from backend.app.models.scheduling import TimeSlot, WorkingDay

logger = logging.getLogger("eduplus.ai.interpreter")


def build_grounding_context(
    db: Session,
    department_id: Optional[str] = None,
    academic_year_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract live institutional data from DB to ground LLM interpretation."""
    dept = None
    if department_id:
        dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        dept = db.query(Department).first()

    dept_id_str = str(dept.id) if dept else None

    # Teachers
    teacher_query = db.query(Teacher)
    if dept_id_str:
        teacher_query = teacher_query.filter(Teacher.department_id == dept_id_str)
    teachers_db = teacher_query.all()
    teachers = [
        {"id": str(t.id), "name": t.name, "short_name": t.short_name}
        for t in teachers_db
    ]

    # Time slots
    time_slots_db = db.query(TimeSlot).order_by(TimeSlot.slot_index).all()
    time_slots = [
        {"slot_index": ts.slot_index, "slot_code": ts.slot_code, "label": ts.label}
        for ts in time_slots_db
    ]

    # Working days
    working_days_query = db.query(WorkingDay)
    if dept_id_str:
        working_days_query = working_days_query.filter(WorkingDay.department_id == dept_id_str)
    working_days_db = working_days_query.order_by(WorkingDay.day_index).all()
    working_days = [wd.day_name for wd in working_days_db if wd.is_active] or [
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"
    ]

    # Academic years
    ay_query = db.query(AcademicYear)
    if dept_id_str:
        ay_query = ay_query.filter(AcademicYear.department_id == dept_id_str)
    academic_years_db = ay_query.all()
    academic_years = [
        {"id": str(ay.id), "year_number": ay.year_number, "label": ay.label}
        for ay in academic_years_db
    ]

    # Divisions
    div_query = db.query(Division)
    if academic_year_id:
        div_query = div_query.filter(Division.academic_year_id == academic_year_id)
    divisions_db = div_query.all()
    divisions = [{"id": str(d.id), "name": d.name} for d in divisions_db]

    # Rooms
    room_query = db.query(Room)
    if dept_id_str:
        room_query = room_query.filter(Room.department_id == dept_id_str)
    rooms_db = room_query.all()
    rooms = [{"id": str(r.id), "name": r.name, "type": r.type} for r in rooms_db]

    # Subjects
    subj_query = db.query(Subject)
    if dept_id_str:
        subj_query = subj_query.filter(Subject.department_id == dept_id_str)
    subjects_db = subj_query.all()
    subjects = [{"id": str(s.id), "name": s.name, "code": s.code} for s in subjects_db]

    return {
        "department_id": dept_id_str,
        "department_name": dept.name if dept else None,
        "teachers": teachers,
        "time_slots": time_slots,
        "working_days": working_days,
        "academic_years": academic_years,
        "divisions": divisions,
        "rooms": rooms,
        "subjects": subjects,
    }


def interpret_prompt(
    prompt: str,
    db: Session,
    department_id: Optional[str] = None,
    academic_year_id: Optional[str] = None,
) -> InterpretationResponse:
    """
    Primary API function to interpret a natural-language scheduling prompt.
    1. Builds grounded context from live database.
    2. Invokes configured LLM provider (Mock or Gemini).
    3. Performs entity validation and returns verified InterpretationResponse.
    """
    context = build_grounding_context(db, department_id, academic_year_id)
    provider = get_llm_provider()
    logger.info(f"Interpreting prompt with provider '{provider.name}': {prompt[:80]}...")

    response = provider.interpret(prompt, context)

    # Post-validation: ensure all identified target_ids actually exist in the DB context
    known_teacher_ids = {t["id"] for t in context["teachers"]}
    for c in response.constraints:
        if c.target_type == "teacher" and c.target_id:
            if c.target_id not in known_teacher_ids:
                c.is_ambiguous = True
                c.clarification_needed = f"Teacher ID {c.target_id} does not match an active teacher."
                response.can_apply = False

    return response
