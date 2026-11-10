"""
backend/tests/test_ai_assistant.py
EduPlus AI Timetable Maker — Automated Tests for Phase 5 AI Assistant

Tests:
- AI status endpoint (/api/v1/ai/status)
- Natural language prompt interpretation (/api/v1/ai/interpret)
  - Teacher unavailability after 2 PM
  - Practical block on Monday
  - Morning preferences
  - Idle gap minimization
  - Ambiguous / unknown faculty clarification
  - Unsupported institutional policies
- Grounded explanation endpoint (/api/v1/ai/explain)
  - Generation run explanation
  - Version comparison explanation
  - Validator violations explanation
- End-to-end integration: Confirmed constraints applied to CP-SAT solver & validator
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.models.academic import Department
from backend.app.models.faculty import Teacher
from backend.app.models.timetable import TimetableVersion
from backend.app.seed.seed_data import seed_database


@pytest.fixture(autouse=True)
def seed_test_db(db_session: Session):
    """Seed baseline AIML department data for AI assistant tests."""
    seed_database(db=db_session)


def test_ai_status_endpoint(client: TestClient):
    """Verify /api/v1/ai/status reports active provider and capabilities."""
    res = client.get("/api/v1/ai/status")
    assert res.status_code == 200
    data = res.json()
    assert "provider" in data
    assert data["is_available"] is True
    assert len(data["supported_constraints"]) >= 4
    assert len(data["capabilities"]) >= 4


def test_ai_interpret_teacher_unavailability(client: TestClient, db_session: Session):
    """Test interpreting 'Give Dr. Priya Sharma no classes after 2 PM'."""
    dept = db_session.query(Department).first()
    teacher = db_session.query(Teacher).filter(Teacher.name.like("%Priya%")).first()

    payload = {
        "prompt": "Give Dr. Priya Sharma no classes after 2 PM",
        "department_id": str(dept.id) if dept else None,
    }
    res = client.post("/api/v1/ai/interpret", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["can_apply"] is True
    assert len(data["constraints"]) >= 1
    c = data["constraints"][0]
    assert c["category"] == "teacher_unavailability"
    assert c["level"] == "HARD"
    assert c["target_type"] == "teacher"
    if teacher:
        assert c["target_id"] == str(teacher.id)
    assert 7 in c["slot_indices"]
    assert 10 in c["slot_indices"]


def test_ai_interpret_practical_block(client: TestClient, db_session: Session):
    """Test interpreting 'Avoid scheduling practicals on Monday'."""
    dept = db_session.query(Department).first()
    payload = {
        "prompt": "Avoid scheduling practicals on Monday",
        "department_id": str(dept.id) if dept else None,
    }
    res = client.post("/api/v1/ai/interpret", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["can_apply"] is True
    assert len(data["constraints"]) >= 1
    c = data["constraints"][0]
    assert c["category"] == "practical_block"
    assert c["level"] == "HARD"
    assert "Monday" in c["day_names"]
    assert c["is_supported"] is True


def test_ai_interpret_soft_preferences(client: TestClient, db_session: Session):
    """Test interpreting soft preferences (morning slots and gap minimization)."""
    dept = db_session.query(Department).first()
    payload = {
        "prompt": "Prefer morning slots and minimize idle gaps between lectures",
        "department_id": str(dept.id) if dept else None,
    }
    res = client.post("/api/v1/ai/interpret", json=payload)
    assert res.status_code == 200
    data = res.json()

    categories = [c["category"] for c in data["constraints"]]
    assert "teacher_preference" in categories or "division_preference" in categories
    assert "gap_minimization" in categories
    # Soft constraints
    for c in data["constraints"]:
        assert c["level"] == "SOFT"


def test_ai_interpret_ambiguous_unknown_entity(client: TestClient, db_session: Session):
    """Test prompt referencing unknown teacher flags ambiguity and requests clarification."""
    dept = db_session.query(Department).first()
    payload = {
        "prompt": "Give Prof. Charles Xavier no classes on Monday",
        "department_id": str(dept.id) if dept else None,
    }
    res = client.post("/api/v1/ai/interpret", json=payload)
    assert res.status_code == 200
    data = res.json()

    # Must be ambiguous and not auto-applicable
    assert data["can_apply"] is False
    assert len(data["clarifications"]) >= 1
    clarification = data["clarifications"][0]
    assert "Charles Xavier" in clarification["message"]
    assert len(clarification["options"]) > 0

    ambiguous_constraints = [c for c in data["constraints"] if c["is_ambiguous"]]
    assert len(ambiguous_constraints) >= 1
    assert ambiguous_constraints[0]["target_id"] is None


def test_ai_interpret_unsupported_request(client: TestClient, db_session: Session):
    """Test prompt with non-scheduling request is marked unsupported with rationale."""
    dept = db_session.query(Department).first()
    payload = {
        "prompt": "Allow faculty to work from home on Friday and provide free lunch",
        "department_id": str(dept.id) if dept else None,
    }
    res = client.post("/api/v1/ai/interpret", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["can_apply"] is False
    unsupported = [c for c in data["constraints"] if not c["is_supported"]]
    assert len(unsupported) >= 1
    assert "institutional" in unsupported[0]["support_rationale"].lower() or "outside" in unsupported[0]["support_rationale"].lower()


def test_ai_explain_generation(client: TestClient, db_session: Session):
    """Test AI explanation for generation outcome."""
    payload = {
        "explanation_type": "generation",
        "payload": {
            "status": "OPTIMAL",
            "solver_time_ms": 1420,
            "objective_value": 248.5,
            "total_sessions": 30,
            "hard_violations": 0,
            "soft_violations": 2,
            "label": "Test Candidate V1",
        },
    }
    res = client.post("/api/v1/ai/explain", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "summary_markdown" in data
    assert len(data["key_insights"]) >= 2
    assert len(data["actionable_recommendations"]) >= 1
    assert "OPTIMAL" in data["summary_markdown"]


def test_ai_explain_comparison(client: TestClient, db_session: Session):
    """Test AI explanation for version comparison diff."""
    v_a = db_session.query(TimetableVersion).first()
    v_b = db_session.query(TimetableVersion).order_by(TimetableVersion.version_number.desc()).first()

    if v_a and v_b and v_a.id != v_b.id:
        payload = {
            "explanation_type": "comparison",
            "version_a_id": str(v_a.id),
            "version_b_id": str(v_b.id),
        }
        res = client.post("/api/v1/ai/explain", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "summary_markdown" in data
        assert len(data["key_insights"]) >= 1
    else:
        # Fallback payload test
        payload = {
            "explanation_type": "comparison",
            "payload": {
                "total_sessions_a": 30,
                "total_sessions_b": 30,
                "added": 0,
                "removed": 0,
                "moved": 3,
                "unchanged": 27,
            },
        }
        res = client.post("/api/v1/ai/explain", json=payload)
        assert res.status_code == 200


def test_ai_confirmed_constraints_enforcement(client: TestClient, db_session: Session):
    """
    End-to-End Test:
    1. Interpret 'Give Dr. Priya Sharma no classes after 2 PM and avoid practicals on Monday'.
    2. Confirm constraints and pass to /timetable/generate.
    3. Verify CP-SAT solver satisfies constraints:
       - No sessions scheduled for Dr. Priya Sharma in slots 7..10.
       - No practical sessions scheduled on Monday.
       - Independent validator reports 0 A08 / A11 violations!
    """
    dept = db_session.query(Department).first()
    assert dept is not None, "Department must exist in test database"

    interpret_res = client.post(
        "/api/v1/ai/interpret",
        json={
            "prompt": "Give Dr. Priya Sharma no classes after 2 PM and avoid practicals on Monday",
            "department_id": str(dept.id),
        },
    )
    assert interpret_res.status_code == 200
    interp_data = interpret_res.json()
    assert interp_data["can_apply"] is True

    # Pass confirmed constraints to generator
    gen_payload = {
        "department_id": str(dept.id),
        "label": "AI Guided Candidate AY26-27",
        "academic_year_code": "2026-27",
        "semester": 1,
        "time_limit_seconds": 30,
        "check_soft_constraints": True,
        "confirmed_constraints": interp_data["constraints"],
    }

    gen_res = client.post("/api/v1/timetable/generate", json=gen_payload)
    assert gen_res.status_code == 202
    gen_data = gen_res.json()
    assert gen_data["status"] in ("OPTIMAL", "FEASIBLE")

    sessions = gen_data["sessions"]
    priya_teacher = db_session.query(Teacher).filter(Teacher.name.like("%Priya%")).first()

    if priya_teacher:
        priya_id = str(priya_teacher.id)
        # Verify no sessions scheduled for Priya after 2 PM (slots 7..10)
        priya_afternoon_sessions = [
            s for s in sessions
            if s["teacher_id"] == priya_id and s["slot_index"] in [7, 8, 9, 10]
        ]
        assert len(priya_afternoon_sessions) == 0, f"Found {len(priya_afternoon_sessions)} sessions for Priya after 2 PM"

    # Verify no practical sessions scheduled on Monday
    monday_practicals = [
        s for s in sessions
        if s["session_type"] == "practical" and s["day_name"] == "Monday"
    ]
    assert len(monday_practicals) == 0, f"Found {len(monday_practicals)} practical sessions on Monday"

    # Verify zero hard violations in validation output
    assert gen_data["hard_violations"] == 0
