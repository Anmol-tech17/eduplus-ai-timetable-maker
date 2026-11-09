# EduPlus — Scheduling Rules Catalogue

> **Document ID:** SCHEDULING_RULES  
> **Version:** 0.1  
> **Status:** Draft — based on project specification; default values provisional until confirmed by institution

---

## 1. Rule Levels

### Level A — Structural Hard Constraints
Cannot be relaxed under any circumstances, through any interface or API call. A timetable violating any Level A rule is **invalid** and **unpublishable**. The independent validator enforces these rules separately from the solver.

### Level B — Institutional Policy Limits
Hard by default. An administrator may approve an explicitly audited relaxation. Every relaxation must be logged with rule ID, original value, new value, reason, and approving administrator. **Level B relaxations cannot bypass Level A.**

### Level C — Soft Preferences
Optimization objectives, not correctness requirements. Violations do not prevent publication. The solver minimizes Level C violations subject to Level A and B satisfaction.

---

## 2. Level A Rules

### A01 — Teacher Simultaneous Booking
**Statement:** A teacher cannot be assigned to two sessions that overlap in time.  
**Scope:** Across all divisions, batches, and years in the same department.  
**Enforcement:** Solver constraint + independent validator.  
**Cannot be relaxed:** Yes.  
**Example violation:** Prof. Mehta assigned to ML Lab (B1) and DL Lecture (Div A) both at Monday 09:00–10:00.

---

### A02 — Room Simultaneous Booking
**Statement:** A room cannot host two sessions that overlap in time.  
**Scope:** All rooms (classrooms and laboratories).  
**Cannot be relaxed:** Yes.

---

### A03 — Student Simultaneous Attendance
**Statement:** A student cannot be required to attend two sessions that overlap in time.  
**Scope:** Determined by target group membership.  
**Cannot be relaxed:** Yes.

---

### A04 — Group Overlap Semantics
**Statement:** Two sessions conflict for student attendance if their target groups share any students.  
Rules:
1. A whole-division session (e.g., `DIV_3A`) overlaps with all batches of that division (`DIV_3A/B1`, `DIV_3A/B2`, `DIV_3A/B3`) and with all elective groups belonging to Division A.
2. A batch session (`DIV_3A/B1`) does **not** conflict with sessions for `DIV_3A/B2` or `DIV_3A/B3`.
3. Two elective group sessions conflict if their enrollment group memberships overlap.
4. Overlap must be determined from authoritative enrollment data, not inferred from group sizes.

**Example (valid):** EG_CV and EG_ROBO run simultaneously — no student overlap confirmed.  
**Example (invalid):** EG_CV and EG_NLP run simultaneously — students E20–E28 are in both groups.

---

### A05 — Session Type and Room Compatibility
**Statement:** Theory lectures and tutorials must use classrooms. Laboratory practicals must use laboratories.  
**Cannot mix:** A lecture cannot be placed in a laboratory; a practical cannot be placed in a classroom.

---

### A06 — Room Capacity
**Statement:** The room assigned to a session must have a capacity ≥ the number of students in the target group.  
**Cannot be relaxed:** Yes.  
**Note:** Classes cannot be split across multiple rooms in Version 1.

---

### A07 — Lab Session Continuity
**Statement:** A laboratory practical session must occupy exactly two consecutive time slots (2 hours) in the same room.  
**Cannot be split** across different rooms or non-consecutive slots.

---

### A08 — Labs Cannot Span Lunch
**Statement:** A two-hour lab session cannot span the configured lunch slot of the target group.  
**Rationale:** A lab placed at 12:00–14:00 where lunch is 13:00–14:00 would require students to miss lunch — prohibited.  
**Scope:** Determined by the target group's configured lunch slot, not a universal global lunch time.  
**Cannot be relaxed:** Yes.

---

### A09 — Working Hours and Days
**Statement:** No session may be placed outside the configured working hours (08:00–18:00) or on non-working days (default: Saturday, Sunday).  
**Configuration:** Saturday may be enabled per institution configuration.

---

### A10 — Absolute Unavailability
**Statement:** Sessions must not be placed during periods marked as absolutely unavailable for the teacher, room, or student group.  
**Distinction:** Absolute unavailability is a hard constraint (Level A). Preferred availability is a soft preference (Level C).

---

### A11 — Teaching Assignment Integrity
**Statement:** Only the teacher specified in the approved teaching assignment may teach a subject for a given division and session type.  
**The scheduler cannot freely reassign teachers.** Co-teaching is out of scope for Version 1.

---

### A12 — Complete Requirement Coverage
**Statement:** A publishable timetable must contain exactly one placed session for each required session in the session requirements for the target divisions.  
**Incomplete:** A timetable with unplaced requirements is diagnostic-only and cannot be published.

---

### A13 — Publication Completeness
**Statement:** A timetable version may only be published after:
1. Passing the independent validator (all Level A rules satisfied).
2. Meeting configured publication-completeness requirements (all Level B policy checks passed or explicitly relaxed with approval).
3. Administrator approval.

---

### A14 — No UI/API Hard Rule Bypass
**Statement:** The system must reject any API or UI action that would result in a Level A violation in the published timetable.  
**Enforcement:** Server-side validation is mandatory. Frontend guards are supplementary only.

---

## 3. Level B Rules (Institutional Policy Defaults)

> ⚠️ **These values are provisional defaults from the project specification. They must be confirmed against the institution's actual policy before the solver is implemented.**

| Rule ID | Description | Default | Configurable |
|---------|-------------|---------|-------------|
| B01 | Max student teaching hours per day | 6 hours | Yes, per institution |
| B02 | Max teacher teaching hours per day | 5 hours | Yes, per teacher |
| B03 | Max consecutive teacher teaching | 3 hours | Yes |
| B04 | Teacher weekly workload cap | Per teacher config | Yes, per teacher |
| B05 | Max student internal gap (non-lunch) | 1 hour (no 2+ hour gaps) | Yes |
| B06 | Lunch window (allowed range) | 12:00–15:00 | Yes, per division |
| B07 | Lunch slot assignment | Configurable per division | Yes |
| B08 | Saturday working day | Disabled | Yes |

### B01 — Maximum Student Daily Teaching Hours
Default: 6 contact hours per day per student group (excluding lunch and free periods).  
Relaxation: Administrator may approve up to 7 hours with documented reason.

### B05 — Maximum Student Internal Gap
A student group should not have two or more consecutive free hours between sessions (excluding lunch and end-of-day).  
This is a Level B constraint. It is checked during validation. Gaps at the beginning or end of the day are excluded from the gap calculation.

---

## 4. Level C Soft Preferences

Ordered by default priority (lexicographic — earlier preferences take priority):

| Preference | ID | Description |
|------------|-----|-------------|
| P01 | Minimize student gaps | Reduce non-lunch idle periods within the teaching day |
| P02 | Minimize repair changes | During repair: preserve existing sessions |
| P03 | Spread repeated lectures | Avoid placing all lectures for a subject on consecutive days |
| P04 | Avoid excessive consecutive sessions | Prefer variety over 6 consecutive hours |
| P05 | Balance teacher load by day | Avoid all teaching concentrated on one or two days |
| P06 | Reduce batch idle time | Coordinate batch lab schedules to minimize idle waiting |
| P07 | Prefer home classroom | Assign division's home room where possible |
| P08 | Reduce teacher gaps | Minimize teacher idle time between their own sessions |
| P09 | Respect teacher preferred slots | Honour teacher time preferences where feasible |
| P10 | Improve room utilization | Prefer higher room utilization rate overall |

---

## 5. Rule Interaction Matrix

| Interaction | Rules Involved | Notes |
|-------------|----------------|-------|
| Lab duration and lunch | A07, A08 | A 2-hour lab must not span the target group's configured lunch slot |
| Elective overlap and parallel scheduling | A03, A04 | Non-overlapping enrollment groups may run simultaneously; overlapping groups cannot |
| Division-wide sessions and lab batches | A04 | A whole-division session conflicts with all batches of that division |
| Teacher workload and availability | A01, A10, B02, B03 | Teacher absolute unavailability is Level A; workload cap is Level B |
| Room capacity and session type | A05, A06 | Both must be satisfied simultaneously |
| Daily teaching caps and gap restrictions | B01, B05 | Both are checked independently; a schedule may satisfy one and violate the other |
| Repair frozen sessions and new constraints | A01–A14 | Frozen sessions occupy their slot and room absolutely; new sessions must respect all Level A rules around them |

---

## 6. Plain-Language Conflict Explanation Templates

| Rule | Template |
|------|----------|
| A01 | "{Teacher} is assigned to {Subject A} for {Group X} and {Subject B} for {Group Y} at the same time ({Day}, {Slot}). A teacher cannot teach two sessions simultaneously." |
| A02 | "{Room} is assigned to both {Session A} and {Session B} at {Day} {Slot}. A room cannot host two sessions simultaneously." |
| A03/A04 | "{Group X} and {Group Y} share {N} students. Both are scheduled at {Day} {Slot}. Students in the overlap cannot attend both sessions." |
| A08 | "The lab for {Group} at {Day} {StartSlot}–{EndSlot} spans the configured lunch slot ({LunchSlot}) for {Division}. Labs may not span the target group's lunch." |
| A12 | "{Subject} requires {N} {type} sessions per week for {Group}. Only {M} of {N} are placed. The timetable is incomplete." |

---

## 7. Examples of Valid and Invalid Schedules

### Valid: Simultaneous Electives
- EG_CV (Computer Vision): Monday 10:00–11:00, Room CR302, Prof. Vikram Singh  
- EG_ROBO (Robotics): Monday 10:00–11:00, Room CR501, Prof. Suresh Babu  
✅ **Valid** — EG_CV and EG_ROBO have confirmed zero student overlap (A04 satisfied).

### Invalid: Overlapping Electives
- EG_CV: Monday 10:00–11:00  
- EG_NLP: Monday 10:00–11:00  
❌ **Invalid** — EG_CV and EG_NLP share students E20–E28 (A03/A04 violated).

### Invalid: Lab Spans Lunch
- ML Lab for DIV_3A/B1: Monday 12:00–14:00  
- DIV_3A configured lunch: 13:00–14:00  
❌ **Invalid** — lab spans the target group's lunch slot (A08 violated).

### Valid: Lab Around Lunch
- ML Lab for DIV_3A/B1: Monday 14:00–16:00 (post-lunch)  
✅ **Valid** — lab does not span the 13:00–14:00 lunch slot.

### Invalid: Teacher Double-Booking
- Prof. Mehta: Monday 09:00 — ML Lab (B1, LAB01) AND Monday 09:00 — DL Lecture (Div A, CR301)  
❌ **Invalid** (A01 violated).

---

## 8. Policy Relaxation Record Requirements

When a Level B constraint is relaxed, the system must persist:

| Field | Description |
|-------|-------------|
| `rule_id` | The rule being relaxed (e.g., B01) |
| `original_value` | The original constraint parameter |
| `relaxed_value` | The approved new value |
| `reason` | Documented justification |
| `approved_by` | Administrator who approved |
| `approved_at` | Timestamp |
| `timetable_version_id` | The timetable version this relaxation applies to |
| `compliance_status` | Whether the resulting timetable is fully or partially compliant |

No relaxation may affect Level A constraints. The system must reject any attempt to record a relaxation that would bypass a Level A rule.
