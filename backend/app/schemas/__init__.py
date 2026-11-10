"""
backend/app/schemas/__init__.py
EduPlus AI Timetable Maker — Pydantic Schemas Exports
"""

from backend.app.schemas.common import ResponseEnvelope, PaginationMeta, PaginatedResponse
from backend.app.schemas.academic import (
    DepartmentCreate, DepartmentUpdate, DepartmentResponse,
    AcademicYearCreate, AcademicYearResponse,
    DivisionCreate, DivisionResponse,
    BatchCreate, BatchResponse,
    SubjectCreate, SubjectResponse,
)
from backend.app.schemas.faculty import TeacherCreate, TeacherUpdate, TeacherResponse
from backend.app.schemas.room import RoomCreate, RoomUpdate, RoomResponse
from backend.app.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse

__all__ = [
    "ResponseEnvelope",
    "PaginationMeta",
    "PaginatedResponse",
    "DepartmentCreate",
    "DepartmentUpdate",
    "DepartmentResponse",
    "AcademicYearCreate",
    "AcademicYearResponse",
    "DivisionCreate",
    "DivisionResponse",
    "BatchCreate",
    "BatchResponse",
    "SubjectCreate",
    "SubjectResponse",
    "TeacherCreate",
    "TeacherUpdate",
    "TeacherResponse",
    "RoomCreate",
    "RoomUpdate",
    "RoomResponse",
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "TokenResponse",
]

