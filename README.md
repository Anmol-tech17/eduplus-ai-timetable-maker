# EduPlus AI Timetable Maker

> **Version:** 0.1-prototype  
> **Status:** Demo-ready — documentation-first, four-page frontend prototype  
> **Department:** AIML — Example Engineering College  
> **Date:** October 2026

---

## Project Overview

EduPlus AI Timetable Maker is a college timetable management and optimization system designed for the AIML Department of Example Engineering College. It will generate, validate, publish, and maintain B.Tech academic timetables across Years 1–4 with multiple divisions, lab batches, elective enrollment groups, and complex constraint requirements.

This repository currently contains:

- A **four-page web demo** (login, admin, teacher, student dashboards)
- **18 documentation files** covering the full system design
- A **mock data layer** with realistic AIML department data
- **No real backend, solver, or database** — all scheduling is simulated

---

## Current Implementation Status

| Component | Status |
|-----------|--------|
| Login page | ✅ Implemented (mock auth) |
| Admin dashboard | ✅ Implemented (mock data) |
| Teacher dashboard | ✅ Implemented (mock data) |
| Student dashboard | ✅ Implemented (mock data) |
| Mock data layer | ✅ Complete |
| CSS design system | ✅ Complete |
| PostgreSQL schema | 📋 Designed (docs only) |
| FastAPI backend | 🔲 Not implemented |
| CP-SAT scheduler | 🔲 Not implemented |
| Independent validator | 🔲 Not implemented |
| Timetable versioning | 🔲 Not implemented |
| Repair mode | 🔲 Not implemented |
| ML query service | 🔲 Planned (future phase) |

> ⚠️ **All timetables shown in the demo are hand-crafted illustrative examples. No constraint solver has been run.**

---

## Technology Stack

### Demo (Current)
| Layer | Technology |
|-------|-----------|
| Markup | HTML5 |
| Styling | Vanilla CSS (custom design system) |
| Logic | Vanilla JavaScript (ES2020, no bundler) |
| Fonts | Inter, JetBrains Mono (Google Fonts) |
| Data | In-memory mock data (`src/data/mockData.js`) |
| Auth | `sessionStorage`-based mock session |

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

No automated tests exist in the prototype phase.

See [`docs/TESTING_STRATEGY.md`](docs/TESTING_STRATEGY.md) for the planned test strategy covering unit tests, validator tests, solver integration tests, property-based tests, and UI interaction tests.

---

## Documentation

All technical documentation is in the `docs/` directory. Start with:

1. [`docs/PROJECT_SPECIFICATION.md`](docs/PROJECT_SPECIFICATION.md) — goals and requirements
2. [`docs/DOMAIN_MODEL.md`](docs/DOMAIN_MODEL.md) — academic domain entities
3. [`docs/ER_DIAGRAM.md`](docs/ER_DIAGRAM.md) — database entity relationships
4. [`docs/SCHEDULING_RULES.md`](docs/SCHEDULING_RULES.md) — constraint catalogue
5. [`docs/SYSTEM_ARCHITECTURE.md`](docs/SYSTEM_ARCHITECTURE.md) — component design
6. [`docs/OPEN_QUESTIONS_AND_ASSUMPTIONS.md`](docs/OPEN_QUESTIONS_AND_ASSUMPTIONS.md) — unresolved decisions
7. [`docs/IMPLEMENTATION_ROADMAP.md`](docs/IMPLEMENTATION_ROADMAP.md) — phased plan

---

## Contact and Continuation

This prototype was built as the documentation-first foundation for EduPlus. A developer continuing this project should:

1. Confirm open questions in `OPEN_QUESTIONS_AND_ASSUMPTIONS.md` with the institution.
2. Implement the PostgreSQL schema from `DATABASE_SCHEMA.md`.
3. Build the independent validator from `VALIDATION_AND_INFERENCE.md`.
4. Build the CP-SAT scheduler from `SCHEDULER_DESIGN.md`.
5. Build the FastAPI backend from `API_SPECIFICATION.md`.
6. Migrate the frontend to React + Vite + TypeScript.
