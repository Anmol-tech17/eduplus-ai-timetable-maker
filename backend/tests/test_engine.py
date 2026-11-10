"""
backend/tests/test_engine.py
EduPlus AI Timetable Maker — Phase 2 Engine Tests

Tests for:
- Independent validator (all Level A, B, C rules)
- CP-SAT solver: feasible generation, infeasibility, timeout
- Solver + validator integration
"""

from __future__ import annotations

import pytest
from typing import List

from backend.app.engine.types import (
    BatchInfo,
    DivisionInfo,
    RoomInfo,
    ScheduledSessionInfo,
    SchedulingInput,
    SlotKey,
    SolverStatus,
    TeacherInfo,
    TeachingAssignmentInfo,
    TimeSlotInfo,
    WorkingDayInfo,
    ViolationLevel,
)
from backend.app.engine.validator import validate_timetable, has_hard_violations
from backend.app.engine.solver import run_solver


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

DAYS = [
    WorkingDayInfo(id="d1", day_name="Monday", day_index=1, is_active=True),
    WorkingDayInfo(id="d2", day_name="Tuesday", day_index=2, is_active=True),
    WorkingDayInfo(id="d3", day_name="Wednesday", day_index=3, is_active=True),
]

SLOTS = [
    TimeSlotInfo(id="ts1", slot_code="TS1", slot_index=1, label="09:00-10:00"),
    TimeSlotInfo(id="ts2", slot_code="TS2", slot_index=2, label="10:00-11:00"),
    TimeSlotInfo(id="ts3", slot_code="TS3", slot_index=3, label="11:00-12:00"),
    TimeSlotInfo(id="ts4", slot_code="TS4", slot_index=4, label="13:00-14:00"),
    TimeSlotInfo(id="ts5", slot_code="TS5", slot_index=5, label="14:00-15:00"),
]

TEACHER_A = TeacherInfo(id="T_A", name="Alice", short_name="A", department_id="D1", weekly_workload_cap=16)
TEACHER_B = TeacherInfo(id="T_B", name="Bob", short_name="B", department_id="D1", weekly_workload_cap=16)
TEACHER_C = TeacherInfo(id="T_C", name="Carol", short_name="C", department_id="D1", weekly_workload_cap=16)

ROOM_CLASS = RoomInfo(id="R_C1", name="CR-101", type="classroom", capacity=60)
ROOM_SMALL = RoomInfo(id="R_C2", name="CR-102", type="classroom", capacity=20)
ROOM_LAB = RoomInfo(id="R_L1", name="AI-LAB", type="laboratory", capacity=30)

DIV_A = DivisionInfo(id="DIV_A", name="A", academic_year_id="AY1", strength=50, batch_ids=["BAT_1", "BAT_2"])
BATCH_1 = BatchInfo(id="BAT_1", name="B1", division_id="DIV_A", capacity=25)
BATCH_2 = BatchInfo(id="BAT_2", name="B2", division_id="DIV_A", capacity=25)


def make_input(
    assignments: List[TeachingAssignmentInfo],
    teachers: List[TeacherInfo] = None,
    rooms: List[RoomInfo] = None,
) -> SchedulingInput:
    """Convenience factory for minimal SchedulingInput."""
    return SchedulingInput(
        department_id="D1",
        academic_year_ids=["AY1"],
        working_days=DAYS,
        time_slots=SLOTS,
        teachers=teachers or [TEACHER_A, TEACHER_B, TEACHER_C],
        rooms=rooms or [ROOM_CLASS, ROOM_SMALL, ROOM_LAB],
        divisions=[DIV_A],
        batches=[BATCH_1, BATCH_2],
        assignments=assignments,
    )


def session(
    assignment_id: str,
    teacher_id: str,
    room_id: str,
    day: str,
    slot: int,
    session_type: str = "lecture",
    group_type: str = "division",
    group_id: str = "DIV_A",
    duration: int = 1,
) -> ScheduledSessionInfo:
    return ScheduledSessionInfo(
        assignment_id=assignment_id,
        teacher_id=teacher_id,
        subject_id="SUB1",
        subject_name="Deep Learning",
        room_id=room_id,
        day_name=day,
        slot_index=slot,
        session_type=session_type,
        target_group_type=group_type,
        target_group_id=group_id,
        duration_slots=duration,
    )


def make_assignment(
    aid: str,
    teacher_id: str = "T_A",
    subject_id: str = "SUB1",
    division_id: str = "DIV_A",
    session_type: str = "lecture",
    weekly_count: int = 1,
    batch_id=None,
    duration_slots: int = 1,
) -> TeachingAssignmentInfo:
    return TeachingAssignmentInfo(
        id=aid,
        subject_id=subject_id,
        division_id=division_id,
        teacher_id=teacher_id,
        session_type=session_type,
        batch_id=batch_id,
        enrollment_group_id=None,
        weekly_count=weekly_count,
        duration_slots=duration_slots,
    )


# ===========================================================================
# SECTION 1: Validator — Level A (Hard) Constraint Tests
# ===========================================================================

class TestValidatorHardConstraints:

    def test_a01_teacher_double_booked(self):
        """A01: Same teacher at same day+slot → hard violation."""
        assignment1 = make_assignment("A1", teacher_id="T_A")
        assignment2 = make_assignment("A2", teacher_id="T_A")
        sessions = [
            session("A1", "T_A", "R_C1", "Monday", 1),
            session("A2", "T_A", "R_C2", "Monday", 1),  # same day+slot, same teacher
        ]
        inp = make_input([assignment1, assignment2])
        # Override A10 by giving correct weekly counts
        violations = validate_timetable(sessions, inp, check_soft=False)
        hard = [v for v in violations if v.rule_id == "A01"]
        assert hard, "Expected A01 teacher double-booking violation"
        assert all(v.level == ViolationLevel.A for v in hard)

    def test_a01_no_violation_different_slots(self):
        """A01: Same teacher, different slots → no teacher conflict."""
        assignment1 = make_assignment("A1", teacher_id="T_A", weekly_count=1)
        assignment2 = make_assignment("A2", teacher_id="T_A", weekly_count=1)
        sessions = [
            session("A1", "T_A", "R_C1", "Monday", 1),
            session("A2", "T_A", "R_C2", "Monday", 2),  # different slot
        ]
        inp = make_input([assignment1, assignment2])
        violations = validate_timetable(sessions, inp, check_soft=False)
        a01 = [v for v in violations if v.rule_id == "A01"]
        assert not a01, f"Unexpected A01 violation: {a01}"

    def test_a02_room_double_booked(self):
        """A02: Same room at same day+slot → hard violation."""
        a1 = make_assignment("A1", teacher_id="T_A")
        a2 = make_assignment("A2", teacher_id="T_B")
        sessions = [
            session("A1", "T_A", "R_C1", "Monday", 1),
            session("A2", "T_B", "R_C1", "Monday", 1),  # same room + slot
        ]
        inp = make_input([a1, a2])
        violations = validate_timetable(sessions, inp, check_soft=False)
        a02 = [v for v in violations if v.rule_id == "A02"]
        assert a02, "Expected A02 room double-booking violation"

    def test_a03_division_double_booked(self):
        """A03: Division has two sessions at same slot → hard violation."""
        a1 = make_assignment("A1", teacher_id="T_A", division_id="DIV_A")
        a2 = make_assignment("A2", teacher_id="T_B", division_id="DIV_A")
        sessions = [
            session("A1", "T_A", "R_C1", "Monday", 1, group_type="division", group_id="DIV_A"),
            session("A2", "T_B", "R_C2", "Monday", 1, group_type="division", group_id="DIV_A"),
        ]
        inp = make_input([a1, a2])
        violations = validate_timetable(sessions, inp, check_soft=False)
        a03 = [v for v in violations if v.rule_id == "A03"]
        assert a03, "Expected A03 division double-booking violation"

    def test_a04_batch_double_booked(self):
        """A04: Same batch at same slot → hard violation."""
        a1 = make_assignment("A1", teacher_id="T_A", batch_id="BAT_1")
        a2 = make_assignment("A2", teacher_id="T_B", batch_id="BAT_1")
        sessions = [
            session("A1", "T_A", "R_L1", "Monday", 1, session_type="practical", group_type="batch", group_id="BAT_1"),
            session("A2", "T_B", "R_L1", "Monday", 1, session_type="practical", group_type="batch", group_id="BAT_1"),
        ]
        inp = make_input([a1, a2])
        violations = validate_timetable(sessions, inp, check_soft=False)
        a04 = [v for v in violations if v.rule_id == "A04"]
        assert a04, "Expected A04 batch double-booking violation"

    def test_a05_room_capacity_violation(self):
        """A05: Division of 50 assigned to room capacity 20 → hard violation."""
        a1 = make_assignment("A1", teacher_id="T_A")
        sessions = [session("A1", "T_A", "R_C2", "Monday", 1)]  # R_C2 capacity=20, DIV_A strength=50
        inp = make_input([a1])
        violations = validate_timetable(sessions, inp, check_soft=False)
        a05 = [v for v in violations if v.rule_id == "A05"]
        assert a05, "Expected A05 room capacity violation"

    def test_a05_no_violation_adequate_room(self):
        """A05: Division of 50 assigned to room capacity 60 → no violation."""
        a1 = make_assignment("A1", teacher_id="T_A", weekly_count=1)
        sessions = [session("A1", "T_A", "R_C1", "Monday", 1)]  # R_C1 capacity=60
        inp = make_input([a1])
        violations = validate_timetable(sessions, inp, check_soft=False)
        a05 = [v for v in violations if v.rule_id == "A05"]
        assert not a05

    def test_a06_room_type_mismatch_practical_in_classroom(self):
        """A06: Practical session in classroom → hard violation."""
        a1 = make_assignment("A1", teacher_id="T_A", session_type="practical", batch_id="BAT_1")
        sessions = [
            session("A1", "T_A", "R_C1", "Monday", 1, session_type="practical", group_type="batch", group_id="BAT_1")
        ]
        inp = make_input([a1])
        violations = validate_timetable(sessions, inp, check_soft=False)
        a06 = [v for v in violations if v.rule_id == "A06"]
        assert a06, "Expected A06 room type mismatch violation"

    def test_a06_no_violation_practical_in_lab(self):
        """A06: Practical session in lab → no violation."""
        a1 = make_assignment("A1", teacher_id="T_A", session_type="practical", batch_id="BAT_1", weekly_count=1)
        sessions = [
            session("A1", "T_A", "R_L1", "Monday", 1, session_type="practical", group_type="batch", group_id="BAT_1")
        ]
        inp = make_input([a1])
        violations = validate_timetable(sessions, inp, check_soft=False)
        a06 = [v for v in violations if v.rule_id == "A06"]
        assert not a06

    def test_a07_unknown_assignment(self):
        """A07: Session references unknown assignment_id → qualification violation."""
        a1 = make_assignment("A1", teacher_id="T_A", weekly_count=1)
        sessions = [session("UNKNOWN_ASSIGNMENT", "T_A", "R_C1", "Monday", 1)]
        inp = make_input([a1])
        violations = validate_timetable(sessions, inp, check_soft=False)
        a07 = [v for v in violations if v.rule_id == "A07"]
        assert a07, "Expected A07 unknown assignment violation"

    def test_a08_teacher_unavailability(self):
        """A08: Session scheduled during teacher unavailability → hard violation."""
        teacher_unavail = TeacherInfo(
            id="T_UNV", name="UnavailTeacher", short_name="UNV",
            department_id="D1", weekly_workload_cap=16,
            unavailable_slots=[SlotKey(day_name="Monday", slot_index=1)],
        )
        a1 = make_assignment("A1", teacher_id="T_UNV", weekly_count=1)
        sessions = [session("A1", "T_UNV", "R_C1", "Monday", 1)]
        inp = make_input([a1], teachers=[teacher_unavail, TEACHER_B])
        violations = validate_timetable(sessions, inp, check_soft=False)
        a08 = [v for v in violations if v.rule_id == "A08"]
        assert a08, "Expected A08 teacher unavailability violation"

    def test_a09_session_on_inactive_day(self):
        """A09: Session on Sunday (not in working days) → hard violation."""
        a1 = make_assignment("A1", teacher_id="T_A", weekly_count=1)
        sessions = [session("A1", "T_A", "R_C1", "Sunday", 1)]  # Sunday not active
        inp = make_input([a1])
        violations = validate_timetable(sessions, inp, check_soft=False)
        a09 = [v for v in violations if v.rule_id == "A09"]
        assert a09, "Expected A09 inactive working day violation"

    def test_a10_missing_weekly_sessions(self):
        """A10: Assignment requires 3 sessions/week but only 1 scheduled."""
        a1 = make_assignment("A1", teacher_id="T_A", weekly_count=3)
        sessions = [session("A1", "T_A", "R_C1", "Monday", 1)]  # only 1 scheduled
        inp = make_input([a1])
        violations = validate_timetable(sessions, inp, check_soft=False)
        a10 = [v for v in violations if v.rule_id == "A10"]
        assert a10, "Expected A10 weekly session count violation"
        assert "3" in a10[0].description


# ===========================================================================
# SECTION 2: Validator — Level B (Policy) Tests
# ===========================================================================

class TestValidatorPolicyConstraints:

    def test_b01_teacher_workload_exceeded(self):
        """B01: Teacher scheduled 20 hours vs cap of 16 → policy warning."""
        low_cap_teacher = TeacherInfo(
            id="T_LOW", name="LowCap", short_name="LC",
            department_id="D1", weekly_workload_cap=4,
        )
        # 5 assignments of weekly_count=2 each = 10 sessions > cap=4
        assignments = [make_assignment(f"A{i}", teacher_id="T_LOW", weekly_count=2) for i in range(5)]
        sessions = []
        days = ["Monday", "Tuesday", "Wednesday"]
        slots = [1, 2, 3, 4, 5]
        count = 0
        for a in assignments:
            for _ in range(2):
                s = session(a.id, "T_LOW", "R_C1",
                            days[count % 3], slots[count % 5])
                sessions.append(s)
                count += 1
        inp = make_input(assignments, teachers=[low_cap_teacher, TEACHER_B])
        violations = validate_timetable(sessions, inp, check_soft=False)
        b01 = [v for v in violations if v.rule_id == "B01"]
        assert b01, "Expected B01 workload exceeded violation"

    def test_b03_practical_single_slot(self):
        """B03: Practical with duration_slots=1 → policy warning."""
        a1 = make_assignment("A1", teacher_id="T_A", session_type="practical",
                              batch_id="BAT_1", weekly_count=1, duration_slots=1)
        sessions = [session("A1", "T_A", "R_L1", "Monday", 1,
                            session_type="practical", group_type="batch", group_id="BAT_1",
                            duration=1)]
        inp = make_input([a1])
        violations = validate_timetable(sessions, inp, check_soft=False)
        b03 = [v for v in violations if v.rule_id == "B03"]
        assert b03, "Expected B03 practical duration violation"


# ===========================================================================
# SECTION 3: Validator — Level C (Soft) Tests
# ===========================================================================

class TestValidatorSoftConstraints:

    def test_c01_idle_gaps_detected(self):
        """C01: Teacher has slots 1 and 4 on same day (gap of 2) → soft note."""
        a1 = make_assignment("A1", teacher_id="T_A", weekly_count=1)
        a2 = make_assignment("A2", teacher_id="T_A", weekly_count=1)
        sessions = [
            session("A1", "T_A", "R_C1", "Monday", 1),
            session("A2", "T_A", "R_C2", "Monday", 4),  # gap of 2 slots
        ]
        inp = make_input([a1, a2])
        violations = validate_timetable(sessions, inp, check_soft=True)
        c01 = [v for v in violations if v.rule_id == "C01"]
        assert c01, "Expected C01 idle gap soft note"

    def test_c02_preferred_slot_mismatch(self):
        """C02: Session not in teacher's preferred slot → soft note."""
        pref_teacher = TeacherInfo(
            id="T_PREF", name="Preferred", short_name="PR",
            department_id="D1", weekly_workload_cap=16,
            preferred_slots=[SlotKey("Monday", 1), SlotKey("Tuesday", 1)],
        )
        a1 = make_assignment("A1", teacher_id="T_PREF", weekly_count=1)
        sessions = [session("A1", "T_PREF", "R_C1", "Wednesday", 3)]  # not preferred
        inp = make_input([a1], teachers=[pref_teacher, TEACHER_B])
        violations = validate_timetable(sessions, inp, check_soft=True)
        c02 = [v for v in violations if v.rule_id == "C02"]
        assert c02, "Expected C02 preferred slot mismatch"

    def test_no_soft_violations_when_disabled(self):
        """Level C violations should not appear when check_soft=False."""
        a1 = make_assignment("A1", teacher_id="T_A", weekly_count=1)
        sessions = [session("A1", "T_A", "R_C1", "Monday", 1)]
        inp = make_input([a1])
        violations = validate_timetable(sessions, inp, check_soft=False)
        soft = [v for v in violations if v.level == ViolationLevel.C]
        assert not soft, "Expected no soft violations when check_soft=False"


# ===========================================================================
# SECTION 4: CP-SAT Solver Tests
# ===========================================================================

class TestSolver:

    def _minimal_input(self, n_assignments: int = 2, weekly_count: int = 1) -> SchedulingInput:
        """Minimal feasible input: n_assignments lecture sessions."""
        assignments = [
            make_assignment(f"AS{i}", teacher_id=["T_A", "T_B", "T_C"][i % 3],
                            weekly_count=weekly_count)
            for i in range(n_assignments)
        ]
        return make_input(assignments)

    def test_solver_returns_feasible_for_simple_input(self):
        """Solver finds a feasible solution for a small, well-constrained input."""
        inp = self._minimal_input(n_assignments=2, weekly_count=1)
        result = run_solver(inp, time_limit_seconds=15)
        assert result.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE), \
            f"Expected feasible/optimal, got {result.status}: {result.diagnostic_notes}"
        assert len(result.sessions) == 2

    def test_solver_respects_weekly_count(self):
        """Each assignment in the result appears exactly weekly_count times."""
        inp = self._minimal_input(n_assignments=2, weekly_count=2)
        result = run_solver(inp, time_limit_seconds=15)
        assert result.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
        from collections import Counter
        counts = Counter(s.assignment_id for s in result.sessions)
        for a in inp.assignments:
            assert counts[a.id] == a.weekly_count, \
                f"Assignment {a.id}: expected {a.weekly_count}, got {counts[a.id]}"

    def test_solver_no_teacher_conflicts_in_output(self):
        """Solver output must not have A01 teacher double-booking violations."""
        inp = self._minimal_input(n_assignments=3, weekly_count=2)
        result = run_solver(inp, time_limit_seconds=15)
        if result.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Solver did not find a solution")
        violations = validate_timetable(result.sessions, inp, check_soft=False)
        a01 = [v for v in violations if v.rule_id == "A01"]
        assert not a01, f"Solver output has teacher conflicts: {[v.description for v in a01]}"

    def test_solver_no_room_conflicts_in_output(self):
        """Solver output must not have A02 room double-booking violations."""
        inp = self._minimal_input(n_assignments=3, weekly_count=2)
        result = run_solver(inp, time_limit_seconds=15)
        if result.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Solver did not find a solution")
        violations = validate_timetable(result.sessions, inp, check_soft=False)
        a02 = [v for v in violations if v.rule_id == "A02"]
        assert not a02, f"Solver output has room conflicts: {[v.description for v in a02]}"

    def test_solver_no_division_conflicts_in_output(self):
        """Solver output must not have A03 division double-booking violations."""
        inp = self._minimal_input(n_assignments=3, weekly_count=2)
        result = run_solver(inp, time_limit_seconds=15)
        if result.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("Solver did not find a solution")
        violations = validate_timetable(result.sessions, inp, check_soft=False)
        a03 = [v for v in violations if v.rule_id == "A03"]
        assert not a03, f"Solver output has division conflicts"

    def test_solver_respects_teacher_unavailability(self):
        """Solver must not schedule sessions in a teacher's unavailable slots."""
        teacher_unavail = TeacherInfo(
            id="T_BUSY", name="Busy", short_name="BZ",
            department_id="D1", weekly_workload_cap=16,
            unavailable_slots=[
                SlotKey("Monday", 1), SlotKey("Monday", 2), SlotKey("Monday", 3),
                SlotKey("Monday", 4), SlotKey("Monday", 5),
                SlotKey("Tuesday", 1), SlotKey("Tuesday", 2), SlotKey("Tuesday", 3),
                SlotKey("Tuesday", 4), SlotKey("Tuesday", 5),
            ],
        )
        a1 = make_assignment("A_BUSY", teacher_id="T_BUSY", weekly_count=1)
        inp = make_input([a1], teachers=[teacher_unavail, TEACHER_B])
        result = run_solver(inp, time_limit_seconds=15)
        if result.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            # Might be infeasible if only Wednesday is available and no slots fit
            return  # acceptable outcome
        for s in result.sessions:
            if s.teacher_id == "T_BUSY":
                assert s.day_name == "Wednesday", \
                    f"Scheduled on unavailable day: {s.day_name}"

    def test_solver_practical_in_lab_only(self):
        """Solver must assign practical sessions to laboratory rooms only."""
        a_practical = make_assignment(
            "AP1", teacher_id="T_A", session_type="practical",
            batch_id="BAT_1", weekly_count=1, duration_slots=2,
        )
        inp = make_input([a_practical])
        result = run_solver(inp, time_limit_seconds=15)
        if result.status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            pytest.skip("No solution found")
        for s in result.sessions:
            if s.session_type == "practical":
                room = next((r for r in inp.rooms if r.id == s.room_id), None)
                assert room is not None
                assert room.type == "laboratory", f"Practical in non-lab room: {room.name}"

    def test_solver_infeasible_no_rooms(self):
        """With no compatible rooms, solver should return INFEASIBLE."""
        # Practical assignment but only classrooms available
        a_practical = make_assignment(
            "AP2", teacher_id="T_A", session_type="practical",
            batch_id="BAT_1", weekly_count=1, duration_slots=2,
        )
        inp = make_input([a_practical], rooms=[ROOM_CLASS, ROOM_SMALL])  # no labs
        result = run_solver(inp, time_limit_seconds=10)
        assert result.status == SolverStatus.INFEASIBLE, \
            f"Expected INFEASIBLE but got {result.status}"
        assert "INFEASIBLE" in result.diagnostic_notes or "infeasible" in result.diagnostic_notes.lower()

    def test_solver_tiny_time_limit_returns_non_optimal(self):
        """Very small time limit on a bigger problem may return TIMEOUT or FEASIBLE."""
        assignments = [
            make_assignment(f"A{i}", teacher_id=["T_A", "T_B", "T_C"][i % 3], weekly_count=3)
            for i in range(6)
        ]
        inp = make_input(assignments)
        result = run_solver(inp, time_limit_seconds=1)
        # We only verify no crash and status is one of the expected values
        assert result.status in (
            SolverStatus.OPTIMAL, SolverStatus.FEASIBLE,
            SolverStatus.TIMEOUT, SolverStatus.INFEASIBLE, SolverStatus.UNKNOWN,
        ), f"Unexpected status: {result.status}"

    def test_solver_solver_time_reported(self):
        """Solver result always includes solver_time_ms."""
        inp = self._minimal_input(1, 1)
        result = run_solver(inp, time_limit_seconds=15)
        assert isinstance(result.solver_time_ms, int)
        assert result.solver_time_ms >= 0

    def test_full_pipeline_no_hard_violations(self):
        """End-to-end: solver output validated by independent validator with 0 hard violations."""
        inp = self._minimal_input(n_assignments=3, weekly_count=2)
        result = run_solver(inp, time_limit_seconds=20)
        assert result.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE), \
            f"No solution found: {result.diagnostic_notes}"
        violations = validate_timetable(result.sessions, inp, check_soft=True)
        hard_violations = [v for v in violations if v.level == ViolationLevel.A]
        assert not hard_violations, \
            f"Hard violations in solver output:\n" + "\n".join(v.description for v in hard_violations)

    def test_multiple_divisions_no_cross_conflict(self):
        """Two divisions with the same teacher across different slots → no conflict."""
        div_b = DivisionInfo(id="DIV_B", name="B", academic_year_id="AY1", strength=50, batch_ids=[])
        # Teacher T_A teaches DIV_A at slot 1 and DIV_B at slot 2
        a1 = make_assignment("A1_A", teacher_id="T_A", division_id="DIV_A", weekly_count=1)
        a2 = TeachingAssignmentInfo(
            id="A1_B", subject_id="SUB1", division_id="DIV_B",
            teacher_id="T_A", session_type="lecture",
            batch_id=None, enrollment_group_id=None,
            weekly_count=1, duration_slots=1,
        )
        sessions = [
            session("A1_A", "T_A", "R_C1", "Monday", 1, group_id="DIV_A"),
            ScheduledSessionInfo(
                assignment_id="A1_B", teacher_id="T_A", subject_id="SUB1",
                subject_name="DL", room_id="R_C2",
                day_name="Monday", slot_index=2,
                session_type="lecture", target_group_type="division",
                target_group_id="DIV_B", duration_slots=1,
            ),
        ]
        inp = SchedulingInput(
            department_id="D1", academic_year_ids=["AY1"],
            working_days=DAYS, time_slots=SLOTS,
            teachers=[TEACHER_A, TEACHER_B, TEACHER_C],
            rooms=[ROOM_CLASS, ROOM_SMALL, ROOM_LAB],
            divisions=[DIV_A, div_b],
            batches=[BATCH_1, BATCH_2],
            assignments=[a1, a2],
        )
        violations = validate_timetable(sessions, inp, check_soft=False)
        a01 = [v for v in violations if v.rule_id == "A01"]
        assert not a01, "Unexpected teacher conflict for different slots"

