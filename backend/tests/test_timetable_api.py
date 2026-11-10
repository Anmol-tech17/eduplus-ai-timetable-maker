"""
backend/tests/test_timetable_api.py
EduPlus AI Timetable Maker — Phase 3 API Integration Tests

Tests for:
- POST /api/v1/timetable/generate
- POST /api/v1/timetable/validate
- GET  /api/v1/timetable/versions
- GET  /api/v1/timetable/versions/{id}
- GET  /api/v1/timetable/compare
- POST /api/v1/timetable/repair
- GET  /api/v1/timetable/runs/{id}
- Existing Phase 0/1 endpoints still functional
"""

from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.seed.seed_data import seed_database
from backend.app.models.scheduling import TeachingAssignment, SessionRequirement
from backend.app.models.timetable import TimetableVersion, ScheduledSession, GenerationRun


# ---------------------------------------------------------------------------
# Fixture — seed baseline AIML data for every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def seed_test_db(db_session: Session):
    """Seed baseline AIML department data for timetable API tests."""
    seed_database(db=db_session)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_dept_id(client: TestClient) -> str:
    resp = client.get("/api/v1/departments")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items, "No departments found in test DB"
    return items[0]["id"]


def _get_academic_year_id(client: TestClient, dept_id: str) -> str:
    resp = client.get(f"/api/v1/academic-years?department_id={dept_id}")
    assert resp.status_code == 200
    items = resp.json()
    assert items, "No academic years found in test DB"
    return items[0]["id"]


def _ensure_teaching_assignments(
    db_session: Session, dept_id: str, div_id: str, teacher_id: str, subject_id: str
) -> str:
    """Create one lecture assignment with 1 session/week if it doesn't exist."""
    existing = (
        db_session.query(TeachingAssignment)
        .filter(TeachingAssignment.division_id == div_id)
        .first()
    )
    if existing:
        return str(existing.id)

    ta = TeachingAssignment(
        id=uuid.uuid4(),
        subject_id=subject_id,
        division_id=div_id,
        teacher_id=teacher_id,
        session_type="lecture",
        batch_id=None,
        enrollment_group_id=None,
    )
    db_session.add(ta)
    db_session.flush()

    req = SessionRequirement(
        id=uuid.uuid4(),
        teaching_assignment_id=ta.id,
        weekly_count=1,
        duration_hours=1,
    )
    db_session.add(req)
    db_session.commit()
    return str(ta.id)


def _generate_test_version(client: TestClient, db_session: Session) -> dict:
    """Helper to generate a real timetable version for test DB."""
    dept_id = _get_dept_id(client)
    ay_id = _get_academic_year_id(client, dept_id)

    resp_div = client.get(f"/api/v1/divisions?academic_year_id={ay_id}")
    div_id = resp_div.json()[0]["id"]

    resp_tea = client.get("/api/v1/teachers")
    teacher_id = resp_tea.json()["items"][0]["id"]

    resp_sub = client.get("/api/v1/subjects")
    subject_id = resp_sub.json()[0]["id"]

    _ensure_teaching_assignments(db_session, dept_id, div_id, teacher_id, subject_id)

    resp = client.post("/api/v1/timetable/generate", json={
        "department_id": dept_id,
        "academic_year_ids": [ay_id],
        "label": "Test Fixture Version",
        "time_limit_seconds": 15,
        "check_soft_constraints": True,
    })
    assert resp.status_code == 202
    return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHealthAndCRUDStillWork:
    """Phase 0/1 endpoints must remain functional after Phase 2/3 changes."""

    def test_health_endpoint(self, client: TestClient):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"

    def test_departments_list(self, client: TestClient):
        resp = client.get("/api/v1/departments")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["pagination"]["total_records"] >= 1

    def test_academic_years_list(self, client: TestClient):
        resp = client.get("/api/v1/academic-years")
        assert resp.status_code == 200

    def test_teachers_list(self, client: TestClient):
        resp = client.get("/api/v1/teachers")
        assert resp.status_code == 200


class TestGenerationEndpoint:
    """Tests for POST /api/v1/timetable/generate."""

    def test_generate_requires_assignments(self, client: TestClient):
        """Generation with no teaching assignments returns 422."""
        dept_id = _get_dept_id(client)
        resp = client.post("/api/v1/timetable/generate", json={
            "department_id": dept_id,
            "label": "Test — no assignments",
            "time_limit_seconds": 10,
        })
        assert resp.status_code in (422, 202)

    def test_generate_with_seed_data_returns_result(self, client: TestClient, db_session: Session):
        """Generate a timetable using seeded data with created teaching assignments."""
        data = _generate_test_version(client, db_session)
        assert data["status"] in ("OPTIMAL", "FEASIBLE")
        assert data["version_id"] is not None
        assert data["solver_time_ms"] >= 0
        assert data["total_sessions"] >= 1
        assert data["hard_violations"] == 0

    def test_generate_persists_version(self, client: TestClient, db_session: Session):
        """A successful generation creates a TimetableVersion in the database."""
        data = _generate_test_version(client, db_session)
        version_id = data.get("version_id")
        assert version_id is not None

        # Verify version exists in DB
        version = db_session.query(TimetableVersion).filter(
            TimetableVersion.id == uuid.UUID(version_id)
        ).first()
        assert version is not None
        assert version.status in ("draft", "candidate")

        # Verify sessions persisted in DB
        sessions_count = db_session.query(ScheduledSession).filter(
            ScheduledSession.timetable_version_id == uuid.UUID(version_id)
        ).count()
        assert sessions_count >= 1

    def test_generate_invalid_department(self, client: TestClient):
        """Generation with non-existent department returns 400 or 422."""
        resp = client.post("/api/v1/timetable/generate", json={
            "department_id": str(uuid.uuid4()),
            "label": "Bad dept",
            "time_limit_seconds": 5,
        })
        assert resp.status_code in (400, 422)


class TestVersionsEndpoint:
    """Tests for GET /api/v1/timetable/versions and /versions/{id}."""

    def test_list_versions_returns_200(self, client: TestClient):
        resp = client.get("/api/v1/timetable/versions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_versions_filter_by_department(self, client: TestClient, db_session: Session):
        dept_id = _get_dept_id(client)
        _generate_test_version(client, db_session)

        resp = client.get(f"/api/v1/timetable/versions?department_id={dept_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        for item in data:
            assert item["department_id"] == dept_id

    def test_get_version_not_found(self, client: TestClient):
        resp = client.get(f"/api/v1/timetable/versions/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_get_version_detail_has_sessions(self, client: TestClient, db_session: Session):
        """Generated version detail endpoint includes sessions and violations."""
        gen_data = _generate_test_version(client, db_session)
        version_id = gen_data["version_id"]

        resp = client.get(f"/api/v1/timetable/versions/{version_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert "violations" in data
        assert isinstance(data["sessions"], list)
        assert len(data["sessions"]) >= 1


class TestCompareEndpoint:
    """Tests for GET /api/v1/timetable/compare."""

    def test_compare_nonexistent_versions(self, client: TestClient):
        resp = client.get(
            f"/api/v1/timetable/compare?version_a={uuid.uuid4()}&version_b={uuid.uuid4()}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sessions_a"] == 0
        assert data["total_sessions_b"] == 0

    def test_compare_real_versions(self, client: TestClient, db_session: Session):
        v1 = _generate_test_version(client, db_session)
        v2 = _generate_test_version(client, db_session)

        resp = client.get(
            f"/api/v1/timetable/compare?version_a={v1['version_id']}&version_b={v2['version_id']}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sessions_a"] >= 1
        assert data["total_sessions_b"] >= 1
        assert "diffs" in data


class TestValidateEndpoint:
    """Tests for POST /api/v1/timetable/validate."""

    def test_validate_nonexistent_version(self, client: TestClient):
        resp = client.post("/api/v1/timetable/validate", json={
            "version_id": str(uuid.uuid4()),
            "check_soft": True,
        })
        assert resp.status_code == 404

    def test_validate_existing_version(self, client: TestClient, db_session: Session):
        gen_data = _generate_test_version(client, db_session)
        version_id = gen_data["version_id"]

        resp = client.post("/api/v1/timetable/validate", json={
            "version_id": version_id,
            "check_soft": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "REVALIDATED"
        assert data["hard_violations"] == 0
        assert data["total_sessions"] >= 1


class TestRepairEndpoint:
    """Tests for POST /api/v1/timetable/repair."""

    def test_repair_nonexistent_version(self, client: TestClient):
        resp = client.post("/api/v1/timetable/repair", json={
            "source_version_id": str(uuid.uuid4()),
            "label": "Repair test",
            "time_limit_seconds": 10,
        })
        assert resp.status_code == 404

    def test_repair_real_version(self, client: TestClient, db_session: Session):
        gen_data = _generate_test_version(client, db_session)
        version_id = gen_data["version_id"]

        resp = client.post("/api/v1/timetable/repair", json={
            "source_version_id": version_id,
            "label": "Repaired Version v2",
            "time_limit_seconds": 15,
        })
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] in ("OPTIMAL", "FEASIBLE")
        assert data["version_id"] is not None
        assert data["total_sessions"] >= 1


class TestGenerationRunEndpoint:
    """Tests for GET /api/v1/timetable/runs/{id}."""

    def test_run_not_found(self, client: TestClient):
        resp = client.get(f"/api/v1/timetable/runs/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_get_generation_run_success(self, client: TestClient, db_session: Session):
        gen_data = _generate_test_version(client, db_session)
        version_id = gen_data["version_id"]

        version = db_session.query(TimetableVersion).filter(
            TimetableVersion.id == uuid.UUID(version_id)
        ).first()
        assert version.generation_run_id is not None

        resp = client.get(f"/api/v1/timetable/runs/{version.generation_run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["solver_status"] in ("OPTIMAL", "FEASIBLE")
        assert data["solver_time_ms"] >= 0
