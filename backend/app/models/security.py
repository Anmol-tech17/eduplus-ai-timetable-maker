"""
backend/app/models/security.py
EduPlus AI Timetable Maker — User Accounts, Audit Logs, and Teacher Requests Models
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Text, ForeignKey,
    DateTime, CheckConstraint, JSON, Uuid, Index
)
from sqlalchemy.orm import relationship
from backend.app.db.session import Base


class UserAccount(Base):
    __tablename__ = "user_accounts"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True, index=True)
    full_name = Column(String(128), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False)  # 'admin', 'coordinator', 'teacher', 'student'
    department_id = Column(Uuid, ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True, index=True)
    linked_entity_id = Column(Uuid, nullable=True)  # Teacher.id for teacher, Division.id for student
    can_approve_timetable = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'coordinator', 'teacher', 'student')",
            name="chk_user_role",
        ),
    )

    department = relationship("Department")
    audit_logs = relationship("AuditLog", back_populates="user")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(64), nullable=False)  # e.g. 'AUTH_LOGIN_SUCCESS', 'TIMETABLE_APPROVE', 'TIMETABLE_PUBLISH'
    entity_type = Column(String(64), nullable=False)  # e.g. 'USER_ACCOUNT', 'TIMETABLE_VERSION'
    entity_id = Column(Uuid, nullable=True)
    payload = Column(JSON, nullable=True)  # Sanitized operational details (never passwords/tokens)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("UserAccount", back_populates="audit_logs")


class TeacherRequest(Base):
    """Availability or timetable change requests submitted by faculty members."""
    __tablename__ = "teacher_requests"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    teacher_id = Column(Uuid, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = Column(Uuid, ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True)
    submitted_by = Column(Uuid, ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True)
    request_type = Column(String(32), nullable=False)  # 'availability', 'reschedule', 'substitution', 'cancellation'
    day_name = Column(String(16), nullable=True)
    time_slot_code = Column(String(16), nullable=True)
    reason = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="pending")  # 'pending', 'approved', 'rejected'
    reviewed_by = Column(Uuid, ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True)
    review_comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "request_type IN ('availability', 'reschedule', 'substitution', 'cancellation')",
            name="chk_teacher_req_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="chk_teacher_req_status",
        ),
        Index("idx_teacher_req_dept_status", "department_id", "status"),
    )

    teacher = relationship("Teacher")
    department = relationship("Department")
