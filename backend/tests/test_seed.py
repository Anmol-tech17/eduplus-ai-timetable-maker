"""
backend/tests/test_seed.py
EduPlus AI Timetable Maker — Database Seed Process Tests
"""

from backend.app.seed.seed_data import seed_database
from backend.app.models.academic import Department, Subject, Division
from backend.app.models.faculty import Teacher
from backend.app.models.room import Room


def test_seed_execution_and_idempotency(db_session):
    """Verifies that seed_database populates the baseline and running it again causes 0 duplicates."""
    # First execution
    stats1 = seed_database(db=db_session)
    assert isinstance(stats1, dict)

    # Verify AIML Department and core data exist
    dept = db_session.query(Department).filter(Department.code == "AIML").first()
    assert dept is not None
    assert dept.name == "Artificial Intelligence & Machine Learning"

    # Verify subjects count >= 7
    subjects_count = db_session.query(Subject).filter(Subject.department_id == dept.id).count()
    assert subjects_count >= 7

    # Verify teachers count >= 12
    teachers_count = db_session.query(Teacher).filter(Teacher.department_id == dept.id).count()
    assert teachers_count >= 12

    # Verify rooms count >= 17
    rooms_count = db_session.query(Room).filter(Room.department_id == dept.id).count()
    assert rooms_count >= 17

    # Second execution must insert 0 new records (idempotent)
    stats2 = seed_database(db=db_session)
    assert stats2["departments"] == 0
    assert stats2["teachers"] == 0
    assert stats2["subjects"] == 0
    assert stats2["rooms"] == 0
    assert stats2["users"] == 0
