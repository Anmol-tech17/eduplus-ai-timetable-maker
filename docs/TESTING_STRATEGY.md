# EduPlus — Testing Strategy

> **Document ID:** TESTING_STRATEGY  
> **Version:** 0.1  
> **Status:** Planned — no tests exist in the prototype phase

---

## 1. Overview

Testing is organized in layers, with the most critical tests — validator correctness and solver constraint tests — having the highest priority.

| Layer | Framework | Priority |
|-------|-----------|---------|
| Unit tests (domain logic) | pytest | High |
| Database integrity tests | pytest + SQLAlchemy | High |
| Validator tests (constraint correctness) | pytest | Critical |
| Solver integration tests | pytest | High |
| Property-based tests (solver) | Hypothesis | High |
| API tests (endpoints + RBAC) | pytest + httpx | High |
| Authorization tests | pytest | Critical |
| UI interaction tests | Playwright | Medium |
| Performance benchmarks | locust / timeit | Medium |

---

## 2. Validator Tests (Highest Priority)

The independent validator must be tested exhaustively before the solver is built.

### Required Scenarios

| ID | Scenario | Expected Result |
|----|---------|----------------|
| VT01 | Teacher assigned two sessions at same time | Rule A01 violation detected |
| VT02 | Room assigned two sessions at same time | Rule A02 violation detected |
| VT03 | Whole-division session conflicts with batch session | Rule A03/A04 violation detected |
| VT04 | EG_CV and EG_NLP scheduled simultaneously | Rule A03/A04 violation (overlap) |
| VT05 | EG_CV and EG_ROBO scheduled simultaneously | Valid — no student overlap |
| VT06 | Lab placed at 12:00–14:00 with 13:00 lunch | Rule A08 violation |
| VT07 | Lab placed at 14:00–16:00 (post-lunch) | Valid |
| VT08 | Lab in a classroom | Rule A05 violation |
| VT09 | Lecture in a laboratory | Rule A05 violation |
| VT10 | Room capacity 20, session for 25 students | Rule A06 violation |
| VT11 | Lab placed in only one slot (not 2 consecutive) | Rule A07 violation |
| VT12 | Lab placed in two non-consecutive slots | Rule A07 violation |
| VT13 | Session outside working hours (07:00–08:00) | Rule A09 violation |
| VT14 | Teacher marked absolutely unavailable at that slot | Rule A10 violation |
| VT15 | Teacher assigned a subject they are not assigned to | Rule A11 violation |
| VT16 | Timetable missing 2 of 15 required sessions | Rule A12 — incomplete |
| VT17 | Valid hand-crafted timetable | All checks pass |
| VT18 | Level A violation present → publication blocked | A13 gate enforced |

---

## 3. Solver Integration Tests

| ID | Scenario | Expected Result |
|----|---------|----------------|
| ST01 | Feasible realistic dataset (Year 3, Div A) | Complete timetable produced |
| ST02 | Teacher double-booked in input assignments | Pre-solve detects overload |
| ST03 | More lab hours than available lab slots | Pre-solve detects infeasibility |
| ST04 | Missing room for session type | Pre-solve reports no compatible room |
| ST05 | Non-overlapping elective groups run simultaneously | Produced in candidate |
| ST06 | Overlapping elective groups cannot be simultaneous | Scheduling prevents this |
| ST07 | Lab continuity enforced in all candidates | No split labs in any candidate |
| ST08 | All Division 3A lunch slots preserved | 13:00–14:00 free in all candidates |
| ST09 | Teacher workload cap (5h/day) enforced | No candidate exceeds cap |
| ST10 | Timeout without solution | Status = TIMEOUT, not INFEASIBLE |
| ST11 | Repair preserves unaffected sessions | Frozen sessions unchanged |
| ST12 | Repair respects all Level A rules | No violation in repaired candidate |

---

## 4. Property-Based Tests (Hypothesis)

For the scheduler, use property-based testing to generate random but valid scheduling inputs and verify invariants:

```python
@given(generate_feasible_input())
def test_produced_timetable_passes_validator(input_snapshot):
    result = scheduler.run(input_snapshot)
    if result.status == 'feasible':
        violations = validator.validate(result.timetable)
        assert violations == [], f"Validator found violations: {violations}"

@given(generate_feasible_input())
def test_no_teacher_double_booking(input_snapshot):
    result = scheduler.run(input_snapshot)
    if result.status == 'feasible':
        assert not has_teacher_double_booking(result.timetable)
```

---

## 5. Authorization Tests

| ID | Test | Expected |
|----|------|---------|
| AT01 | Student calls `/admin/timetable/generate` | 403 Forbidden |
| AT02 | Teacher calls `/admin/publish/{id}` | 403 Forbidden |
| AT03 | Student accesses unpublished draft timetable | 403 Forbidden |
| AT04 | Admin publishes timetable with Level A violation | 422 Unprocessable — blocked by server |
| AT05 | Unauthenticated request to any protected endpoint | 401 Unauthorized |
| AT06 | Teacher accesses another teacher's requests | 403 Forbidden |
| AT07 | Attempt to relax Level A constraint via API | 422 — rejected |

---

## 6. API Tests

All endpoints must be tested for:
- Correct HTTP status codes
- Correct response schema (Pydantic validation)
- Authorization enforcement (wrong role → 403)
- Input validation (malformed body → 422)
- Not-found cases (non-existent IDs → 404)

---

## 7. UI Interaction Tests (Playwright)

| Test | Scenario |
|------|---------|
| UI01 | Login with admin credentials → lands on admin dashboard |
| UI02 | Login with teacher credentials → lands on teacher dashboard |
| UI03 | Login with student credentials → lands on student dashboard |
| UI04 | Wrong password → error message shown |
| UI05 | Admin selects Candidate 2 → Publish button is disabled |
| UI06 | Admin selects Candidate 1 → Publish button is enabled |
| UI07 | Teacher submits request form with empty fields → validation error shown |
| UI08 | Teacher submits valid request → appears in My Requests list |
| UI09 | Student submits query → success message shown, mock notice visible |
| UI10 | Admin filters timetable by teacher → only matching sessions visible |

---

## 8. Infeasibility Tests

| ID | Scenario | Expected |
|----|---------|---------|
| IF01 | Teacher assigned 8h on a 5h-cap day | Pre-solve: teacher overload |
| IF02 | All labs need same room simultaneously | Pre-solve: lab capacity insufficient |
| IF03 | A session requirement has no compatible room | Pre-solve: no compatible room |
| IF04 | Solver times out | Status = TIMEOUT; no feasibility claim; partial diagnostic |
| IF05 | Conflicting pinned sessions | Pre-solve: pinned conflict detected |

---

## 9. Test Fixtures

A set of standard test fixtures must be prepared:

| Fixture | Description |
|---------|-------------|
| `minimal_feasible` | Year 3, Div A only; 1 subject, 1 teacher, 1 room — always solvable |
| `realistic_aiml` | Year 3 Div A with all subjects, electives, lab batches |
| `teacher_overloaded` | Teacher assigned 10h/day — should fail pre-solve |
| `missing_room` | Practical with no compatible lab — should fail pre-solve |
| `elective_overlap_conflict` | EG_CV and EG_NLP both scheduled Monday 09:00 — validator catches |
| `lab_spans_lunch` | Lab placed 12:00–14:00 with 13:00 lunch — validator catches A08 |
| `repair_input` | Published timetable V1 + change request → repair target |

---

## 10. What Must Not Be Claimed Until Tests Exist

- Solver correctness is not verified until scenarios ST01–ST12 pass.
- Validator independence is not verified until VT01–VT18 pass.
- Authorization is not secure until AT01–AT07 pass.
- No solver feature is documented as implemented until its test passes.
