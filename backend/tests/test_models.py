"""
backend/tests/test_models.py
EduPlus AI Timetable Maker — Database Model Integrity Tests
"""

import pytest
from sqlalchemy.exc import IntegrityError
from backend.app.models.academic import Department, AcademicYear, Division, Batch, Subject
from backend.app.models.room import Room
from backend.app.models.faculty import Teacher
from backend.app.core.security import get_password_hash, verify_password


def test_department_unique_code_constraint(db_session):
    """Verifies that duplicate department codes raise IntegrityError."""
    d1 = Department(code="CS", name="Computer Science", college_name="Test College")
    db_session.add(d1)
    db_session.flush()

    d2 = Department(code="CS", name="Duplicate CS", college_name="Test College")
    db_session.add(d2)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_academic_hierarchy_relationships(db_session):
    """Verifies relationship cascade from Department -> AcademicYear -> Division -> Batch."""
    dept = Department(code="IT", name="Information Technology", college_name="Engineering College")
    db_session.add(dept)
    db_session.flush()

    ay = AcademicYear(department_id=dept.id, year_number=3, label="Third Year")
    db_session.add(ay)
    db_session.flush()

    room = Room(department_id=dept.id, name="LH-301", type="classroom", capacity=65, floor=3)
    db_session.add(room)
    db_session.flush()

    div = Division(academic_year_id=ay.id, name="A", strength=55, home_room_id=room.id)
    db_session.add(div)
    db_session.flush()

    batch = Batch(division_id=div.id, name="B1", capacity=20)
    db_session.add(batch)
    db_session.flush()

    assert batch.division.name == "A"
    assert batch.division.academic_year.year_number == 3
    assert batch.division.academic_year.department.code == "IT"
    assert batch.division.home_room.name == "LH-301"


def test_password_hashing():
    """Verifies secure password hashing and verification."""
    password = "secret_password_123"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False
