"""
backend/app/schemas/academic.py
EduPlus AI Timetable Maker — Academic Pydantic Validation Schemas
"""

from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


# ─── Department ───────────────────────────────────────────────────────────────
class DepartmentBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=16, description="Unique department code, e.g. AIML")
    name: str = Field(..., min_length=2, max_length=255, description="Full department name")
    college_name: str = Field(..., min_length=2, max_length=255, description="Parent college title")


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    college_name: Optional[str] = Field(None, min_length=2, max_length=255)


class DepartmentResponse(DepartmentBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─── Academic Year ────────────────────────────────────────────────────────────
class AcademicYearBase(BaseModel):
    department_id: UUID
    year_number: int = Field(..., ge=1, le=4, description="B.Tech year level (1 to 4)")
    label: str = Field(..., min_length=2, max_length=64, description="Display label, e.g. 'Third Year'")


class AcademicYearCreate(AcademicYearBase):
    pass


class AcademicYearResponse(AcademicYearBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─── Division ─────────────────────────────────────────────────────────────────
class DivisionBase(BaseModel):
    academic_year_id: UUID
    name: str = Field(..., min_length=1, max_length=16, description="Division letter (A, B, C)")
    strength: int = Field(60, gt=0, le=120, description="Enrolled students count")
    home_room_id: Optional[UUID] = None


class DivisionCreate(DivisionBase):
    pass


class DivisionResponse(DivisionBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─── Batch ────────────────────────────────────────────────────────────────────
class BatchBase(BaseModel):
    division_id: UUID
    name: str = Field(..., min_length=1, max_length=16, description="Batch name (B1, B2, B3)")
    capacity: int = Field(20, gt=0, le=60, description="Max batch capacity")


class BatchCreate(BatchBase):
    pass


class BatchResponse(BatchBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─── Subject ──────────────────────────────────────────────────────────────────
class SubjectBase(BaseModel):
    department_id: UUID
    code: str = Field(..., min_length=2, max_length=32, description="Course code, e.g. AIML301")
    name: str = Field(..., min_length=2, max_length=255, description="Full subject name")
    short_name: str = Field(..., min_length=1, max_length=32, description="Short code, e.g. ML")
    year_number: int = Field(..., ge=1, le=4)
    ltp_credits: str = Field("3-0-0", max_length=16, description="L-T-P pattern, e.g. 3-0-2")
    is_elective: bool = False


class SubjectCreate(SubjectBase):
    pass


class SubjectResponse(SubjectBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

