# EduPlus — Implementation Roadmap

> **Document ID:** IMPLEMENTATION_ROADMAP  
> **Version:** 0.1

---

## Phase 0 — Prototype Demo (Current — October 2026)

**Goal:** Presentable four-page web demo for stakeholder review.

### Deliverables
- [x] Four-page HTML/CSS/JS demo (login, admin, teacher, student)
- [x] Realistic mock data layer
- [x] Admin timetable grid with conflict demonstration
- [x] Teacher request submission workflow
- [x] Student timetable and query submission
- [x] README and core documentation

### Acceptance Criteria
- All four pages exist and are navigable
- Login routes to correct dashboard per role
- Timetable grid is legible and populated
- Admin can inspect a simulated conflict with rule explanation
- Publish button disabled for invalid/incomplete candidate
- Teacher request form validates and adds to local state
- Student query submits with clear ML-future notice
- No fake solver or ML claims

### Dependencies
None — self-contained prototype

---

## Phase 1 — Domain Model and Database (November 2026)

**Goal:** Implement the relational schema and seed data; establish the data foundation.

### Deliverables
- [ ] PostgreSQL schema (all entities from ER_DIAGRAM.md)
- [ ] Alembic migrations
- [ ] Seed data: AIML department, Year 3 divisions, teachers, rooms, subjects, assignments
- [ ] Import validation scripts
- [ ] Domain validation tests (uniqueness, FK integrity, lunch policy coherence)
- [ ] FastAPI project scaffold with SQLAlchemy models

### Open Questions to Resolve First
- Q01: L-T-P credit mapping
- Q02: Elective group membership source
- Q04: Lunch slot configuration

### Acceptance Criteria
- Schema matches ER_DIAGRAM.md exactly
- All FK constraints enforced
- Seed data imports cleanly
- Domain validation tests pass

---

## Phase 2 — Backend API (November–December 2026)

**Goal:** FastAPI backend with auth, RBAC, and academic data CRUD.

### Deliverables
- [ ] Authentication (JWT or session; TBD per Q11)
- [ ] Role-based access control middleware
- [ ] Academic data endpoints (departments, years, divisions, batches, subjects, rooms, teachers)
- [ ] Teaching assignment endpoints
- [ ] Session requirement endpoints
- [ ] Lunch policy configuration endpoints
- [ ] Room and teacher availability endpoints
- [ ] Enrollment group management endpoints
- [ ] Teacher request endpoints
- [ ] Student query endpoints (stub — ML integration later)
- [ ] Audit log writes for all sensitive actions
- [ ] OpenAPI documentation

### Acceptance Criteria
- All endpoints return correct data
- Role restrictions enforced on every protected endpoint
- Backend rejects unauthorized actions (not just frontend)
- Audit log populated for admin writes

---

## Phase 3 — Independent Validator (December 2026)

**Goal:** A standalone Python module that validates any timetable snapshot against all Level A and B rules.

### Deliverables
- [ ] Validator module (no DB dependency, pure function)
- [ ] Level A checks: A01–A14
- [ ] Level B checks: B01–B08
- [ ] Conflict explanation output (structured JSON)
- [ ] Violation records written to DB via service layer
- [ ] Test suite: 18+ scenarios from TESTING_STRATEGY.md
- [ ] Publication eligibility gate using validator

### Acceptance Criteria
- All 18 test scenarios from specification pass or fail correctly
- Validator is completely independent of the solver
- No Level A violation can be bypassed
- Conflict explanations are plain-language and entity-specific

---

## Phase 4 — CP-SAT Scheduler (January–February 2027)

**Goal:** First working constraint solver producing complete timetables.

### Deliverables
- [ ] Pre-solve feasibility checks (all 12 from SCHEDULER_DESIGN.md)
- [ ] CP-SAT model: decision variables, session intervals
- [ ] Level A constraints in model (A01–A12)
- [ ] Level B constraints in model (B01–B08)
- [ ] Level C soft objectives (P01–P10, lexicographic)
- [ ] Single candidate generation
- [ ] Solver status mapping (feasible, infeasible, timeout, unknown)
- [ ] Partial diagnostic draft on failure
- [ ] Multiple candidates (3 by default)
- [ ] Integration with background worker
- [ ] API endpoint: trigger generation, poll status, retrieve candidates

### Open Questions to Resolve First
- Q01, Q02, Q03, Q04, Q07, Q10

### Acceptance Criteria
- Feasible test dataset produces complete timetable
- Teacher double-booking impossible
- Room double-booking impossible
- Student group overlap impossible
- Lab continuity enforced
- Lunch constraint enforced
- Validator passes on every produced candidate
- Timeout does not claim infeasibility

---

## Phase 5 — Conflict Explanation and Admin Workflow (February 2027)

**Goal:** Admin can understand why a timetable is infeasible and what to do about it.

### Deliverables
- [ ] Structured conflict explanation endpoint
- [ ] Plain-language explanation generation from rule violations
- [ ] Pre-solve diagnostic output with entity names and counts
- [ ] Admin UI: conflict detail panel (expand from prototype)
- [ ] Admin UI: candidate comparison view with scores
- [ ] Publication workflow with multi-step approval

---

## Phase 6 — Timetable Versioning and Repair (March 2027)

**Goal:** Published timetables can be safely modified without overwriting history.

### Deliverables
- [ ] Version lifecycle management (draft → published → archived)
- [ ] Repair mode in scheduler (frozen sessions, minimal change objective)
- [ ] Change request workflow (teacher submits → admin approves → repair runs)
- [ ] Session exception recording (cancellations, substitutions, one-off changes)
- [ ] Repair run audit record (what changed and why)
- [ ] Rollback to previous version
- [ ] Admin UI: version comparison, change summary

### Open Questions to Resolve First
- Q09: Policy relaxation approval rules
- Q15: Make-up session policy

---

## Phase 7 — Teacher and Student Views (March 2027)

**Goal:** React frontend with real API integration replaces the prototype.

### Deliverables
- [ ] React + TypeScript + Vite + Tailwind migration
- [ ] Teacher: real timetable from API, real request submission
- [ ] Student: real published timetable filtered by division/batch/elective group
- [ ] Notification system (email or in-app)
- [ ] Mobile-responsive layout

---

## Phase 8 — ML Query Service Integration (April 2027+)

**Goal:** Structured query routing for teacher and student scheduling questions.

### Deliverables
- [ ] Query category classification
- [ ] Deterministic DB query handler (slot/room lookups)
- [ ] Constraint engine query handler (availability, feasibility checks)
- [ ] AI gateway interface (intent parsing, structured routing)
- [ ] ML model integration for complex questions (when model is ready)
- [ ] Privacy gate: no PII sent to external services

### Open Questions to Resolve First
- Q02, Q13: Student data source and privacy requirements

---

## Phase 9 — Advanced Features (May 2027+)

- [ ] PDF/Excel timetable export
- [ ] iCal feed per teacher/student
- [ ] Multi-department support
- [ ] Role-specific notification preferences
- [ ] Performance benchmarks against large datasets (40 teachers, 6 divisions/year)
- [ ] Solver reproducibility verification with stored seeds
- [ ] Bulk import from college ERP

---

## Dependency Graph

```
Phase 0 (Demo) → Phase 1 (DB) → Phase 2 (API) → Phase 3 (Validator)
                                                        ↓
                                               Phase 4 (Solver) → Phase 5 (Conflicts)
                                                                         ↓
                                                              Phase 6 (Versioning/Repair)
                                                                         ↓
                                                              Phase 7 (React Frontend)
                                                                         ↓
                                                              Phase 8 (ML Queries)
                                                                         ↓
                                                              Phase 9 (Advanced)
```

> ⚠️ **Phase 3 (Validator) must be implemented and tested before Phase 4 (Solver).** The validator's independence from the solver is a core architectural requirement.
