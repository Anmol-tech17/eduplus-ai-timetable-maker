# EduPlus — ER Diagram and Data Model

> **Document ID:** ER_DIAGRAM  
> **Version:** 0.1  
> **Status:** Design specification — not yet implemented in a database

---

## 1. ER Diagram (Mermaid)

```mermaid
erDiagram

    %% ─── ACADEMIC STRUCTURE ─────────────────────────────────────────────────

    DEPARTMENT {
        uuid    id           PK
        string  code         "e.g. AIML"
        string  name
        string  college_name
    }

    ACADEMIC_YEAR {
        uuid    id           PK
        uuid    department_id FK
        int     year_number   "1, 2, 3, 4"
        string  label         "e.g. Third Year"
    }

    DIVISION {
        uuid    id            PK
        uuid    academic_year_id FK
        string  name          "e.g. A"
        int     strength
        uuid    home_room_id  FK "nullable"
    }

    BATCH {
        uuid    id            PK
        uuid    division_id   FK
        string  name          "e.g. B1"
    }

    SUBJECT {
        uuid    id             PK
        uuid    department_id  FK
        string  code
        string  name
        string  short_name
        int     year_number
        string  ltp_credits    "e.g. 3-1-2"
        bool    is_elective
    }

    ENROLLMENT_GROUP {
        uuid    id             PK
        uuid    subject_id     FK
        uuid    division_id    FK
        string  name
        int     student_count
    }

    ENROLLMENT_GROUP_OVERLAP {
        uuid    id              PK
        uuid    group_a_id      FK
        uuid    group_b_id      FK
    }

    %% ─── TEACHING RESOURCES ─────────────────────────────────────────────────

    TEACHER {
        uuid    id             PK
        uuid    department_id  FK
        string  name
        string  short_name
        string  designation
        int     weekly_workload_cap
    }

    TEACHER_QUALIFICATION {
        uuid    id             PK
        uuid    teacher_id     FK
        uuid    subject_id     FK
        string  qualification_level "primary, secondary"
    }

    ROOM {
        uuid    id             PK
        uuid    department_id  FK
        string  name
        string  type           "classroom, laboratory"
        int     capacity
        int     floor
    }

    ROOM_CAPABILITY {
        uuid    id             PK
        uuid    room_id        FK
        string  capability     "e.g. GPU_Workstations"
    }

    %% ─── SCHEDULING CONFIG ───────────────────────────────────────────────────

    TIME_SLOT {
        uuid    id             PK
        int     start_hour
        int     end_hour
        string  label
        int     slot_index     "ordering within day"
    }

    WORKING_DAY {
        uuid    id             PK
        uuid    department_id  FK
        string  day_name       "Monday–Saturday"
        bool    is_active
    }

    DIVISION_LUNCH_POLICY {
        uuid    id             PK
        uuid    division_id    FK
        string  allowed_slots  "JSON array of TIME_SLOT IDs"
        uuid    assigned_slot_id FK "nullable — if fixed"
    }

    TEACHER_AVAILABILITY {
        uuid    id             PK
        uuid    teacher_id     FK
        string  day_name
        uuid    time_slot_id   FK
        string  availability_type "unavailable, preferred"
    }

    ROOM_UNAVAILABILITY {
        uuid    id             PK
        uuid    room_id        FK
        string  day_name
        uuid    time_slot_id   FK
        string  reason
    }

    BLOCKED_SLOT {
        uuid    id             PK
        uuid    division_id    FK "nullable"
        string  day_name
        uuid    time_slot_id   FK
        string  reason
    }

    TEACHING_ASSIGNMENT {
        uuid    id             PK
        uuid    subject_id     FK
        uuid    division_id    FK
        uuid    teacher_id     FK
        string  session_type   "lecture, tutorial, practical"
        uuid    batch_id       FK "nullable — for practicals"
        uuid    enrollment_group_id FK "nullable — for electives"
    }

    SESSION_REQUIREMENT {
        uuid    id             PK
        uuid    teaching_assignment_id FK
        int     weekly_count
        int     duration_hours "1 or 2"
        string  session_type
    }

    %% ─── SCHEDULING OUTPUT ───────────────────────────────────────────────────

    INPUT_SNAPSHOT {
        uuid    id             PK
        jsonb   data
        timestamptz created_at
    }

    GENERATION_RUN {
        uuid    id              PK
        uuid    input_snapshot_id FK
        string  status          "running, completed, infeasible, timeout"
        timestamptz started_at
        timestamptz finished_at
        int     solver_time_ms
        string  solver_status
        string  notes
    }

    TIMETABLE_VERSION {
        uuid    id              PK
        uuid    generation_run_id FK "nullable for manual"
        uuid    parent_version_id FK "nullable — for repair"
        uuid    department_id   FK
        int     version_number
        string  status          "draft, published, archived"
        string  label
        string  academic_year
        int     semester
        timestamptz published_at
        uuid    published_by    FK
        bool    is_repair
    }

    SCHEDULED_SESSION {
        uuid    id              PK
        uuid    timetable_version_id FK
        uuid    teaching_assignment_id FK
        uuid    teacher_id      FK
        uuid    room_id         FK
        string  day_name
        uuid    time_slot_id    FK
        string  session_type
        string  target_group_type "division, batch, enrollment_group"
        uuid    target_group_id
    }

    VIOLATION {
        uuid    id              PK
        uuid    timetable_version_id FK
        string  rule_id         "A01, B05, etc."
        string  rule_level      "A, B, C"
        string  severity        "error, warning"
        text    description
        jsonb   affected_session_ids
        jsonb   affected_entity_ids
    }

    RULE_CONFIG {
        uuid    id              PK
        uuid    department_id   FK
        string  rule_id
        jsonb   parameters
        timestamptz updated_at
        uuid    updated_by      FK
    }

    POLICY_RELAXATION {
        uuid    id              PK
        uuid    timetable_version_id FK
        string  rule_id
        jsonb   original_value
        jsonb   relaxed_value
        text    reason
        uuid    approved_by     FK
        timestamptz approved_at
        string  compliance_status
    }

    %% ─── REPAIR / CHANGE MANAGEMENT ─────────────────────────────────────────

    REPAIR_RUN {
        uuid    id              PK
        uuid    source_version_id FK
        uuid    result_version_id FK "nullable — if repair failed"
        string  status
        jsonb   frozen_session_ids
        text    objective_note
    }

    SESSION_CHANGE {
        uuid    id              PK
        uuid    repair_run_id   FK
        uuid    session_id      FK
        string  change_type     "moved, cancelled, substituted"
        jsonb   before_state
        jsonb   after_state
        text    reason
    }

    CHANGE_REQUEST {
        uuid    id              PK
        uuid    requester_id    FK
        string  requester_role
        string  request_type    "reschedule, substitution, cancellation"
        text    details
        string  status          "pending, approved, rejected"
        uuid    reviewed_by     FK "nullable"
        timestamptz submitted_at
        timestamptz reviewed_at
    }

    SESSION_EXCEPTION {
        uuid    id              PK
        uuid    timetable_version_id FK
        uuid    scheduled_session_id FK
        date    exception_date
        string  exception_type  "cancelled, substituted, rescheduled"
        uuid    substitute_teacher_id FK "nullable"
        uuid    alternate_room_id FK "nullable"
        text    reason
        bool    requires_makeup
    }

    %% ─── APPLICATION & SECURITY ──────────────────────────────────────────────

    USER_ACCOUNT {
        uuid    id              PK
        string  email           UNIQUE
        string  password_hash
        string  role            "admin, teacher, student"
        uuid    department_id   FK
        uuid    linked_entity_id "teacher_id or student_id"
        bool    is_active
        timestamptz created_at
    }

    AUDIT_LOG {
        uuid    id              PK
        uuid    actor_id        FK
        string  action
        string  entity_type
        uuid    entity_id
        jsonb   before_state
        jsonb   after_state
        timestamptz created_at
        string  ip_address
    }

    %% ─── RELATIONSHIPS ──────────────────────────────────────────────────────

    DEPARTMENT        ||--o{ ACADEMIC_YEAR            : "has"
    ACADEMIC_YEAR     ||--o{ DIVISION                 : "has"
    DIVISION          ||--o{ BATCH                    : "has"
    DIVISION          ||--o{ ENROLLMENT_GROUP          : "has"
    SUBJECT           ||--o{ ENROLLMENT_GROUP          : "enrolled_in"
    ENROLLMENT_GROUP  ||--o{ ENROLLMENT_GROUP_OVERLAP  : "group_a"
    ENROLLMENT_GROUP  ||--o{ ENROLLMENT_GROUP_OVERLAP  : "group_b"
    DEPARTMENT        ||--o{ TEACHER                  : "employs"
    DEPARTMENT        ||--o{ ROOM                     : "owns"
    ROOM              ||--o{ ROOM_CAPABILITY           : "has"
    TEACHER           ||--o{ TEACHER_QUALIFICATION     : "has"
    TEACHER           ||--o{ TEACHER_AVAILABILITY      : "has"
    ROOM              ||--o{ ROOM_UNAVAILABILITY        : "has"
    DIVISION          ||--o{ DIVISION_LUNCH_POLICY     : "has"
    SUBJECT           ||--o{ TEACHING_ASSIGNMENT       : "assigned_in"
    DIVISION          ||--o{ TEACHING_ASSIGNMENT       : "receives"
    TEACHER           ||--o{ TEACHING_ASSIGNMENT       : "performs"
    TEACHING_ASSIGNMENT ||--o{ SESSION_REQUIREMENT     : "requires"
    DEPARTMENT        ||--o{ TIMETABLE_VERSION         : "has"
    GENERATION_RUN    ||--o{ TIMETABLE_VERSION         : "produces"
    INPUT_SNAPSHOT    ||--o{ GENERATION_RUN            : "used_in"
    TIMETABLE_VERSION ||--o{ SCHEDULED_SESSION         : "contains"
    TIMETABLE_VERSION ||--o{ VIOLATION                 : "has"
    TIMETABLE_VERSION ||--o{ POLICY_RELAXATION         : "has"
    TIMETABLE_VERSION ||--o{ SESSION_EXCEPTION         : "has"
    TIMETABLE_VERSION ||--o| TIMETABLE_VERSION         : "parent_of"
    REPAIR_RUN        ||--o{ SESSION_CHANGE            : "records"
    CHANGE_REQUEST    ||--o| REPAIR_RUN                : "triggers"
    USER_ACCOUNT      ||--o{ AUDIT_LOG                 : "generates"
```

---

## 2. Entity Descriptions

| Entity | Purpose |
|--------|---------|
| `DEPARTMENT` | Top-level organizational unit; all scheduling is department-scoped |
| `ACADEMIC_YEAR` | One of Years 1–4 within a department |
| `DIVISION` | A student cohort within a year (e.g., Div A, Div B) |
| `BATCH` | A lab sub-group of a division (e.g., B1, B2, B3) |
| `SUBJECT` | An academic subject with LTP credits and elective flag |
| `ENROLLMENT_GROUP` | A named set of students enrolled in an elective subject |
| `ENROLLMENT_GROUP_OVERLAP` | Explicit conflict record between two enrollment groups that share students |
| `TEACHER` | A teaching staff member with workload cap |
| `TEACHER_QUALIFICATION` | Which subjects a teacher is qualified to teach (primary/secondary) |
| `ROOM` | A schedulable space — classroom or laboratory |
| `ROOM_CAPABILITY` | Equipment or specialization tags for labs |
| `TIME_SLOT` | One-hour scheduling unit; 08:00–18:00 = 10 slots per day |
| `WORKING_DAY` | Configured working days (Mon–Fri default; Sat optional) |
| `DIVISION_LUNCH_POLICY` | Allowed and assigned lunch slots per division; supports different slots per division |
| `TEACHER_AVAILABILITY` | Teacher unavailability (Level A) or preferences (Level C) |
| `ROOM_UNAVAILABILITY` | Periods when a room cannot be used |
| `BLOCKED_SLOT` | Department- or division-level blocked periods |
| `TEACHING_ASSIGNMENT` | Who teaches which subject for which division/batch/elective group |
| `SESSION_REQUIREMENT` | How many sessions of each type are needed per week |
| `INPUT_SNAPSHOT` | Serialized, versioned input to the solver; stored with every generation run |
| `GENERATION_RUN` | A solver execution record — status, timing, solver status |
| `TIMETABLE_VERSION` | A candidate or published timetable; versioned with parent chain |
| `SCHEDULED_SESSION` | One placed session within a timetable version |
| `VIOLATION` | A constraint violation recorded against a timetable version |
| `RULE_CONFIG` | Per-department Level B constraint parameters |
| `POLICY_RELAXATION` | Approved relaxation of a Level B rule for a specific timetable version |
| `REPAIR_RUN` | A repair operation linking source and result timetable versions |
| `SESSION_CHANGE` | Record of what changed between timetable versions during repair |
| `CHANGE_REQUEST` | Teacher or admin request that triggers a repair operation |
| `SESSION_EXCEPTION` | Date-specific override (cancellation, substitution) on a published timetable |
| `USER_ACCOUNT` | Application user with role; links to teacher or student entity |
| `AUDIT_LOG` | Immutable record of sensitive administrative actions |

---

## 3. Key Design Decisions

### Session Requirements are Separate from Scheduled Sessions
`SESSION_REQUIREMENT` records what *must* be placed. `SCHEDULED_SESSION` records what *has been* placed. A complete timetable has every requirement covered exactly once.

### Enrollment Overlap is Explicit, Not Derived
`ENROLLMENT_GROUP_OVERLAP` is an authoritative table, not computed from individual student membership. This avoids errors from incomplete membership data and makes conflict checking O(1) for group pairs.

### Lunch Policy is Per-Division
`DIVISION_LUNCH_POLICY` allows different lunch slots for different divisions. A single global lunch slot is not assumed.

### Timetable Versions are Immutable Once Published
A published `TIMETABLE_VERSION` is never overwritten. Repairs create a new version with a `parent_version_id` pointing to the previous version.

### Input Snapshots are Stored
Every `GENERATION_RUN` references an `INPUT_SNAPSHOT` so that the run can be reproduced, debugged, or audited independently of later data changes.

### Target Groups in Scheduled Sessions
`SCHEDULED_SESSION.target_group_type` distinguishes whether the session is for a `division`, `batch`, or `enrollment_group`, and `target_group_id` references the relevant entity.
