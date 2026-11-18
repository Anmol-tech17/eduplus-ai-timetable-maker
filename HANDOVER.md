# EduPlus AI Timetable Maker — Project Handover Guide

> **Current Status:** Pilot-ready with limitations (NOT certified production-ready; see Section 20)  
> **Repository:** `https://github.com/Anmol-tech17/eduplus-ai-timetable-maker.git`  
> **Branch:** `main`  
> **Application Version:** `0.7.0`  
> **Handover Baseline Commit (prior to this doc):** `48175ce` (`feat: prepare Eduplus for production deployment`) + `abbc7e2` (`style: align secondary accent palette to institutional yellow`)

---

## 1. Project Overview and Purpose

**EduPlus AI Timetable Maker** is an institutional academic timetable scheduling, validation, approval, and management platform built for multi-department engineering colleges (seeded with an AIML Department baseline for Example Engineering College).

It replaces manual spreadsheet-based timetable creation by combining:
- **Deterministic constraint optimization** (Google OR-Tools CP-SAT) to produce conflict-free weekly timetables.
- **Independent rule validation** to verify every hard (Level A), policy (Level B), and soft preference (Level C) constraint before publication.
- **Role-based security and controlled approval workflows** so coordinators generate and submit candidates, authorized approvers review and publish them, and teachers/students only view authorized published schedules.
- **Natural-language AI assistance** to interpret coordinator constraints and explain solver/diff outcomes without ever allowing an LLM to fabricate or override schedules.

---

## 2. Main Features and Functionality

| Feature Area | Implementation Status | Verification Status |
|---|---|---|
| Academic Hierarchy CRUD (Departments, Years, Divisions, Batches, Subjects, Teachers, Rooms) | Implemented (PostgreSQL + FastAPI) | Verified via automated pytest (`test_api_crud.py`, `test_models.py`) |
| CP-SAT Timetable Generation (Lectures, Tutorials, 2-hr Practicals, Capacities, Unavailabilities) | Implemented (`backend/app/engine/solver.py`) | Verified across unit + Small/Medium/Large scale benchmarks |
| Independent Deterministic Validator (Rules A01–A11, B01–B03, C01–C03) | Implemented (`backend/app/engine/validator.py`) | Verified via 30 engine tests + end-to-end API tests |
| Asynchronous Background Generation + Duplicate-Job Guard + Crash Recovery | Implemented (`backend/app/services/job_runner.py`) | Verified in unit/manager tests; live multi-worker soak test **unverified** |
| Timetable Versioning, Session Diffing & Localized Repair (Pinned Sessions) | Implemented (`backend/app/api/v1/timetable.py`) | Verified via `test_timetable_api.py` & `test_scale_performance.py` |
| Controlled Approval & Publication Lifecycle (`draft`/`candidate` → `pending_approval` → `approved`/`rejected` → `published` → `archived`) | Implemented (`backend/app/api/v1/timetable.py`) | Verified via `test_auth_rbac.py` & 11-step E2E acceptance test |
| JWT Auth, Refresh Rotation, HttpOnly Cookies + CSRF, Persistent Multi-Worker Revocation & Rate Limiting | Implemented (`backend/app/core/security.py`, `auth.py`, `deps.py`) | Verified via `test_auth_rbac.py` & `test_phase7_production.py` |
| RBAC & Institutional Data Isolation (Admin, Coordinator, Teacher, Student) | Implemented across all API routers | Verified via direct API IDOR tests in `test_auth_rbac.py` |
| Immutable Audit Logging with Automatic Secret Redaction | Implemented (`backend/app/services/audit.py`) | Verified via `test_auth_rbac.py` & `test_phase7_production.py` |
| Teacher Availability / Schedule Change Requests | Implemented (`backend/app/api/v1/requests.py` + `teacher.js`) | Backend verified; interactive browser flow **unverified** |
| Natural-Language AI Assistant (Mock Deterministic Provider) | Implemented (`backend/app/ai/`) | Verified via `test_ai_assistant.py` & E2E test |
| Natural-Language AI Assistant (Live Gemini API Provider) | Implemented (`GeminiLLMProvider`) | **UNVERIFIED** (no live `GEMINI_API_KEY` tested; fallback tested via mocks) |
| Individual Student Elective Enrollment Filtering | **Not implemented** (schema lacks student enrollment tables) | Division + division-batch isolation verified; elective-level mapping pending |
| Frontend Dashboards (`index.html`, `admin.html`, `teacher.html`, `student.html`) | Implemented (Vanilla HTML/CSS/JS) | Automated browser E2E tests **not configured** (**unverified** in Playwright/Selenium) |
| Docker, Docker Compose & Nginx HTTPS Reverse Proxy | Authored (`Dockerfile`, `docker-compose.yml`, `deploy/nginx.conf`) | **UNVERIFIED** on a live Docker / TLS host |
| Student/Teacher Query Forms & Notifications Panels (UI) | Prototype/placeholder in `teacher.html`, `student.html` | Static/mock UI — not wired to a backend ML query service |

---

## 3. Technology Stack and Architecture

| Layer | Technology | Notes |
|---|---|---|
| Backend Runtime | Python 3.10+ | Tested on Python `3.10.0rc2` (Windows 10) |
| Web Framework | FastAPI `>=0.115.0` + Uvicorn `>=0.30.0` + Pydantic v2 `>=2.9.0` | OpenAPI docs disabled by default when `ENVIRONMENT=production` |
| Database | PostgreSQL 18 (local dev cluster on `127.0.0.1:5433`) | SQLAlchemy `>=2.0.30` ORM, `psycopg2-binary`, Alembic `>=1.13.0` |
| Optimization Solver | Google OR-Tools CP-SAT (`ortools>=9.9`, tested `9.15`) | Integer/boolean constraint programming |
| Security | `passlib` (`pbkdf2_sha256`), `PyJWT>=2.8.0` (`HS256`), `secrets` CSRF | Persistent revocation & login rate-limiting in PostgreSQL |
| HTTP Client | `httpx>=0.27.0` | Used for Gemini REST calls and FastAPI `TestClient` |
| Frontend | Vanilla HTML5, CSS3 (`src/css/style.css`), ES2020 JS (`src/js/*.js`) | Zero frontend build step required |
| Testing | `pytest>=8.0.0`, `pytest-asyncio>=0.23.0` | 106 backend tests across 11 test files |

### High-Level Request & Data Flow
```text
Browser (index/admin/teacher/student.html + src/js/api.js)
   │  Bearer JWT and/or HttpOnly Cookies + X-CSRF-Token
   ▼
[Nginx Reverse Proxy (deploy/nginx.conf)] ──► FastAPI (backend/app/main.py)
                                                ├── Middleware: X-Request-ID, Security Headers, Structured JSON/Text Logs
                                                ├── Auth & RBAC Dependencies (backend/app/api/deps.py)
                                                ├── AI Gateway (backend/app/ai/)  [Interpret & Explain ONLY]
                                                ├── CP-SAT Solver (backend/app/engine/solver.py) [Sync or ThreadPoolExecutor]
                                                ├── Independent Validator (backend/app/engine/validator.py) [Authoritative Gate]
                                                └── PostgreSQL 18 (29 tables: Academic, Timetable, Security, Audit)
```

---

## 4. AI Architecture (Strict Separation of Concerns)

EduPlus uses a **hybrid AI + deterministic optimization** architecture. Do not blur these three boundaries when maintaining or extending the codebase:

1. **LLM Layer (`backend/app/ai/provider.py`, `interpreter.py`, `explainer.py`) — Interpretation & Explanation ONLY:**
   - Parses coordinator English instructions (e.g., *"Give Dr. Priya Sharma no classes after 2 PM and avoid scheduling practicals on Monday"*) into typed Pydantic `InterpretedConstraint` objects.
   - Grounds all entity references (teachers, departments, academic years, divisions, slots) against live PostgreSQL rows via `build_grounding_context()`. Unrecognized entities are flagged `is_ambiguous=True` with a `ClarificationQuestion` rather than hallucinated.
   - Translates solver outcomes, validator violations, and version diffs into readable Markdown insights.
   - **Prohibited:** The LLM never places sessions, never writes SQL, never bypasses constraints, and never declares a timetable valid.
2. **OR-Tools CP-SAT Layer (`backend/app/engine/solver.py`) — Generation & Optimization:**
   - Takes a normalized `SchedulingInput` plus user-confirmed constraints (`teacher.unavailable_slots`, `teacher.preferred_slots`, `blocked_practical_days`, `gap_penalty_weight`).
   - Encodes hard rules (`H1`–`H8`, pinned repair sessions, room type/capacity filtering) as linear CP-SAT constraints and soft goals (`S1`–`S4`) as weighted objective terms.
   - Mathematically determines `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, or `TIMEOUT`.
3. **Independent Validator Layer (`backend/app/engine/validator.py`) — Authoritative Verification:**
   - Completely decoupled from CP-SAT; inspects any session list (solver-generated or manually repaired) against hard rules `A01`–`A11`, policy rules `B01`–`B03`, and soft checks `C01`–`C03`.
   - Acts as the final backend publication gate: submission (`POST /submit`), approval (`POST /approve`), and publication (`POST /publish`) are **hard-blocked (`HTTP 422`)** whenever any Level A violation exists.

---

## 5. Project Folder Structure and Important Files

```text
Eduplus AI Timetable Maker/
├── HANDOVER.md                         # This developer transfer guide
├── README.md                           # High-level project overview & quickstart
├── .env.production.example             # Production env template (no real secrets)
├── Dockerfile                          # Non-root Python 3.10 backend container
├── docker-compose.yml                  # PostgreSQL 18 + FastAPI API + Nginx stack
├── deploy/nginx.conf                   # Static hosting + /api/ reverse proxy + TLS guide
├── index.html                          # Login page (4 roles, expired/unauth banners)
├── admin.html                          # Admin & Coordinator workspace (role-aware)
├── teacher.html                        # Teacher workspace (published schedule & requests)
├── student.html                        # Student workspace (division published schedule)
├── src/
│   ├── css/style.css                   # Institutional white/blue/yellow design system
│   ├── js/api.js                       # Fetch client: JWT/Cookie+CSRF, auto-refresh, timeouts
│   ├── js/admin.js                     # Admin/Coordinator UI, AI assistant, approvals, users, audit
│   ├── js/teacher.js                   # Teacher grid + live /api/v1/requests submission
│   ├── js/student.js                   # Student division/batch schedule view
│   └── data/mockData.js                # Offline development prototype fallback dataset
├── docs/
│   ├── DEPLOYMENT_AND_OPERATIONS.md    # Env validation, Docker, HTTPS, pg_dump/pg_restore runbook
│   ├── ROLE_ACCESS_MATRIX.md           # Intended institutional RBAC policy reference
│   ├── AI_AND_ML_ROADMAP.md            # Permitted vs. prohibited AI responsibilities
│   ├── SCHEDULING_RULES.md             # Level A / B / C scheduling rule catalogue
│   ├── SCHEDULER_DESIGN.md             # CP-SAT mathematical formulation
│   └── ...                             # Domain model, ER diagram, API spec, roadmap
└── backend/
    ├── .env.example                    # Local dev env template
    ├── alembic.ini                     # Alembic configuration
    ├── requirements.txt                # Python dependencies
    ├── alembic/versions/
    │   ├── 5cc27eb93e43_initial_baseline_22_entities.py
    │   ├── a7f3c91e2b14_phase6_auth_rbac_approvals.py
    │   └── c4e8a12f9b03_phase7_production_security_reliability.py
    ├── app/
    │   ├── main.py                     # FastAPI factory, lifespan validation, middleware
    │   ├── core/
    │   │   ├── config.py               # Environment settings & validate_production_config()
    │   │   ├── logging.py              # Structured JSON/text logs, X-Request-ID, secret filter
    │   │   └── security.py             # PBKDF2, PyJWT access/refresh, DB revocation/rate-limit, CSRF
    │   ├── db/session.py               # Pooled SQLAlchemy engine & get_db()
    │   ├── models/                     # academic.py, faculty.py, room.py, scheduling.py, timetable.py, security.py
    │   ├── schemas/                    # academic.py, common.py, faculty.py, room.py, security.py, timetable.py
    │   ├── engine/                     # types.py, input_builder.py, solver.py, validator.py, persistence.py, comparator.py
    │   ├── ai/                         # schemas.py, provider.py, interpreter.py, explainer.py
    │   ├── services/
    │   │   ├── audit.py                # AuditLog recorder with automatic secret redaction
    │   │   └── job_runner.py           # ThreadPoolExecutor background solver & crash recovery
    │   ├── api/
    │   │   ├── deps.py                 # Bearer/Cookie+CSRF auth, require_roles, require_approver, dept isolation
    │   │   └── v1/                     # router.py, health.py, auth.py, users.py, requests.py, departments.py,
    │   │                               # academic_years.py, divisions.py, batches.py, subjects.py,
    │   │                               # teachers.py, rooms.py, timetable.py, ai.py
    │   └── seed/seed_data.py           # Idempotent AIML baseline seed (dept, faculty, rooms, 4 role accounts)
    └── tests/                          # 11 pytest suites (106 tests total) + conftest.py
```

---

## 6. Database Architecture and Migrations

PostgreSQL 18 holds **29 physical tables** managed via Alembic (current head: `c4e8a12f9b03`):

### Table Groups & Key Relationships
- **Academic Hierarchy (`models/academic.py`):** `departments` → `academic_years` → `divisions` → `batches`; `departments` → `subjects` → `enrollment_groups` ↔ `enrollment_group_overlaps`.
- **Faculty & Rooms (`models/faculty.py`, `models/room.py`):** `teachers` → `teacher_qualifications` (FK `subjects`), `teacher_availabilities` (FK `time_slots`); `rooms` → `room_capabilities`.
- **Scheduling Configuration (`models/scheduling.py`):** `time_slots` (`TS1`–`TS10`), `working_days`, `division_lunch_policies`, `teaching_assignments` (links `subject`, `division`, `teacher`, optional `batch`/`enrollment_group`) → `session_requirements` (`weekly_count`, `duration_hours` 1 or 2).
- **Timetable Execution & Versioning (`models/timetable.py`):** `input_snapshots` → `generation_runs` → `timetable_versions` (self-referencing `parent_version_id`, statuses: `draft`, `candidate`, `pending_approval`, `approved`, `rejected`, `published`, `archived`; tracks `submitted_by/at`, `approved_by/at`, `approval_comment`, `published_by/at`) → `scheduled_sessions`, `violations`, `session_exceptions`.
- **Security, Requests & Multi-Worker Persistence (`models/security.py`):**
  - `user_accounts` (`role IN ('admin','coordinator','teacher','student')`, `department_id`, `linked_entity_id`, `can_approve_timetable`, `is_active`).
  - `audit_logs` (immutable actor/action/entity/sanitized JSON payload/IP/timestamp).
  - `teacher_requests` (`availability`, `reschedule`, `substitution`, `cancellation`; status `pending`/`approved`/`rejected`).
  - `revoked_tokens` (persistent JTI blocklist shared across workers).
  - `login_attempts` (persistent failed-login sliding window shared across workers).

### Alembic Migration Chain
1. `5cc27eb93e43` — Initial baseline 22 entities
2. `a7f3c91e2b14` — Phase 6: `coordinator` role, `full_name`, `can_approve_timetable`, `timetable_versions` approval columns/statuses, `teacher_requests`
3. `c4e8a12f9b03` — Phase 7: `revoked_tokens`, `login_attempts`, composite query indexes on `audit_logs`, `generation_runs`, and `timetable_versions`

```bash
# Apply all migrations
python -m alembic -c backend/alembic.ini upgrade head

# Check current applied revision
python -m alembic -c backend/alembic.ini current
```

---

## 7. User Roles and Permissions (Backend-Enforced)

Every rule below is enforced server-side in `backend/app/api/deps.py` and the respective v1 routers (frontend navigation hides restricted tabs for usability, not as a security boundary).

| Role | Scope | Permitted Actions | Explicitly Forbidden (`HTTP 403`) |
|---|---|---|---|
| **`admin`** | Institution-wide | Manage users & roles (`can_approve_timetable`), manage all academic entities/rooms/teachers, view immutable audit logs, use AI assistant, generate/validate/compare/repair, submit/approve/reject/publish timetables, review teacher requests | Cannot demote or deactivate own admin account (`400`); cannot publish versions with Level A violations (`422`) or unapproved versions (`409`) |
| **`coordinator`** | Own `department_id` only | Use AI assistant, generate/validate/compare/repair own dept timetables, submit candidates for approval, view & review own dept teacher requests. Can approve/reject/publish **only if** `can_approve_timetable=True` | Managing departments/years/divisions/batches/subjects/rooms/teachers/users, viewing audit logs, accessing another department, approving/publishing without `can_approve_timetable=True` |
| **`teacher`** | Own `linked_entity_id` (Teacher.id) & own dept | View **published** timetables filtered strictly to own teaching sessions, view own teacher profile, submit & track own availability/schedule requests | Viewing unpublished timetable versions, viewing other teachers' profiles or requests (IDOR blocked), using AI assistant, generating/approving/publishing timetables, modifying configuration |
| **`student`** | Own `linked_entity_id` (Division.id) & its batches | View **published** timetables filtered strictly to own division & division batches, view own division & batches | Viewing unpublished timetable versions, viewing other divisions/batches, accessing `/teachers`, `/rooms`, `/requests`, `/ai/*`, `/users`, `/audit-logs`, or generation endpoints |

---

## 8. Authentication, Refresh Tokens, Cookies, CSRF, and Audit Logging

- **Password Hashing:** Salted PBKDF2-SHA256 (`passlib.hash.pbkdf2_sha256`). Passwords are never stored, returned, or logged in plaintext.
- **Access & Refresh Tokens:** HS256 JWTs (`PyJWT`) with `sub`, `role`, `email`, `dept`, `jti`, `type` (`access` | `refresh`), `iat`, `exp`. Default lifetimes: access `60 min` (`ACCESS_TOKEN_EXPIRE_MINUTES`), refresh `7 days` (`REFRESH_TOKEN_EXPIRE_DAYS`).
- **Token Transport:**
  - `Authorization: Bearer <token>` header (used by API clients and cross-origin local file development).
  - `HttpOnly`, `Secure` (in production), `SameSite` cookies (`eduplus_access_token`, `eduplus_refresh_token`) + JS-readable `eduplus_csrf_token` cookie set on login/refresh.
- **CSRF Protection:** Any mutating request (`POST`, `PUT`, `PATCH`, `DELETE`) authenticated via cookie (without `Authorization: Bearer`) MUST include header `X-CSRF-Token` matching `eduplus_csrf_token` (constant-time `secrets.compare_digest`), otherwise `403 Forbidden`.
- **Refresh Rotation & Logout Revocation:** `POST /api/v1/auth/refresh` immediately inserts the consumed refresh token's `jti` into PostgreSQL `revoked_tokens` and issues a fresh access + refresh pair (replaying an old refresh token returns `401`). `POST /api/v1/auth/logout` revokes both access and refresh `jti`s in PostgreSQL and clears cookies.
- **Persistent Rate Limiting:** Failed logins insert into `login_attempts`; exceeding `LOGIN_RATE_LIMIT_MAX_ATTEMPTS` (default 10) within `LOGIN_RATE_LIMIT_WINDOW_SECONDS` (default 60s) per `IP:email` returns `429 Too Many Requests` across all workers.
- **Audit Logging:** `record_audit_event()` records actor, action, entity type/ID, IP address, timestamp, and sanitized JSON payload (any key containing `password`, `token`, `secret`, `api_key`, `authorization`, `credential`, `hash` is automatically replaced with `[REDACTED]`). Logged actions include `AUTH_LOGIN_SUCCESS`, `AUTH_LOGIN_FAILURE`, `AUTH_LOGIN_RATE_LIMITED`, `AUTH_TOKEN_REFRESH`, `AUTH_LOGOUT`, `AUTH_PASSWORD_CHANGED`, `USER_CREATED`, `USER_UPDATED`, `USER_ROLE_CHANGED`, `CONFIG_*`, `AI_PROMPT_INTERPRETED`, `AI_CONSTRAINTS_CONFIRMED`, `TIMETABLE_GENERATE`, `TIMETABLE_GENERATE_ASYNC`, `TIMETABLE_SUBMIT`, `TIMETABLE_APPROVE`, `TIMETABLE_REJECT`, `TIMETABLE_PUBLISH`, `TIMETABLE_REPAIR`, `TEACHER_REQUEST_CREATED`, and `TEACHER_REQUEST_REVIEWED`.

---

## 9. Complete End-to-End User Workflows

### Workflow 1: AI-Assisted Generation → Approval → Publication → Distribution
1. **Login:** User signs in at `index.html` (`POST /api/v1/auth/login`) and is routed by role (`admin`/`coordinator` → `admin.html`, `teacher` → `teacher.html`, `student` → `student.html`).
2. **Interpret Constraints (Coordinator/Admin):** In **Generate & Validate**, enter an English instruction (e.g., *"Give Dr. Priya Sharma no classes after 2 PM and avoid scheduling practicals on Monday"*) and click **Interpret with AI** (`POST /api/v1/ai/interpret`).
3. **Review & Confirm:** Inspect extracted Level A/C constraints, resolve any entity clarifications, toggle checkboxes, and click **Apply Confirmed Constraints & Solve**.
4. **Generate & Validate:** Backend builds `SchedulingInput`, applies confirmed constraints, runs OR-Tools CP-SAT (`POST /api/v1/timetable/generate` or `/generate/async`), runs the independent validator (`validate_timetable`), and persists a `candidate` (0 hard violations) or `draft` (>0 hard violations) version.
5. **Submit for Approval:** Coordinator clicks **Submit for Approval** (`POST /api/v1/timetable/versions/{id}/submit`). Hard violations block submission (`422`). Status becomes `pending_approval`.
6. **Review (Approver):** Admin (or Coordinator with `can_approve_timetable=True`) clicks **Approve** (`POST /approve` → `approved`) or **Reject** (`POST /reject` with reason → `rejected`, which can be repaired/resubmitted).
7. **Publish:** Approver clicks **Publish Approved Timetable** (`POST /publish`). Requires `status == 'approved'` and 0 Level A violations. Any previously `published` version for the same `(department, academic_year_code, semester)` is preserved as `archived`.
8. **Role-Isolated Consumption:** Teachers log in (`teacher.html`) and see only their assigned sessions from the published version; Students log in (`student.html`) and see only their division/batch sessions.
9. **Audit Review:** Admin inspects **Audit Logs** (`GET /api/v1/audit-logs`) for the complete trail.

### Workflow 2: Teacher Availability / Schedule Request
1. Teacher signs in (`teacher.html`), opens **Submit Request**, submits a request (`POST /api/v1/requests`), and tracks its status under **My Requests** (`GET /api/v1/requests`).
2. Coordinator/Admin reviews incoming department requests (`GET /api/v1/requests`, `POST /api/v1/requests/{id}/review`) and optionally triggers a localized repair (`POST /api/v1/timetable/repair`).

---

## 10. Frontend Pages, Dashboards, and Design System

| File | Roles | Panels / Features |
|---|---|---|
| `index.html` | Public | Real JWT login form, 4 test account quick-fill rows, expired-session (`?reason=session_expired`) & unauthorized (`?reason=unauthorized`) alert banners, offline demo fallback |
| `admin.html` + `src/js/admin.js` | `admin`, `coordinator` | **Dashboard** (`overview`), **Timetable Grid** (`timetable`), **Generate & Validate** (`generate` — AI Scheduling Assistant, CP-SAT params, candidate list, validation report, AI explanation, Approval & Publication controls), **Conflicts** (`conflicts`), **Version Comparison & Repair** (`compare` — diff table, AI diff explanation, localized repair), **Teachers** (`teachers`), **Rooms & Labs** (`rooms`), **Request Inbox** (`requests`), plus Admin-only **Users & Roles** (`users`) and **Audit Logs** (`audit`) |
| `teacher.html` + `src/js/teacher.js` | `teacher` | **My Timetable** (`my-timetable`, live published sessions filtered to self), **Today's Classes** (`today`), **Submit Request** (`submit-request`, wired to `POST /api/v1/requests`), **My Requests** (`my-requests`, wired to `GET /api/v1/requests`), **Submit Query** (`teacher-query`, prototype UI), **Notifications** (`notifications`, static UI) |
| `student.html` + `src/js/student.js` | `student` | **Overview** (`student-home`), **My Timetable** (`student-timetable`, live published division/batch sessions), **Today's Classes** (`student-today`), **Notices** (`student-notices`, static UI), **Submit Query** (`student-query`, prototype UI) |

### Institutional Visual Design (`src/css/style.css`)
- **Background:** White (`#ffffff`) and light neutral gray (`#f9fafb`) content areas.
- **Primary Color:** Institutional Blue (`--brand-500: #2255a4`, `--brand-600: #1a3a6e`, `--brand-900: #0a1628`) for primary actions, active highlights, and sidebar.
- **Secondary Accent:** Institutional Yellow (`--yellow-500: #ca8a04`, `--yellow-300: #fde047`, `--yellow-100: #fef9c3`, `--yellow-700: #713f12`), used sparingly for badges, pending/repair highlights, and notices. *(Note: During handover preparation in commit `abbc7e2`, legacy `--orange-*` CSS tokens in `src/css/style.css` were aligned to institutional yellow to satisfy the white/blue/yellow palette consistently across all pages without breaking existing class names.)*
- **Typography & Responsiveness:** Inter font, dark readable text (`#111827` / `#374151`), neutral borders (`#e5e7eb`), responsive single-column collapse under `768px`, and text-overflow wrapping on long subject/teacher names.

---

## 11. Backend API Reference (Prefix: `/api/v1`)

### Health & Observability (`api/v1/health.py`)
| Method | Endpoint | Auth / Roles | Purpose |
|---|---|---|---|
| `GET` | `/` (root) | Public | Service metadata & health URLs |
| `GET` | `/api/v1/health` | Public | Liveness & DB connectivity probe |
| `GET` | `/api/v1/health/ready` | Public | Readiness probe (DB + schema + worker pool; `503` if degraded) |

### Authentication (`api/v1/auth.py`)
| Method | Endpoint | Auth / Roles | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | Public (rate-limited) | Verify credentials, issue JWT access + refresh tokens & HttpOnly/CSRF cookies |
| `POST` | `/api/v1/auth/refresh` | Refresh token (cookie/body) | Rotate refresh token (persistently revokes old JTI) & issue fresh pair |
| `POST` | `/api/v1/auth/logout` | Any authenticated | Persistently revoke access & refresh JTIs and clear cookies |
| `GET` | `/api/v1/auth/me` | Any authenticated | Return active user profile & resolved permission list |
| `POST` | `/api/v1/auth/change-password` | Any authenticated | Verify current password and hash new password |

### User Management & Audit Logs (`api/v1/users.py`)
| Method | Endpoint | Auth / Roles | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/users` | `admin` | Paginated list of institutional users (filterable by `role`, `department_id`) |
| `POST` | `/api/v1/users` | `admin` | Create user with role, dept, linked entity, and `can_approve_timetable` |
| `PUT` | `/api/v1/users/{user_id}` | `admin` | Update role, approval permission, active status, or password reset |
| `GET` | `/api/v1/audit-logs` | `admin` | Immutable paginated audit trail (`action`, `entity_type`, `user_id` filters) |

### Academic Structure & Resources (`departments.py`, `academic_years.py`, `divisions.py`, `batches.py`, `subjects.py`, `teachers.py`, `rooms.py`)
| Method | Endpoint | Auth / Roles | Purpose |
|---|---|---|---|
| `POST/PUT/DELETE` | `/api/v1/departments[/{id}]` | `admin` | Create, update, delete departments |
| `GET` | `/api/v1/departments[/{id}]` | Any authenticated | List/get departments (scoped to own dept for non-admins) |
| `POST` / `GET` | `/api/v1/academic-years[/{id}]` | `admin` (write) / Any auth (read) | Manage/view academic years (dept-scoped) |
| `POST` / `GET` | `/api/v1/divisions[/{id}]` | `admin` (write) / Any auth (read) | Manage/view divisions (students isolated to own division) |
| `POST` / `GET` | `/api/v1/batches` | `admin` (write) / Any auth (read) | Manage/view lab batches (students isolated to own division) |
| `POST` / `GET` | `/api/v1/subjects[/{id}]` | `admin` (write) / Any auth (read) | Manage/view curriculum subjects (dept-scoped) |
| `POST/PUT` / `GET` | `/api/v1/teachers[/{id}]` | `admin` (write) / `admin`,`coordinator`,`teacher` (read) | Manage/view faculty (`teacher` sees own profile only; `student` gets `403`) |
| `POST` / `GET` | `/api/v1/rooms[/{id}]` | `admin` (write) / `admin`,`coordinator`,`teacher` (read) | Manage/view classrooms & labs (`student` gets `403`) |

### Timetable Lifecycle & Approvals (`api/v1/timetable.py`)
| Method | Endpoint | Auth / Roles | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/timetable/generate` | `admin`, `coordinator` | Synchronous CP-SAT generation + independent validation + persistence |
| `POST` | `/api/v1/timetable/generate/async` | `admin`, `coordinator` | Non-blocking background generation (`202` + `run_id`; `409` if dept busy) |
| `GET` | `/api/v1/timetable/runs/{run_id}` | `admin`, `coordinator` | Poll generation run status, diagnostics, and resulting `version_id` |
| `POST` | `/api/v1/timetable/validate` | `admin`, `coordinator` | Re-run independent validator on a persisted version |
| `GET` | `/api/v1/timetable/versions` | Any authenticated | List versions (Teacher/Student: published + own dept only) |
| `GET` | `/api/v1/timetable/versions/{id}` | Any authenticated | Version details (Teacher: own sessions; Student: own division/batch sessions; unpublished → `403`) |
| `POST` | `/api/v1/timetable/versions/{id}/submit` | `admin`, `coordinator` | Submit candidate for approval (`422` if Level A violations > 0) |
| `POST` | `/api/v1/timetable/versions/{id}/approve` | `admin` or authorized `coordinator` | Approve `pending_approval` version with optional comment |
| `POST` | `/api/v1/timetable/versions/{id}/reject` | `admin` or authorized `coordinator` | Reject `pending_approval` version with optional reason |
| `POST` | `/api/v1/timetable/versions/{id}/publish` | `admin` or authorized `coordinator` | Publish `approved` version (`422` on hard violations, `409` on unapproved/duplicate; archives prior published) |
| `GET` | `/api/v1/timetable/compare` | `admin`, `coordinator` | Structured diff (`added`, `removed`, `moved`, `unchanged`) between two versions |
| `POST` | `/api/v1/timetable/repair` | `admin`, `coordinator` | Localized CP-SAT repair keeping frozen/unaffected sessions pinned |

### AI Assistant & Teacher Requests (`api/v1/ai.py`, `api/v1/requests.py`)
| Method | Endpoint | Auth / Roles | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/ai/status` | `admin`, `coordinator` | Active LLM provider name, availability, capabilities |
| `POST` | `/api/v1/ai/interpret` | `admin`, `coordinator` | Parse English prompt into DB-grounded `InterpretedConstraint` list |
| `POST` | `/api/v1/ai/explain` | `admin`, `coordinator` | Grounded Markdown explanation for generation runs, violations, or diffs |
| `POST` | `/api/v1/requests` | `teacher` | Submit own availability/schedule change request |
| `GET` | `/api/v1/requests[/{id}]` | `admin`, `coordinator`, `teacher` | View requests (`teacher`: own only; `coordinator`: own dept) |
| `POST` | `/api/v1/requests/{id}/review` | `admin`, `coordinator` | Approve or reject a pending teacher request |

---

## 12. AI Assistant Workflow & Independent Gemini Configuration

### Supported Constraints & Confirmation Flow
- **Hard (`HARD`):** `teacher_unavailability` (e.g. *"no classes after 2 PM"* → slots 7–10, *"unavailable on Friday"*), `practical_block` (e.g. *"avoid scheduling practicals on Monday"*).
- **Soft (`SOFT`):** `teacher_preference` / `division_preference` (e.g. *"prefer morning slots"* → slots 1–4), `gap_minimization` (increases gap weight), `consecutive_limit`.
- **Safety:** Unrecognized faculty names return `is_ambiguous=True`, `can_apply=False`, and `ClarificationQuestion` options from DB. Non-scheduling policies (e.g., *"work from home"*, *"free lunch"*) return `is_supported=False` with rationale. Constraints are **never** applied until confirmed by the user and passed in `confirmed_constraints`.
- **Offline Fallback:** When `GEMINI_API_KEY` is unset, or if Gemini returns an HTTP error/timeout/malformed JSON, `GeminiLLMProvider` falls back transparently to `MockLLMProvider` without interrupting CP-SAT generation.

### How the Next Developer Should Configure & Verify Live Gemini Independently
> **Important:** No Gemini API key is configured in this repository, and live Gemini verification has **not** been performed.

1. Obtain a Gemini API key independently and set it ONLY in your local uncommitted `backend/.env` (or deployment secret manager):
   ```env
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=<your-real-key-never-commit>
   GEMINI_MODEL=gemini-1.5-flash
   ```
2. Restart FastAPI and verify `GET /api/v1/ai/status` (authenticated as Admin/Coordinator) reports `"provider": "gemini (gemini-1.5-flash)"` and `"is_available": true`.
3. Send a real prompt to `POST /api/v1/ai/interpret` (e.g., `"Give Dr. Priya Sharma no classes after 2 PM and avoid scheduling practicals on Monday"`):
   - Verify the JSON conforms to `InterpretationResponse` and `target_id` matches Dr. Priya Sharma's actual UUID in PostgreSQL.
   - Test an unknown teacher name (e.g. `"Give Prof. Unknown Person no classes on Friday"`) and confirm `is_ambiguous=true` with no fabricated UUID.
   - Test `POST /api/v1/ai/explain` on an existing version ID and verify output reflects actual DB session/violation counts.
4. Confirm `git status` shows no committed `.env` or secret files.

---

## 13. Timetable Generation, Validation, Repair, Comparison & Publishing

- **Solver Constraints (`backend/app/engine/solver.py`):** Enforces exact weekly session counts (`H1`), teacher/room/division/batch no-overlap (`H2`–`H5`), 2-slot consecutive practical blocks (`H6`), teacher unavailability across both slots of practicals (`H7`), room type & capacity matching (`H8`), `blocked_practical_days`, and pinned sessions for repair. Optimizes teacher preferred slots (`S1`) and configurable objective weights.
- **Validator Rules (`backend/app/engine/validator.py`):**
  - **Level A (Hard — blocks submit/approve/publish):** `A01` teacher double-booked, `A02` room double-booked, `A03` division double-booked, `A04` batch double-booked, `A05` room capacity exceeded, `A06` practical in non-lab, `A07` unknown assignment, `A08` teacher unavailable slot, `A09` invalid working day/slot, `A10` weekly count mismatch, `A11` practical on blocked day.
  - **Level B (Policy):** `B01` weekly workload cap exceeded, `B02` >2 consecutive sessions, `B03` practical single-slot duration.
  - **Level C (Soft):** `C01` idle gaps, `C02` non-preferred slot, `C03` uneven weekly spread.
- **Localized Repair:** `POST /api/v1/timetable/repair` locks all `is_frozen=True` and unaffected sessions from `source_version_id`, re-solves only `affected_assignment_ids`, validates the combined timetable, and persists a new version linked via `parent_version_id` with `is_repair=True`.
- **Versioning & Atomic Publication:** Publishing runs inside a single PostgreSQL transaction: checks `status == 'approved'`, verifies 0 Level A violations, archives any currently published version for the same `(department_id, academic_year_code, semester)`, marks the target `published`, and writes `TIMETABLE_PUBLISH` to `audit_logs`.

---

## 14. Installation and Local Development Setup

### Prerequisites
- Python `3.10+`
- PostgreSQL `18` (or `16+`) with `psql`, `pg_dump`, `pg_restore`
- Git

### Install Dependencies
```bash
git clone https://github.com/Anmol-tech17/eduplus-ai-timetable-maker.git
cd "Eduplus AI Timetable Maker"
python -m pip install -r backend/requirements.txt
```

---

## 15. Environment Variables and Configuration

Create `backend/.env` from `backend/.env.example` (for local dev) or `.env.production.example` (for staging/production). **Never commit `.env` files.**

| Variable | Dev Default | Production Requirement |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` (triggers `validate_production_config()` at startup) |
| `SECRET_KEY` | Dev placeholder | **Required:** >=32 random chars (`openssl rand -hex 32`) |
| `DATABASE_URL` | `postgresql+psycopg2://postgres@127.0.0.1:5433/eduplus_db` | **Required:** Non-test PostgreSQL URL with strong credentials |
| `TEST_DATABASE_URL` | `postgresql+psycopg2://postgres@127.0.0.1:5433/eduplus_test_db` | Test suite only |
| `ALLOWED_ORIGINS` | Localhost ports + `null` | **Required:** Explicit HTTPS origin(s); `*` and `null` are rejected |
| `COOKIE_AUTH_ENABLED` / `COOKIE_SECURE` | `false` / `false` | `true` / `true` (startup fails if cookie auth enabled without `COOKIE_SECURE=true`) |
| `COOKIE_SAMESITE` | `lax` | `strict` or `lax` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | `60` / `7` | Recommended `15`–`30` min / `7` days |
| `LOGIN_RATE_LIMIT_MAX_ATTEMPTS` / `_WINDOW_SECONDS` | `10` / `60` | Tune per institutional network |
| `ENABLE_DEV_FALLBACKS` / `ENABLE_DOCS` | `true` / `true` | `false` / `false` (`ENABLE_DEV_FALLBACKS=true` fails startup in production) |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `text` | `INFO` / `json` |
| `SOLVER_MAX_WORKERS` | `2` | Match available CPU cores (each CP-SAT run uses up to 4 internal workers) |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_RECYCLE` | `10` / `20` / `1800` | Tune against PostgreSQL `max_connections` |
| `LLM_PROVIDER` / `GEMINI_API_KEY` / `GEMINI_MODEL` | `auto` / `""` / `gemini-1.5-flash` | Set key via secret manager only when enabling live Gemini |

---

## 16. Database Setup, Migrations, Seeding, and Backup/Restore

```bash
# 1. Ensure PostgreSQL is running (this machine uses dedicated cluster on 127.0.0.1:5433)
# Windows example:
# & "C:\Program Files\PostgreSQL\18\bin\postgres.exe" -D "C:\Users\dell\pgdata_eduplus" -p 5433 -h 127.0.0.1

# 2. Create dev and test databases (first time only)
createdb -h 127.0.0.1 -p 5433 -U postgres eduplus_db
createdb -h 127.0.0.1 -p 5433 -U postgres eduplus_test_db

# 3. Apply Alembic migrations
python -m alembic -c backend/alembic.ini upgrade head

# 4. Seed baseline AIML institution & 4 role accounts (idempotent)
python -m backend.app.seed.seed_data
```

### Seeded Development Accounts (Change Passwords Immediately in Any Shared Environment)
| Role | Email | Password | Linked Entity |
|---|---|---|---|
| `admin` | `admin@eduplus.demo` | `admin123` | Dr. Priya Sharma (`can_approve_timetable=True`) |
| `coordinator` | `coordinator@eduplus.demo` | `coordinator123` | Prof. Vikram Singh (`can_approve_timetable=False`) |
| `teacher` | `teacher@eduplus.demo` | `teacher123` | Prof. Arjun Mehta (`Teacher.id`) |
| `student` | `student@eduplus.demo` | `student123` | Year 3 Division A (`Division.id`) |

### Backup & Restore (Verified on Local `eduplus_db` in Phase 7)
```bash
pg_dump -h 127.0.0.1 -p 5433 -U postgres -Fc -f eduplus_backup.dump eduplus_db
createdb -h 127.0.0.1 -p 5433 -U postgres eduplus_restore_verify
pg_restore -h 127.0.0.1 -p 5433 -U postgres -d eduplus_restore_verify --no-owner eduplus_backup.dump
```
Full operations runbook: [`docs/DEPLOYMENT_AND_OPERATIONS.md`](docs/DEPLOYMENT_AND_OPERATIONS.md).

---

## 17. How to Run Backend, Frontend, and Tests

```bash
# Start FastAPI backend (port 8000)
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# Serve frontend locally (port 3000) — avoids file:// cookie restrictions
python -m http.server 3000
# Then open http://127.0.0.1:3000/index.html in a browser

# Run the complete backend test suite (106 tests)
python -m pytest backend/tests -v

# Run specific suites
python -m pytest backend/tests/test_auth_rbac.py -v
python -m pytest backend/tests/test_ai_assistant.py -v
python -m pytest backend/tests/test_scale_performance.py -v -s
python -m pytest backend/tests/test_phase7_production.py -v
```

### Troubleshooting Quick Reference
- **PostgreSQL connection refused (`5433`):** Verify the dedicated cluster on port `5433` is running (separate from default system Postgres on `5432`).
- **`429 Too Many Requests` on login:** Wait `LOGIN_RATE_LIMIT_WINDOW_SECONDS` (60s) or clear `login_attempts` in dev DB.
- **Browser `403 CSRF validation failed`:** Ensure `index.html` is served via HTTP (`http://127.0.0.1:3000`) or using Bearer token mode; verify `ALLOWED_ORIGINS` includes the exact frontend origin.
- **Test DB schema drift after pulling new migrations:** Run `Base.metadata.create_all` or apply Alembic against `eduplus_test_db`.

---

## 18. Docker and Deployment Instructions

> **Status: UNVERIFIED on a live Docker / TLS host.** Files were authored in Phase 7 and must be built and verified on the target host before production rollout.

```bash
# 1. Create production env file from template (replace all placeholders)
cp .env.production.example .env

# 2. Build and start PostgreSQL 18 + FastAPI + Nginx
docker compose up -d --build

# 3. Run migrations inside API container
docker compose exec api python -m alembic -c backend/alembic.ini upgrade head

# 4. Check readiness probe
curl -fsS http://127.0.0.1/api/v1/health/ready
```
Terminate HTTPS/TLS in `deploy/nginx.conf` (or upstream load balancer) and enforce HTTPS before any public deployment. See `docs/DEPLOYMENT_AND_OPERATIONS.md` for full startup, shutdown, and recovery steps.

---

## 19. Automated Test Coverage and Reported Results

Reported from Phase 7 full suite run (`python -m pytest backend/tests -q`, **106 passed, 0 failed, 3 deprecation warnings, 102.65s** on Windows 10, 4 CPU cores, Python 3.10, PostgreSQL 18.6):

| Test File | Tests | Coverage |
|---|---:|---|
| `backend/tests/test_db_connection.py` | 2 | PostgreSQL connectivity & dialect |
| `backend/tests/test_health.py` | 2 | Root & `/api/v1/health` |
| `backend/tests/test_models.py` | 3 | Unique constraints, hierarchy FKs, PBKDF2 hashing |
| `backend/tests/test_seed.py` | 1 | Baseline seed execution & idempotency |
| `backend/tests/test_api_crud.py` | 4 | Department, academic hierarchy, teacher, room CRUD & 409/422 errors |
| `backend/tests/test_engine.py` | 30 | Validator rules A01–C02, CP-SAT hard constraints, labs, capacity, infeasibility, timeouts |
| `backend/tests/test_timetable_api.py` | 21 | Sync generation, persistence, versions, submit/approve/publish, compare, repair, runs |
| `backend/tests/test_ai_assistant.py` | 9 | Mock NLP interpretation, DB grounding, clarifications, unsupported policies, solver injection, explanations |
| `backend/tests/test_auth_rbac.py` | 20 | Auth (4 roles), expired/tampered/revoked tokens, rate limiting, RBAC, IDOR isolation, approvals, hard-violation block, audit redaction |
| `backend/tests/test_scale_performance.py` | 5 | Small (1d/2div), Medium (3d/10div), Large (5d/25div), infeasibility, repair & repeated runs |
| `backend/tests/test_phase7_production.py` | 9 | Prod config validation, refresh rotation, persistent DB revocation/rate-limit, cookie+CSRF, readiness probe, orphan recovery, Gemini fallback resilience, 11-step E2E workflow |

### Phase 7 Measured Solver Benchmarks (Actual Recorded Numbers)
- **Small (1 dept, 2 divs, 10 assignments, 20 sessions):** `OPTIMAL`, `937 ms`, `0.28 MiB` peak traced memory, `0` hard violations, `4` soft violations.
- **Medium (3 depts, 10 divs, 50 assignments, 100 sessions):** `OPTIMAL` (3/3), `5,000 ms`, `0.64 MiB` peak traced memory, `0` hard violations, `28` soft violations.
- **Large (5 depts, 25 divs, 125 assignments, 250 sessions):** `OPTIMAL` (5/5), `16,125 ms`, `0.92 MiB` peak traced memory, `0` hard violations, `95` soft violations.
- **Seed AIML E2E API + DB Persist (15 assignments, 17 rooms):** `OPTIMAL`, `1,593 ms` solve / `1,875 ms` total HTTP round-trip (`~282 ms` validation + DB persistence + audit log).

---

## 20. Known Limitations, Incomplete Functionality, and Risks

1. **Live Gemini API Verification Unverified:** All AI tests ran with `MockLLMProvider` or mocked `httpx` errors; live Gemini API behavior, latency, and JSON compliance remain unverified until tested with a real key.
2. **Individual Student Elective Enrollment Not Modeled:** Schema has aggregate `EnrollmentGroup` counts but lacks `students` / `student_elective_enrollments` tables. Student timetable isolation currently filters by `Division` + division `Batch` records only and never guesses elective membership.
3. **Docker Build & Live HTTPS/TLS Deployment Unverified:** Container build, Compose networking, and TLS termination have not been executed on a live Linux/Docker host.
4. **No Automated Browser E2E Tests:** Frontend interactions (`index.html`, `admin.html`, `teacher.html`, `student.html`) are not covered by Playwright/Cypress; manual browser QA is required across all roles.
5. **Single-Node Background Worker Pool:** Async generation uses an in-process `ThreadPoolExecutor` + DB lock. Multi-host horizontal scaling would require an external broker/queue (e.g., Celery/ARQ + Redis) and scheduled pruning of expired `revoked_tokens` / `login_attempts` rows.
6. **Prototype UI Sections Remaining:** Student/Teacher **Submit Query** and **Notifications / Notices** tabs in `teacher.html` and `student.html` remain static/prototype UI (no backend ML query service or notification engine). PDF/Excel timetable export is not implemented.
7. **Admin Request Inbox UI:** Backend `/api/v1/requests` endpoints are implemented and tested, while `admin.html` Request Inbox UI still displays local demo state when offline and should be verified against live requests during QA.
8. **Not Security-Certified:** Application-level controls are implemented, but an independent security review and penetration test are required prior to public production deployment.

---

## 21. Git Repository Information

- **Remote (`origin`):** `https://github.com/Anmol-tech17/eduplus-ai-timetable-maker.git`
- **Primary Branch:** `main` (synchronized with `origin/main`)
- **Recent Milestone Commits:**
  - `abbc7e2` — `style: align secondary accent palette to institutional yellow`
  - `48175ce` — `feat: prepare Eduplus for production deployment` (Phase 7)
  - `33e1134` — `feat: add authentication RBAC and timetable approvals` (Phase 6)
  - `b20762b` — `feat: add natural language AI timetable assistant` (Phase 5)
  - `c49596f` — `feat: integrate timetable frontend with backend APIs` (Phase 4)
  - `043d5c3` — `feat: integrate timetable generation and version lifecycle APIs` (Phase 3)
  - `4ac1ae7` — `feat: implement timetable validator and CP-SAT scheduling engine` (Phase 2)

---

## 22. Final Developer Verification Checklist

> **Execution Rule:** Do **not** mark any item complete merely because code exists. Independently execute each workflow and record **PASS**, **FAIL** (with error details), or **NOT TESTED** (with reason) alongside evidence.

### A. Repository and setup
- [ ] Clone or pull the latest remote repository.
- [ ] Confirm the correct branch and latest commit.
- [ ] Confirm the working tree is clean before making changes.
- [ ] Install dependencies successfully.
- [ ] Configure local environment variables without committing secrets.
- [ ] Start PostgreSQL and connect to the correct database.
- [ ] Run all Alembic migrations successfully.
- [ ] Start the backend and frontend successfully.

### B. Authentication and permissions
- [ ] Test login and logout.
- [ ] Test token refresh and expired-token handling.
- [ ] Test password change.
- [ ] Verify Admin, Coordinator, Teacher, and Student access restrictions.
- [ ] Verify unauthorized requests are rejected.
- [ ] Verify users cannot access another department's, teacher's, or student's restricted data.
- [ ] Verify audit logs are recorded correctly.

### C. Admin functionality
- [ ] Test department, academic year, semester, subject, course, division, batch, teacher, and room management wherever implemented.
- [ ] Test user and role management.
- [ ] Test configuration and scheduling policies.
- [ ] Test audit-log access.

### D. Timetable coordinator functionality
- [ ] Test natural-language constraint interpretation using the mock provider.
- [ ] Check that interpreted constraints are grounded in actual database entities.
- [ ] Test confirmation before applying AI-interpreted constraints.
- [ ] Generate a timetable using CP-SAT.
- [ ] Verify hard constraints and validation results.
- [ ] Test timetable editing or repair.
- [ ] Test timetable version history and comparison.
- [ ] Test submission for approval.

### E. Approval and publication
- [ ] Test approval and rejection.
- [ ] Verify hard violations prevent invalid publication.
- [ ] Publish an approved timetable.
- [ ] Verify the previous published version is handled correctly.
- [ ] Verify audit records include the relevant actors and timestamps.

### F. Teacher and student functionality
- [ ] Verify teachers can see their own timetable.
- [ ] Verify teachers cannot see other teachers' restricted information.
- [ ] Test teacher availability or change requests where implemented.
- [ ] Verify students can see their published timetable.
- [ ] Verify students cannot access unpublished versions or other divisions' restricted data.
- [ ] Confirm and document the existing elective-enrollment limitation.

### G. Solver and reliability
- [ ] Run the complete backend test suite.
- [ ] Test a small timetable generation.
- [ ] Test a larger timetable generation.
- [ ] Test an infeasible scheduling scenario.
- [ ] Test practical sessions and consecutive slots.
- [ ] Test teacher, room, division, and batch clash prevention.
- [ ] Test teacher unavailability and room capacity/type restrictions.
- [ ] Test timetable repair and repeated generation.
- [ ] Verify asynchronous generation and status polling.
- [ ] Check database persistence and error handling.

### H. GUI and deployment
- [ ] Open and test every major page.
- [ ] Test all navigation links, forms, buttons, filters, and tables.
- [ ] Check that no important function is just a visual placeholder.
- [ ] Test loading, empty, success, and error states.
- [ ] Check browser console and backend logs for errors.
- [ ] Test responsive layouts.
- [ ] Confirm white/blue/yellow design consistency.
- [ ] Verify Docker build and deployment configuration if the target environment supports it.
- [ ] Verify HTTPS/TLS before any real public deployment.

### I. Final Git verification
- [ ] Commit every intended final code change.
- [ ] Push the changes to the correct remote branch.
- [ ] Verify remote synchronization.
- [ ] Confirm no intended changes remain uncommitted.
- [ ] Record the final commit hash.
