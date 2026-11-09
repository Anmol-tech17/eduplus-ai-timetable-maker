"""
backend/app/schemas/common.py
EduPlus AI Timetable Maker — Common API Schema Envelopes
"""

from typing import Generic, TypeVar, Optional, List, Any
from pydantic import BaseModel

T = TypeVar("T")


class ResponseEnvelope(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None
    errors: Optional[List[Any]] = None


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total_records: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    pagination: PaginationMeta
