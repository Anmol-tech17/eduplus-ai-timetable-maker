"""
backend/tests/test_auth_rbac.py
EduPlus AI Timetable Maker — Phase 6 Authentication, RBAC, Isolation,
Approval Workflow, Audit Logging, and Security Tests
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from backend.app.models.academic import AcademicYear, Department, Division
from backend.app.models.faculty import Teacher
from backend.app.models.security import AuditLog, UserAccount
from backend.app.models.timetable import TimetableVersion, Violation
from backend.app.seed.seed_data import seed_database


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def seed_baseline(db_session: Session):
    """Seed baseline AIML institution and all 4 role accounts."""
    seed_database(db=db_session)


def _login(unauth_client: TestClient, email: str, password: str) -> dict:
    resp = unauth_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    return resp.json()


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _generate_candidate(unauth_client: TestClient, headers: dict, dept_id: str, label: str = "Phase 6 Candidate") -> dict:
    resp = unauth_client.post(
        "/api/v1/timetable/generate",
        headers=headers,
        json={
            "department_id": dept_id,
            "label": label,
            "academic_year_code": "2026-27",
            "semester": 1,
            "time_limit_seconds": 20,
            "check_soft_constraints": True,
        },
    )
    assert resp.status_code == 202, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# 1. Authentication & Token Security Tests
# ---------------------------------------------------------------------------

class TestAuthentication:
    def test_password_hashing_salted_and_non_plaintext(self):
        raw = "SuperSecret#2026"
        h1 = get_password_hash(raw)
        h2 = get_password_hash(raw)
        assert h1 != raw
        assert h1 != h2  # unique salt per hash
        assert verify_password(raw, h1) is True
        assert verify_password("WrongPassword", h1) is False

    def test_login_success_all_four_roles(self, unauth_client: TestClient):
        for email, pwd, expected_role in [
            ("admin@eduplus.demo", "admin123", "admin"),
            ("coordinator@eduplus.demo", "coordinator123", "coordinator"),
            ("teacher@eduplus.demo", "teacher123", "teacher"),
            ("student@eduplus.demo", "student123", "student"),
        ]:
            data = _login(unauth_client, email, pwd)
            assert data["token_type"] == "bearer"
            assert data["access_token"]
            assert data["expires_in"] > 0
            assert data["user"]["role"] == expected_role
            assert "password_hash" not in data["user"]

            me_resp = unauth_client.get("/api/v1/auth/me", headers=_auth_header(data["access_token"]))
            assert me_resp.status_code == 200
            assert me_resp.json()["email"] == email

    def test_login_invalid_credentials_rejected(self, unauth_client: TestClient):
        resp = unauth_client.post(
            "/api/v1/auth/login",
            json={"email": "admin@eduplus.demo", "password": "wrongpassword"},
        )
        assert resp.status_code == 401
        assert "invalid" in resp.json()["detail"].lower()

        resp2 = unauth_client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@eduplus.demo", "password": "somepassword"},
        )
        assert resp2.status_code == 401

    def test_inactive_user_cannot_login_or_access_api(self, unauth_client: TestClient, db_session: Session):
        user = db_session.query(UserAccount).filter(UserAccount.email == "teacher@eduplus.demo").first()
        assert user is not None
        # Obtain token while active, then deactivate
        token = _login(unauth_client, "teacher@eduplus.demo", "teacher123")["access_token"]
        user.is_active = False
        db_session.commit()

        # Existing token rejected
        me_resp = unauth_client.get("/api/v1/auth/me", headers=_auth_header(token))
        assert me_resp.status_code == 403

        # Fresh login rejected
        login_resp = unauth_client.post(
            "/api/v1/auth/login",
            json={"email": "teacher@eduplus.demo", "password": "teacher123"},
        )
        assert login_resp.status_code == 403

    def test_unauthenticated_requests_rejected_401(self, unauth_client: TestClient):
        protected_paths = [
            ("GET", "/api/v1/auth/me"),
            ("GET", "/api/v1/departments"),
            ("GET", "/api/v1/teachers"),
            ("GET", "/api/v1/rooms"),
            ("GET", "/api/v1/timetable/versions"),
            ("GET", "/api/v1/ai/status"),
            ("GET", "/api/v1/users"),
            ("GET", "/api/v1/audit-logs"),
            ("GET", "/api/v1/requests"),
        ]
        for method, path in protected_paths:
            resp = unauth_client.request(method, path)
            assert resp.status_code == 401, f"Expected 401 for {method} {path}, got {resp.status_code}"

    def test_expired_and_tampered_tokens_rejected(self, unauth_client: TestClient, db_session: Session):
        admin = db_session.query(UserAccount).filter(UserAccount.email == "admin@eduplus.demo").first()
        expired_token, _jti, _ = create_access_token(
            subject=str(admin.id),
            role=admin.role,
            email=admin.email,
            expires_delta=timedelta(seconds=-10),
        )
        resp_exp = unauth_client.get("/api/v1/auth/me", headers=_auth_header(expired_token))
        assert resp_exp.status_code == 401
        assert "expired" in resp_exp.json()["detail"].lower()

        resp_bad = unauth_client.get("/api/v1/auth/me", headers=_auth_header("not.a.valid.jwt"))
        assert resp_bad.status_code == 401

        # Tamper with signature of valid token
        valid_token = _login(unauth_client, "admin@eduplus.demo", "admin123")["access_token"]
        tampered = valid_token[:-4] + "XXXX"
        resp_tampered = unauth_client.get("/api/v1/auth/me", headers=_auth_header(tampered))
        assert resp_tampered.status_code == 401

    def test_logout_revokes_token_immediately(self, unauth_client: TestClient):
        token = _login(unauth_client, "coordinator@eduplus.demo", "coordinator123")["access_token"]
        headers = _auth_header(token)

        assert unauth_client.get("/api/v1/auth/me", headers=headers).status_code == 200
        logout_resp = unauth_client.post("/api/v1/auth/logout", headers=headers)
        assert logout_resp.status_code == 200

        # Token must now be rejected
        after_resp = unauth_client.get("/api/v1/auth/me", headers=headers)
        assert after_resp.status_code == 401
        assert "revoked" in after_resp.json()["detail"].lower()

    def test_login_rate_limiting_blocks_brute_force(self, unauth_client: TestClient):
        from backend.app.core.config import settings
        max_attempts = settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS
        for _ in range(max_attempts):
            r = unauth_client.post(
                "/api/v1/auth/login",
                json={"email": "student@eduplus.demo", "password": "wrong"},
            )
            assert r.status_code == 401

        blocked = unauth_client.post(
            "/api/v1/auth/login",
            json={"email": "student@eduplus.demo", "password": "wrong"},
        )
        assert blocked.status_code == 429

    def test_change_password_and_relogin(self, unauth_client: TestClient):
        token = _login(unauth_client, "student@eduplus.demo", "student123")["access_token"]
        resp = unauth_client.post(
            "/api/v1/auth/change-password",
            headers=_auth_header(token),
            json={"current_password": "student123", "new_password": "NewSecurePassword!9"},
        )
        assert resp.status_code == 200

        # Old password fails, new password succeeds
        old_resp = unauth_client.post(
            "/api/v1/auth/login",
            json={"email": "student@eduplus.demo", "password": "student123"},
        )
        assert old_resp.status_code == 401
        new_data = _login(unauth_client, "student@eduplus.demo", "NewSecurePassword!9")
        assert new_data["user"]["role"] == "student"


# ---------------------------------------------------------------------------
# 2. Role-Based Access Control (Permitted & Forbidden Operations)
# ---------------------------------------------------------------------------

class TestRoleAccessControl:
    def test_admin_user_management_and_self_lockout_guard(self, unauth_client: TestClient, db_session: Session):
        admin_login = _login(unauth_client, "admin@eduplus.demo", "admin123")
        headers = _auth_header(admin_login["access_token"])
        dept = db_session.query(Department).first()

        # Create a new coordinator user
        create_resp = unauth_client.post(
            "/api/v1/users",
            headers=headers,
            json={
                "email": "new.coord@eduplus.demo",
                "password": "Password123!",
                "full_name": "New Coordinator",
                "role": "coordinator",
                "department_id": str(dept.id),
                "can_approve_timetable": False,
            },
        )
        assert create_resp.status_code == 201
        new_user_id = create_resp.json()["id"]

        # Update role & approval permission
        upd_resp = unauth_client.put(
            f"/api/v1/users/{new_user_id}",
            headers=headers,
            json={"can_approve_timetable": True},
        )
        assert upd_resp.status_code == 200
        assert upd_resp.json()["can_approve_timetable"] is True

        # Admin cannot demote or deactivate self
        self_demote = unauth_client.put(
            f"/api/v1/users/{admin_login['user']['id']}",
            headers=headers,
            json={"role": "coordinator"},
        )
        assert self_demote.status_code == 400
        self_disable = unauth_client.put(
            f"/api/v1/users/{admin_login['user']['id']}",
            headers=headers,
            json={"is_active": False},
        )
        assert self_disable.status_code == 400

    def test_coordinator_permitted_and_forbidden_operations(self, unauth_client: TestClient, db_session: Session):
        coord_headers = _auth_header(_login(unauth_client, "coordinator@eduplus.demo", "coordinator123")["access_token"])
        dept = db_session.query(Department).first()

        # PERMITTED: AI status, AI interpret, timetable generation, validation, versions list
        assert unauth_client.get("/api/v1/ai/status", headers=coord_headers).status_code == 200
        interp = unauth_client.post(
            "/api/v1/ai/interpret",
            headers=coord_headers,
            json={"prompt": "Avoid scheduling practicals on Monday", "department_id": str(dept.id)},
        )
        assert interp.status_code == 200
        assert interp.json()["can_apply"] is True

        gen = _generate_candidate(unauth_client, coord_headers, str(dept.id), "Coord AI Candidate")
        assert gen["version_id"] is not None

        # FORBIDDEN: Admin configuration, user management, audit logs
        assert unauth_client.post(
            "/api/v1/departments",
            headers=coord_headers,
            json={"code": "UNAUTH", "name": "Unauthorized Dept", "college_name": "College"},
        ).status_code == 403
        assert unauth_client.post(
            "/api/v1/rooms",
            headers=coord_headers,
            json={"department_id": str(dept.id), "name": "R999", "type": "classroom", "capacity": 60, "floor": 1},
        ).status_code == 403
        assert unauth_client.get("/api/v1/users", headers=coord_headers).status_code == 403
        assert unauth_client.get("/api/v1/audit-logs", headers=coord_headers).status_code == 403

    def test_teacher_forbidden_administrative_and_ai_operations(self, unauth_client: TestClient, db_session: Session):
        teacher_headers = _auth_header(_login(unauth_client, "teacher@eduplus.demo", "teacher123")["access_token"])
        dept = db_session.query(Department).first()

        assert unauth_client.post(
            "/api/v1/timetable/generate",
            headers=teacher_headers,
            json={"department_id": str(dept.id), "label": "Illegal", "time_limit_seconds": 10},
        ).status_code == 403
        assert unauth_client.post(
            "/api/v1/ai/interpret",
            headers=teacher_headers,
            json={"prompt": "No classes on Monday"},
        ).status_code == 403
        assert unauth_client.get("/api/v1/users", headers=teacher_headers).status_code == 403
        assert unauth_client.get("/api/v1/audit-logs", headers=teacher_headers).status_code == 403
        assert unauth_client.post(
            "/api/v1/departments",
            headers=teacher_headers,
            json={"code": "TCH", "name": "Illegal", "college_name": "X"},
        ).status_code == 403

    def test_student_forbidden_operations(self, unauth_client: TestClient, db_session: Session):
        student_headers = _auth_header(_login(unauth_client, "student@eduplus.demo", "student123")["access_token"])
        dept = db_session.query(Department).first()

        assert unauth_client.get("/api/v1/teachers", headers=student_headers).status_code == 403
        assert unauth_client.get("/api/v1/rooms", headers=student_headers).status_code == 403
        assert unauth_client.get("/api/v1/requests", headers=student_headers).status_code == 403
        assert unauth_client.get("/api/v1/ai/status", headers=student_headers).status_code == 403
        assert unauth_client.get("/api/v1/users", headers=student_headers).status_code == 403
        assert unauth_client.get("/api/v1/audit-logs", headers=student_headers).status_code == 403
        assert unauth_client.post(
            "/api/v1/timetable/generate",
            headers=student_headers,
            json={"department_id": str(dept.id), "label": "Illegal", "time_limit_seconds": 10},
        ).status_code == 403


# ---------------------------------------------------------------------------
# 3. Institutional Data Isolation & IDOR Protection Tests
# ---------------------------------------------------------------------------

class TestInstitutionalDataIsolation:
    def test_teacher_cannot_access_other_teacher_records_or_requests(
        self, unauth_client: TestClient, db_session: Session
    ):
        teacher_login = _login(unauth_client, "teacher@eduplus.demo", "teacher123")
        teacher_headers = _auth_header(teacher_login["access_token"])
        own_teacher_id = teacher_login["user"]["linked_entity_id"]

        other_teacher = (
            db_session.query(Teacher)
            .filter(Teacher.id != uuid.UUID(own_teacher_id))
            .first()
        )
        assert other_teacher is not None

        # Own teacher profile: allowed
        assert unauth_client.get(f"/api/v1/teachers/{own_teacher_id}", headers=teacher_headers).status_code == 200
        # List teachers returns ONLY own record
        list_resp = unauth_client.get("/api/v1/teachers", headers=teacher_headers)
        assert list_resp.status_code == 200
        assert len(list_resp.json()["items"]) == 1
        assert list_resp.json()["items"][0]["id"] == own_teacher_id

        # Other teacher profile via direct API IDOR: 403 Forbidden
        idor_resp = unauth_client.get(f"/api/v1/teachers/{other_teacher.id}", headers=teacher_headers)
        assert idor_resp.status_code == 403

        # Teacher submits own request
        req_resp = unauth_client.post(
            "/api/v1/requests",
            headers=teacher_headers,
            json={
                "request_type": "availability",
                "day_name": "Friday",
                "time_slot_code": "TS8",
                "reason": "Departmental research committee meeting",
            },
        )
        assert req_resp.status_code == 201
        req_id = req_resp.json()["id"]

        # Create a second teacher account and verify they CANNOT view the first teacher's request
        admin_headers = _auth_header(_login(unauth_client, "admin@eduplus.demo", "admin123")["access_token"])
        t2_resp = unauth_client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={
                "email": "teacher2@eduplus.demo",
                "password": "Password123!",
                "full_name": other_teacher.name,
                "role": "teacher",
                "department_id": str(other_teacher.department_id),
                "linked_entity_id": str(other_teacher.id),
            },
        )
        assert t2_resp.status_code == 201
        t2_headers = _auth_header(_login(unauth_client, "teacher2@eduplus.demo", "Password123!")["access_token"])

        assert unauth_client.get(f"/api/v1/requests/{req_id}", headers=t2_headers).status_code == 403
        assert unauth_client.get("/api/v1/requests", headers=t2_headers).json() == []

    def test_student_division_isolation_and_unpublished_version_blocked(
        self, unauth_client: TestClient, db_session: Session
    ):
        admin_headers = _auth_header(_login(unauth_client, "admin@eduplus.demo", "admin123")["access_token"])
        student_login = _login(unauth_client, "student@eduplus.demo", "student123")
        student_headers = _auth_header(student_login["access_token"])
        own_div_id = student_login["user"]["linked_entity_id"]
        dept = db_session.query(Department).first()

        # Find another division (e.g., Year 3 Div B)
        other_div = db_session.query(Division).filter(Division.id != uuid.UUID(own_div_id)).first()
        assert other_div is not None

        # Student can access own division, NOT another division
        assert unauth_client.get(f"/api/v1/divisions/{own_div_id}", headers=student_headers).status_code == 200
        assert unauth_client.get(f"/api/v1/divisions/{other_div.id}", headers=student_headers).status_code == 403
        assert unauth_client.get(f"/api/v1/batches?division_id={other_div.id}", headers=student_headers).status_code == 403

        # Generate an UNPUBLISHED candidate version
        gen = _generate_candidate(unauth_client, admin_headers, str(dept.id), "Secret Candidate")
        cand_id = gen["version_id"]

        # Student & Teacher CANNOT see unpublished candidate via list or direct ID
        assert unauth_client.get("/api/v1/timetable/versions", headers=student_headers).json() == []
        assert unauth_client.get("/api/v1/timetable/versions?status=candidate", headers=student_headers).status_code == 403
        assert unauth_client.get(f"/api/v1/timetable/versions/{cand_id}", headers=student_headers).status_code == 403

        teacher_headers = _auth_header(_login(unauth_client, "teacher@eduplus.demo", "teacher123")["access_token"])
        assert unauth_client.get(f"/api/v1/timetable/versions/{cand_id}", headers=teacher_headers).status_code == 403

        # Now approve & publish the version
        assert unauth_client.post(f"/api/v1/timetable/versions/{cand_id}/submit", headers=admin_headers).status_code == 200
        assert unauth_client.post(f"/api/v1/timetable/versions/{cand_id}/approve", headers=admin_headers).status_code == 200
        assert unauth_client.post(f"/api/v1/timetable/versions/{cand_id}/publish", headers=admin_headers).status_code == 200

        # Now student sees published version with ONLY their division/batches sessions and zero internal violations
        st_ver = unauth_client.get(f"/api/v1/timetable/versions/{cand_id}", headers=student_headers)
        assert st_ver.status_code == 200
        st_data = st_ver.json()
        assert st_data["status"] == "published"
        assert st_data["violations"] == []
        assert len(st_data["sessions"]) >= 1

        # Teacher sees published version with ONLY their own assigned teaching sessions
        tch_ver = unauth_client.get(f"/api/v1/timetable/versions/{cand_id}", headers=teacher_headers)
        assert tch_ver.status_code == 200
        tch_login = _login(unauth_client, "teacher@eduplus.demo", "teacher123")
        tch_id = tch_login["user"]["linked_entity_id"]
        for s in tch_ver.json()["sessions"]:
            assert s["teacher_id"] == tch_id

    def test_coordinator_isolated_to_own_department(self, unauth_client: TestClient, db_session: Session):
        admin_headers = _auth_header(_login(unauth_client, "admin@eduplus.demo", "admin123")["access_token"])
        coord_headers = _auth_header(_login(unauth_client, "coordinator@eduplus.demo", "coordinator123")["access_token"])

        # Admin creates a second department
        other_dept_resp = unauth_client.post(
            "/api/v1/departments",
            headers=admin_headers,
            json={"code": "MECH2", "name": "Mechanical Engg", "college_name": "Example College"},
        )
        assert other_dept_resp.status_code == 201
        other_dept_id = other_dept_resp.json()["id"]

        # AIML Coordinator cannot view or generate for MECH2 department
        assert unauth_client.get(f"/api/v1/departments/{other_dept_id}", headers=coord_headers).status_code == 403
        assert unauth_client.post(
            "/api/v1/timetable/generate",
            headers=coord_headers,
            json={"department_id": other_dept_id, "label": "Cross-dept attempt", "time_limit_seconds": 10},
        ).status_code == 403


# ---------------------------------------------------------------------------
# 4. Controlled Timetable Approval Workflow & History Preservation
# ---------------------------------------------------------------------------

class TestApprovalWorkflow:
    def test_full_approval_rejection_resubmission_and_archive_lifecycle(
        self, unauth_client: TestClient, db_session: Session
    ):
        admin_headers = _auth_header(_login(unauth_client, "admin@eduplus.demo", "admin123")["access_token"])
        coord_headers = _auth_header(_login(unauth_client, "coordinator@eduplus.demo", "coordinator123")["access_token"])
        dept = db_session.query(Department).first()

        # 1. Coordinator generates v1 candidate
        v1 = _generate_candidate(unauth_client, coord_headers, str(dept.id), "Candidate v1")
        v1_id = v1["version_id"]

        # 2. Direct publish without approval is blocked (409)
        assert unauth_client.post(f"/api/v1/timetable/versions/{v1_id}/publish", headers=admin_headers).status_code == 409

        # 3. Coordinator (without can_approve_timetable) submits v1 for approval
        sub1 = unauth_client.post(
            f"/api/v1/timetable/versions/{v1_id}/submit",
            headers=coord_headers,
            json={"comment": "Ready for HOD review"},
        )
        assert sub1.status_code == 200
        assert sub1.json()["status"] == "pending_approval"

        # 4. Unauthorized coordinator CANNOT approve, reject, or publish (403)
        assert unauth_client.post(f"/api/v1/timetable/versions/{v1_id}/approve", headers=coord_headers).status_code == 403
        assert unauth_client.post(f"/api/v1/timetable/versions/{v1_id}/reject", headers=coord_headers).status_code == 403
        assert unauth_client.post(f"/api/v1/timetable/versions/{v1_id}/publish", headers=coord_headers).status_code == 403

        # 5. Admin rejects v1 with reason
        rej = unauth_client.post(
            f"/api/v1/timetable/versions/{v1_id}/reject",
            headers=admin_headers,
            json={"comment": "Please balance Tuesday afternoon labs"},
        )
        assert rej.status_code == 200
        assert rej.json()["status"] == "rejected"
        assert "Tuesday" in rej.json()["approval_comment"]

        # 6. Coordinator resubmits v1, Admin approves, Admin publishes
        assert unauth_client.post(f"/api/v1/timetable/versions/{v1_id}/submit", headers=coord_headers).status_code == 200
        app_resp = unauth_client.post(
            f"/api/v1/timetable/versions/{v1_id}/approve",
            headers=admin_headers,
            json={"comment": "Approved for AY26-27"},
        )
        assert app_resp.status_code == 200
        assert app_resp.json()["status"] == "approved"
        assert app_resp.json()["approved_by"] is not None
        assert app_resp.json()["approved_at"] is not None

        pub1 = unauth_client.post(f"/api/v1/timetable/versions/{v1_id}/publish", headers=admin_headers)
        assert pub1.status_code == 200
        assert pub1.json()["status"] == "published"
        assert pub1.json()["published_by"] is not None
        assert pub1.json()["published_at"] is not None

        # 7. Duplicate publication blocked (409)
        dup_pub = unauth_client.post(f"/api/v1/timetable/versions/{v1_id}/publish", headers=admin_headers)
        assert dup_pub.status_code == 409

        # 8. Publish a second version v2 -> v1 must be preserved as 'archived'
        v2 = _generate_candidate(unauth_client, coord_headers, str(dept.id), "Candidate v2")
        v2_id = v2["version_id"]
        assert unauth_client.post(f"/api/v1/timetable/versions/{v2_id}/submit", headers=coord_headers).status_code == 200
        assert unauth_client.post(f"/api/v1/timetable/versions/{v2_id}/approve", headers=admin_headers).status_code == 200
        assert unauth_client.post(f"/api/v1/timetable/versions/{v2_id}/publish", headers=admin_headers).status_code == 200

        v1_after = unauth_client.get(f"/api/v1/timetable/versions/{v1_id}", headers=admin_headers).json()
        assert v1_after["status"] == "archived"
        assert len(v1_after["sessions"]) >= 1  # History preserved

    def test_configurable_coordinator_approval_permission(self, unauth_client: TestClient, db_session: Session):
        admin_headers = _auth_header(_login(unauth_client, "admin@eduplus.demo", "admin123")["access_token"])
        coord_login = _login(unauth_client, "coordinator@eduplus.demo", "coordinator123")
        coord_headers = _auth_header(coord_login["access_token"])
        dept = db_session.query(Department).first()

        # Admin enables configurable approval permission for this coordinator
        upd = unauth_client.put(
            f"/api/v1/users/{coord_login['user']['id']}",
            headers=admin_headers,
            json={"can_approve_timetable": True},
        )
        assert upd.status_code == 200

        v = _generate_candidate(unauth_client, coord_headers, str(dept.id), "Delegated Approval Candidate")
        vid = v["version_id"]
        assert unauth_client.post(f"/api/v1/timetable/versions/{vid}/submit", headers=coord_headers).status_code == 200
        assert unauth_client.post(f"/api/v1/timetable/versions/{vid}/approve", headers=coord_headers).status_code == 200
        pub = unauth_client.post(f"/api/v1/timetable/versions/{vid}/publish", headers=coord_headers)
        assert pub.status_code == 200
        assert pub.json()["status"] == "published"

    def test_hard_violations_block_submission_and_publication(self, unauth_client: TestClient, db_session: Session):
        admin_headers = _auth_header(_login(unauth_client, "admin@eduplus.demo", "admin123")["access_token"])
        dept = db_session.query(Department).first()

        gen = _generate_candidate(unauth_client, admin_headers, str(dept.id), "Hard Conflict Candidate")
        vid = uuid.UUID(gen["version_id"])

        # Inject a Level A hard violation into DB to simulate invalid timetable
        db_session.add(Violation(
            timetable_version_id=vid,
            rule_id="A01",
            rule_level="A",
            severity="error",
            description="Simulated teacher double-booking conflict.",
            affected_session_ids=[],
            affected_entity_ids=[],
        ))
        db_session.commit()

        # Submission blocked (422)
        sub_resp = unauth_client.post(f"/api/v1/timetable/versions/{vid}/submit", headers=admin_headers)
        assert sub_resp.status_code == 422

        # Even if status were manually forced to approved, publication gate MUST still block (422)
        ver = db_session.query(TimetableVersion).filter(TimetableVersion.id == vid).first()
        ver.status = "approved"
        db_session.commit()

        pub_resp = unauth_client.post(f"/api/v1/timetable/versions/{vid}/publish", headers=admin_headers)
        assert pub_resp.status_code == 422
        assert "hard violation" in pub_resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 5. Audit Logging & Secret Redaction Tests
# ---------------------------------------------------------------------------

class TestAuditLogging:
    def test_security_and_workflow_audit_logs_created_without_secrets(
        self, unauth_client: TestClient, db_session: Session
    ):
        # Failed login + successful login
        unauth_client.post("/api/v1/auth/login", json={"email": "admin@eduplus.demo", "password": "BadPassword!99"})
        admin_token = _login(unauth_client, "admin@eduplus.demo", "admin123")["access_token"]
        admin_headers = _auth_header(admin_token)
        dept = db_session.query(Department).first()

        # AI interpret + Generate with confirmed constraint + Submit + Approve + Publish
        interp = unauth_client.post(
            "/api/v1/ai/interpret",
            headers=admin_headers,
            json={"prompt": "Avoid scheduling practicals on Monday", "department_id": str(dept.id)},
        )
        assert interp.status_code == 200
        gen = unauth_client.post(
            "/api/v1/timetable/generate",
            headers=admin_headers,
            json={
                "department_id": str(dept.id),
                "label": "Audited AI Candidate",
                "time_limit_seconds": 20,
                "confirmed_constraints": interp.json()["constraints"],
            },
        )
        assert gen.status_code == 202
        vid = gen.json()["version_id"]

        assert unauth_client.post(f"/api/v1/timetable/versions/{vid}/submit", headers=admin_headers).status_code == 200
        assert unauth_client.post(f"/api/v1/timetable/versions/{vid}/approve", headers=admin_headers).status_code == 200
        assert unauth_client.post(f"/api/v1/timetable/versions/{vid}/publish", headers=admin_headers).status_code == 200

        # Retrieve audit logs via Admin API
        logs_resp = unauth_client.get("/api/v1/audit-logs?page_size=100", headers=admin_headers)
        assert logs_resp.status_code == 200
        items = logs_resp.json()["items"]
        actions = {entry["action"] for entry in items}

        for expected_action in (
            "AUTH_LOGIN_FAILURE",
            "AUTH_LOGIN_SUCCESS",
            "AI_PROMPT_INTERPRETED",
            "AI_CONSTRAINTS_CONFIRMED",
            "TIMETABLE_GENERATE",
            "TIMETABLE_SUBMIT",
            "TIMETABLE_APPROVE",
            "TIMETABLE_PUBLISH",
        ):
            assert expected_action in actions, f"Missing audit log for {expected_action}"

        # Verify NO passwords or tokens appear anywhere in audit log payloads
        serialized = str(items)
        assert "BadPassword!99" not in serialized
        assert "admin123" not in serialized
        assert admin_token not in serialized
