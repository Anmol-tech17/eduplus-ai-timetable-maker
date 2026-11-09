# EduPlus — Database Schema Specification

> **Document ID:** DATABASE_SCHEMA  
> **Version:** 0.1  
> **Dialect:** PostgreSQL 16  
> **Status:** Architecture Design Baseline — Planned for Phase 1  

---

## 1. Overview & Principles

The EduPlus database schema models college academic scheduling for one or more departments. It is designed under the following principles:

1. **Relational Integrity First:** Hard constraints (Level A) and ownership hierarchies are enforced at the database level using primary keys, foreign keys with strict referential actions, unique compound constraints, and check constraints.
2. **Deterministic Versioning:** Published timetables are immutable. Any revision or repair produces a new `TIMETABLE_VERSION` record referencing its parent or creates a date-bounded `SESSION_EXCEPTION`.
3. **Auditable Inputs & Outputs:** Every automated solver run preserves its complete input parameter set in an immutable `INPUT_SNAPSHOT` (JSONB) linked to a `GENERATION_RUN`.
4. **UUID Primary Keys:** All primary keys use RFC 4122 UUIDv4 to avoid sequence enumeration, simplify cross-environment data synchronization, and support distributed job queues.

---

## 2. Table Definitions & Column Specifications

### 2.1 Academic Structure

#### Table: `departments`
Stores academic department units within the institution.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `code` | `VARCHAR(16)` | No | — | Unique department code (e.g., `AIML`, `CSE`) |
| `name` | `VARCHAR(255)` | No | — | Full department title |
| `college_name` | `VARCHAR(255)` | No | — | Parent institution name |
| `created_at` | `TIMESTAMPTZ` | No | `CURRENT_TIMESTAMP` | Audit timestamp |
| `updated_at` | `TIMESTAMPTZ` | No | `CURRENT_TIMESTAMP` | Audit timestamp |

*Constraints & Indexes:*
- `CONSTRAINT uq_department_code UNIQUE (code)`

#### Table: `academic_years`
Represents the B.Tech cohorts (Years 1 to 4) under a department.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `department_id` | `UUID` | No | — | FK &rarr; `departments(id)` ON DELETE RESTRICT |
| `year_number` | `SMALLINT` | No | — | Year level (1, 2, 3, or 4) |
| `label` | `VARCHAR(64)` | No | — | e.g., 'First Year', 'Second Year', 'Third Year', 'Final Year' |

*Constraints & Indexes:*
- `CONSTRAINT chk_year_number CHECK (year_number BETWEEN 1 AND 4)`
- `CONSTRAINT uq_dept_year UNIQUE (department_id, year_number)`
- `INDEX idx_academic_years_dept (department_id)`

#### Table: `divisions`
Classroom cohorts within an academic year (e.g., Third Year Div A, Div B).

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `academic_year_id` | `UUID` | No | — | FK &rarr; `academic_years(id)` ON DELETE CASCADE |
| `name` | `VARCHAR(16)` | No | — | Division identifier (e.g., 'A', 'B') |
| `strength` | `INTEGER` | No | `60` | Number of enrolled students |
| `home_room_id` | `UUID` | Yes | `NULL` | FK &rarr; `rooms(id)` ON DELETE SET NULL |

*Constraints & Indexes:*
- `CONSTRAINT chk_div_strength CHECK (strength > 0)`
- `CONSTRAINT uq_year_div_name UNIQUE (academic_year_id, name)`
- `INDEX idx_divisions_year (academic_year_id)`

#### Table: `batches`
Sub-cohorts within a division for lab practicals and tutorials (e.g., Batch B1, B2, B3).

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `division_id` | `UUID` | No | — | FK &rarr; `divisions(id)` ON DELETE CASCADE |
| `name` | `VARCHAR(16)` | No | — | Batch code (e.g., 'B1', 'B2', 'B3') |
| `capacity` | `INTEGER` | No | `20` | Max batch size |

*Constraints & Indexes:*
- `CONSTRAINT uq_division_batch UNIQUE (division_id, name)`
- `INDEX idx_batches_div (division_id)`

#### Table: `subjects`
Course syllabus catalogue.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `department_id` | `UUID` | No | — | FK &rarr; `departments(id)` ON DELETE RESTRICT |
| `code` | `VARCHAR(32)` | No | — | Course code (e.g., `CS301`, `AI302`) |
| `name` | `VARCHAR(255)` | No | — | Course full title |
| `short_name` | `VARCHAR(32)` | No | — | Display abbreviation (e.g., `ML`, `DL`, `NLP`) |
| `year_number` | `SMALLINT` | No | — | Year level (1 to 4) |
| `ltp_credits` | `VARCHAR(16)` | No | `'3-0-0'` | Lecture-Tutorial-Practical structure |
| `is_elective` | `BOOLEAN` | No | `FALSE` | Flag for elective subjects |

*Constraints & Indexes:*
- `CONSTRAINT uq_dept_subject_code UNIQUE (department_id, code)`
- `INDEX idx_subjects_dept_year (department_id, year_number)`

#### Table: `enrollment_groups`
Represents an elective subject cohort across divisions or within a division.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `subject_id` | `UUID` | No | — | FK &rarr; `subjects(id)` ON DELETE CASCADE |
| `division_id` | `UUID` | Yes | `NULL` | FK &rarr; `divisions(id)` ON DELETE SET NULL |
| `name` | `VARCHAR(64)` | No | — | Cohort name (e.g., 'EG_CV', 'EG_NLP') |
| `student_count` | `INTEGER` | No | `0` | Number of enrolled students |

*Constraints & Indexes:*
- `INDEX idx_enrollment_groups_subject (subject_id)`

#### Table: `enrollment_group_overlaps`
Explicit conflict graph matrix between elective cohorts that share student enrollment.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `group_a_id` | `UUID` | No | — | FK &rarr; `enrollment_groups(id)` ON DELETE CASCADE |
| `group_b_id` | `UUID` | No | — | FK &rarr; `enrollment_groups(id)` ON DELETE CASCADE |
| `shared_student_count`| `INTEGER` | No | `0` | Count of common students |

*Constraints & Indexes:*
- `CONSTRAINT chk_group_overlap_order CHECK (group_a_id < group_b_id)`
- `CONSTRAINT uq_group_overlap UNIQUE (group_a_id, group_b_id)`

---

### 2.2 Teaching Resources & Facilities

#### Table: `teachers`
Faculty profiles and workload capabilities.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `department_id` | `UUID` | No | — | FK &rarr; `departments(id)` ON DELETE RESTRICT |
| `name` | `VARCHAR(128)` | No | — | Teacher full name |
| `short_name` | `VARCHAR(16)` | No | — | Display code (e.g., `PVS`, `AKM`) |
| `designation` | `VARCHAR(64)` | No | — | Professor, Associate Prof, Assistant Prof |
| `weekly_workload_cap`| `SMALLINT`| No | `16` | Maximum teaching hours per week |
| `email` | `VARCHAR(255)` | No | — | Institutional email address |

*Constraints & Indexes:*
- `CONSTRAINT uq_teacher_email UNIQUE (email)`
- `CONSTRAINT chk_teacher_cap CHECK (weekly_workload_cap BETWEEN 4 AND 30)`

#### Table: `teacher_qualifications`
Subject competency mapping for teachers.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `teacher_id` | `UUID` | No | — | FK &rarr; `teachers(id)` ON DELETE CASCADE |
| `subject_id` | `UUID` | No | — | FK &rarr; `subjects(id)` ON DELETE CASCADE |
| `qualification_level`| `VARCHAR(32)`| No | `'primary'` | `'primary'` or `'secondary'` |

*Constraints & Indexes:*
- `CONSTRAINT uq_teacher_subject UNIQUE (teacher_id, subject_id)`
- `CONSTRAINT chk_qual_level CHECK (qualification_level IN ('primary', 'secondary'))`

#### Table: `rooms`
Physical spaces for lectures and lab sessions.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `department_id` | `UUID` | No | — | FK &rarr; `departments(id)` ON DELETE RESTRICT |
| `name` | `VARCHAR(64)` | No | — | Room name / code (e.g., `LH-101`, `Lab-2`) |
| `type` | `VARCHAR(32)` | No | `'classroom'` | `'classroom'` or `'laboratory'` |
| `capacity` | `INTEGER` | No | `60` | Seating capacity |
| `floor` | `SMALLINT` | No | `1` | Floor number |

*Constraints & Indexes:*
- `CONSTRAINT uq_room_name UNIQUE (department_id, name)`
- `CONSTRAINT chk_room_type CHECK (type IN ('classroom', 'laboratory'))`

#### Table: `room_capabilities`
Specialized equipment or software features available in a room.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `room_id` | `UUID` | No | — | FK &rarr; `rooms(id)` ON DELETE CASCADE |
| `capability` | `VARCHAR(64)` | No | — | e.g., `'GPU_Workstations'`, `'Network_Racks'` |

*Constraints & Indexes:*
- `CONSTRAINT uq_room_capability UNIQUE (room_id, capability)`

---

### 2.3 Scheduling Configuration & Academic Contracts

#### Table: `time_slots`
Ordered hourly schedule periods throughout the academic day.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `slot_code` | `VARCHAR(16)` | No | — | Identifier (e.g., `TS1`, `TS2`, ... `TS8`) |
| `start_time` | `TIME` | No | — | Slot start (e.g., `09:00:00`) |
| `end_time` | `TIME` | No | — | Slot end (e.g., `10:00:00`) |
| `slot_index` | `SMALLINT` | No | — | Daily sequence index (1 to 8) |
| `label` | `VARCHAR(64)` | No | — | e.g., '09:00 – 10:00' |

*Constraints & Indexes:*
- `CONSTRAINT uq_slot_index UNIQUE (slot_index)`
- `CONSTRAINT uq_slot_code UNIQUE (slot_code)`

#### Table: `working_days`
Operating calendar days for the department.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `department_id` | `UUID` | No | — | FK &rarr; `departments(id)` ON DELETE RESTRICT |
| `day_name` | `VARCHAR(16)` | No | — | `'Monday'`, `'Tuesday'`, ... `'Saturday'` |
| `day_index` | `SMALLINT` | No | — | 1 = Monday, 6 = Saturday |
| `is_active` | `BOOLEAN` | No | `TRUE` | Whether scheduling occurs on this day |

*Constraints & Indexes:*
- `CONSTRAINT uq_dept_day UNIQUE (department_id, day_name)`

#### Table: `division_lunch_policies`
Lunch slot configuration per division (fixed vs staggered windows).

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `division_id` | `UUID` | No | — | FK &rarr; `divisions(id)` ON DELETE CASCADE |
| `allowed_slots` | `JSONB` | No | `'["TS5", "TS6"]'` | Candidate slot codes |
| `assigned_slot_id` | `UUID` | Yes | `NULL` | FK &rarr; `time_slots(id)` when lunch is fixed |

*Constraints & Indexes:*
- `CONSTRAINT uq_div_lunch UNIQUE (division_id)`

#### Table: `teacher_availabilities`
Specific unavailability windows and soft time preferences.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `teacher_id` | `UUID` | No | — | FK &rarr; `teachers(id)` ON DELETE CASCADE |
| `day_name` | `VARCHAR(16)` | No | — | Day of week |
| `time_slot_id` | `UUID` | No | — | FK &rarr; `time_slots(id)` ON DELETE CASCADE |
| `availability_type` | `VARCHAR(16)` | No | `'unavailable'` | `'unavailable'` (Hard) or `'preferred'` (Soft) |

*Constraints & Indexes:*
- `CONSTRAINT chk_avail_type CHECK (availability_type IN ('unavailable', 'preferred'))`
- `INDEX idx_teacher_avail (teacher_id, day_name, time_slot_id)`

#### Table: `teaching_assignments`
Formal syllabus contract assigning teacher, subject, and student cohort.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `subject_id` | `UUID` | No | — | FK &rarr; `subjects(id)` ON DELETE RESTRICT |
| `division_id` | `UUID` | No | — | FK &rarr; `divisions(id)` ON DELETE CASCADE |
| `teacher_id` | `UUID` | No | — | FK &rarr; `teachers(id)` ON DELETE RESTRICT |
| `session_type` | `VARCHAR(16)` | No | `'lecture'` | `'lecture'`, `'tutorial'`, or `'practical'` |
| `batch_id` | `UUID` | Yes | `NULL` | FK &rarr; `batches(id)` ON DELETE CASCADE |
| `enrollment_group_id` | `UUID` | Yes | `NULL` | FK &rarr; `enrollment_groups(id)` ON DELETE SET NULL |

*Constraints & Indexes:*
- `CONSTRAINT chk_session_type CHECK (session_type IN ('lecture', 'tutorial', 'practical'))`
- `INDEX idx_assign_teacher (teacher_id)`
- `INDEX idx_assign_div (division_id)`

#### Table: `session_requirements`
Curriculum weekly hour requirements per assignment.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `teaching_assignment_id` | `UUID` | No | — | FK &rarr; `teaching_assignments(id)` ON DELETE CASCADE |
| `weekly_count` | `SMALLINT` | No | `3` | Sessions required per week |
| `duration_hours` | `SMALLINT` | No | `1` | Duration (1 for lecture/tutorial, 2 for practical) |

*Constraints & Indexes:*
- `CONSTRAINT chk_duration CHECK (duration_hours IN (1, 2))`
- `CONSTRAINT chk_weekly_count CHECK (weekly_count BETWEEN 1 AND 10)`

---

### 2.4 Scheduling Output & Versioning

#### Table: `input_snapshots`
Immutable JSON record of all inputs provided to the solver at execution time.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `data` | `JSONB` | No | — | Normalized snapshot of subjects, teachers, rooms, rules |
| `checksum` | `VARCHAR(64)` | No | — | SHA-256 hash of canonicalized JSON data |
| `created_at` | `TIMESTAMPTZ` | No | `CURRENT_TIMESTAMP` | Snapshot timestamp |

#### Table: `generation_runs`
Execution log and diagnostics of solver invocations.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `input_snapshot_id` | `UUID` | No | — | FK &rarr; `input_snapshots(id)` ON DELETE RESTRICT |
| `status` | `VARCHAR(32)` | No | `'running'` | `'running'`, `'completed'`, `'infeasible'`, `'timeout'` |
| `started_at` | `TIMESTAMPTZ` | No | `CURRENT_TIMESTAMP` | Job start time |
| `finished_at` | `TIMESTAMPTZ` | Yes | `NULL` | Job completion time |
| `solver_time_ms` | `INTEGER` | Yes | `NULL` | Elapsed engine runtime |
| `solver_status` | `VARCHAR(32)` | Yes | `NULL` | CP-SAT code: `OPTIMAL`, `FEASIBLE`, `INFEASIBLE` |
| `notes` | `TEXT` | Yes | `NULL` | Diagnostic summary or error trace |

*Constraints & Indexes:*
- `CONSTRAINT chk_gen_status CHECK (status IN ('running', 'completed', 'infeasible', 'timeout', 'failed'))`

#### Table: `timetable_versions`
Master container for generated, candidate, and published timetables.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `generation_run_id` | `UUID` | Yes | `NULL` | FK &rarr; `generation_runs(id)` ON DELETE SET NULL |
| `parent_version_id` | `UUID` | Yes | `NULL` | FK &rarr; `timetable_versions(id)` ON DELETE SET NULL |
| `department_id` | `UUID` | No | — | FK &rarr; `departments(id)` ON DELETE RESTRICT |
| `version_number` | `INTEGER` | No | `1` | Incremental version number |
| `status` | `VARCHAR(32)` | No | `'draft'` | `'draft'`, `'candidate'`, `'published'`, `'archived'` |
| `label` | `VARCHAR(128)` | No | — | e.g., 'AY2026-27 Sem 1 - v1.0 Final' |
| `academic_year_code` | `VARCHAR(32)`| No | `'2026-27'` | Academic session |
| `semester` | `SMALLINT` | No | `1` | Semester 1 or 2 |
| `is_repair` | `BOOLEAN` | No | `FALSE` | Flag if produced by repair workflow |
| `published_at` | `TIMESTAMPTZ` | Yes | `NULL` | Null until published |
| `published_by` | `UUID` | Yes | `NULL` | FK &rarr; `user_accounts(id)` |
| `created_at` | `TIMESTAMPTZ` | No | `CURRENT_TIMESTAMP` | Record creation |

*Constraints & Indexes:*
- `CONSTRAINT chk_tt_status CHECK (status IN ('draft', 'candidate', 'published', 'archived'))`
- `INDEX idx_tt_dept_status (department_id, status)`

#### Table: `scheduled_sessions`
Individual timetable cell assignments.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `timetable_version_id`| `UUID` | No | — | FK &rarr; `timetable_versions(id)` ON DELETE CASCADE |
| `teaching_assignment_id`| `UUID`| No | — | FK &rarr; `teaching_assignments(id)` ON DELETE RESTRICT |
| `teacher_id` | `UUID` | No | — | FK &rarr; `teachers(id)` ON DELETE RESTRICT |
| `room_id` | `UUID` | No | — | FK &rarr; `rooms(id)` ON DELETE RESTRICT |
| `day_name` | `VARCHAR(16)` | No | — | Monday through Saturday |
| `time_slot_id` | `UUID` | No | — | FK &rarr; `time_slots(id)` ON DELETE RESTRICT |
| `session_type` | `VARCHAR(16)` | No | — | `'lecture'`, `'tutorial'`, `'practical'` |
| `target_group_type` | `VARCHAR(32)` | No | — | `'division'`, `'batch'`, `'enrollment_group'` |
| `target_group_id` | `UUID` | No | — | Target entity ID |
| `is_frozen` | `BOOLEAN` | No | `FALSE` | Set to TRUE to pin session during repair |

*Critical Compound Indexes for Scheduling Integrity:*
- `INDEX idx_session_version_lookup (timetable_version_id, day_name, time_slot_id)`
- `INDEX idx_session_teacher_slot (timetable_version_id, teacher_id, day_name, time_slot_id)`
- `INDEX idx_session_room_slot (timetable_version_id, room_id, day_name, time_slot_id)`
- `INDEX idx_session_target_slot (timetable_version_id, target_group_id, day_name, time_slot_id)`

#### Table: `violations`
Persisted validation defects detected by the independent validator.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `timetable_version_id`| `UUID` | No | — | FK &rarr; `timetable_versions(id)` ON DELETE CASCADE |
| `rule_id` | `VARCHAR(16)` | No | — | e.g., `A01`, `B03`, `C02` |
| `rule_level` | `VARCHAR(2)` | No | — | `'A'`, `'B'`, or `'C'` |
| `severity` | `VARCHAR(16)` | No | — | `'error'`, `'warning'`, `'info'` |
| `description` | `TEXT` | No | — | Human-readable explanation |
| `affected_session_ids`| `JSONB` | No | `'[]'` | Array of `scheduled_session.id`s |
| `affected_entity_ids` | `JSONB` | No | `'[]'` | Array of teacher/room/division UUIDs |
| `created_at` | `TIMESTAMPTZ` | No | `CURRENT_TIMESTAMP` | Validation timestamp |

*Constraints & Indexes:*
- `CONSTRAINT chk_rule_level CHECK (rule_level IN ('A', 'B', 'C'))`
- `INDEX idx_violations_version (timetable_version_id, rule_level)`

#### Table: `session_exceptions`
Date-specific deviations from the master published weekly timetable.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `timetable_version_id`| `UUID` | No | — | FK &rarr; `timetable_versions(id)` ON DELETE RESTRICT |
| `scheduled_session_id`| `UUID` | No | — | FK &rarr; `scheduled_sessions(id)` ON DELETE CASCADE |
| `exception_date` | `DATE` | No | — | Specific date (e.g., `2026-11-04`) |
| `exception_type` | `VARCHAR(32)` | No | — | `'cancelled'`, `'substituted'`, `'rescheduled'` |
| `substitute_teacher_id`| `UUID` | Yes | `NULL` | FK &rarr; `teachers(id)` ON DELETE SET NULL |
| `alternate_room_id` | `UUID` | Yes | `NULL` | FK &rarr; `rooms(id)` ON DELETE SET NULL |
| `alternate_slot_id` | `UUID` | Yes | `NULL` | FK &rarr; `time_slots(id)` ON DELETE SET NULL |
| `reason` | `TEXT` | No | — | Reason for change |
| `requires_makeup` | `BOOLEAN` | No | `FALSE` | Whether a makeup session must be booked |
| `created_by` | `UUID` | No | — | FK &rarr; `user_accounts(id)` |
| `created_at` | `TIMESTAMPTZ` | No | `CURRENT_TIMESTAMP` | Creation audit |

*Constraints & Indexes:*
- `CONSTRAINT uq_session_exception_date UNIQUE (scheduled_session_id, exception_date)`
- `INDEX idx_exceptions_date_lookup (exception_date, timetable_version_id)`

---

### 2.5 Security & Audit

#### Table: `user_accounts`
Authentication accounts for administrative and portal access.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `email` | `VARCHAR(255)` | No | — | Institutional login identifier |
| `password_hash` | `VARCHAR(255)` | No | — | Argon2id password hash |
| `role` | `VARCHAR(32)` | No | — | `'admin'`, `'teacher'`, `'student'` |
| `department_id` | `UUID` | No | — | FK &rarr; `departments(id)` ON DELETE RESTRICT |
| `linked_entity_id` | `UUID` | Yes | `NULL` | FK to `teachers.id` or `students.id` |
| `is_active` | `BOOLEAN` | No | `TRUE` | Account lock flag |
| `created_at` | `TIMESTAMPTZ` | No | `CURRENT_TIMESTAMP` | Account creation |

*Constraints & Indexes:*
- `CONSTRAINT uq_user_email UNIQUE (email)`
- `CONSTRAINT chk_user_role CHECK (role IN ('admin', 'teacher', 'student'))`

#### Table: `audit_logs`
Append-only system security and workflow audit trail.

| Column | Data Type | Nullable | Default | Constraints / Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | No | `gen_random_uuid()` | Primary Key |
| `user_id` | `UUID` | Yes | `NULL` | FK &rarr; `user_accounts(id)` ON DELETE SET NULL |
| `action` | `VARCHAR(64)` | No | — | e.g., `'TIMETABLE_PUBLISH'`, `'SESSION_MOVE'` |
| `entity_type` | `VARCHAR(64)` | No | — | e.g., `'TIMETABLE_VERSION'`, `'TEACHER'` |
| `entity_id` | `UUID` | Yes | `NULL` | Targeted entity identifier |
| `payload` | `JSONB` | Yes | `NULL` | Diff or operational context |
| `ip_address` | `INET` | Yes | `NULL` | Origin client IP |
| `created_at` | `TIMESTAMPTZ` | No | `CURRENT_TIMESTAMP` | Timestamp |

---

## 3. Referential Integrity Matrix

| Child Table | Foreign Key | Parent Table | On Delete Action | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `divisions` | `home_room_id` | `rooms` | `SET NULL` | Division remains even if classroom changes |
| `batches` | `division_id` | `divisions` | `CASCADE` | Batches only exist within a division |
| `subjects` | `department_id` | `departments` | `RESTRICT` | Prevent orphaned syllabus items |
| `teaching_assignments` | `teacher_id` | `teachers` | `RESTRICT` | Cannot delete faculty with active teaching assignments |
| `timetable_versions` | `parent_version_id` | `timetable_versions` | `SET NULL` | Preserves lineage if an intermediate draft is purged |
| `scheduled_sessions` | `timetable_version_id` | `timetable_versions` | `CASCADE` | Purging a draft version cleans up all its scheduled cells |
| `scheduled_sessions` | `room_id` | `rooms` | `RESTRICT` | Cannot delete a room actively used in a timetable version |
| `violations` | `timetable_version_id` | `timetable_versions` | `CASCADE` | Re-running validation replaces previous violation records |
| `session_exceptions` | `scheduled_session_id` | `scheduled_sessions` | `CASCADE` | Exception belongs to a scheduled session |

---

## 4. Migration Strategy

EduPlus uses version-controlled database migrations (Alembic for Python / Flyway for JVM/Go) with strict forward/backward compatibility:

```
migrations/
├── 0001_initial_academic_structure.sql
├── 0002_teaching_resources_and_facilities.sql
├── 0003_scheduling_configuration.sql
├── 0004_generation_and_versions.sql
├── 0005_sessions_and_violations.sql
└── 0006_security_and_audit.sql
```

### Migration Rules:
1. **Never Drop Columns In-Place:** Deprecations follow a two-release cycle: mark nullable &rarr; deprecate in code &rarr; drop column.
2. **Transactional DDL:** All migration scripts run in atomic transactions (`BEGIN ... COMMIT`).
3. **Seed Data:** Standard time slots (`TS1` to `TS8`) and standard days are seeded in migration `0003`.
4. **Zero-Downtime Safe:** Compound indexes on `scheduled_sessions` are created with `CREATE INDEX CONCURRENTLY` in production environments.

---

## 5. Example Data Records (AIML Department Baseline)

### Department & Cohort
```sql
INSERT INTO departments (id, code, name, college_name)
VALUES ('d0000001-0000-0000-0000-000000000001', 'AIML', 'Artificial Intelligence & Machine Learning', 'Example Engineering College');

INSERT INTO academic_years (id, department_id, year_number, label)
VALUES ('y0000003-0000-0000-0000-000000000003', 'd0000001-0000-0000-0000-000000000001', 3, 'Third Year');

INSERT INTO divisions (id, academic_year_id, name, strength)
VALUES ('v000003a-0000-0000-0000-00000000003a', 'y000003-0000-0000-0000-000000000003', 'A', 60);

INSERT INTO batches (id, division_id, name, capacity)
VALUES 
('b00000b1-0000-0000-0000-0000000000b1', 'v000003a-0000-0000-0000-00000000003a', 'B1', 20),
('b00000b2-0000-0000-0000-0000000000b2', 'v000003a-0000-0000-0000-00000000003a', 'B2', 20),
('b00000b3-0000-0000-0000-0000000000b3', 'v000003a-0000-0000-0000-00000000003a', 'B3', 20);
```

### Teacher & Room
```sql
INSERT INTO teachers (id, department_id, name, short_name, designation, weekly_workload_cap, email)
VALUES ('t0000001-0000-0000-0000-000000000001', 'd0000001-0000-0000-0000-000000000001', 'Dr. Priya Sharma', 'PVS', 'Professor & HOD', 14, 'priya.sharma@college.edu');

INSERT INTO rooms (id, department_id, name, type, capacity, floor)
VALUES 
('r0000101-0000-0000-0000-000000000101', 'd0000001-0000-0000-0000-000000000001', 'LH-101', 'classroom', 70, 1),
('r0000201-0000-0000-0000-000000000201', 'd0000001-0000-0000-0000-000000000001', 'Lab-2 (GPU)', 'laboratory', 30, 2);
```

### Scheduled Session
```sql
INSERT INTO scheduled_sessions (
    id, timetable_version_id, teaching_assignment_id, teacher_id, room_id,
    day_name, time_slot_id, session_type, target_group_type, target_group_id, is_frozen
) VALUES (
    's0000001-0000-0000-0000-000000000001',
    'tt000001-0000-0000-0000-000000000001',
    'ta000001-0000-0000-0000-000000000001',
    't0000001-0000-0000-0000-000000000001',
    'r0000101-0000-0000-0000-000000000101',
    'Monday',
    'ts000001-0000-0000-0000-000000000001',
    'lecture',
    'division',
    'v000003a-0000-0000-0000-00000000003a',
    FALSE
);
```

---

## 6. Data Import & Ingestion Validation

When populating academic data from external SIS (Student Information Systems) or Excel/CSV uploads:
1. **Staging Schema:** Data is loaded first into unconstrained staging tables (`staging_teachers`, `staging_courses`).
2. **Pre-Ingestion Verifications:**
   - Confirm room capacity $\ge$ division strength for assigned lecture rooms.
   - Verify weekly hours match $L + T + P$ credit totals.
   - Ensure elective group memberships sum to division or cohort totals without orphan students.
3. **Transactional Migration to Core:** Once staging validation succeeds with 0 errors, records are copied into production tables in foreign-key dependency order within a single transaction.
