"""
backend/app/api/v1/academic_years.py
EduPlus AI Timetable Maker — Academic Year Endpoints (RBAC Protected)
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from backend.app.api.deps import (
    assert_department_access,
    get_current_user,
    get_db,
    require_roles,
)
from backend.app.models.academic import AcademicYear, Department
from backend.app.models.security import UserAccount
from backend.app.schemas.academic import AcademicYearCreate, AcademicYearResponse
from backend.app.services.audit import record_audit_event

router = APIRouter(prefix="/academic-years", tags=["Academic Years"])


@router.post("", response_model=AcademicYearResponse, status_code=status.HTTP_201_CREATED)
def create_academic_year(
    year_in: AcademicYearCreate,
    request: Request,
    current_user: UserAccount = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Creates a new academic year cohort under a department (Admin only)."""
    dept = db.query(Department).filter(Department.id == year_in.department_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {year_in.department_id} not found.",
        )

    existing = db.query(AcademicYear).filter(
        AcademicYear.department_id == year_in.department_id,
        AcademicYear.year_number == year_in.year_number,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Year number {year_in.year_number} already exists for this department.",
        )

    ay = AcademicYear(
        department_id=year_in.department_id,
        year_number=year_in.year_number,
        label=year_in.label,
    )
    db.add(ay)
    db.flush()
    record_audit_event(
        db=db,
        action="CONFIG_ACADEMIC_YEAR_CREATED",
        entity_type="ACADEMIC_YEAR",
        user_id=current_user.id,
        entity_id=ay.id,
        payload={"department_id": str(ay.department_id), "year_number": ay.year_number, "label": ay.label},
        request=request,
    )
    db.commit()
    db.refresh(ay)
    return ay


@router.get("", response_model=List[AcademicYearResponse])
def list_academic_years(
    department_id: Optional[UUID] = Query(None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists academic years (scoped to own department for non-admins)."""
    if department_id:
        assert_department_access(current_user, department_id)
    query = db.query(AcademicYear)
    if current_user.role != "admin" and current_user.department_id:
        query = query.filter(AcademicYear.department_id == current_user.department_id)
    elif department_id:
        query = query.filter(AcademicYear.department_id == department_id)
    return query.order_by(AcademicYear.year_number.asc()).all()


@router.get("/{year_id}", response_model=AcademicYearResponse)
def get_academic_year(
    year_id: UUID,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves an academic year by ID (department-isolated for non-admins)."""
    ay = db.query(AcademicYear).filter(AcademicYear.id == year_id).first()
    if not ay:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Academic Year with ID {year_id} not found.",
        )
    assert_department_access(current_user, ay.department_id)
    return ay
