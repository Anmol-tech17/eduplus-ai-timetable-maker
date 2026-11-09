"""
backend/app/api/v1/teachers.py
EduPlus AI Timetable Maker — Faculty Profile Endpoints
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from backend.app.api.deps import get_db
from backend.app.models.faculty import Teacher
from backend.app.models.academic import Department
from backend.app.schemas.faculty import TeacherCreate, TeacherUpdate, TeacherResponse
from backend.app.schemas.common import PaginatedResponse, PaginationMeta

router = APIRouter(prefix="/teachers", tags=["Teachers"])


@router.post("", response_model=TeacherResponse, status_code=status.HTTP_201_CREATED)
def create_teacher(teacher_in: TeacherCreate, db: Session = Depends(get_db)):
    """Creates a new faculty member profile."""
    dept = db.query(Department).filter(Department.id == teacher_in.department_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {teacher_in.department_id} not found."
        )

    existing = db.query(Teacher).filter(Teacher.email == teacher_in.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Teacher with email '{teacher_in.email}' already exists."
        )

    teacher = Teacher(
        department_id=teacher_in.department_id,
        name=teacher_in.name,
        short_name=teacher_in.short_name,
        designation=teacher_in.designation,
        weekly_workload_cap=teacher_in.weekly_workload_cap,
        email=teacher_in.email,
    )
    db.add(teacher)
    try:
        db.commit()
        db.refresh(teacher)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict creating faculty profile."
        )
    return teacher


@router.get("", response_model=PaginatedResponse[TeacherResponse])
def list_teachers(
    department_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Lists teachers with pagination and optional department filter."""
    query = db.query(Teacher)
    if department_id:
        query = query.filter(Teacher.department_id == department_id)
    total = query.count()
    items = query.order_by(Teacher.name.asc()).offset((page - 1) * page_size).limit(page_size).all()
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    return PaginatedResponse(
        items=items,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total_records=total,
            total_pages=total_pages,
        )
    )


@router.get("/{teacher_id}", response_model=TeacherResponse)
def get_teacher(teacher_id: UUID, db: Session = Depends(get_db)):
    """Retrieves teacher by ID."""
    t = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not t:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Teacher with ID {teacher_id} not found."
        )
    return t


@router.put("/{teacher_id}", response_model=TeacherResponse)
def update_teacher(teacher_id: UUID, teacher_in: TeacherUpdate, db: Session = Depends(get_db)):
    """Updates faculty details."""
    t = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not t:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Teacher with ID {teacher_id} not found."
        )

    if teacher_in.name is not None:
        t.name = teacher_in.name
    if teacher_in.designation is not None:
        t.designation = teacher_in.designation
    if teacher_in.weekly_workload_cap is not None:
        t.weekly_workload_cap = teacher_in.weekly_workload_cap

    db.commit()
    db.refresh(t)
    return t
