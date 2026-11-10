"""
backend/app/models/room.py
EduPlus AI Timetable Maker — Classroom & Laboratory Models
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, SmallInteger, ForeignKey,
    DateTime, UniqueConstraint, CheckConstraint, Uuid
)
from sqlalchemy.orm import relationship
from backend.app.db.session import Base


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    department_id = Column(Uuid, ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False, index=True)
    name = Column(String(64), nullable=False)  # 'Room 101', 'AI/ML Lab 1'
    type = Column(String(32), nullable=False, default="classroom")  # 'classroom', 'laboratory'
    capacity = Column(Integer, nullable=False, default=60)
    floor = Column(SmallInteger, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("department_id", "name", name="uq_dept_room_name"),
        CheckConstraint("type IN ('classroom', 'laboratory')", name="chk_room_type"),
        CheckConstraint("capacity > 0", name="chk_room_capacity"),
    )

    department = relationship("Department", back_populates="rooms")
    capabilities = relationship("RoomCapability", back_populates="room", cascade="all, delete-orphan")


class RoomCapability(Base):
    __tablename__ = "room_capabilities"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    room_id = Column(Uuid, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    capability = Column(String(64), nullable=False)  # e.g., 'GPU Workstations', 'Cisco Routers'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("room_id", "capability", name="uq_room_capability"),
    )

    room = relationship("Room", back_populates="capabilities")

