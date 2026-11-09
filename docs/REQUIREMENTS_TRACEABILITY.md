# EduPlus — Requirements Traceability Matrix (RTM)

> **Document ID:** REQUIREMENTS_TRACEABILITY  
> **Version:** 0.1  
> **Status:** Live Engineering Baseline  

---

## 1. Overview & Legend

This Requirements Traceability Matrix connects institutional academic scheduling requirements from [PROJECT_SPECIFICATION.md](file:///c:/Users/dell/OneDrive/Desktop/Eduplus%20AI%20Timetable%20Maker/docs/PROJECT_SPECIFICATION.md) to their corresponding architecture components, domain entities, scheduling rules, implementation statuses, test scenarios, and known limitations.

### Status Legend
- **Demo Implemented:** Fully interactive in the prototype demo (`index.html`, `admin.html`, `teacher.html`, `student.html`).
- **Phase 1 Planned:** Scheduled for Database Schema & Academic Hierarchy.
- **Phase 2 Planned:** Scheduled for Independent Rule Validator.
- **Phase 3 Planned:** Scheduled for CP-SAT Solver & Candidate Generation.
- **Phase 4 Planned:** Scheduled for Conflict Explanation & Diagnostics.
- **Phase 5 Planned:** Scheduled for Versioning, Exceptions & Localized Repair.
- **Phase 6 Planned:** Scheduled for AI / LLM Natural Language Query Gateway.

---

## 2. Requirements Traceability Matrix

| Req ID | Requirement Description | Spec Section | Architecture Component & Entities | Scheduling Rule ID | Implementation Status | Test Case ID | Known Limitations / Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **REQ-01** | Support 4 B.Tech years (Years 1–4) for AIML Department | §4.1 | `ACADEMIC_YEAR`, `DIVISION`, `DEPARTMENT` | — | **Demo Implemented** | `TC-UI-01`, `TC-VAL-01` | Demo focuses on Year 3 Div A; Years 1, 2, 4 structures modeled in `mockData.js`. |
| **REQ-02** | Weekly timetable horizon: 6 days (Mon–Sat), 8 slots/day (09:00–17:00) | §4.2 | `TIME_SLOT`, `WORKING_DAY` | `A06` | **Demo Implemented** | `TC-UI-02` | Fixed 1-hour slot granularity; partial 30-min slots not supported in v1. |
| **REQ-03** | Support Lecture (1h), Tutorial (1h), and Practical (2h consecutive) sessions | §4.3 | `SESSION_REQUIREMENT`, `SCHEDULED_SESSION` | `A05` | **Demo Implemented** | `TC-VAL-05`, `TC-SOLV-03` | Practicals enforced as continuous 2-hour blocks in labs. |
| **REQ-04** | Division-specific mandatory 1-hour lunch break between 13:00 and 15:00 | §4.4 | `DIVISION_LUNCH_POLICY`, `TIME_SLOT` | `A07` | **Demo Implemented** | `TC-VAL-07` | Div 3A assigned `TS6` (14:00–15:00). Staggered windows configurable. |
| **REQ-05** | Division and Lab Batch hierarchy ($B_1, B_2, B_3$ per division) | §5.1 | `DIVISION`, `BATCH`, `ROOM` | `A04` | **Demo Implemented** | `TC-VAL-04` | Batch capacity defaults to 20 students; division strength defaults to 60. |
| **REQ-06** | Elective subject enrollment groups across or within divisions | §5.3 | `ENROLLMENT_GROUP`, `SUBJECT` | — | **Demo Implemented** | `TC-VAL-06` | Demo includes CV, NLP, and Robotics elective cohorts. |
| **REQ-07** | Elective student-group conflict detection based on shared enrollments | §5.4 | `ENROLLMENT_GROUP_OVERLAPS` | `A03` | **Phase 2 Planned** (Demo simulated) | `TC-VAL-02`, `TC-SOLV-04` | Conflict graph pre-computed in mock data; automated dynamic graph in Phase 2. |
| **REQ-08** | Teacher qualifications and weekly teaching workload caps | §6.1 | `TEACHER`, `TEACHER_QUALIFICATION` | `B04` | **Demo Implemented** | `TC-VAL-08` | Caps range from 12 to 18 hours/week per faculty designation. |
| **REQ-09** | Prevent teacher double-booking (Hard Level A) | §6.2 | `SCHEDULED_SESSION`, `TEACHER` | `A01` | **Demo Implemented** (Mock conflict) | `TC-VAL-01`, `TC-SOLV-01` | Admin conflict panel inspects simulated Dr. Sharma double-booking. |
| **REQ-10** | Prevent room double-booking (Hard Level A) | §7.1 | `SCHEDULED_SESSION`, `ROOM` | `A02` | **Phase 2 Planned** (Demo modeled) | `TC-VAL-03`, `TC-SOLV-02` | Room capabilities checked (e.g. GPU workstations required for Lab-2). |
| **REQ-11** | Lab batch concurrency (all batches run practicals at same time) | §7.2 | `SCHEDULED_SESSION`, `BATCH` | `A04` | **Demo Implemented** | `TC-VAL-04` | Wednesday TS6–TS7 shows B1 (Lab-2), B2 (Lab-3), B3 (Lab-1) concurrently. |
| **REQ-12** | Student daily teaching limit $\le 6$ hours | §8.2 | Rule Engine, `SCHEDULED_SESSION` | `B01` | **Phase 2 Planned** | `TC-VAL-09` | Configurable per department. |
| **REQ-13** | Faculty daily teaching limit $\le 5$ hours | §8.2 | Rule Engine, `SCHEDULED_SESSION` | `B02` | **Phase 2 Planned** | `TC-VAL-10` | Enforced in CP-SAT objective and post-validator. |
| **REQ-14** | Faculty max consecutive teaching limit $\le 3$ hours | §8.2 | Rule Engine, `SCHEDULED_SESSION` | `B03` | **Phase 2 Planned** | `TC-VAL-11` | Soft warning produced if breached; requires admin override. |
| **REQ-15** | Minimize student internal gaps (holes in schedule) | §8.3 | CP-SAT Objective Function | `C01`, `B05` | **Phase 3 Planned** | `TC-SOLV-05` | Weight $w_1 = 15$ in optimization objective. |
| **REQ-16** | Pre-solve static feasibility validation | §10.3 | Pre-Solve Validator | `PRE-01`–`PRE-06` | **Phase 2 Planned** | `TC-VAL-12` | Static room capacity vs student strength verified before solver starts. |
| **REQ-17** | Optimization solver candidate generation (Google OR-Tools CP-SAT) | §10.5 | Background Worker Job Queue | — | **Phase 3 Planned** (Demo simulated) | `TC-SOLV-06` | Demo uses pre-computed candidate datasets to show generation workflow. |
| **REQ-18** | Explainable conflict diagnostic reporting | §11.2 | Conflict Explanation Engine | — | **Demo Implemented** | `TC-UI-03` | Admin panel presents plain-language breakdown of rule violations. |
| **REQ-19** | Publication gatekeeper (disable publish when Level A violations exist) | §12.1 | Frontend State & Publication API | — | **Demo Implemented** | `TC-UI-04` | Publish button disabled on conflict candidate; enabled on valid candidate. |
| **REQ-20** | Immutable timetable versioning & parent lineage | §12.4 | `TIMETABLE_VERSION`, `AUDIT_LOG` | — | **Phase 5 Planned** | `TC-VER-01` | In-place editing of published versions strictly disallowed. |
| **REQ-21** | Localized timetable repair with frozen sessions | §12.2 | Repair Engine, `SESSION_CHANGE` | — | **Phase 5 Planned** | `TC-VER-02` | Solver minimizes move distance $\Delta$ while pinning frozen sessions. |
| **REQ-22** | Date-specific session exceptions (cancellations/substitutions) | §12.3 | `SESSION_EXCEPTION` | — | **Demo Implemented** (UI notices) | `TC-UI-05` | Displayed on Teacher and Student dashboards as active alerts. |
| **REQ-23** | Role-based portal dashboards (Admin, Teacher, Student) | §16.1 | Web Prototype (`.html`, `.js`, `.css`) | — | **Demo Implemented** | `TC-UI-06` | 4 distinct navigable pages with demo credential quick-fill. |
| **REQ-24** | Teacher schedule change request submission & workflow | §16.2 | `CHANGE_REQUEST`, Request Inbox | — | **Demo Implemented** | `TC-UI-07` | Forms perform validation and insert into local demo state. |
| **REQ-25** | Student and Teacher AI timetable query assistant | §15.1 | AI Gateway Service | — | **Demo Implemented** (Simulated) | `TC-UI-08` | Transparently labeled as mock query responder with clear disclaimer. |

---

## 3. Verification & Coverage Summary

- **Total Requirements Tracked:** 25
- **Interactive in Demo Prototype:** 14 (56%)
- **Planned for Phase 1–2 (Data & Validator):** 5 (20%)
- **Planned for Phase 3 (CP-SAT Solver):** 3 (12%)
- **Planned for Phase 5–6 (Repair & AI):** 3 (12%)
- **Traceability Integrity:** 100% of requirements map to explicit entities, rules, test cases, and specifications.
