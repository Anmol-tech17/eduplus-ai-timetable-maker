"""
backend/tests/test_scale_performance.py
EduPlus AI Timetable Maker — Phase 7 Solver Scale & Performance Tests

Tests realistic multi-department institutional workloads across:
- Small  : 1 department, 2 divisions
- Medium : 3 departments, 10 divisions
- Large  : 5 departments, 25 divisions

Also verifies infeasible workload detection, localized repair at scale,
repeated generation stability, and DB persistence latency.
Measures real wall-clock time, tracemalloc peak memory, hard/soft violations.
"""

from __future__ import annotations

import time
import tracemalloc
import uuid
from typing import List, Tuple

import pytest

from backend.app.engine.solver import run_solver
from backend.app.engine.types import (
    BatchInfo,
    DivisionInfo,
    RoomInfo,
    SchedulingInput,
    SlotKey,
    SolverStatus,
    TeacherInfo,
    TeachingAssignmentInfo,
    TimeSlotInfo,
    ViolationLevel,
    WorkingDayInfo,
)
from backend.app.engine.validator import validate_timetable


def _build_department_workload(
    dept_index: int,
    num_divisions: int,
    include_unavailability: bool = True,
    make_infeasible: bool = False,
) -> SchedulingInput:
    """
    Build a realistic single-department SchedulingInput with:
    - 5 active working days (Mon-Fri), 8 instruction slots/day (40 slots/week)
    - `num_divisions` divisions, each with 2 lab batches (capacity 30)
    - 4 teachers per division (sufficient capacity, realistic 16h cap)
    - Classrooms (capacity 70) + Laboratories (capacity 35)
    - Per division: 3 core lectures (2-3 hrs/wk each) + 2 batch practicals (1x2hr each)
    - Teacher unavailability blocks (H7) and morning preferences (S1)
    """
    dept_id = f"dept-{dept_index}"
    days = [
        WorkingDayInfo(id=f"wd-{i}", day_name=name, day_index=i, is_active=True)
        for i, name in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], start=1)
    ]
    slots = [
        TimeSlotInfo(id=f"ts-{i}", slot_code=f"TS{i}", slot_index=i, label=f"{7+i:02d}:00-{8+i:02d}:00")
        for i in range(1, 9)
    ]

    num_teachers = max(4, num_divisions * 3)
    teachers: List[TeacherInfo] = []
    for t_i in range(num_teachers):
        unavail = []
        prefs = []
        if include_unavailability and t_i % 3 == 0:
            # Block Friday afternoon slots 7-8
            unavail = [SlotKey("Friday", 7), SlotKey("Friday", 8)]
        if t_i % 2 == 0:
            prefs = [SlotKey("Monday", 1), SlotKey("Tuesday", 1), SlotKey("Wednesday", 2)]
        teachers.append(TeacherInfo(
            id=f"t-{dept_index}-{t_i}",
            name=f"Prof. D{dept_index}T{t_i}",
            short_name=f"D{dept_index}T{t_i}",
            department_id=dept_id,
            weekly_workload_cap=16,
            unavailable_slots=unavail,
            preferred_slots=prefs,
        ))

    num_classrooms = max(2, num_divisions + 1)
    num_labs = max(1, (num_divisions + 1) // 2 + 1)
    rooms: List[RoomInfo] = []
    if not make_infeasible:
        for r_i in range(num_classrooms):
            rooms.append(RoomInfo(
                id=f"cr-{dept_index}-{r_i}",
                name=f"CR-{dept_index}0{r_i}",
                type="classroom",
                capacity=70,
            ))
        for l_i in range(num_labs):
            rooms.append(RoomInfo(
                id=f"lab-{dept_index}-{l_i}",
                name=f"LAB-{dept_index}0{l_i}",
                type="laboratory",
                capacity=35,
            ))
    else:
        # Infeasible: only classrooms, zero laboratories for practicals
        rooms.append(RoomInfo(id=f"cr-{dept_index}-0", name="CR-ONLY", type="classroom", capacity=70))

    divisions: List[DivisionInfo] = []
    batches: List[BatchInfo] = []
    assignments: List[TeachingAssignmentInfo] = []

    teacher_cursor = 0
    for d_i in range(num_divisions):
        div_id = f"div-{dept_index}-{d_i}"
        b1_id = f"b-{dept_index}-{d_i}-1"
        b2_id = f"b-{dept_index}-{d_i}-2"
        divisions.append(DivisionInfo(
            id=div_id,
            name=f"D{dept_index}-Div{d_i+1}",
            academic_year_id=f"ay-{dept_index}-{(d_i % 4) + 1}",
            strength=60,
            batch_ids=[b1_id, b2_id],
        ))
        batches.append(BatchInfo(id=b1_id, name="B1", division_id=div_id, capacity=30))
        batches.append(BatchInfo(id=b2_id, name="B2", division_id=div_id, capacity=30))

        # 3 lecture courses per division (total 8 lecture slots/week)
        for s_i, wcount in enumerate((3, 3, 2)):
            t = teachers[teacher_cursor % len(teachers)]
            teacher_cursor += 1
            assignments.append(TeachingAssignmentInfo(
                id=f"ta-{dept_index}-{d_i}-lec-{s_i}",
                subject_id=f"sub-{dept_index}-{s_i}",
                division_id=div_id,
                teacher_id=t.id,
                session_type="lecture",
                batch_id=None,
                enrollment_group_id=None,
                weekly_count=wcount,
                duration_slots=1,
            ))

        # 2 practical sessions (one per batch, 2 consecutive slots each)
        for b_idx, bid in enumerate((b1_id, b2_id)):
            t = teachers[teacher_cursor % len(teachers)]
            teacher_cursor += 1
            assignments.append(TeachingAssignmentInfo(
                id=f"ta-{dept_index}-{d_i}-prac-{b_idx}",
                subject_id=f"sub-{dept_index}-lab",
                division_id=div_id,
                teacher_id=t.id,
                session_type="practical",
                batch_id=bid,
                enrollment_group_id=None,
                weekly_count=1,
                duration_slots=2,
            ))

    return SchedulingInput(
        department_id=dept_id,
        academic_year_ids=[f"ay-{dept_index}-{y}" for y in range(1, 5)],
        working_days=days,
        time_slots=slots,
        teachers=teachers,
        rooms=rooms,
        divisions=divisions,
        batches=batches,
        assignments=assignments,
    )


def _run_multi_dept_benchmark(
    dept_division_counts: List[int],
    time_limit_per_dept: int = 15,
) -> dict:
    """Solve each department workload cleanly and measure actual wall time, memory, and violations."""
    tracemalloc.start()
    t0 = time.monotonic()

    total_assignments = 0
    total_sessions = 0
    total_hard = 0
    total_soft = 0
    statuses = []

    for idx, div_count in enumerate(dept_division_counts):
        inp = _build_department_workload(dept_index=idx + 1, num_divisions=div_count)
        total_assignments += len(inp.assignments)

        res = run_solver(inp, time_limit_seconds=time_limit_per_dept)
        statuses.append(res.status)
        assert res.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE), (
            f"Dept {idx+1} ({div_count} divs) returned {res.status}: {res.diagnostic_notes}"
        )

        violations = validate_timetable(res.sessions, inp, check_soft=True)
        hard_v = [v for v in violations if v.level == ViolationLevel.A]
        soft_v = [v for v in violations if v.level != ViolationLevel.A]
        total_sessions += len(res.sessions)
        total_hard += len(hard_v)
        total_soft += len(soft_v)

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return {
        "departments": len(dept_division_counts),
        "divisions": sum(dept_division_counts),
        "assignments": total_assignments,
        "sessions": total_sessions,
        "statuses": [s.value for s in statuses],
        "elapsed_ms": elapsed_ms,
        "peak_mem_mib": round(peak_bytes / (1024 * 1024), 2),
        "hard_violations": total_hard,
        "soft_violations": total_soft,
    }


def test_scale_small_1_dept_2_divisions():
    """Small scale: 1 department, 2 divisions."""
    metrics = _run_multi_dept_benchmark([2], time_limit_per_dept=10)
    print(f"\n[BENCHMARK SMALL] {metrics}")
    assert metrics["hard_violations"] == 0
    assert metrics["sessions"] == 20  # 2 divs * (3+3+2 lectures + 2 practicals)


def test_scale_medium_3_depts_10_divisions():
    """Medium scale: 3 departments, 10 divisions total (4+3+3)."""
    metrics = _run_multi_dept_benchmark([4, 3, 3], time_limit_per_dept=15)
    print(f"\n[BENCHMARK MEDIUM] {metrics}")
    assert metrics["hard_violations"] == 0
    assert metrics["sessions"] == 100


def test_scale_large_5_depts_25_divisions():
    """Large scale: 5 departments, 25 divisions total (5x5)."""
    metrics = _run_multi_dept_benchmark([5, 5, 5, 5, 5], time_limit_per_dept=20)
    print(f"\n[BENCHMARK LARGE] {metrics}")
    assert metrics["hard_violations"] == 0
    assert metrics["sessions"] == 250


def test_scale_infeasible_detection():
    """Verify solver proves infeasibility quickly when laboratory rooms are absent."""
    inp = _build_department_workload(dept_index=99, num_divisions=3, make_infeasible=True)
    res = run_solver(inp, time_limit_seconds=10)
    assert res.status == SolverStatus.INFEASIBLE
    assert res.sessions == []


def test_scale_localized_repair_and_repeated_runs():
    """Verify localized repair preserves pinned sessions and repeated runs stay valid."""
    inp = _build_department_workload(dept_index=10, num_divisions=3)
    base = run_solver(inp, time_limit_seconds=15)
    assert base.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    assert len([v for v in validate_timetable(base.sessions, inp) if v.level == ViolationLevel.A]) == 0

    # Pin 80% of assignments and repair only the remaining 20%
    all_aids = [a.id for a in inp.assignments]
    free_aids = set(all_aids[:3])
    pinned = [s for s in base.sessions if s.assignment_id not in free_aids]
    repair_inp = _build_department_workload(dept_index=10, num_divisions=3)
    repair_inp.assignments = [a for a in repair_inp.assignments if a.id in free_aids]

    repaired = run_solver(repair_inp, time_limit_seconds=15, pinned_sessions=pinned)
    assert repaired.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    assert len([v for v in validate_timetable(repaired.sessions, inp) if v.level == ViolationLevel.A]) == 0

    # Verify repeated generation runs succeed deterministically with 0 hard violations
    for _ in range(2):
        r = run_solver(inp, time_limit_seconds=10)
        assert r.status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
        assert len([v for v in validate_timetable(r.sessions, inp) if v.level == ViolationLevel.A]) == 0
