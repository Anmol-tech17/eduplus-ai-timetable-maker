"""
backend/app/models/__init__.py
EduPlus AI Timetable Maker — Database Model Exports
"""

from backend.app.models.academic import (
    Department,
    AcademicYear,
    Division,
    Batch,
    Subject,
    EnrollmentGroup,
    EnrollmentGroupOverlap,
)
from backend.app.models.room import (
    Room,
    RoomCapability,
)
from backend.app.models.faculty import (
    Teacher,
    TeacherQualification,
    TeacherAvailability,
)
from backend.app.models.scheduling import (
    TimeSlot,
    WorkingDay,
    DivisionLunchPolicy,
    TeachingAssignment,
    SessionRequirement,
)
from backend.app.models.timetable import (
    InputSnapshot,
    GenerationRun,
    TimetableVersion,
    ScheduledSession,
    Violation,
    SessionException,
)
from backend.app.models.security import (
    UserAccount,
    AuditLog,
)

__all__ = [
    "Department",
    "AcademicYear",
    "Division",
    "Batch",
    "Subject",
    "EnrollmentGroup",
    "EnrollmentGroupOverlap",
    "Room",
    "RoomCapability",
    "Teacher",
    "TeacherQualification",
    "TeacherAvailability",
    "TimeSlot",
    "WorkingDay",
    "DivisionLunchPolicy",
    "TeachingAssignment",
    "SessionRequirement",
    "InputSnapshot",
    "GenerationRun",
    "TimetableVersion",
    "ScheduledSession",
    "Violation",
    "SessionException",
    "UserAccount",
    "AuditLog",
]

