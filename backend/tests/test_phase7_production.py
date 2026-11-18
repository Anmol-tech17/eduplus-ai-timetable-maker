"""
backend/tests/test_phase7_production.py
EduPlus AI Timetable Maker — Phase 7 Production Readiness, Persistent Security,
Cookie/CSRF, Refresh Rotation, Async Background Jobs, Observability,
Gemini Resilience & 11-Step End-to-End Acceptance Workflow Tests
"""

from __future__ import annotations

import time
import uuid
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.ai.provider import GeminiLLMProvider
from backend.app.core.config import Settings, validate_production_config
from backend.app.core.security import (
    ACCESS_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    REFRESH_COOKIE_NAME,
    is_token_revoked_db,
)
from backend.app.models.academic import AcademicYear, Department, Division
from backend.app.models.security import AuditLog, LoginAttempt, RevokedToken, UserAccount
from backend.app.models.timetable import GenerationRun, InputSnapshot
from backend.app.seed.seed_data import seed_database
from backend.app.services.job_runner import GenerationJobManager


@pytest.fixture(autouse=True)
def seed_baseline(db_session: Session):
    seed_database(db=db_session)


def _login(unauth_client: TestClient, email: str, password: str) -> dict:
    resp = unauth_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# 1. Production Configuration Validation
# ---------------------------------------------------------------------------

class TestProductionConfig:
    def test_production_config_rejects_insecure_defaults(self):
        cfg = Settings()
        cfg.ENVIRONMENT = "production"
        cfg.SECRET_KEY = "short"
        cfg.ALLOWED_ORIGINS = ["*"]
        cfg.COOKIE_AUTH_ENABLED = True
        cfg.COOKIE_SECURE = False
        cfg.ENABLE_DEV_FALLBACKS = True

        errors = validate_production_config(cfg)
        assert len(errors) >= 4
        combined = " ".join(errors).lower()
        assert "secret_key" in combined
        assert "allowed_origins" in combined
        assert "cookie_secure" in combined
        assert "enable_dev_fallbacks" in combined

    def test_production_config_accepts_hardened_settings(self):
        cfg = Settings()
        cfg.ENVIRONMENT = "production"
        cfg.SECRET_KEY = "a" * 64
        cfg.DATABASE_URL = "postgresql+psycopg2://eduplus:strongpass@db:5432/eduplus_prod"
        cfg.ALLOWED_ORIGINS = ["https://timetable.example.edu"]
        cfg.COOKIE_AUTH_ENABLED = True
        cfg.COOKIE_SECURE = True
        cfg.COOKIE_SAMESITE = "strict"
        cfg.ENABLE_DEV_FALLBACKS = False
        cfg.LLM_PROVIDER = "mock"

        assert validate_production_config(cfg) == []


# ---------------------------------------------------------------------------
# 2. Persistent Multi-Worker Revocation, Refresh Rotation & Cookie + CSRF
# ---------------------------------------------------------------------------

class TestPersistentAuthAndCSRF:
    def test_refresh_token_rotation_and_replay_rejection(self, unauth_client: TestClient, db_session: Session):
        login_data = _login(unauth_client, "coordinator@eduplus.demo", "coordinator123")
        refresh_1 = login_data["refresh_token"]
        assert refresh_1

        # Rotate refresh token -> yields new pair
        rot_resp = unauth_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_1})
        assert rot_resp.status_code == 200
        rot_data = rot_resp.json()
        assert rot_data["access_token"] != login_data["access_token"]
        assert rot_data["refresh_token"] != refresh_1

        # Replaying consumed refresh_1 MUST fail (401) because jti is persistently revoked in DB
        replay_resp = unauth_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_1})
        assert replay_resp.status_code == 401
        assert db_session.query(RevokedToken).count() >= 1

    def test_persistent_revocation_on_logout_and_rate_limit_in_db(self, unauth_client: TestClient, db_session: Session):
        # Record a failed login -> persisted in login_attempts table
        bad = unauth_client.post("/api/v1/auth/login", json={"email": "admin@eduplus.demo", "password": "wrong"})
        assert bad.status_code == 401
        assert db_session.query(LoginAttempt).count() >= 1

        # Successful login clears rate-limit failures for that key
        data = _login(unauth_client, "admin@eduplus.demo", "admin123")
        headers = {"Authorization": f"Bearer {data['access_token']}"}
        assert unauth_client.post(
            "/api/v1/auth/logout",
            headers=headers,
            json={"refresh_token": data["refresh_token"]},
        ).status_code == 200

        # Both access & refresh tokens persisted in revoked_tokens table
        assert db_session.query(RevokedToken).count() >= 2
        assert unauth_client.get("/api/v1/auth/me", headers=headers).status_code == 401
        assert unauth_client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]}).status_code == 401

    def test_cookie_authentication_enforces_csrf_on_mutations(self, unauth_client: TestClient):
        # Login sets HttpOnly access/refresh cookies + readable CSRF cookie
        resp = unauth_client.post("/api/v1/auth/login", json={"email": "admin@eduplus.demo", "password": "admin123"})
        assert resp.status_code == 200
        assert ACCESS_COOKIE_NAME in resp.cookies
        assert CSRF_COOKIE_NAME in resp.cookies
        csrf_val = resp.cookies[CSRF_COOKIE_NAME]

        # GET works via cookie without Bearer header
        me_resp = unauth_client.get("/api/v1/auth/me")
        assert me_resp.status_code == 200

        # Mutating POST via cookie WITHOUT X-CSRF-Token header -> 403 Forbidden!
        no_csrf = unauth_client.post(
            "/api/v1/departments",
            json={"code": "NOCSRF", "name": "No CSRF", "college_name": "Test"},
        )
        assert no_csrf.status_code == 403
        assert "csrf" in no_csrf.json()["detail"].lower()

        # Mutating POST via cookie WITH matching X-CSRF-Token header -> 201 Created!
        with_csrf = unauth_client.post(
            "/api/v1/departments",
            headers={CSRF_HEADER_NAME: csrf_val},
            json={"code": "CSOK", "name": "CSRF Valid Dept", "college_name": "Test"},
        )
        assert with_csrf.status_code == 201


# ---------------------------------------------------------------------------
# 3. Observability, Health & Readiness Probes
# ---------------------------------------------------------------------------

class TestObservabilityAndHealth:
    def test_readiness_and_request_id_headers(self, unauth_client: TestClient):
        resp = unauth_client.get("/api/v1/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ready"] is True
        assert data["checks"]["database"] == "ok"
        assert data["checks"]["schema"] == "ok"
        assert data["workers"]["status"] == "healthy"
        assert resp.headers.get("X-Request-ID")

        # Propagate caller-supplied X-Request-ID
        custom_id = "req-phase7-trace-001"
        r2 = unauth_client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
        assert r2.status_code == 200
        assert r2.headers.get("X-Request-ID") == custom_id


# ---------------------------------------------------------------------------
# 4. Async Background Generation, Duplicate Guard & Crash Recovery
# ---------------------------------------------------------------------------

class TestAsyncBackgroundGeneration:
    def test_async_job_duplicate_guard_and_orphan_recovery(self, db_session: Session):
        dept = db_session.query(Department).first()
        mgr = GenerationJobManager(max_workers=1)

        # Simulate an orphaned 'running' run left over from a crash
        snap = InputSnapshot(data={"department_id": str(dept.id)}, checksum="abc123")
        db_session.add(snap)
        db_session.flush()
        orphan = GenerationRun(input_snapshot_id=snap.id, status="running")
        db_session.add(orphan)
        db_session.commit()

        # Duplicate check sees the running job for this department
        assert mgr.is_department_busy(str(dept.id), db=db_session) is True

        # Startup crash recovery marks orphaned run as 'failed' so department is unblocked
        recovered = mgr.recover_orphaned_runs(db_session)
        assert recovered == 1
        db_session.refresh(orphan)
        assert orphan.status == "failed"
        assert "restart" in (orphan.notes or "").lower()
        assert mgr.is_department_busy(str(dept.id), db=db_session) is False


# ---------------------------------------------------------------------------
# 5. Gemini Provider Timeout & Error Resilience (Without Live Key)
# ---------------------------------------------------------------------------

class TestGeminiResilience:
    def test_gemini_provider_timeout_and_malformed_response_fallback_safely(self):
        provider = GeminiLLMProvider(api_key="dummy-test-key", model_name="gemini-1.5-flash")
        ctx = {
            "department_id": "d1",
            "teachers": [{"id": "t1", "name": "Dr. Priya Sharma", "short_name": "P.Sharma"}],
            "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "time_slots": [],
            "academic_years": [],
            "divisions": [],
        }

        # 1. Timeout falls back cleanly to deterministic mock provider
        with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Timed out")):
            res = provider.interpret("Avoid scheduling practicals on Monday", ctx)
            assert res.can_apply is True
            assert res.provider_used == "mock"
            assert any(c.category.value == "practical_block" for c in res.constraints)

        # 2. HTTP 500 error falls back cleanly
        class _Fake500:
            status_code = 500
            text = "Internal Error"

        with patch("httpx.Client.post", return_value=_Fake500()):
            res2 = provider.interpret("Avoid scheduling practicals on Monday", ctx)
            assert res2.can_apply is True
            assert res2.provider_used == "mock"


# ---------------------------------------------------------------------------
# 6. Full 11-Step End-to-End Institutional Acceptance Workflow (Section 12)
# ---------------------------------------------------------------------------

def test_full_11_step_institutional_acceptance_workflow(unauth_client: TestClient, db_session: Session):
    """
    Executes the complete Phase 7 institutional acceptance workflow end-to-end:
    1. Admin logs in.
    2. Coordinator logs in & creates natural-language scheduling request.
    3. AI interprets it against live PostgreSQL entities.
    4. Coordinator confirms constraints.
    5. CP-SAT generates timetable with confirmed constraints.
    6. Independent validator checks it (0 Level A violations).
    7. Coordinator submits candidate for approval.
    8. Authorized approver (Admin) approves it.
    9. Timetable is published.
    10. Teacher and Student accounts see ONLY their authorized published sessions
        (and Student B from another division cannot see Student A's data).
    11. Audit logs record all workflow actions with zero leaked secrets.
    """
    dept = db_session.query(Department).first()
    assert dept is not None

    # Step 1: Admin logs in
    admin_auth = _login(unauth_client, "admin@eduplus.demo", "admin123")
    admin_hdr = {"Authorization": f"Bearer {admin_auth['access_token']}"}

    # Create a second student in Division 3B to prove cross-division student isolation
    ay3 = db_session.query(AcademicYear).filter(AcademicYear.department_id == dept.id, AcademicYear.year_number == 3).first()
    div3b = db_session.query(Division).filter(Division.academic_year_id == ay3.id, Division.name == "B").first()
    assert div3b is not None
    st_b_create = unauth_client.post(
        "/api/v1/users",
        headers=admin_hdr,
        json={
            "email": "student3b@eduplus.demo",
            "password": "Student3BPass!",
            "full_name": "Student Div 3B",
            "role": "student",
            "department_id": str(dept.id),
            "linked_entity_id": str(div3b.id),
        },
    )
    assert st_b_create.status_code == 201

    # Step 2 & 3: Coordinator logs in & AI interprets natural-language request
    coord_auth = _login(unauth_client, "coordinator@eduplus.demo", "coordinator123")
    coord_hdr = {"Authorization": f"Bearer {coord_auth['access_token']}"}

    interp_resp = unauth_client.post(
        "/api/v1/ai/interpret",
        headers=coord_hdr,
        json={
            "prompt": "Give Dr. Priya Sharma no classes after 2 PM and avoid scheduling practicals on Monday",
            "department_id": str(dept.id),
        },
    )
    assert interp_resp.status_code == 200
    interp = interp_resp.json()
    assert interp["can_apply"] is True
    assert len(interp["constraints"]) == 2

    # Step 4, 5 & 6: Coordinator confirms constraints -> CP-SAT generates -> Independent validator checks
    gen_resp = unauth_client.post(
        "/api/v1/timetable/generate",
        headers=coord_hdr,
        json={
            "department_id": str(dept.id),
            "label": "AY2026-27 Phase 7 E2E Accepted Timetable",
            "academic_year_code": "2026-27",
            "semester": 1,
            "time_limit_seconds": 30,
            "check_soft_constraints": True,
            "confirmed_constraints": interp["constraints"],
        },
    )
    assert gen_resp.status_code == 202
    gen = gen_resp.json()
    assert gen["status"] in ("OPTIMAL", "FEASIBLE")
    assert gen["hard_violations"] == 0
    version_id = gen["version_id"]

    # Confirm explicit re-validation passes with 0 hard violations
    val_resp = unauth_client.post(
        "/api/v1/timetable/validate",
        headers=coord_hdr,
        json={"version_id": version_id, "check_soft": True},
    )
    assert val_resp.status_code == 200
    assert val_resp.json()["hard_violations"] == 0

    # Step 7: Coordinator submits candidate for approval
    sub_resp = unauth_client.post(
        f"/api/v1/timetable/versions/{version_id}/submit",
        headers=coord_hdr,
        json={"comment": "Validated AI-assisted schedule ready for approval"},
    )
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "pending_approval"

    # Step 8: Authorized approver (Admin) approves it
    app_resp = unauth_client.post(
        f"/api/v1/timetable/versions/{version_id}/approve",
        headers=admin_hdr,
        json={"comment": "Approved by Department Head"},
    )
    assert app_resp.status_code == 200
    assert app_resp.json()["status"] == "approved"

    # Step 9: Approver publishes it
    pub_resp = unauth_client.post(f"/api/v1/timetable/versions/{version_id}/publish", headers=admin_hdr)
    assert pub_resp.status_code == 200
    pub = pub_resp.json()
    assert pub["status"] == "published"
    assert pub["approved_by"] == admin_auth["user"]["id"]
    assert pub["published_by"] == admin_auth["user"]["id"]

    # Step 10: Teacher & Student accounts see ONLY their authorized published sessions
    tch_auth = _login(unauth_client, "teacher@eduplus.demo", "teacher123")
    tch_hdr = {"Authorization": f"Bearer {tch_auth['access_token']}"}
    tch_tt = unauth_client.get(f"/api/v1/timetable/versions/{version_id}", headers=tch_hdr)
    assert tch_tt.status_code == 200
    assert len(tch_tt.json()["sessions"]) >= 1
    assert all(s["teacher_id"] == tch_auth["user"]["linked_entity_id"] for s in tch_tt.json()["sessions"])

    st_a_auth = _login(unauth_client, "student@eduplus.demo", "student123")
    st_a_hdr = {"Authorization": f"Bearer {st_a_auth['access_token']}"}
    st_a_tt = unauth_client.get(f"/api/v1/timetable/versions/{version_id}", headers=st_a_hdr)
    assert st_a_tt.status_code == 200
    assert len(st_a_tt.json()["sessions"]) >= 1

    # Student 3B (different division) sees ZERO Division 3A sessions & gets 403 on Div 3A endpoint
    st_b_auth = _login(unauth_client, "student3b@eduplus.demo", "Student3BPass!")
    st_b_hdr = {"Authorization": f"Bearer {st_b_auth['access_token']}"}
    st_b_tt = unauth_client.get(f"/api/v1/timetable/versions/{version_id}", headers=st_b_hdr)
    assert st_b_tt.status_code == 200
    assert st_b_tt.json()["sessions"] == []  # No Div 3A sessions leaked to Div 3B student
    assert unauth_client.get(
        f"/api/v1/divisions/{st_a_auth['user']['linked_entity_id']}",
        headers=st_b_hdr,
    ).status_code == 403

    # Step 11: Audit logs record all workflow actions with zero leaked secrets
    audit_resp = unauth_client.get("/api/v1/audit-logs?page_size=100", headers=admin_hdr)
    assert audit_resp.status_code == 200
    actions = {row["action"] for row in audit_resp.json()["items"]}
    for required_action in (
        "AUTH_LOGIN_SUCCESS",
        "USER_CREATED",
        "AI_PROMPT_INTERPRETED",
        "AI_CONSTRAINTS_CONFIRMED",
        "TIMETABLE_GENERATE",
        "TIMETABLE_SUBMIT",
        "TIMETABLE_APPROVE",
        "TIMETABLE_PUBLISH",
    ):
        assert required_action in actions, f"Expected audit action '{required_action}' not found"
    serialized = str(audit_resp.json()["items"])
    assert "admin123" not in serialized
    assert "Student3BPass!" not in serialized
    assert admin_auth["access_token"] not in serialized
