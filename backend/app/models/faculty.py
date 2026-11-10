"""
backend/app/models/faculty.py
EduPlus AI Timetable Maker — Faculty & Availability Models
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, SmallInteger, ForeignKey,
    DateTime, UniqueConstraint, CheckConstraint, Uuid
)
from sqlalchemy.orm import relationship
from backend.app.db.session import Base


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    department_id = Column(Uuid, ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    short_name = Column(String(16), nullable=False)  # 'P.Sharma', 'A.Mehta'
    designation = Column(String(64), nullable=False)  # 'Professor', 'Assistant Professor'
    weekly_workload_cap = Column(SmallInteger, nullable=False, default=16)
    email = Column(String(255), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("weekly_workload_cap BETWEEN 4 AND 36", name="chk_teacher_cap"),
    )

    department = relationship("Department", back_populates="teachers")
    qualifications = relationship("TeacherQualification", back_populates="teacher", cascade="all, delete-orphan")
    availabilities = relationship("TeacherAvailability", back_populates="teacher", cascade="all, delete-orphan")
    assignments = relationship("TeachingAssignment", back_populates="teacher")


class TeacherQualification(Base):
    __tablename__ = "teacher_qualifications"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    teacher_id = Column(Uuid, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_id = Column(Uuid, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    qualification_level = Column(String(32), nullable=False, default="primary")  # 'primary', 'secondary'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("teacher_id", "subject_id", name="uq_teacher_subject"),
        CheckConstraint("qualification_level IN ('primary', 'secondary')", name="chk_qual_level"),
    )

    teacher = relationship("Teacher", back_populates="qualifications")
    subject = relationship("Subject", back_populates="qualifications")


class TeacherAvailability(Base):
    __tablename__ = "teacher_availabilities"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    teacher_id = Column(Uuid, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    day_name = Column(String(16), nullable=False)  # 'Monday'
    time_slot_id = Column(Uuid, ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False, index=True)
    availability_type = Column(String(16), nullable=False, default="unavailable")  # 'unavailable', 'preferred'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("availability_type IN ('unavailable', 'preferred')", name="chk_avail_type"),
    )

    teacher = relationship("Teacher", back_populates="availabilities")
    time_slot = relationship("TimeSlot")

