"""
backend/app/models/scheduling.py
EduPlus AI Timetable Maker — Scheduling Configuration & Teaching Assignment Models
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, SmallInteger, Boolean, Time, ForeignKey,
    DateTime, UniqueConstraint, CheckConstraint, JSON, Uuid
)
from sqlalchemy.orm import relationship
from backend.app.db.session import Base


class TimeSlot(Base):
    __tablename__ = "time_slots"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    slot_code = Column(String(16), nullable=False, unique=True, index=True)  # 'TS1', 'TS2'
    start_time = Column(Time, nullable=False)  # 08:00:00
    end_time = Column(Time, nullable=False)    # 09:00:00
    slot_index = Column(SmallInteger, nullable=False, unique=True)  # 1 to 10
    label = Column(String(64), nullable=False)  # '08:00 – 09:00'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class WorkingDay(Base):
    __tablename__ = "working_days"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    department_id = Column(Uuid, ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True)
    day_name = Column(String(16), nullable=False)  # 'Monday'
    day_index = Column(SmallInteger, nullable=False)  # 1 = Monday, 6 = Saturday
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("department_id", "day_name", name="uq_dept_day"),
        CheckConstraint("day_index BETWEEN 1 AND 7", name="chk_day_index"),
    )

    department = relationship("Department", back_populates="working_days")


class DivisionLunchPolicy(Base):
    __tablename__ = "division_lunch_policies"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    division_id = Column(Uuid, ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False, unique=True)
    allowed_slots = Column(JSON, nullable=False, default=["TS5", "TS6"])  # JSON array of slot codes
    assigned_slot_id = Column(Uuid, ForeignKey("time_slots.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    division = relationship("Division", back_populates="lunch_policy")
    assigned_slot = relationship("TimeSlot")


class TeachingAssignment(Base):
    __tablename__ = "teaching_assignments"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    subject_id = Column(Uuid, ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False, index=True)
    division_id = Column(Uuid, ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(Uuid, ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False, index=True)
    session_type = Column(String(16), nullable=False, default="lecture")  # 'lecture', 'tutorial', 'practical'
    batch_id = Column(Uuid, ForeignKey("batches.id", ondelete="CASCADE"), nullable=True, index=True)
    enrollment_group_id = Column(Uuid, ForeignKey("enrollment_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("session_type IN ('lecture', 'tutorial', 'practical')", name="chk_session_type"),
    )

    subject = relationship("Subject")
    division = relationship("Division")
    teacher = relationship("Teacher", back_populates="assignments")
    batch = relationship("Batch")
    enrollment_group = relationship("EnrollmentGroup")
    session_requirements = relationship("SessionRequirement", back_populates="teaching_assignment", cascade="all, delete-orphan")


class SessionRequirement(Base):
    __tablename__ = "session_requirements"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    teaching_assignment_id = Column(Uuid, ForeignKey("teaching_assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    weekly_count = Column(SmallInteger, nullable=False, default=3)
    duration_hours = Column(SmallInteger, nullable=False, default=1)  # 1 for lecture/tutorial, 2 for practical
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("duration_hours IN (1, 2)", name="chk_duration"),
        CheckConstraint("weekly_count BETWEEN 1 AND 10", name="chk_weekly_count"),
    )

    teaching_assignment = relationship("TeachingAssignment", back_populates="session_requirements")
