# EduPlus — Project Specification

> **Document ID:** PROJECT_SPECIFICATION  
> **Version:** 0.1  
> **Department:** AIML — Example Engineering College

---

## 1. Problem Statement

College academic timetable scheduling is a complex combinatorial optimization problem. Manually producing a conflict-free timetable for a department with 4 years, 10 divisions, 40 teachers, 20 classrooms, and 10 laboratories — while respecting dozens of institutional rules, teacher availability, lab batch requirements, and elective enrollment groups — is error-prone, time-consuming, and difficult to audit.

EduPlus AI Timetable Maker automates this process using a constraint optimization engine, provides explainable conflict diagnostics, and maintains a versioned, auditable record of all timetable changes.

---

## 2. Goals

1. Generate feasible weekly timetables satisfying all mandatory institutional constraints.
2. Optimize timetable quality against configurable soft preferences.
3. Validate every candidate independently of the solver.
4. Explain conflicts, infeasibility, and constraint violations in plain language.
5. Support timetable versioning, repair, and audit history.
6. Provide role-appropriate views for administrators, teachers, and students.
7. Support teacher scheduling requests and student queries.
8. Maintain correctness and explainability over automation convenience.

---

## 3. Non-Goals (Version 1)

- Attendance tracking
- Examination scheduling
- Multi-department scheduling (single department only)
- Co-teaching (one teacher per session)
- Partial-hour scheduling
- Mobile application
- Integration with external college ERP (import manually or via CSV)
- Real-time notifications (email/push in v1 scope is limited)
- Student individual timetable customization

---

## 4. Stakeholders and Roles

| Role | Description | Capabilities |
|------|-------------|-------------|
| **Admin (HoD/Coordinator)** | Department scheduling coordinator | Full scheduling authority within the department; cannot bypass Level A rules |
| **Teacher** | Teaching staff member | View own timetable; submit requests; submit queries |
| **Student** | B.Tech student | View published timetable for own division/batch/elective group; submit queries |

---

## 5. Functional Requirements

### FR01 — Academic Data Management
The system shall allow an administrator to create and manage departments, years, divisions, batches, subjects, teachers, rooms, and enrollment groups.

### FR02 — Teaching Assignments
The system shall maintain a teaching assignment record specifying which teacher teaches which subject for which division/batch/enrollment group.

### FR03 — Session Requirements
The system shall derive and store weekly session requirements from subject LTP credits and the institution's credit mapping.

### FR04 — Scheduling Configuration
The system shall support configuration of working days, working hours, lunch policies, teacher availability, room unavailability, and blocked periods.

### FR05 — Timetable Generation
The system shall generate candidate weekly timetables using a CP-SAT constraint solver.

### FR06 — Pre-Solve Validation
The system shall perform feasibility checks before invoking the solver and return precise diagnostics when the input is infeasible.

### FR07 — Independent Validation
The system shall validate every timetable candidate using a module that is completely independent of the solver.

### FR08 — Conflict Explanation
The system shall produce plain-language, entity-specific explanations for every constraint violation.

### FR09 — Candidate Selection and Publication
The system shall allow an administrator to compare candidates, select one, and publish it as the official timetable.

### FR10 — Publication Gate
The system shall prevent publication of any timetable candidate that has Level A violations or is incomplete.

### FR11 — Timetable Versioning
The system shall maintain an immutable history of all timetable versions.

### FR12 — Repair Mode
The system shall support repair operations that produce a new timetable version by minimizing changes to an existing published version.

### FR13 — Session Exceptions
The system shall support date-specific exceptions (cancellations, substitutions) layered on top of the weekly template without modifying the template.

### FR14 — Teacher Requests
The system shall allow teachers to submit reschedule, substitution, and cancellation requests; allow admins to approve or reject; trigger a repair operation on approval.

### FR15 — Student Queries
The system shall accept student scheduling queries. Automated query processing by ML models is planned for a future phase. The interface is present in Version 1 with manual admin response.

### FR16 — Role-Appropriate Views
The system shall display only the data appropriate for each role. Teachers see their own sessions; students see their division/batch/elective group sessions only.

### FR17 — Audit Log
The system shall log all sensitive administrative actions with actor, timestamp, action type, and before/after state.

---

## 6. Non-Functional Requirements

| NFR | Description |
|-----|-------------|
| NFR01 | Solver must produce a complete timetable within a configurable time limit (default 60 seconds) |
| NFR02 | All authorization checks must be enforced server-side |
| NFR03 | Published timetable versions must be immutable |
| NFR04 | The scheduler must be independently testable without a database or HTTP server |
| NFR05 | The validator must be independent of the solver's constraint construction |
| NFR06 | The system must never claim that a timetable is valid if it contains a Level A violation |
| NFR07 | Individual student names must not be sent to external AI/ML services |
| NFR08 | The system must distinguish solver timeout from proven infeasibility |

---

## 7. Version 1 Scope

| In Scope | Out of Scope |
|----------|-------------|
| One department, 4 years | Multi-department |
| Up to 6 divisions/year | Examination scheduling |
| Up to 40 teachers | Attendance tracking |
| Up to 20 classrooms, 10 labs | Student ERP integration |
| 3 batches/division | Co-teaching |
| Elective enrollment groups | ML query processing (stub only) |
| Weekly timetable template | Calendar integration |
| Date-specific exceptions | Mobile app |
| Timetable versioning and repair | |
| Teacher requests and admin approval | |

---

## 8. Confirmed Decisions

| ID | Decision |
|----|---------|
| C01 | Electives may run simultaneously if enrollment groups do not conflict |
| C02 | Lab batches scheduled flexibly — minimize idle time |
| C03 | Infeasible generation returns partial diagnostic draft (never publishable) |
| C04 | Published timetable changes use repair mode — minimize changes |
| C05 | Lunch window: 12:00–15:00; configurable per division |
| C06 | LLM may not place sessions or determine validity |
| C07 | Student names must not be sent to an LLM |
| C08 | Independent validator operates separately from the solver |
| C09 | Level A hard constraints cannot be relaxed through any interface |

---

## 9. Unresolved Decisions

See `OPEN_QUESTIONS_AND_ASSUMPTIONS.md` for the full list (15 open questions as of October 2026).

---

## 10. Acceptance Criteria for Prototype Demo

1. All four pages exist and are navigable.
2. Login routes to the correct dashboard per role.
3. Each role sees only its intended demo functionality.
4. The timetable grid is legible and populated.
5. Admin filters work on the mock data.
6. Teacher requests can be submitted and displayed.
7. Student queries can be submitted and displayed.
8. Admin can inspect a simulated conflict with rule explanation.
9. Publication is disabled for the incomplete/invalid mock candidate.
10. The interface makes mock behavior obvious — no fake solver claims.
11. The project runs locally with documented instructions.
12. No mock ML answer is represented as an output from a trained model.
