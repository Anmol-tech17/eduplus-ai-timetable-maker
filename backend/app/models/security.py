"""
backend/app/models/security.py
EduPlus AI Timetable Maker — User Accounts & Audit Log Models
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, ForeignKey,
    DateTime, UniqueConstraint, CheckConstraint, JSON, Uuid
)
from sqlalchemy.orm import relationship
from backend.app.db.session import Base


class UserAccount(Base):
    __tablename__ = "user_accounts"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False)  # 'admin', 'teacher', 'student'
    department_id = Column(Uuid, ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True, index=True)
    linked_entity_id = Column(Uuid, nullable=True)  # Links to Teacher.id or Student identifier
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'teacher', 'student')", name="chk_user_role"),
    )

    department = relationship("Department")
    audit_logs = relationship("AuditLog", back_populates="user")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(64), nullable=False)  # 'TIMETABLE_PUBLISH', 'SESSION_MOVE'
    entity_type = Column(String(64), nullable=False)  # 'TIMETABLE_VERSION', 'TEACHER'
    entity_id = Column(Uuid, nullable=True)
    payload = Column(JSON, nullable=True)  # Operational diff or params
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("UserAccount", back_populates="audit_logs")
