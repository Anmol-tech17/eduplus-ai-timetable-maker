"""
backend/app/schemas/room.py
EduPlus AI Timetable Maker — Room & Laboratory Pydantic Schemas
"""

from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class RoomBase(BaseModel):
    department_id: UUID
    name: str = Field(..., min_length=2, max_length=64, description="Room number or title, e.g. CR301")
    type: str = Field("classroom", description="'classroom' or 'laboratory'")
    capacity: int = Field(60, gt=0, le=300, description="Seating capacity")
    floor: int = Field(1, ge=0, le=10, description="Floor index")


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=64)
    capacity: Optional[int] = Field(None, gt=0, le=300)
    floor: Optional[int] = Field(None, ge=0, le=10)


class RoomResponse(RoomBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

