"""
backend/app/models/academic.py
EduPlus AI Timetable Maker — Academic Hierarchy Models
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, SmallInteger, Boolean, ForeignKey,
    DateTime, UniqueConstraint, CheckConstraint, Uuid
)
from sqlalchemy.orm import relationship
from backend.app.db.session import Base


class Department(Base):
    __tablename__ = "departments"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    code = Column(String(16), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    college_name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    academic_years = relationship("AcademicYear", back_populates="department", cascade="all, delete-orphan")
    subjects = relationship("Subject", back_populates="department", cascade="all, delete-orphan")
    teachers = relationship("Teacher", back_populates="department", cascade="all, delete-orphan")
    rooms = relationship("Room", back_populates="department", cascade="all, delete-orphan")
    working_days = relationship("WorkingDay", back_populates="department", cascade="all, delete-orphan")
    timetable_versions = relationship("TimetableVersion", back_populates="department")


class AcademicYear(Base):
    __tablename__ = "academic_years"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    department_id = Column(Uuid, ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True)
    year_number = Column(SmallInteger, nullable=False)  # 1, 2, 3, 4
    label = Column(String(64), nullable=False)  # e.g., 'Third Year'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("department_id", "year_number", name="uq_dept_year"),
        CheckConstraint("year_number BETWEEN 1 AND 4", name="chk_year_number"),
    )

    department = relationship("Department", back_populates="academic_years")
    divisions = relationship("Division", back_populates="academic_year", cascade="all, delete-orphan")


class Division(Base):
    __tablename__ = "divisions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    academic_year_id = Column(Uuid, ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(16), nullable=False)  # 'A', 'B', etc.
    strength = Column(Integer, nullable=False, default=60)
    home_room_id = Column(Uuid, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("academic_year_id", "name", name="uq_year_div_name"),
        CheckConstraint("strength > 0", name="chk_div_strength"),
    )

    academic_year = relationship("AcademicYear", back_populates="divisions")
    batches = relationship("Batch", back_populates="division", cascade="all, delete-orphan")
    home_room = relationship("Room", foreign_keys=[home_room_id])
    lunch_policy = relationship("DivisionLunchPolicy", back_populates="division", uselist=False, cascade="all, delete-orphan")


class Batch(Base):
    __tablename__ = "batches"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    division_id = Column(Uuid, ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(16), nullable=False)  # 'B1', 'B2', 'B3'
    capacity = Column(Integer, nullable=False, default=20)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("division_id", "name", name="uq_division_batch"),
        CheckConstraint("capacity > 0", name="chk_batch_capacity"),
    )

    division = relationship("Division", back_populates="batches")


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    department_id = Column(Uuid, ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True)
    code = Column(String(32), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    short_name = Column(String(32), nullable=False)
    year_number = Column(SmallInteger, nullable=False)
    ltp_credits = Column(String(16), nullable=False, default="3-0-0")
    is_elective = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("department_id", "code", name="uq_dept_subject_code"),
    )

    department = relationship("Department", back_populates="subjects")
    enrollment_groups = relationship("EnrollmentGroup", back_populates="subject", cascade="all, delete-orphan")
    qualifications = relationship("TeacherQualification", back_populates="subject", cascade="all, delete-orphan")


class EnrollmentGroup(Base):
    __tablename__ = "enrollment_groups"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    subject_id = Column(Uuid, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    division_id = Column(Uuid, ForeignKey("divisions.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(64), nullable=False)  # 'EG_CV', 'EG_NLP'
    student_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    subject = relationship("Subject", back_populates="enrollment_groups")
    division = relationship("Division")


class EnrollmentGroupOverlap(Base):
    __tablename__ = "enrollment_group_overlaps"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    group_a_id = Column(Uuid, ForeignKey("enrollment_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    group_b_id = Column(Uuid, ForeignKey("enrollment_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    shared_student_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("group_a_id", "group_b_id", name="uq_group_overlap"),
    )

    group_a = relationship("EnrollmentGroup", foreign_keys=[group_a_id])
    group_b = relationship("EnrollmentGroup", foreign_keys=[group_b_id])

