# EduPlus — Open Questions and Assumptions

> **Document ID:** OPEN_QUESTIONS_AND_ASSUMPTIONS  
> **Version:** 0.1  
> **Status:** Active — must be resolved before solver implementation

> ⚠️ **These questions must be answered by the institution before the scheduling engine is built.  
> Proceeding with unconfirmed assumptions may produce a timetable that does not match institutional requirements.**

---

## Summary Table

| # | Topic | Status | Impact if Unresolved |
|---|-------|--------|----------------------|
| Q01 | L-T-P credit mapping | ❓ Open | Cannot derive session requirements from curriculum data |
| Q02 | Elective group membership source | ❓ Open | Cannot determine student overlap for elective scheduling |
| Q03 | Group overlap: calculated or maintained | ❓ Open | Different implementations have different error modes |
| Q04 | Lunch: fixed or selectable per division | ❓ Open | Cannot configure lunch constraints correctly |
| Q05 | Teacher lunch requirement | ❓ Open | Teacher idle time calculation may be wrong |
| Q06 | Lab teacher assignment rules | ❓ Open | Cannot determine who teaches which lab batch |
| Q07 | Batch simultaneous lab requirement | ❓ Open | Scheduling strategy for lab batches differs significantly |
| Q08 | Specialized lab equipment requirements | ❓ Open | Cannot confirm room interchangeability |
| Q09 | Policy relaxation approval rules | ❓ Open | Cannot implement the approval workflow |
| Q10 | Solver time limits and candidate count | ❓ Open | Solver may time out or produce too few candidates |
| Q11 | Production authentication method | ❓ Open | Cannot build the auth system |
| Q12 | Deployment requirements | ❓ Open | Cannot design infrastructure |
| Q13 | Student membership data source | ❓ Open | Cannot import enrollment groups |
| Q14 | Saturday working day | ❓ Open | Working day configuration may be wrong |
| Q15 | Make-up session policy | ❓ Open | Cancellation workflow incomplete |

---

## Q01 — L-T-P Credit Mapping

**Question:** How exactly does the institution convert L-T-P (Lecture-Tutorial-Practical) credits into weekly session counts?

**Why it matters:** The scheduling engine derives session requirements from subject credit data. An incorrect mapping produces the wrong number of weekly sessions.

**Current assumption:** L = weekly lecture hours; T = weekly tutorial hours; P = weekly practical lab hours. A subject with L-T-P = 3-1-2 requires 3 lectures, 1 tutorial, and 1 lab (2h block) per week.

**Recommended default:** Confirm with the department's curriculum documents and Autonomous Board of Studies resolution.

**Impact if unresolved:** Session requirements will be incorrect; the generated timetable will not match what students actually need to attend.

**Status:** ❓ Unconfirmed — do not implement solver until confirmed.

---

## Q02 — Elective Group Membership Source

**Question:** Where does elective group membership data come from? Is it maintained by the department, imported from a college ERP, or entered manually?

**Why it matters:** Enrollment group membership determines student overlap. Without authoritative membership data, the system cannot correctly prevent simultaneous scheduling of conflicting elective groups.

**Current assumption:** An administrator manually maintains enrollment groups and the overlap table (`ENROLLMENT_GROUP_OVERLAP`) before scheduling.

**Recommended default:** Import from college ERP where possible. Provide an admin UI for manual maintenance as a fallback.

**Impact if unresolved:** Overlap data may be incorrect; elective conflicts may be missed.

**Status:** ❓ Unconfirmed.

---

## Q03 — Group Overlap: Calculated or Manually Maintained

**Question:** Should the system calculate enrollment group overlap by comparing individual student membership lists, or should an administrator explicitly mark which groups overlap?

**Why it matters:**
- Calculated from membership: more accurate, requires individual student records.
- Manually maintained: simpler, but may be incorrect if not updated when students change electives.

**Current assumption:** Explicit `ENROLLMENT_GROUP_OVERLAP` table maintained by admin. Individual student membership stored where available but overlap is the authoritative field.

**Recommended default:** Store both — individual membership for audit, explicit overlap table for scheduling. Compute overlap automatically from membership on import; allow admin override.

**Impact if unresolved:** May schedule conflicting electives simultaneously without warning.

**Status:** ❓ Unconfirmed.

---

## Q04 — Lunch: Fixed or Selectable Per Division

**Question:** Does each division have a single fixed lunch slot, or does the institution allow a division to take lunch at any slot within a permitted window?

**Why it matters:** The domain model supports both. The solver constraint differs significantly:
- Fixed slot: block exactly one slot for lunch.
- Permitted window: ensure at least one slot in the window is lunch; the solver must choose.

**Current assumption (demo):** Division 3A has a fixed lunch slot at 13:00–14:00. Division 3B can take lunch at 12:00–13:00 or 13:00–14:00 per DIVISION_LUNCH_POLICY.

**Recommended default:** Fixed slot per division, configured by admin before generation.

**Impact if unresolved:** Lunch constraints may be over- or under-constrained in the solver.

**Status:** ❓ Unconfirmed — institution must specify.

---

## Q05 — Teacher Lunch Requirement

**Question:** Are teachers required to have a lunch break? Is it the same slot as any of their divisions? Or is it configurable per teacher?

**Why it matters:** If teachers must be free during their assigned lunch slot, this creates an additional availability constraint distinct from student lunch. The specification notes: "Do not assume that every teacher and room must be unavailable whenever any division is having lunch."

**Current assumption:** Teacher lunch is not a separate hard constraint. Teacher unavailability is configured in `TEACHER_AVAILABILITY`. If a teacher needs lunch, they mark a slot as unavailable.

**Impact if unresolved:** Teachers may be assigned sessions during periods they cannot attend for personal reasons.

**Status:** ❓ Unconfirmed.

---

## Q06 — Lab Teacher Assignment Rules

**Question:** When a division has 3 batches and 1 lab teacher assigned, does that teacher take all 3 batch labs sequentially? Or can different teachers handle different batches?

**Why it matters:** This affects whether the teacher's daily workload cap can accommodate teaching labs for 3 batches (potentially 6 hours of lab per day if sequential).

**Current assumption (demo):** Each lab batch has a separate TEACHING_ASSIGNMENT. A teacher may be assigned to labs for all 3 batches if their workload cap allows. The solver respects the cap.

**Impact if unresolved:** Teacher overload conditions may not be detected correctly.

**Status:** ❓ Unconfirmed.

---

## Q07 — Batch Simultaneous Lab Requirement

**Question:** Must all batches of a division complete their practical in the same week? Can Batch B1 and B2 do their labs on different days while B3 waits until the following week?

**Confirmed in spec:** Batches can be scheduled flexibly with the objective of reducing idle time. Do not force simultaneous labs.

**Remaining open question:** Is there a maximum lag allowed between when different batches complete the same lab? For example, is it acceptable for B1 to complete Lab 3 two weeks before B3?

**Current assumption:** All batches must complete each lab within the same weekly template (i.e., the weekly template repeats identically each week).

**Impact if unresolved:** Multi-week rotation models cannot be supported without additional scheduling horizon data.

**Status:** ❓ Partially confirmed — flexible scheduling confirmed; lag limit unconfirmed.

---

## Q08 — Specialized Lab Equipment Requirements

**Question:** Do any subjects require specific lab equipment that is only available in certain rooms? For example, does a GPU-intensive lab require AI/ML Lab 1 specifically, or can it use any lab?

**Why it matters:** Room interchangeability is currently assumed per lab type. If specialized rooms are required, the room assignment is no longer flexible.

**Current assumption:** Labs of the same type are interchangeable unless an equipment requirement is explicitly configured in `ROOM_CAPABILITY`.

**Impact if unresolved:** The solver may assign a session to a lab that lacks required equipment.

**Status:** ❓ Unconfirmed — lab equipment mapping needed.

---

## Q09 — Policy Relaxation Approval Rules

**Question:** Who is authorized to approve a Level B policy relaxation? Are there escalation rules (e.g., only the HoD can approve)? Are there maximum relaxation bounds (e.g., max 7 hours per day, never 8)?

**Why it matters:** The authorization workflow and maximum permitted relaxation values must be implemented before the relaxation feature is built.

**Current assumption:** Any admin can approve. Maximum relaxation bounds are not enforced in the prototype.

**Impact if unresolved:** The relaxation approval system cannot be implemented securely.

**Status:** ❓ Unconfirmed.

---

## Q10 — Solver Time Limits and Candidate Count

**Question:** How many seconds should the solver be allowed to run? How many candidate timetables should it produce?

**Why it matters:** CP-SAT may run indefinitely on complex inputs if not time-limited. Too short a time limit may produce poor results; too long may frustrate the admin.

**Current assumption:** Default time limit: 60 seconds. Default candidate count: 3.

**Recommended default:** Start with 60 seconds / 3 candidates; allow admin configuration.

**Impact if unresolved:** Solver may time out without producing useful results, or run too long.

**Status:** ❓ Provisional defaults documented; must be validated against actual dataset sizes.

---

## Q11 — Production Authentication Method

**Question:** What authentication system will be used? LDAP/SSO (integrated with college ERP)? Email/password? OAuth2? Google Workspace?

**Why it matters:** Production auth affects the entire user management architecture.

**Current assumption (demo):** Mock credentials in sessionStorage. No real auth.

**Impact if unresolved:** Cannot implement production login, password reset, session management, or ERP integration.

**Status:** ❓ Unconfirmed — must be decided before production implementation.

---

## Q12 — Deployment Requirements

**Question:** Will EduPlus be deployed on-premises (college server), cloud (AWS/GCP/Azure), or a managed hosting service? Who manages the server?

**Why it matters:** Deployment target affects infrastructure choices, Docker usage, network security, database backup strategy.

**Current assumption:** On-premises server with Linux OS; Docker Compose for initial deployment.

**Status:** ❓ Unconfirmed.

---

## Q13 — Student Membership Data Source

**Question:** How is individual student data obtained? Is there a college ERP API? CSV export? Manual entry?

**Why it matters:** Student membership is needed for enrollment group management and (eventually) attendance and notification features.

**Current assumption:** Admin manually enters enrollment group assignments. Individual student records are stored only where required.

**Status:** ❓ Unconfirmed.

---

## Q14 — Saturday as Working Day

**Question:** Does the institution hold classes on Saturday? If so, for which years?

**Current assumption:** Saturday is disabled by default. Admin can enable it per configuration.

**Impact if unresolved:** Timetable horizon may be incorrect; solver may miss available slots.

**Status:** ❓ Unconfirmed.

---

## Q15 — Make-Up Session Policy

**Question:** When a session is cancelled, is a make-up session automatically required? Who decides? Is it per-subject or per-teacher?

**Why it matters:** The cancellation workflow must know whether to prompt for a make-up session or simply record the exception.

**Current assumption:** Admin decides per cancellation whether a make-up is required. The system records the decision but does not auto-schedule make-ups.

**Status:** ❓ Unconfirmed.

---

## Confirmed Decisions

| # | Decision | Source |
|---|----------|--------|
| C01 | Electives may run simultaneously if enrollment groups do not conflict | Project specification |
| C02 | Lab batches scheduled flexibly — objective: minimize idle time | Project specification |
| C03 | Infeasible generation may return partial diagnostic draft (never publishable) | Project specification |
| C04 | Published timetable changes use repair mode — minimize changes | Project specification |
| C05 | Lunch window: 12:00–15:00, different slots may be configured per division | Project specification |
| C06 | LLM must not place sessions or determine validity | Project specification |
| C07 | Student names must not be sent to an LLM | Project specification |
| C08 | Independent validator must check separately from solver | Project specification |
| C09 | Level A hard constraints cannot be relaxed through any interface | Project specification |
