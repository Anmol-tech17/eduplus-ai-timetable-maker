"""
backend/app/engine/types.py
EduPlus AI Timetable Maker — Shared Data Types for the Scheduling Engine

All dataclasses here are plain Python (no SQLAlchemy). They serve as the
interface layer between the database and the validator / CP-SAT solver.
Keeping types separate makes the engine independently testable.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class SessionType(str, Enum):
    LECTURE = "lecture"
    TUTORIAL = "tutorial"
    PRACTICAL = "practical"


class TargetGroupType(str, Enum):
    DIVISION = "division"
    BATCH = "batch"
    ENROLLMENT_GROUP = "enrollment_group"


class RoomType(str, Enum):
    CLASSROOM = "classroom"
    LABORATORY = "laboratory"


class AvailabilityType(str, Enum):
    UNAVAILABLE = "unavailable"
    PREFERRED = "preferred"


class ViolationLevel(str, Enum):
    A = "A"   # Hard constraint — schedule is invalid
    B = "B"   # Policy — schedule is discouraged
    C = "C"   # Soft preference — schedule is suboptimal


class SolverStatus(str, Enum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Domain value objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SlotKey:
    """Identifies a unique (day, time-slot) position in the weekly grid."""
    day_name: str        # 'Monday' … 'Saturday'
    slot_index: int      # 1 … 10


@dataclass
class TimeSlotInfo:
    id: str
    slot_code: str
    slot_index: int
    label: str


@dataclass
class WorkingDayInfo:
    id: str
    day_name: str
    day_index: int
    is_active: bool


@dataclass
class TeacherInfo:
    id: str
    name: str
    short_name: str
    department_id: str
    weekly_workload_cap: int
    unavailable_slots: List[SlotKey] = field(default_factory=list)   # hard blocks
    preferred_slots: List[SlotKey] = field(default_factory=list)      # soft preferences


@dataclass
class SubjectInfo:
    id: str
    code: str
    name: str
    short_name: str
    year_number: int
    is_elective: bool
    ltp_credits: str   # e.g. '3-0-0'


@dataclass
class RoomInfo:
    id: str
    name: str
    type: str           # 'classroom' or 'laboratory'
    capacity: int
    capabilities: List[str] = field(default_factory=list)   # e.g. ['GPU Workstations']


@dataclass
class BatchInfo:
    id: str
    name: str
    division_id: str
    capacity: int


@dataclass
class DivisionInfo:
    id: str
    name: str
    academic_year_id: str
    strength: int
    batch_ids: List[str] = field(default_factory=list)


@dataclass
class TeachingAssignmentInfo:
    id: str
    subject_id: str
    division_id: str
    teacher_id: str
    session_type: str         # SessionType value
    batch_id: Optional[str]   # None for division-level sessions
    enrollment_group_id: Optional[str]
    # From SessionRequirement
    weekly_count: int
    duration_slots: int       # 1 for lecture/tutorial, 2 for practical


@dataclass
class SchedulingInput:
    """
    Normalised, solver-ready representation of all scheduling inputs
    for a single department / academic-year scope.

    Constructed by SchedulingInputBuilder (db/input_builder.py).
    """
    department_id: str
    academic_year_ids: List[str]      # scope filter
    working_days: List[WorkingDayInfo]
    time_slots: List[TimeSlotInfo]
    teachers: List[TeacherInfo]
    rooms: List[RoomInfo]
    divisions: List[DivisionInfo]
    batches: List[BatchInfo]
    assignments: List[TeachingAssignmentInfo]
    # Optional: pre-fixed sessions during repair
    pinned_sessions: List["ScheduledSessionInfo"] = field(default_factory=list)
    # AI-injected / dynamic constraints
    blocked_practical_days: List[str] = field(default_factory=list)
    slot_preference_weight: int = 2
    gap_penalty_weight: int = 3


@dataclass
class ScheduledSessionInfo:
    """
    A single timetable entry — the output unit of the solver,
    also used for validation input.
    """
    assignment_id: str
    teacher_id: str
    subject_id: str
    subject_name: str
    room_id: str
    day_name: str
    slot_index: int
    session_type: str
    target_group_type: str    # 'division' | 'batch' | 'enrollment_group'
    target_group_id: str
    duration_slots: int = 1
    is_frozen: bool = False


# ---------------------------------------------------------------------------
# Violation record
# ---------------------------------------------------------------------------

@dataclass
class ViolationRecord:
    rule_id: str               # 'A01', 'B03', 'C02' …
    level: ViolationLevel
    severity: str              # 'error' | 'warning' | 'info'
    description: str
    affected_session_ids: List[str] = field(default_factory=list)
    affected_entity_ids: List[str] = field(default_factory=list)
    suggestion: Optional[str] = None

    @property
    def is_hard(self) -> bool:
        return self.level == ViolationLevel.A


# ---------------------------------------------------------------------------
# Solver result
# ---------------------------------------------------------------------------

@dataclass
class SolverResult:
    status: SolverStatus
    sessions: List[ScheduledSessionInfo] = field(default_factory=list)
    violations: List[ViolationRecord] = field(default_factory=list)
    solver_time_ms: int = 0
    objective_value: Optional[float] = None
    num_conflicts: Optional[int] = None
    diagnostic_notes: str = ""

