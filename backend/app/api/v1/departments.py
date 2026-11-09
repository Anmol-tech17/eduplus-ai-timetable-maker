"""
backend/app/api/v1/departments.py
EduPlus AI Timetable Maker — Department CRUD Endpoints
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from backend.app.api.deps import get_db
from backend.app.models.academic import Department
from backend.app.schemas.academic import DepartmentCreate, DepartmentUpdate, DepartmentResponse
from backend.app.schemas.common import PaginatedResponse, PaginationMeta

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(dept_in: DepartmentCreate, db: Session = Depends(get_db)):
    """Creates a new academic department."""
    existing = db.query(Department).filter(Department.code == dept_in.code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Department with code '{dept_in.code}' already exists."
        )

    dept = Department(
        code=dept_in.code.upper(),
        name=dept_in.name,
        college_name=dept_in.college_name,
    )
    db.add(dept)
    try:
        db.commit()
        db.refresh(dept)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict creating department."
        )
    return dept


@router.get("", response_model=PaginatedResponse[DepartmentResponse])
def list_departments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Lists departments with pagination."""
    query = db.query(Department)
    total = query.count()
    items = query.order_by(Department.code.asc()).offset((page - 1) * page_size).limit(page_size).all()
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


@router.get("/{dept_id}", response_model=DepartmentResponse)
def get_department(dept_id: UUID, db: Session = Depends(get_db)):
    """Retrieves department by UUID."""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {dept_id} not found."
        )
    return dept


@router.put("/{dept_id}", response_model=DepartmentResponse)
def update_department(dept_id: UUID, dept_in: DepartmentUpdate, db: Session = Depends(get_db)):
    """Updates an existing department."""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {dept_id} not found."
        )

    if dept_in.name is not None:
        dept.name = dept_in.name
    if dept_in.college_name is not None:
        dept.college_name = dept_in.college_name

    db.commit()
    db.refresh(dept)
    return dept


@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(dept_id: UUID, db: Session = Depends(get_db)):
    """Deletes a department if no child entities restrict it."""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {dept_id} not found."
        )
    try:
        db.delete(dept)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete department: associated academic records exist."
        )
    return None
