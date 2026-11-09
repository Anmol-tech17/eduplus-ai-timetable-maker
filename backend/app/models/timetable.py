"""
backend/app/models/timetable.py
EduPlus AI Timetable Maker — Timetable Runs, Versions, Sessions, and Exceptions
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, SmallInteger, Boolean, Date, Text,
    ForeignKey, DateTime, CheckConstraint, JSON, Uuid, Index
)
from sqlalchemy.orm import relationship
from backend.app.db.session import Base


class InputSnapshot(Base):
    __tablename__ = "input_snapshots"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    data = Column(JSON, nullable=False)  # Normalized snapshot of subjects, teachers, rooms, rules
    checksum = Column(String(64), nullable=False)  # SHA-256 hash
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class GenerationRun(Base):
    __tablename__ = "generation_runs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    input_snapshot_id = Column(Uuid, ForeignKey("input_snapshots.id", ondelete="RESTRICT"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="running")  # 'running', 'completed', 'infeasible', 'timeout', 'failed'
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    solver_time_ms = Column(Integer, nullable=True)
    solver_status = Column(String(32), nullable=True)  # 'OPTIMAL', 'FEASIBLE', 'INFEASIBLE'
    notes = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('running', 'completed', 'infeasible', 'timeout', 'failed')", name="chk_gen_status"),
    )

    input_snapshot = relationship("InputSnapshot")
    timetable_versions = relationship("TimetableVersion", back_populates="generation_run")


class TimetableVersion(Base):
    __tablename__ = "timetable_versions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    generation_run_id = Column(Uuid, ForeignKey("generation_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    parent_version_id = Column(Uuid, ForeignKey("timetable_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    department_id = Column(Uuid, ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False, default=1)
    status = Column(String(32), nullable=False, default="draft")  # 'draft', 'candidate', 'published', 'archived'
    label = Column(String(128), nullable=False)  # e.g., 'AY2026-27 Sem 1 - v1.0 Final'
    academic_year_code = Column(String(32), nullable=False, default="2026-27")
    semester = Column(SmallInteger, nullable=False, default=1)
    is_repair = Column(Boolean, nullable=False, default=False)
    published_at = Column(DateTime, nullable=True)
    published_by = Column(Uuid, ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'candidate', 'published', 'archived')", name="chk_tt_status"),
        Index("idx_tt_dept_status", "department_id", "status"),
    )

    department = relationship("Department", back_populates="timetable_versions")
    generation_run = relationship("GenerationRun", back_populates="timetable_versions")
    parent_version = relationship("TimetableVersion", remote_side=[id])
    sessions = relationship("ScheduledSession", back_populates="timetable_version", cascade="all, delete-orphan")
    violations = relationship("Violation", back_populates="timetable_version", cascade="all, delete-orphan")
    exceptions = relationship("SessionException", back_populates="timetable_version", cascade="all, delete-orphan")


class ScheduledSession(Base):
    __tablename__ = "scheduled_sessions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    timetable_version_id = Column(Uuid, ForeignKey("timetable_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    teaching_assignment_id = Column(Uuid, ForeignKey("teaching_assignments.id", ondelete="RESTRICT"), nullable=False, index=True)
    teacher_id = Column(Uuid, ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False, index=True)
    room_id = Column(Uuid, ForeignKey("rooms.id", ondelete="RESTRICT"), nullable=False, index=True)
    day_name = Column(String(16), nullable=False)  # 'Monday'
    time_slot_id = Column(Uuid, ForeignKey("time_slots.id", ondelete="RESTRICT"), nullable=False, index=True)
    session_type = Column(String(16), nullable=False)  # 'lecture', 'tutorial', 'practical'
    target_group_type = Column(String(32), nullable=False)  # 'division', 'batch', 'enrollment_group'
    target_group_id = Column(Uuid, nullable=False, index=True)
    is_frozen = Column(Boolean, nullable=False, default=False)  # Pin during repair
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_session_version_lookup", "timetable_version_id", "day_name", "time_slot_id"),
        Index("idx_session_teacher_slot", "timetable_version_id", "teacher_id", "day_name", "time_slot_id"),
        Index("idx_session_room_slot", "timetable_version_id", "room_id", "day_name", "time_slot_id"),
    )

    timetable_version = relationship("TimetableVersion", back_populates="sessions")
    teaching_assignment = relationship("TeachingAssignment")
    teacher = relationship("Teacher")
    room = relationship("Room")
    time_slot = relationship("TimeSlot")


class Violation(Base):
    __tablename__ = "violations"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    timetable_version_id = Column(Uuid, ForeignKey("timetable_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id = Column(String(16), nullable=False)  # 'A01', 'A03', 'B01'
    rule_level = Column(String(2), nullable=False)  # 'A', 'B', 'C'
    severity = Column(String(16), nullable=False, default="error")  # 'error', 'warning', 'info'
    description = Column(Text, nullable=False)
    affected_session_ids = Column(JSON, nullable=False, default=[])
    affected_entity_ids = Column(JSON, nullable=False, default=[])
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("rule_level IN ('A', 'B', 'C')", name="chk_rule_level"),
        Index("idx_violations_version", "timetable_version_id", "rule_level"),
    )

    timetable_version = relationship("TimetableVersion", back_populates="violations")


class SessionException(Base):
    __tablename__ = "session_exceptions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    timetable_version_id = Column(Uuid, ForeignKey("timetable_versions.id", ondelete="RESTRICT"), nullable=False, index=True)
    scheduled_session_id = Column(Uuid, ForeignKey("scheduled_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    exception_date = Column(Date, nullable=False, index=True)
    exception_type = Column(String(32), nullable=False)  # 'cancelled', 'substituted', 'rescheduled'
    substitute_teacher_id = Column(Uuid, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True)
    alternate_room_id = Column(Uuid, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    alternate_slot_id = Column(Uuid, ForeignKey("time_slots.id", ondelete="SET NULL"), nullable=True)
    reason = Column(Text, nullable=False)
    requires_makeup = Column(Boolean, nullable=False, default=False)
    created_by = Column(Uuid, ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    timetable_version = relationship("TimetableVersion", back_populates="exceptions")
    scheduled_session = relationship("ScheduledSession")
    substitute_teacher = relationship("Teacher", foreign_keys=[substitute_teacher_id])
    alternate_room = relationship("Room", foreign_keys=[alternate_room_id])
    alternate_slot = relationship("TimeSlot", foreign_keys=[alternate_slot_id])
