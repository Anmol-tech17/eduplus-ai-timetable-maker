"""
backend/app/api/v1/academic_years.py
EduPlus AI Timetable Maker — Academic Year Endpoints
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from backend.app.api.deps import get_db
from backend.app.models.academic import AcademicYear, Department
from backend.app.schemas.academic import AcademicYearCreate, AcademicYearResponse

router = APIRouter(prefix="/academic-years", tags=["Academic Years"])


@router.post("", response_model=AcademicYearResponse, status_code=status.HTTP_201_CREATED)
def create_academic_year(year_in: AcademicYearCreate, db: Session = Depends(get_db)):
    """Creates a new academic year cohort under a department."""
    dept = db.query(Department).filter(Department.id == year_in.department_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {year_in.department_id} not found."
        )

    existing = db.query(AcademicYear).filter(
        AcademicYear.department_id == year_in.department_id,
        AcademicYear.year_number == year_in.year_number
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Year number {year_in.year_number} already exists for this department."
        )

    ay = AcademicYear(
        department_id=year_in.department_id,
        year_number=year_in.year_number,
        label=year_in.label,
    )
    db.add(ay)
    db.commit()
    db.refresh(ay)
    return ay


@router.get("", response_model=List[AcademicYearResponse])
def list_academic_years(
    department_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db)
):
    """Lists academic years, optionally filtered by department."""
    query = db.query(AcademicYear)
    if department_id:
        query = query.filter(AcademicYear.department_id == department_id)
    return query.order_by(AcademicYear.year_number.asc()).all()


@router.get("/{year_id}", response_model=AcademicYearResponse)
def get_academic_year(year_id: UUID, db: Session = Depends(get_db)):
    """Retrieves an academic year by ID."""
    ay = db.query(AcademicYear).filter(AcademicYear.id == year_id).first()
    if not ay:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Academic Year with ID {year_id} not found."
        )
    return ay
