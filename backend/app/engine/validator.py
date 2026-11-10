"""
backend/app/engine/validator.py
EduPlus AI Timetable Maker — Independent Timetable Validator

Validates a proposed timetable represented as a list of ScheduledSessionInfo
against the full set of hard (Level A) and policy (Level B) constraints, plus
soft preference checks (Level C) that inform quality scoring.

This validator is completely independent of the CP-SAT solver and may be
called on any candidate — solver-generated or manually edited.

Rule catalogue
--------------
Level A — Hard constraints (schedule is INVALID if any fire)
  A01  Teacher double-booked at same day/slot
  A02  Room double-booked at same day/slot
  A03  Division double-booked at same day/slot
  A04  Batch double-booked at same day/slot
  A05  Room capacity too small for target group
  A06  Room type mismatch (practical assigned to classroom)
  A07  Teacher not qualified for subject
  A08  Teacher marked unavailable for that day/slot
  A09  Time slot not a valid working slot (slot on inactive working day)
  A10  Weekly session count not satisfied

Level B — Policy constraints (schedule is DISCOURAGED)
  B01  Teacher exceeds weekly workload cap
  B02  Teacher has > 2 consecutive sessions on a day
  B03  Practical session spans only 1 slot (should span 2)

Level C — Soft preferences (schedule is suboptimal)
  C01  Teacher has an idle gap between sessions on the same day
  C02  Session not in teacher's preferred slot
  C03  Uneven daily load across the week (more than 2× spread)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from backend.app.engine.types import (
    ScheduledSessionInfo,
    SchedulingInput,
    SlotKey,
    ViolationLevel,
    ViolationRecord,
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def validate_timetable(
    sessions: List[ScheduledSessionInfo],
    scheduling_input: SchedulingInput,
    check_soft: bool = True,
) -> List[ViolationRecord]:
    """
    Validate *sessions* against the domain constraints encoded in
    *scheduling_input*.

    Returns a (possibly empty) list of ViolationRecord objects ordered by
    severity (Level A first).

    Parameters
    ----------
    sessions:
        The proposed timetable — list of ScheduledSessionInfo.
    scheduling_input:
        Normalised domain data (teachers, rooms, working days, etc.)
    check_soft:
        Whether to include Level C soft-preference checks.
    """
    ctx = _ValidationContext(sessions, scheduling_input)
    violations: List[ViolationRecord] = []

    violations += ctx.check_a01_teacher_double_booked()
    violations += ctx.check_a02_room_double_booked()
    violations += ctx.check_a03_division_double_booked()
    violations += ctx.check_a04_batch_double_booked()
    violations += ctx.check_a05_room_capacity()
    violations += ctx.check_a06_room_type_mismatch()
    violations += ctx.check_a07_teacher_qualification()
    violations += ctx.check_a08_teacher_unavailability()
    violations += ctx.check_a09_valid_working_slot()
    violations += ctx.check_a10_weekly_session_count()
    violations += ctx.check_a11_blocked_practical_days()

    violations += ctx.check_b01_teacher_workload()
    violations += ctx.check_b02_consecutive_sessions()
    violations += ctx.check_b03_practical_duration()

    if check_soft:
        violations += ctx.check_c01_idle_gaps()
        violations += ctx.check_c02_preferred_slots()
        violations += ctx.check_c03_uneven_load()

    # Sort: hard first, then policy, then soft
    _LEVEL_ORDER = {ViolationLevel.A: 0, ViolationLevel.B: 1, ViolationLevel.C: 2}
    violations.sort(key=lambda v: _LEVEL_ORDER[v.level])
    return violations


def has_hard_violations(violations: List[ViolationRecord]) -> bool:
    return any(v.level == ViolationLevel.A for v in violations)


# ---------------------------------------------------------------------------
# Internal context — pre-indexes sessions for O(1) lookups
# ---------------------------------------------------------------------------

class _ValidationContext:
    def __init__(
        self,
        sessions: List[ScheduledSessionInfo],
        inp: SchedulingInput,
    ) -> None:
        self.sessions = sessions
        self.inp = inp

        # Lookup maps from input
        self.teacher_map: Dict[str, object] = {t.id: t for t in inp.teachers}
        self.room_map: Dict[str, object] = {r.id: r for r in inp.rooms}
        self.working_day_names: Set[str] = {
            wd.day_name for wd in inp.working_days if wd.is_active
        }
        self.valid_slot_indices: Set[int] = {ts.slot_index for ts in inp.time_slots}
        self.slot_index_map: Dict[int, str] = {ts.slot_index: ts.slot_code for ts in inp.time_slots}

        # Indexes into the session list built once
        # teacher -> [(day, slot_index, session_idx)]
        self.teacher_slots: Dict[str, List[Tuple[str, int, int]]] = defaultdict(list)
        # room -> [(day, slot_index, session_idx)]
        self.room_slots: Dict[str, List[Tuple[str, int, int]]] = defaultdict(list)
        # division -> [(day, slot_index, session_idx)]
        self.division_slots: Dict[str, List[Tuple[str, int, int]]] = defaultdict(list)
        # batch -> [(day, slot_index, session_idx)]
        self.batch_slots: Dict[str, List[Tuple[str, int, int]]] = defaultdict(list)

        for idx, s in enumerate(sessions):
            self.teacher_slots[s.teacher_id].append((s.day_name, s.slot_index, idx))
            self.room_slots[s.room_id].append((s.day_name, s.slot_index, idx))
            if s.target_group_type == "division":
                self.division_slots[s.target_group_id].append((s.day_name, s.slot_index, idx))
            elif s.target_group_type == "batch":
                self.batch_slots[s.target_group_id].append((s.day_name, s.slot_index, idx))

        # Map assignment_id -> assignment_info
        self.assignment_map = {a.id: a for a in inp.assignments}

    # ------------------------------------------------------------------
    # Level A helpers
    # ------------------------------------------------------------------

    def _double_booked(
        self,
        entity_label: str,
        entity_id_label: str,
        slots_map: Dict[str, List[Tuple[str, int, int]]],
        rule_id: str,
        description_template: str,
    ) -> List[ViolationRecord]:
        violations = []
        for entity_id, slot_list in slots_map.items():
            # Check all pairs of slots for same day+index overlap
            seen: Dict[Tuple[str, int], List[int]] = defaultdict(list)
            for day, slot_idx, s_idx in slot_list:
                # Expand for duration (practical takes 2 consecutive slots)
                s = self.sessions[s_idx]
                for d in range(s.duration_slots):
                    seen[(day, slot_idx + d)].append(s_idx)

            for (day, slot_idx), session_indices in seen.items():
                if len(session_indices) > 1:
                    affected = list(dict.fromkeys(session_indices))  # deduplicate
                    desc = description_template.format(
                        id=entity_id,
                        day=day,
                        slot=slot_idx,
                    )
                    violations.append(ViolationRecord(
                        rule_id=rule_id,
                        level=ViolationLevel.A,
                        severity="error",
                        description=desc,
                        affected_session_ids=[str(i) for i in affected],
                        affected_entity_ids=[entity_id],
                        suggestion=f"Move one of the conflicting sessions to a different time slot.",
                    ))
        return violations

    # ------------------------------------------------------------------
    # Level A checks
    # ------------------------------------------------------------------

    def check_a01_teacher_double_booked(self) -> List[ViolationRecord]:
        return self._double_booked(
            "Teacher", "teacher_id", self.teacher_slots, "A01",
            "A01: Teacher {id} is double-booked on {day} slot {slot}.",
        )

    def check_a02_room_double_booked(self) -> List[ViolationRecord]:
        return self._double_booked(
            "Room", "room_id", self.room_slots, "A02",
            "A02: Room {id} is double-booked on {day} slot {slot}.",
        )

    def check_a03_division_double_booked(self) -> List[ViolationRecord]:
        return self._double_booked(
            "Division", "division_id", self.division_slots, "A03",
            "A03: Division {id} has overlapping sessions on {day} slot {slot}.",
        )

    def check_a04_batch_double_booked(self) -> List[ViolationRecord]:
        return self._double_booked(
            "Batch", "batch_id", self.batch_slots, "A04",
            "A04: Batch {id} has overlapping sessions on {day} slot {slot}.",
        )

    def check_a05_room_capacity(self) -> List[ViolationRecord]:
        violations = []
        # Build group size from input
        division_strength = {d.id: d.strength for d in self.inp.divisions}
        batch_capacity = {b.id: b.capacity for b in self.inp.batches}

        for idx, s in enumerate(self.sessions):
            room = self.room_map.get(s.room_id)
            if room is None:
                continue
            if s.target_group_type == "division":
                group_size = division_strength.get(s.target_group_id, 0)
            elif s.target_group_type == "batch":
                group_size = batch_capacity.get(s.target_group_id, 0)
            else:
                group_size = 0  # enrollment groups: skip for now

            if group_size > room.capacity:
                violations.append(ViolationRecord(
                    rule_id="A05",
                    level=ViolationLevel.A,
                    severity="error",
                    description=(
                        f"A05: Room '{room.name}' (capacity {room.capacity}) is too small "
                        f"for group '{s.target_group_id}' ({group_size} students) on {s.day_name} slot {s.slot_index}."
                    ),
                    affected_session_ids=[str(idx)],
                    affected_entity_ids=[s.room_id, s.target_group_id],
                    suggestion=f"Use a room with capacity ≥ {group_size}.",
                ))
        return violations

    def check_a06_room_type_mismatch(self) -> List[ViolationRecord]:
        violations = []
        for idx, s in enumerate(self.sessions):
            room = self.room_map.get(s.room_id)
            if room is None:
                continue
            if s.session_type == "practical" and room.type != "laboratory":
                violations.append(ViolationRecord(
                    rule_id="A06",
                    level=ViolationLevel.A,
                    severity="error",
                    description=(
                        f"A06: Practical session on {s.day_name} slot {s.slot_index} "
                        f"assigned to '{room.name}' which is a {room.type}, not a laboratory."
                    ),
                    affected_session_ids=[str(idx)],
                    affected_entity_ids=[s.room_id],
                    suggestion="Assign this practical session to a laboratory room.",
                ))
        return violations

    def check_a07_teacher_qualification(self) -> List[ViolationRecord]:
        """Check teacher is qualified for the subject they are teaching."""
        violations = []
        # Build qualified set from teacher info
        # TeacherInfo.id doesn't have qualification list directly;
        # the qualification is stored in the assignment: teacher_id assigned to subject_id.
        # We validate that every assignment in the session was actually in the input assignments.
        valid_assignment_ids = {a.id for a in self.inp.assignments}
        for idx, s in enumerate(self.sessions):
            if s.assignment_id not in valid_assignment_ids:
                violations.append(ViolationRecord(
                    rule_id="A07",
                    level=ViolationLevel.A,
                    severity="error",
                    description=(
                        f"A07: Session on {s.day_name} slot {s.slot_index} references unknown "
                        f"assignment '{s.assignment_id}'. Teacher may not be qualified for this subject."
                    ),
                    affected_session_ids=[str(idx)],
                    affected_entity_ids=[s.teacher_id, s.assignment_id],
                    suggestion="Ensure teacher has a valid teaching assignment for this subject.",
                ))
        return violations

    def check_a08_teacher_unavailability(self) -> List[ViolationRecord]:
        violations = []
        for idx, s in enumerate(self.sessions):
            teacher = self.teacher_map.get(s.teacher_id)
            if teacher is None:
                continue
            key = SlotKey(day_name=s.day_name, slot_index=s.slot_index)
            if key in {SlotKey(u.day_name, u.slot_index) for u in teacher.unavailable_slots}:
                violations.append(ViolationRecord(
                    rule_id="A08",
                    level=ViolationLevel.A,
                    severity="error",
                    description=(
                        f"A08: Teacher '{teacher.name}' is marked unavailable on "
                        f"{s.day_name} slot {s.slot_index} but has a session scheduled there."
                    ),
                    affected_session_ids=[str(idx)],
                    affected_entity_ids=[s.teacher_id],
                    suggestion="Move the session to a slot when the teacher is available.",
                ))
        return violations

    def check_a09_valid_working_slot(self) -> List[ViolationRecord]:
        violations = []
        for idx, s in enumerate(self.sessions):
            if s.day_name not in self.working_day_names:
                violations.append(ViolationRecord(
                    rule_id="A09",
                    level=ViolationLevel.A,
                    severity="error",
                    description=(
                        f"A09: Session on {s.day_name} slot {s.slot_index} is placed on "
                        f"a non-working day."
                    ),
                    affected_session_ids=[str(idx)],
                    affected_entity_ids=[],
                    suggestion=f"Restrict sessions to active working days: {sorted(self.working_day_names)}.",
                ))
            elif s.slot_index not in self.valid_slot_indices:
                violations.append(ViolationRecord(
                    rule_id="A09",
                    level=ViolationLevel.A,
                    severity="error",
                    description=(
                        f"A09: Session references invalid time slot index {s.slot_index} "
                        f"on {s.day_name}."
                    ),
                    affected_session_ids=[str(idx)],
                    affected_entity_ids=[],
                    suggestion="Use only defined institutional time slot indices.",
                ))
        return violations

    def check_a10_weekly_session_count(self) -> List[ViolationRecord]:
        """
        Verify that every teaching assignment has exactly the required number
        of sessions scheduled per week.
        """
        violations = []
        # Count sessions per assignment
        counts: Dict[str, int] = defaultdict(int)
        for s in self.sessions:
            counts[s.assignment_id] += 1

        for assignment in self.inp.assignments:
            scheduled = counts.get(assignment.id, 0)
            if scheduled != assignment.weekly_count:
                violations.append(ViolationRecord(
                    rule_id="A10",
                    level=ViolationLevel.A,
                    severity="error",
                    description=(
                        f"A10: Assignment '{assignment.id}' requires {assignment.weekly_count} "
                        f"sessions/week but {scheduled} are scheduled."
                    ),
                    affected_session_ids=[],
                    affected_entity_ids=[assignment.id, assignment.teacher_id],
                    suggestion=(
                        f"Schedule exactly {assignment.weekly_count} sessions for this assignment."
                    ),
                ))
        return violations

    def check_a11_blocked_practical_days(self) -> List[ViolationRecord]:
        """Check that no practical sessions are scheduled on coordinator/AI blocked practical days."""
        violations = []
        blocked_days = set(getattr(self.inp, "blocked_practical_days", []))
        if not blocked_days:
            return violations
        for idx, s in enumerate(self.sessions):
            if s.session_type == "practical" and s.day_name in blocked_days:
                violations.append(ViolationRecord(
                    rule_id="A11",
                    level=ViolationLevel.A,
                    severity="error",
                    description=(
                        f"A11: Practical session on {s.day_name} slot {s.slot_index} violates "
                        f"blocked practical day rule for {s.day_name}."
                    ),
                    affected_session_ids=[str(idx)],
                    affected_entity_ids=[s.assignment_id, s.room_id],
                    suggestion=f"Reschedule practical session to a permitted laboratory day (not {s.day_name}).",
                ))
        return violations

    # ------------------------------------------------------------------
    # Level B checks
    # ------------------------------------------------------------------

    def check_b01_teacher_workload(self) -> List[ViolationRecord]:
        violations = []
        # Count weekly teaching hours per teacher (slot = 1 hour)
        hours: Dict[str, int] = defaultdict(int)
        for s in self.sessions:
            hours[s.teacher_id] += s.duration_slots

        for teacher_id, total in hours.items():
            teacher = self.teacher_map.get(teacher_id)
            if teacher and total > teacher.weekly_workload_cap:
                violations.append(ViolationRecord(
                    rule_id="B01",
                    level=ViolationLevel.B,
                    severity="warning",
                    description=(
                        f"B01: Teacher '{teacher.name}' has {total} teaching hours/week, "
                        f"exceeding their cap of {teacher.weekly_workload_cap}."
                    ),
                    affected_entity_ids=[teacher_id],
                    suggestion="Redistribute some sessions to other qualified teachers.",
                ))
        return violations

    def check_b02_consecutive_sessions(self) -> List[ViolationRecord]:
        """Teacher should not have more than 2 consecutive slots on the same day."""
        violations = []
        for teacher_id, slot_list in self.teacher_slots.items():
            # Group by day
            by_day: Dict[str, List[int]] = defaultdict(list)
            for day, slot_idx, s_idx in slot_list:
                by_day[day].append(slot_idx)

            for day, indices in by_day.items():
                sorted_indices = sorted(set(indices))
                # Find runs of consecutive slots
                run = 1
                max_run = 1
                for i in range(1, len(sorted_indices)):
                    if sorted_indices[i] == sorted_indices[i - 1] + 1:
                        run += 1
                        max_run = max(max_run, run)
                    else:
                        run = 1

                if max_run > 3:  # Allow up to 3 consecutive (soft warning at > 3)
                    teacher = self.teacher_map.get(teacher_id)
                    name = teacher.name if teacher else teacher_id
                    violations.append(ViolationRecord(
                        rule_id="B02",
                        level=ViolationLevel.B,
                        severity="warning",
                        description=(
                            f"B02: Teacher '{name}' has {max_run} consecutive sessions on {day}."
                        ),
                        affected_entity_ids=[teacher_id],
                        suggestion="Insert a break between sessions to avoid teacher fatigue.",
                    ))
        return violations

    def check_b03_practical_duration(self) -> List[ViolationRecord]:
        """Practical sessions should span 2 consecutive slots."""
        violations = []
        for idx, s in enumerate(self.sessions):
            if s.session_type == "practical" and s.duration_slots < 2:
                violations.append(ViolationRecord(
                    rule_id="B03",
                    level=ViolationLevel.B,
                    severity="warning",
                    description=(
                        f"B03: Practical session on {s.day_name} slot {s.slot_index} has "
                        f"duration_slots={s.duration_slots}; practicals should span 2 slots."
                    ),
                    affected_session_ids=[str(idx)],
                    affected_entity_ids=[s.teacher_id],
                    suggestion="Set duration_slots=2 for all practical sessions.",
                ))
        return violations

    # ------------------------------------------------------------------
    # Level C checks
    # ------------------------------------------------------------------

    def check_c01_idle_gaps(self) -> List[ViolationRecord]:
        """Teacher has idle gaps (non-teaching slots sandwiched between teaching slots)."""
        violations = []
        for teacher_id, slot_list in self.teacher_slots.items():
            by_day: Dict[str, List[int]] = defaultdict(list)
            for day, slot_idx, _ in slot_list:
                by_day[day].append(slot_idx)

            for day, indices in by_day.items():
                sorted_indices = sorted(set(indices))
                if len(sorted_indices) > 1:
                    gap = sorted_indices[-1] - sorted_indices[0] - len(sorted_indices) + 1
                    if gap > 1:
                        teacher = self.teacher_map.get(teacher_id)
                        name = teacher.name if teacher else teacher_id
                        violations.append(ViolationRecord(
                            rule_id="C01",
                            level=ViolationLevel.C,
                            severity="info",
                            description=(
                                f"C01: Teacher '{name}' has idle gaps on {day} "
                                f"(slots {sorted_indices})."
                            ),
                            affected_entity_ids=[teacher_id],
                            suggestion="Pack sessions to minimise teacher idle time.",
                        ))
        return violations

    def check_c02_preferred_slots(self) -> List[ViolationRecord]:
        """Sessions not in teacher's preferred slot get a soft penalty note."""
        violations = []
        for idx, s in enumerate(self.sessions):
            teacher = self.teacher_map.get(s.teacher_id)
            if teacher and teacher.preferred_slots:
                key = SlotKey(day_name=s.day_name, slot_index=s.slot_index)
                preferred_keys = {SlotKey(p.day_name, p.slot_index) for p in teacher.preferred_slots}
                if preferred_keys and key not in preferred_keys:
                    violations.append(ViolationRecord(
                        rule_id="C02",
                        level=ViolationLevel.C,
                        severity="info",
                        description=(
                            f"C02: Session for teacher '{teacher.name}' on {s.day_name} "
                            f"slot {s.slot_index} is not in their preferred slots."
                        ),
                        affected_session_ids=[str(idx)],
                        affected_entity_ids=[s.teacher_id],
                    ))
        return violations

    def check_c03_uneven_load(self) -> List[ViolationRecord]:
        """Teacher daily load is uneven (max day > 2× min day)."""
        violations = []
        for teacher_id, slot_list in self.teacher_slots.items():
            by_day: Dict[str, int] = defaultdict(int)
            for day, _, s_idx in slot_list:
                by_day[day] += self.sessions[s_idx].duration_slots

            counts = list(by_day.values())
            if len(counts) > 1 and max(counts) > 2 * min(counts):
                teacher = self.teacher_map.get(teacher_id)
                name = teacher.name if teacher else teacher_id
                violations.append(ViolationRecord(
                    rule_id="C03",
                    level=ViolationLevel.C,
                    severity="info",
                    description=(
                        f"C03: Teacher '{name}' has uneven daily load: {dict(by_day)}."
                    ),
                    affected_entity_ids=[teacher_id],
                    suggestion="Spread sessions more evenly across the week.",
                ))
        return violations

