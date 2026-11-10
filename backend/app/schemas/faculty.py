"""
backend/app/schemas/faculty.py
EduPlus AI Timetable Maker — Faculty Pydantic Validation Schemas
"""

from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, EmailStr, ConfigDict


class TeacherBase(BaseModel):
    department_id: UUID
    name: str = Field(..., min_length=2, max_length=128, description="Full name of faculty")
    short_name: str = Field(..., min_length=2, max_length=16, description="Display short name, e.g. P.Sharma")
    designation: str = Field(..., min_length=2, max_length=64, description="Professor, Associate Prof, etc.")
    weekly_workload_cap: int = Field(16, ge=4, le=36, description="Max teaching hours cap per week")
    email: EmailStr = Field(..., description="Institutional email address")


class TeacherCreate(TeacherBase):
    pass


class TeacherUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=128)
    designation: Optional[str] = Field(None, min_length=2, max_length=64)
    weekly_workload_cap: Optional[int] = Field(None, ge=4, le=36)


class TeacherResponse(TeacherBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

