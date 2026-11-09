# EduPlus — Domain Model

> **Document ID:** DOMAIN_MODEL  
> **Version:** 0.1

---

## 1. Academic Hierarchy

```
Department
└── Academic Year (1, 2, 3, 4)
    └── Division (A, B, C, …)
        ├── Batch (B1, B2, B3) — for lab practicals
        └── Enrollment Group — for elective subjects
```

A **Department** is the top-level organizational unit. All scheduling is scoped to one department.

An **Academic Year** (1–4) contains multiple **Divisions**. A Division is the standard student cohort for scheduling purposes. Whole-division sessions are attended by all students in the division.

A **Batch** is a sub-group of a division used exclusively for laboratory practicals. A typical division has 3 batches (B1, B2, B3). Batch sessions are independent of other batches — B1 having a lab does not conflict with B2 or B3.

An **Enrollment Group** is a named set of students enrolled in a specific elective subject. Enrollment groups may span students from the same division. Two enrollment groups conflict for scheduling purposes if and only if they share students.

---

## 2. Subject Semantics

A **Subject** is an academic course offered in a specific year. Subjects carry LTP credits: Lecture–Tutorial–Practical.

| Session Type | Duration | Target Group | Notes |
|-------------|----------|-------------|-------|
| Lecture | 1 hour | Division | Whole-division; no splitting |
| Tutorial | 1 hour | Division | May be whole-division or sub-group |
| Practical (Lab) | 2 consecutive hours | Batch | Must use a laboratory room |

**Fixed subjects** are attended by all students in a division (typically 5–6 per division per semester).

**Elective subjects** are attended by a predefined enrollment group. The enrollment group does not equal the whole division.

---

## 3. Session Requirements

A **Session Requirement** is the derived weekly obligation for a subject offering:

- A subject with L-T-P = 3-1-2 requires: 3 × 1-hour lecture, 1 × 1-hour tutorial, and 1 × 2-hour practical.
- Session requirements are derived from the LTP credits via the institution's configured credit mapping.
- The credit mapping must be confirmed with the institution before the solver is implemented (see Open Questions Q01).

Session requirements are stored separately from scheduled sessions. A complete timetable has every session requirement placed exactly once per week.

---

## 4. Teaching Assignments

A **Teaching Assignment** specifies: which teacher teaches which subject for which target group with which session type.

- A subject may have different teachers for different divisions.
- A subject may have different teachers for lectures vs. practicals.
- The scheduler does not freely choose teachers — it uses the assignment record as the source of truth.
- Co-teaching is out of scope for Version 1.

---

## 5. Student Group Overlap

Two sessions conflict for student attendance if their target groups share students.

| Group A | Group B | Conflict? |
|---------|---------|----------|
| DIV_3A | DIV_3A | Yes (same group) |
| DIV_3A | DIV_3A/B1 | Yes (B1 is a subset of DIV_3A) |
| DIV_3A/B1 | DIV_3A/B2 | No (different batches) |
| EG_CV | EG_NLP | Yes (if they share students — must be confirmed from enrollment data) |
| EG_CV | EG_ROBO | No (if confirmed no shared students) |

Overlap between enrollment groups is determined by the authoritative `ENROLLMENT_GROUP_OVERLAP` table — not inferred from group sizes.

---

## 6. Lunch Policy

The lunch period falls within the 12:00–15:00 window and occupies one hour.

- Different divisions may have different lunch slots.
- A division's lunch slot is configured in `DIVISION_LUNCH_POLICY`.
- Labs cannot span the target group's lunch period (Rule A08).
- The lunch slot is excluded from the student gap calculation.
- Teacher lunch is not a separate system constraint — teachers configure their own unavailability.

**Critical distinction:** Teacher, student-group, and room availability are separate constraints. A teacher being free during a student group's lunch does not mean the teacher is forbidden from teaching another group at that time.

---

## 7. Weekly Template vs. Date-Specific Exceptions

The timetable produced by the solver is a **weekly recurring template**. It repeats unchanged every week for the semester.

A **Session Exception** is a date-specific override applied to one occurrence of a session:
- Cancellation (one class does not meet)
- Substitution (different teacher covers one occurrence)
- Room change (moved to a different room for one date)
- Reschedule (one occurrence moved to a different time or date)

Exceptions do not modify the weekly template. They are layered on top of it for display and notification purposes.

A structural change that should repeat every week requires creating a new **Timetable Version** via the repair workflow.

---

## 8. Glossary

| Term | Definition |
|------|-----------|
| **Division** | A standard student cohort within a year; whole-division sessions are for all students |
| **Batch** | A sub-group of a division for laboratory practicals |
| **Enrollment Group** | A named set of students enrolled in an elective subject |
| **Session Requirement** | The weekly obligation to place a specific session type for a specific target group |
| **Scheduled Session** | A placed instance of a session requirement in a timetable version |
| **Timetable Version** | A complete or partial weekly timetable; versioned and immutable once published |
| **Teaching Assignment** | The approved record of which teacher teaches which subject for which group |
| **Lunch Policy** | The configured lunch slot(s) per division |
| **Session Exception** | A date-specific override on a published timetable version |
| **Repair Operation** | A constrained re-optimization that minimizes changes to an existing published timetable |
| **Diagnostic Draft** | An incomplete timetable candidate produced when full scheduling is infeasible |
| **Independent Validator** | A module that verifies constraint compliance separately from the solver |
| **Enrollment Group Overlap** | A confirmed conflict between two enrollment groups that share students |
| **Level A Rule** | A structural hard constraint that cannot be relaxed |
| **Level B Rule** | An institutional policy limit that may be relaxed with explicit approval |
| **Level C Preference** | A soft optimization objective; violations do not prevent publication |
