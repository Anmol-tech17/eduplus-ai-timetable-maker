# EduPlus — Project Changelog

> **Document ID:** CHANGELOG  
> **Version:** 0.1  
> **Format:** Based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)  
> **Versioning Scheme:** Semantic Versioning (`vMAJOR.MINOR.PATCH-PRERELEASE`)  

---

## [0.1.0-prototype] — 2026-10-21

### Milestone: Prototype Demo & Technical Architecture Baseline

This initial release delivers the foundational engineering specification, relational domain model, formal scheduling rule catalogue, and a fully interactive, four-page web prototype for stakeholder evaluation.

---

### Added

#### 1. Interactive Web Demonstration Prototype
- **Page 1: Login (`index.html`)**
  - Brand header and academic unit subtitle (`AIML Department`).
  - Prominent prototype security and mock disclaimer banner.
  - Interactive demo credential auto-fill buttons for Admin, Teacher, and Student personas.
  - Role-aware client-side redirect to dashboard pages.
- **Page 2: Admin Dashboard (`admin.html`, `src/js/admin.js`)**
  - Department overview metric cards: 8 Divisions, 14 Teachers, 9 Rooms/Labs, 142 Weekly Sessions.
  - Interactive weekly timetable grid displaying Year 3 Division A with dynamic filtering by Faculty (`TEACHERS`) and Rooms (`ROOMS`).
  - Session modal inspection detailing course code, credits, room capabilities, and assigned cohort.
  - Simulated **Generate Timetable** workflow showing progress animation and candidate switching (`Candidate 1: Optimal` vs `Candidate 2: With Conflict`).
  - Rule-check panel and conflict diagnosis reporting simulated Level A violation (Dr. Priya Sharma double-booking).
  - Dynamic **Publication Gatekeeper**: Publish action is strictly disabled when inspecting Candidate 2 (conflict), and enabled with state feedback on Candidate 1 (valid).
  - Teacher Request Inbox with accept/reject interaction updating local state.
  - Faculty and Room directory panels displaying capacity, floor, and designation.
- **Page 3: Teacher Dashboard (`teacher.html`, `src/js/teacher.js`)**
  - Personalized teacher portal for Dr. Priya Sharma (`PVS`).
  - Personal weekly teaching schedule grid highlighting lectures, labs, and elective batches.
  - "Today's Schedule" quick glance widget with "Next Up" indicator.
  - Fully interactive Request Submission Modal supporting Rescheduling, Substitution, and Cancellation requests.
  - Teacher Request History tracker with real-time addition of newly submitted requests.
  - AI Assistant query box with transparent simulation disclaimer.
- **Page 4: Student Dashboard (`student.html`, `src/js/student.js`)**
  - Personalized student portal for Aarav Patel (Third Year, Div A, Batch B1, Electives: CV & NLP).
  - Published division weekly schedule with distinct color coding for Lectures, Practicals, and Electives.
  - "Today's Classes" agenda card with live countdown to next class.
  - Active Schedule Notices panel displaying date-specific cancellations and room relocations.
  - Natural Language Timetable Query interface with mock response handling and clear disclaimer.

#### 2. Design System & Assets (`src/css/style.css`, `src/data/mockData.js`)
- Modern SaaS academic interface styling with curated HSL color tokens, dark navigation sidebar, clean typography (`Inter`), accessible contrast, and zero layout thrashing.
- Comprehensive normalized mock dataset representing realistic AIML Department operations (Year 1 to 4 structure, 14 faculty members, 9 classrooms/labs, 142 scheduled weekly sessions, elective conflict graphs, and standard time slots `TS1` to `TS8`).

#### 3. Complete Technical Documentation Suite (`docs/`)
- `README.md`: Master project guide, system boundaries, demo instructions, and credentials.
- `PROJECT_SPECIFICATION.md`: Problem statement, 17 functional and 8 non-functional requirements, v1 scope, stakeholders, and acceptance criteria.
- `DOMAIN_MODEL.md`: Academic hierarchy, elective cohort semantics, student-group overlap mathematics, lunch policies, and domain glossary.
- `ER_DIAGRAM.md`: Mermaid entity-relationship diagram with 22 relational entities and cardinalities.
- `DATABASE_SCHEMA.md`: PostgreSQL 16 schema specification with table definitions, column types, compound indexes, check constraints, referential integrity table, migration strategy, and seed data.
- `SCHEDULING_RULES.md`: Catalogue of Level A (hard), Level B (policy), and Level C (soft) rules with plain-language explanation templates.
- `SCHEDULER_DESIGN.md`: Google OR-Tools CP-SAT formulation, interval variables, mathematical constraints, objective hierarchy, and candidate diversity mechanics.
- `VALIDATION_AND_INFERENCE.md`: Independent validator architecture, pre-solve static checks, conflict explanation engine, and publication gatekeeper rules.
- `SYSTEM_ARCHITECTURE.md`: High-level component architecture, data flow diagrams, background worker queue, and deployment model.
- `API_SPECIFICATION.md`: REST API endpoint contracts (OpenAPI style), error envelopes (RFC 7807), request/response schemas, and authorization requirements.
- `ROLE_ACCESS_MATRIX.md`: Granular permission matrix across Admin, Teacher, and Student roles distinguishing demo behavior from production authorization.
- `TIMETABLE_VERSIONING_AND_REPAIR.md`: Immutable versioning state machine, parent-child DAG lineage, localized repair with frozen sessions, and date-specific exceptions.
- `AI_AND_ML_ROADMAP.md`: Principles for AI integration, prohibited LLM operations, planned ML query service categories, and structured I/O contracts.
- `TESTING_STRATEGY.md`: Test pyramid covering validator tests, solver integration tests, property-based tests, API tests, and Playwright UI scenarios.
- `IMPLEMENTATION_ROADMAP.md`: Phased delivery plan from Phase 0 (current prototype) through Phase 8 (advanced extensions).
- `OPEN_QUESTIONS_AND_ASSUMPTIONS.md`: Record of 12 critical architectural assumptions and open institutional policy questions.
- `REQUIREMENTS_TRACEABILITY.md`: Bidirectional traceability matrix mapping 25 requirements to architecture, rules, test cases, and code components.
- `CHANGELOG.md`: This document.

---

### Key Architectural Decisions (ADRs) Recorded

1. **ADR-01: Independent Validator Preceding Solver**  
   *Decision:* The rule validator must be implemented and tested prior to the optimization solver.  
   *Rationale:* Decoupling the validator guarantees an unbiased audit mechanism for solver candidates, manual GUI edits, and external schedule imports.

2. **ADR-02: Google OR-Tools CP-SAT as Optimization Engine**  
   *Decision:* CP-SAT selected over MILP and Genetic Algorithms.  
   *Rationale:* SAT-based constraint programming natively excels at non-overlapping interval constraints and provides mathematically sound proofs of infeasibility.

3. **ADR-03: Deterministic Core with AI as Supplementary Advisory Gateway**  
   *Decision:* Large Language Models are strictly prohibited from generating slot allocations or solving constraint satisfaction problems directly.  
   *Rationale:* Timetabling requires strict combinatorial correctness; LLMs hallucinate invalid schedules. LLMs are restricted to natural language translation, query parsing, and conflict summarization.

4. **ADR-04: Immutable Append-Only Versions & Date-Specific Exceptions**  
   *Decision:* Published timetables cannot be modified in-place. Permanent updates increment version lineage; temporary disruptions generate date-specific `SESSION_EXCEPTION` rows.  
   *Rationale:* Preserves academic audit trails and prevents silent changes to active institutional commitments.
