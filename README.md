# EduPlus AI Timetable Maker

> **Version:** 0.4.0 (Phase 4 Complete)  
> **Status:** Production-ready backend & integrated frontend — Live CP-SAT scheduling, PostgreSQL persistence, versioning & diffing  
> **Department:** AIML — Example Engineering College  
> **Date:** October 2026 – November 2026

---

## Project Overview

EduPlus AI Timetable Maker is an enterprise academic timetable management and constraint optimization platform developed for educational institutions. The system models multi-department, multi-year cohorts with divisions, laboratory batches, teacher availability, room suitability, and elective enrollment groups.

Equipped with a **Google OR-Tools CP-SAT constraint optimization engine**, a decoupled **independent validator**, a **FastAPI backend** running on dedicated PostgreSQL, and an **integrated web interface**, EduPlus automates the generation, auditing, versioning, comparison, and localized repair of institutional schedules.

---

## Current Implementation Status

| Component | Status | Details |
|-----------|--------|---------|
| Login page | ✅ Implemented | Prototype UI + real backend user hashing (pbkdf2-sha256) |
| Admin dashboard | ✅ Implemented & Integrated | Live CP-SAT generation, validation results, version dropdowns, comparison diffs, localized repair |
| Teacher dashboard | ✅ Implemented & Integrated | Live timetable view filtered to assigned faculty sessions + local fallback |
| Student dashboard | ✅ Implemented & Integrated | Live timetable view filtered to division, batch, and elective groups + local fallback |
| API Service Layer | ✅ Complete | REST client (`src/js/api.js`) connecting frontend to FastAPI backend endpoints |
| CSS design system | ✅ Complete | Institutional white background, primary blue highlights, secondary orange accents |
| PostgreSQL schema | ✅ Implemented | PostgreSQL 18 dedicated cluster, 26 physical tables via Alembic `5cc27eb93e43` |
| FastAPI backend | ✅ Implemented | 33 endpoints (Health, Academic CRUD, Generation, Validation, Versioning, Compare, Repair, Runs) |
| CP-SAT scheduler | ✅ Implemented | Google OR-Tools 9.15 integer programming formulation with hard/soft constraints |
| Independent validator | ✅ Implemented | Standalone rule engine (Level A hard, Level B policy, Level C soft preferences) |
| Timetable versioning | ✅ Implemented | Version tracking, session diffing (`/timetable/compare`), audit runs, publish lifecycle |
| Localized repair mode | ✅ Implemented | Pinned session preservation and localized re-optimization (`/timetable/repair`) |
| ML / LLM query service | 🔲 Planned | Phase 5 natural language explanation & query handling |

---

## Technology Stack

### Backend & Optimization Engine (Phase 0 – Phase 3)
| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.10 |
| Framework | FastAPI 0.115 + Pydantic v2 + Uvicorn |
| Database | PostgreSQL 18.6 (dedicated local cluster on port 5433) |
| ORM & Migrations | SQLAlchemy 2.0 + Alembic |
| Constraint Solver | Google OR-Tools 9.15 CP-SAT (`ortools`) |
| Validation Engine | Independent multi-level rule validator (`backend/app/engine/validator.py`) |
| Test Suite | Pytest 9.2 + Pytest-Asyncio + HTTPX TestClient (62 automated tests) |

### Frontend Prototype (Phase 0)
| Layer | Technology |
|-------|-----------|
| Markup & Styling | HTML5 + Vanilla CSS design system |
| Logic & API Client | Vanilla JS (ES2020) + `src/js/api.js` (Fetch REST client) |
| Data | In-memory mock data (`src/data/mockData.js`) |

### Planned Production Stack
| Layer | Technology |
|-------|-----------|
| Frontend | React + TypeScript + Vite + Tailwind CSS |
| Backend | Python + FastAPI (REST/JSON) |
| Database | PostgreSQL |
| Scheduler | Python package — Google OR-Tools CP-SAT |
| Background jobs | Celery or equivalent worker |
| AI gateway | Provider-independent interface (future) |

---

## Prerequisites

- A modern web browser (Chrome, Firefox, Edge, Safari)
- No build tools, Node.js, or Python required for the demo

---

## Installation

```bash
# Clone or download the project
# No npm install, pip install, or build step is required for the prototype

# Open index.html in a browser — or use a local HTTP server:
npx serve .
# or
python -m http.server 8000
```

---

## How to Run the Demo

1. Open `index.html` in a browser (or start a local server and navigate to `http://localhost:8000`).
2. Use one of the demo credentials below to log in.
3. After login, you will be redirected to the role-appropriate dashboard.
4. Use the sidebar navigation to explore all panels.

### Demo Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@eduplus.demo` | `admin123` |
| Teacher | `teacher@eduplus.demo` | `teacher123` |
| Student | `student@eduplus.demo` | `student123` |

> ⚠️ **These credentials are not real. Authentication is mocked using `sessionStorage`. This system has no production security.**

---

## Project Structure

```
EduPlus AI Timetable Maker/
├── index.html              # Page 1: Login
├── admin.html              # Page 2: Admin Dashboard
├── teacher.html            # Page 3: Teacher Dashboard
├── student.html            # Page 4: Student Dashboard
│
├── src/
│   ├── css/
│   │   └── style.css       # Full CSS design system
│   ├── js/
│   │   ├── admin.js        # Admin dashboard logic
│   │   ├── teacher.js      # Teacher dashboard logic
│   │   └── student.js      # Student dashboard logic
│   └── data/
│       └── mockData.js     # Mock data layer (all demo data)
│
└── docs/
    ├── PROJECT_SPECIFICATION.md
    ├── DOMAIN_MODEL.md
    ├── ER_DIAGRAM.md
    ├── DATABASE_SCHEMA.md
    ├── SCHEDULING_RULES.md
    ├── SCHEDULER_DESIGN.md
    ├── VALIDATION_AND_INFERENCE.md
    ├── SYSTEM_ARCHITECTURE.md
    ├── API_SPECIFICATION.md
    ├── ROLE_ACCESS_MATRIX.md
    ├── TIMETABLE_VERSIONING_AND_REPAIR.md
    ├── AI_AND_ML_ROADMAP.md
    ├── TESTING_STRATEGY.md
    ├── IMPLEMENTATION_ROADMAP.md
    ├── OPEN_QUESTIONS_AND_ASSUMPTIONS.md
    ├── REQUIREMENTS_TRACEABILITY.md
    └── CHANGELOG.md
```

---

## Demo Features Walkthrough

### Admin Dashboard
- **Dashboard overview**: department stats, elective group conflict map, policy summary
- **Timetable Grid**: interactive weekly grid for Year 3 / Division A; click sessions for details
- **Filters**: filter by teacher or room — non-matching slots go blank
- **Generate & Validate**: two mock candidates — Candidate 1 (valid, publishable), Candidate 2 (diagnostic with 3 hard violations)
- **Conflict Report**: detailed Level A violation explanations (A01, A03/A04, A08) with rule IDs
- **Publish gate**: disabled for Candidate 2; simulated publish on Candidate 1
- **Request Inbox**: approve/reject teacher requests (local state only)

### Teacher Dashboard
- **My Timetable**: filtered view showing only assigned sessions
- **Today's Classes**: Wednesday schedule with substitution notice
- **Submit Request**: working form — validates fields, adds to local request list
- **My Requests**: history with status badges

### Student Dashboard
- **Overview**: identity card, next class highlight, today at a glance
- **My Timetable**: grid filtered to Division A / Batch B1 / CV elective sessions
- **Today's Classes**: Wednesday sessions with group labels
- **Notices**: cancellation and substitution notices
- **Submit Query**: form with ML-future notice; query history displayed

---

## Demo — What Is Mocked

| Feature | Status in Demo |
|---------|---------------|
| Authentication | Mocked via `sessionStorage` |
| Timetable scheduling | Hand-crafted mock data, no solver |
| CP-SAT solver | Not implemented — simulate button shows mock result |
| Publishing | Local state update only, no database write |
| Repair operation | Not implemented |
| Teacher request processing | Local state only |
| Student query ML model | Not implemented — shows future-phase notice |
| Conflict detection | Pre-populated in mock data |
| Validation | Pre-populated results in mock data |

---

## Known Limitations

1. **No backend**: all data resets on page refresh.
2. **No real solver**: the Generate button simulates a 1.8-second delay and returns a pre-populated result.
3. **No real authentication**: `sessionStorage` can be manually overridden.
4. **Single timetable shown**: only Year 3 Division A is fully populated.
5. **No responsive sidebar on mobile**: sidebar hidden below 900px width.
6. **No export**: PDF/Excel export not implemented.
7. **No real notifications**: all notifications are static mock data.

---

## Tests

A comprehensive 63-test automated test suite is implemented across:
- **Database & Dialect:** `backend/tests/test_db_connection.py`
- **Domain Models & Constraints:** `backend/tests/test_models.py`
- **Institutional Seeding:** `backend/tests/test_seed.py`
- **Institutional CRUD APIs:** `backend/tests/test_api_crud.py`
- **System Health:** `backend/tests/test_health.py`
- **Validator & CP-SAT Engine:** `backend/tests/test_engine.py` (30 tests: hard/policy/soft rules, capacity, multi-slot practicals, infeasibility, solver timeouts)
- **Timetable Lifecycle APIs:** `backend/tests/test_timetable_api.py` (21 tests: generation, persistence, versioning, comparison, localized repair, run diagnostics, publish lifecycle)

```bash
# Run the entire test suite
python -m pytest backend/tests -v

# Run engine tests only
python -m pytest backend/tests/test_engine.py -v

# Run timetable API tests only
python -m pytest backend/tests/test_timetable_api.py -v
```

---

## Documentation

All technical documentation is in the `docs/` directory. Key design references:

1. [`docs/PROJECT_SPECIFICATION.md`](docs/PROJECT_SPECIFICATION.md) — goals and requirements
2. [`docs/DOMAIN_MODEL.md`](docs/DOMAIN_MODEL.md) — academic domain entities
3. [`docs/ER_DIAGRAM.md`](docs/ER_DIAGRAM.md) — database entity relationships
4. [`docs/SCHEDULING_RULES.md`](docs/SCHEDULING_RULES.md) — constraint catalogue
5. [`docs/SCHEDULER_DESIGN.md`](docs/SCHEDULER_DESIGN.md) — CP-SAT formulation and objective weights
6. [`docs/VALIDATION_AND_INFERENCE.md`](docs/VALIDATION_AND_INFERENCE.md) — independent validator design
7. [`docs/SYSTEM_ARCHITECTURE.md`](docs/SYSTEM_ARCHITECTURE.md) — backend & service architecture
8. [`docs/API_SPECIFICATION.md`](docs/API_SPECIFICATION.md) — REST API endpoints
9. [`docs/TIMETABLE_VERSIONING_AND_REPAIR.md`](docs/TIMETABLE_VERSIONING_AND_REPAIR.md) — versioning, diffing & repair
10. [`docs/IMPLEMENTATION_ROADMAP.md`](docs/IMPLEMENTATION_ROADMAP.md) — phased development roadmap
