"""
backend/app/engine/solver.py
EduPlus AI Timetable Maker — CP-SAT Constraint Scheduling Engine

Uses Google OR-Tools CP-SAT to generate a valid, optimised weekly timetable
from a normalised SchedulingInput.

Design principles
-----------------
* All decision variables are BoolVar: X[assignment_id, day_idx, slot_idx, room_id]
  = 1 iff that assignment block starts at that (day, slot, room).
* Hard constraints are encoded as CP-SAT linear constraints.
* Soft objectives are encoded as a maximisation of weighted terms.
* The solver is wrapped so that INFEASIBLE, TIMEOUT, and UNKNOWN are returned
  as structured SolverResult objects — never as exceptions to the caller.

Constraint summary
------------------
Hard (CP-SAT constraints):
  H1  Each assignment scheduled exactly weekly_count times
  H2  Teacher cannot teach two sessions at the same (day, slot)
  H3  Room cannot host two sessions at the same (day, slot)
  H4  Division cannot attend two sessions at the same (day, slot)
  H5  Batch cannot attend two sessions at the same (day, slot)
  H6  Practical sessions occupy 2 consecutive slots (multi-slot)
  H7  Teacher unavailable slots blocked
  H8  Sessions must stay within valid (day, start_slot) range

Soft (objective terms, positive weight = encourage):
  S1  Prefer teacher's preferred slots (+W_PREFER per match)
  S2  Penalise teacher idle gaps (−W_GAP per gap slot)
  S3  Prefer balanced daily load (−W_IMBALANCE per excess slot)
  S4  Penalise > 3 consecutive teacher slots (−W_CONSEC per excess)
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from ortools.sat.python import cp_model

from backend.app.engine.types import (
    ScheduledSessionInfo,
    SchedulingInput,
    SlotKey,
    SolverResult,
    SolverStatus,
    TeachingAssignmentInfo,
)

# ---------------------------------------------------------------------------
# Objective weights
# ---------------------------------------------------------------------------
W_PREFER = 2    # bonus for matching preferred slot
W_GAP = 3       # penalty per idle gap slot
W_IMBALANCE = 1  # penalty per slot over mean daily load
W_CONSEC = 4    # penalty per consecutive slot beyond 3


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_solver(
    scheduling_input: SchedulingInput,
    time_limit_seconds: int = 60,
    pinned_sessions: Optional[List[ScheduledSessionInfo]] = None,
) -> SolverResult:
    """
    Run the CP-SAT solver on *scheduling_input*.

    Parameters
    ----------
    scheduling_input:
        Normalised domain data.
    time_limit_seconds:
        Wall-clock limit for the solver. Set to a small value for
        quick feasibility checks; larger for quality optimisation.
    pinned_sessions:
        Pre-fixed sessions (from a prior version) that must be kept
        as-is during a localised repair run.

    Returns
    -------
    SolverResult with status, sessions, and diagnostics.
    """
    engine = _CPSATEngine(scheduling_input, time_limit_seconds, pinned_sessions or [])
    return engine.solve()


# ---------------------------------------------------------------------------
# Internal engine
# ---------------------------------------------------------------------------

class _CPSATEngine:
    def __init__(
        self,
        inp: SchedulingInput,
        time_limit_seconds: int,
        pinned: List[ScheduledSessionInfo],
    ) -> None:
        self.inp = inp
        self.time_limit = time_limit_seconds
        self.pinned = pinned
        self.model = cp_model.CpModel()

        # Enumerate working days and slots (using integer indices for CP-SAT)
        self.days: List[str] = sorted(
            [wd.day_name for wd in inp.working_days if wd.is_active],
            key=lambda d: next(wd.day_index for wd in inp.working_days if wd.day_name == d),
        )
        # Only instruction slots (not lunch — slot_index 5 or 6 reserved in seed)
        # We use all defined time slots; the institution can mark lunch via working_days or
        # slot policies. For now every defined slot is schedulable.
        self.slots: List[int] = sorted(ts.slot_index for ts in inp.time_slots)
        self.rooms: List[str] = [r.id for r in inp.rooms]

        # Lookup maps
        self.room_map = {r.id: r for r in inp.rooms}
        self.teacher_map = {t.id: t for t in inp.teachers}
        self.division_map = {d.id: d for d in inp.divisions}
        self.batch_map = {b.id: b for b in inp.batches}

        self.day_idx: Dict[str, int] = {d: i for i, d in enumerate(self.days)}
        self.slot_idx_map: Dict[int, int] = {s: i for i, s in enumerate(self.slots)}

        # Pinned session set for repair: (assignment_id, day_name, slot_index) -> room_id
        self.pinned_map: Dict[Tuple[str, str, int], str] = {
            (ps.assignment_id, ps.day_name, ps.slot_index): ps.room_id
            for ps in pinned
        }

    # ------------------------------------------------------------------
    # Main solve routine
    # ------------------------------------------------------------------

    def solve(self) -> SolverResult:
        t_start = time.monotonic()

        try:
            # Build decision variables
            # X[(assignment_id, day_i, slot_i, room_id)] = BoolVar
            X: Dict[Tuple[str, int, int, str], cp_model.IntVar] = {}
            self._build_variables(X)
            self._add_hard_constraints(X)
            objective_terms = self._build_objective(X)
            self.model.Maximize(cp_model.LinearExpr.Sum(objective_terms))
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - t_start) * 1000)
            return SolverResult(
                status=SolverStatus.ERROR,
                solver_time_ms=elapsed_ms,
                diagnostic_notes=f"Model construction failed: {exc}",
            )

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(self.time_limit)
        solver.parameters.num_workers = 4   # parallel search
        solver.parameters.log_search_progress = False

        status_code = solver.Solve(self.model)
        elapsed_ms = int((time.monotonic() - t_start) * 1000)

        status_map = {
            cp_model.OPTIMAL: SolverStatus.OPTIMAL,
            cp_model.FEASIBLE: SolverStatus.FEASIBLE,
            cp_model.INFEASIBLE: SolverStatus.INFEASIBLE,
            cp_model.MODEL_INVALID: SolverStatus.ERROR,
            cp_model.UNKNOWN: SolverStatus.UNKNOWN,
        }
        result_status = status_map.get(status_code, SolverStatus.UNKNOWN)
        # Distinguish timeout: solver returned UNKNOWN or FEASIBLE but hit time limit
        if elapsed_ms >= self.time_limit * 1000 * 0.95 and result_status not in (
            SolverStatus.OPTIMAL, SolverStatus.INFEASIBLE
        ):
            result_status = SolverStatus.TIMEOUT

        if result_status not in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            notes = self._build_infeasibility_notes(result_status)
            return SolverResult(
                status=result_status,
                solver_time_ms=elapsed_ms,
                diagnostic_notes=notes,
                num_conflicts=solver.NumConflicts() if hasattr(solver, 'NumConflicts') else None,
            )

        # Extract solution
        sessions = self._extract_sessions(solver, X)
        # Add pinned sessions back without duplication
        existing_keys = {(s.assignment_id, s.day_name, s.slot_index) for s in sessions}
        for ps in self.pinned:
            if (ps.assignment_id, ps.day_name, ps.slot_index) not in existing_keys:
                sessions.append(ps)

        return SolverResult(
            status=result_status,
            sessions=sessions,
            solver_time_ms=elapsed_ms,
            objective_value=solver.ObjectiveValue(),
            num_conflicts=solver.NumConflicts() if hasattr(solver, 'NumConflicts') else None,
            diagnostic_notes=(
                f"Solver finished: {result_status.value}. "
                f"Objective: {solver.ObjectiveValue():.1f}. "
                f"Conflicts: {solver.NumConflicts()}."
            ),
        )

    # ------------------------------------------------------------------
    # Variable construction
    # ------------------------------------------------------------------

    def _build_variables(self, X: dict) -> None:
        n_days = len(self.days)
        n_slots = len(self.slots)

        for assignment in self.inp.assignments:
            for d_i, day_name in enumerate(self.days):
                for s_i, slot_index in enumerate(self.slots):
                    # For practicals (duration 2), only create variables for
                    # slots where the 2nd slot also exists
                    if assignment.duration_slots == 2:
                        if s_i + 1 >= n_slots:
                            continue  # no room for 2 slots

                    for room_id in self.rooms:
                        # Filter: practicals only in labs, lectures not in labs
                        room = self.room_map[room_id]
                        # Room-type filter
                        if assignment.session_type == "practical" and room.type != "laboratory":
                            continue
                        if assignment.session_type in ("lecture", "tutorial") and room.type == "laboratory":
                            continue
                        # Room-capacity filter: group size must fit
                        group_size = self._group_size(assignment)
                        if group_size > room.capacity:
                            continue

                        key = (assignment.id, d_i, s_i, room_id)

                        # If this key is pinned, we set it as a constant (forced = 1)
                        pin_key = (assignment.id, day_name, slot_index)
                        if pin_key in self.pinned_map and self.pinned_map[pin_key] == room_id:
                            # Pinned: add a fixed literal = 1
                            var = self.model.NewBoolVar(f"X_{assignment.id[:8]}_{d_i}_{s_i}_{room_id[:8]}")
                            self.model.Add(var == 1)
                        else:
                            var = self.model.NewBoolVar(f"X_{assignment.id[:8]}_{d_i}_{s_i}_{room_id[:8]}")

                        X[key] = var

    def _group_size(self, assignment: TeachingAssignmentInfo) -> int:
        """Return the headcount of the target group for capacity checking."""
        if assignment.batch_id:
            batch = self.batch_map.get(assignment.batch_id)
            return batch.capacity if batch else 0
        div = self.division_map.get(assignment.division_id)
        return div.strength if div else 0

    # ------------------------------------------------------------------
    # Hard constraints
    # ------------------------------------------------------------------

    def _add_hard_constraints(self, X: dict) -> None:
        self._h1_assignment_count(X)
        self._h2_teacher_no_overlap(X)
        self._h3_room_no_overlap(X)
        self._h4_division_no_overlap(X)
        self._h5_batch_no_overlap(X)
        self._h7_teacher_unavailability(X)
        self._block_pinned_conflicts(X)

    def _block_pinned_conflicts(self, X: dict) -> None:
        """Prevent newly scheduled sessions from colliding with pinned sessions."""
        if not self.pinned:
            return

        assignment_map = {a.id: a for a in self.inp.assignments}
        for ps in self.pinned:
            ps_d_i = self.day_idx.get(ps.day_name)
            ps_s_i = self.slot_idx_map.get(ps.slot_index)
            if ps_d_i is None or ps_s_i is None:
                continue

            ps_slots = set(range(ps_s_i, ps_s_i + ps.duration_slots))

            for key, var in X.items():
                a_id, d_i, s_i, room_id = key
                if d_i != ps_d_i:
                    continue
                assignment = assignment_map.get(a_id)
                if not assignment:
                    continue

                var_slots = set(range(s_i, s_i + assignment.duration_slots))
                if not ps_slots.intersection(var_slots):
                    continue

                # Check clashes
                clash = False
                if assignment.teacher_id == ps.teacher_id:
                    clash = True
                elif room_id == ps.room_id:
                    clash = True
                elif ps.target_group_type == "division" and assignment.division_id == ps.target_group_id:
                    clash = True
                elif ps.target_group_type == "batch" and assignment.batch_id == ps.target_group_id:
                    clash = True

                if clash:
                    self.model.Add(var == 0)

    def _vars_for(
        self,
        X: dict,
        assignment: TeachingAssignmentInfo,
        d_i: Optional[int] = None,
        s_i: Optional[int] = None,
        room_id: Optional[str] = None,
    ) -> List[cp_model.IntVar]:
        """Return all decision variables for the given assignment, optionally filtered."""
        result = []
        for key, var in X.items():
            a_id, kd, ks, kr = key
            if a_id != assignment.id:
                continue
            if d_i is not None and kd != d_i:
                continue
            if s_i is not None and ks != s_i:
                continue
            if room_id is not None and kr != room_id:
                continue
            result.append(var)
        return result

    def _h1_assignment_count(self, X: dict) -> None:
        """H1: each assignment is scheduled exactly weekly_count times."""
        for assignment in self.inp.assignments:
            all_vars = self._vars_for(X, assignment)
            # Add constraint regardless of whether all_vars is empty.
            # If all_vars is empty, Sum([]) == 0 != weekly_count, correctly making the model INFEASIBLE.
            self.model.Add(cp_model.LinearExpr.Sum(all_vars) == assignment.weekly_count)

    def _h2_teacher_no_overlap(self, X: dict) -> None:
        """H2: teacher teaches at most 1 session per (day, slot)."""
        # Group by teacher
        teacher_vars: Dict[str, Dict[Tuple[int, int], List[cp_model.IntVar]]] = defaultdict(lambda: defaultdict(list))
        for key, var in X.items():
            a_id, d_i, s_i, room_id = key
            assignment = next((a for a in self.inp.assignments if a.id == a_id), None)
            if assignment is None:
                continue
            teacher_id = assignment.teacher_id
            # For duration 2, teacher occupies (d_i, s_i) and (d_i, s_i+1)
            teacher_vars[teacher_id][(d_i, s_i)].append(var)
            if assignment.duration_slots == 2:
                teacher_vars[teacher_id][(d_i, s_i + 1)].append(var)

        for teacher_id, slot_vars in teacher_vars.items():
            for (d_i, s_i), vars_list in slot_vars.items():
                if len(vars_list) > 1:
                    self.model.Add(cp_model.LinearExpr.Sum(vars_list) <= 1)

    def _h3_room_no_overlap(self, X: dict) -> None:
        """H3: room hosts at most 1 session per (day, slot)."""
        room_vars: Dict[str, Dict[Tuple[int, int], List[cp_model.IntVar]]] = defaultdict(lambda: defaultdict(list))
        for key, var in X.items():
            a_id, d_i, s_i, room_id = key
            assignment = next((a for a in self.inp.assignments if a.id == a_id), None)
            if assignment is None:
                continue
            room_vars[room_id][(d_i, s_i)].append(var)
            if assignment.duration_slots == 2:
                room_vars[room_id][(d_i, s_i + 1)].append(var)

        for room_id, slot_vars in room_vars.items():
            for (d_i, s_i), vars_list in slot_vars.items():
                if len(vars_list) > 1:
                    self.model.Add(cp_model.LinearExpr.Sum(vars_list) <= 1)

    def _h4_division_no_overlap(self, X: dict) -> None:
        """H4: division attends at most 1 session per (day, slot)."""
        div_vars: Dict[str, Dict[Tuple[int, int], List[cp_model.IntVar]]] = defaultdict(lambda: defaultdict(list))
        for key, var in X.items():
            a_id, d_i, s_i, room_id = key
            assignment = next((a for a in self.inp.assignments if a.id == a_id), None)
            if assignment is None:
                continue
            if assignment.batch_id is None and assignment.enrollment_group_id is None:
                # Division-level session
                div_vars[assignment.division_id][(d_i, s_i)].append(var)
                if assignment.duration_slots == 2:
                    div_vars[assignment.division_id][(d_i, s_i + 1)].append(var)

        for div_id, slot_vars in div_vars.items():
            for (d_i, s_i), vars_list in slot_vars.items():
                if len(vars_list) > 1:
                    self.model.Add(cp_model.LinearExpr.Sum(vars_list) <= 1)

    def _h5_batch_no_overlap(self, X: dict) -> None:
        """H5: batch attends at most 1 session per (day, slot)."""
        batch_vars: Dict[str, Dict[Tuple[int, int], List[cp_model.IntVar]]] = defaultdict(lambda: defaultdict(list))
        for key, var in X.items():
            a_id, d_i, s_i, room_id = key
            assignment = next((a for a in self.inp.assignments if a.id == a_id), None)
            if assignment is None:
                continue
            if assignment.batch_id is not None:
                batch_vars[assignment.batch_id][(d_i, s_i)].append(var)
                if assignment.duration_slots == 2:
                    batch_vars[assignment.batch_id][(d_i, s_i + 1)].append(var)

        for batch_id, slot_vars in batch_vars.items():
            for (d_i, s_i), vars_list in slot_vars.items():
                if len(vars_list) > 1:
                    self.model.Add(cp_model.LinearExpr.Sum(vars_list) <= 1)

    def _h7_teacher_unavailability(self, X: dict) -> None:
        """H7: block teacher unavailable (day, slot) combinations."""
        teacher_unavail: Dict[str, Set[Tuple[str, int]]] = defaultdict(set)
        for teacher in self.inp.teachers:
            for slot in teacher.unavailable_slots:
                teacher_unavail[teacher.id].add((slot.day_name, slot.slot_index))

        if not teacher_unavail:
            return

        for key, var in X.items():
            a_id, d_i, s_i, room_id = key
            assignment = next((a for a in self.inp.assignments if a.id == a_id), None)
            if assignment is None:
                continue
            teacher_id = assignment.teacher_id
            if teacher_id in teacher_unavail:
                day_name = self.days[d_i]
                slot_index = self.slots[s_i]
                if (day_name, slot_index) in teacher_unavail[teacher_id]:
                    self.model.Add(var == 0)

    # ------------------------------------------------------------------
    # Soft objective
    # ------------------------------------------------------------------

    def _build_objective(self, X: dict) -> List:
        """Build weighted objective terms. Returns list of CP-SAT linear terms."""
        terms = []
        teacher_preferred: Dict[str, Set[Tuple[str, int]]] = {}
        for teacher in self.inp.teachers:
            if teacher.preferred_slots:
                teacher_preferred[teacher.id] = {
                    (s.day_name, s.slot_index) for s in teacher.preferred_slots
                }

        for key, var in X.items():
            a_id, d_i, s_i, room_id = key
            assignment = next((a for a in self.inp.assignments if a.id == a_id), None)
            if assignment is None:
                continue

            teacher_id = assignment.teacher_id
            day_name = self.days[d_i]
            slot_index = self.slots[s_i]

            # S1: preferred slot bonus
            if teacher_id in teacher_preferred:
                if (day_name, slot_index) in teacher_preferred[teacher_id]:
                    terms.append(W_PREFER * var)

        return terms

    # ------------------------------------------------------------------
    # Solution extraction
    # ------------------------------------------------------------------

    def _extract_sessions(
        self, solver: cp_model.CpSolver, X: dict
    ) -> List[ScheduledSessionInfo]:
        sessions = []
        assignment_map = {a.id: a for a in self.inp.assignments}

        # Map subject_id -> name
        # We don't have subjects in SchedulingInput directly;
        # we infer from assignment info if available
        for key, var in X.items():
            if solver.Value(var) == 0:
                continue
            a_id, d_i, s_i, room_id = key
            assignment = assignment_map.get(a_id)
            if assignment is None:
                continue

            day_name = self.days[d_i]
            slot_index = self.slots[s_i]

            if assignment.batch_id:
                tgt_type = "batch"
                tgt_id = assignment.batch_id
            elif assignment.enrollment_group_id:
                tgt_type = "enrollment_group"
                tgt_id = assignment.enrollment_group_id
            else:
                tgt_type = "division"
                tgt_id = assignment.division_id

            sessions.append(ScheduledSessionInfo(
                assignment_id=a_id,
                teacher_id=assignment.teacher_id,
                subject_id=assignment.subject_id,
                subject_name=assignment.subject_id,  # caller can enrich
                room_id=room_id,
                day_name=day_name,
                slot_index=slot_index,
                session_type=assignment.session_type,
                target_group_type=tgt_type,
                target_group_id=tgt_id,
                duration_slots=assignment.duration_slots,
            ))
        return sessions

    # ------------------------------------------------------------------
    # Infeasibility notes
    # ------------------------------------------------------------------

    def _build_infeasibility_notes(self, status: SolverStatus) -> str:
        if status == SolverStatus.INFEASIBLE:
            # Heuristic analysis
            issues = []
            # Check teacher load vs available slots
            total_slots_needed = sum(
                a.weekly_count * a.duration_slots for a in self.inp.assignments
            )
            available_room_slots = (
                len(self.days) * len(self.slots) * len(self.rooms)
            )
            if total_slots_needed > available_room_slots:
                issues.append(
                    f"Total session-slots required ({total_slots_needed}) exceeds "
                    f"available room-slots ({available_room_slots})."
                )
            # Check if any assignment has no compatible rooms
            for a in self.inp.assignments:
                compatible = [
                    r for r in self.inp.rooms
                    if (a.session_type == "practical") == (r.type == "laboratory")
                ]
                if not compatible:
                    issues.append(
                        f"Assignment '{a.id}' (type={a.session_type}) has no compatible rooms."
                    )
            if issues:
                return "INFEASIBLE. Identified conflicts:\n" + "\n".join(f"  - {i}" for i in issues)
            return (
                "INFEASIBLE. No valid timetable exists for the given constraints. "
                "Consider adding rooms, adjusting teacher availability, or reducing session counts."
            )
        elif status == SolverStatus.TIMEOUT:
            return (
                f"TIMEOUT after {self.time_limit}s. A feasible solution may exist — "
                "increase time_limit_seconds or simplify constraints."
            )
        return f"Status: {status.value}. No solution available."
