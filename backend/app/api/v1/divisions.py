"""
backend/app/api/v1/divisions.py
EduPlus AI Timetable Maker — Division Cohort Endpoints (RBAC & Isolation Protected)
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
from backend.app.models.academic import Division, AcademicYear
from backend.app.models.room import Room
from backend.app.models.security import UserAccount
from backend.app.schemas.academic import DivisionCreate, DivisionResponse
from backend.app.services.audit import record_audit_event

router = APIRouter(prefix="/divisions", tags=["Divisions"])


@router.post("", response_model=DivisionResponse, status_code=status.HTTP_201_CREATED)
def create_division(
    div_in: DivisionCreate,
    request: Request,
    current_user: UserAccount = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Creates a new division under an academic year (Admin only)."""
    ay = db.query(AcademicYear).filter(AcademicYear.id == div_in.academic_year_id).first()
    if not ay:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Academic Year with ID {div_in.academic_year_id} not found.",
        )

    if div_in.home_room_id:
        room = db.query(Room).filter(Room.id == div_in.home_room_id).first()
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Home room with ID {div_in.home_room_id} not found.",
            )

    existing = db.query(Division).filter(
        Division.academic_year_id == div_in.academic_year_id,
        Division.name == div_in.name.upper(),
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Division '{div_in.name}' already exists in this academic year.",
        )

    div = Division(
        academic_year_id=div_in.academic_year_id,
        name=div_in.name.upper(),
        strength=div_in.strength,
        home_room_id=div_in.home_room_id,
    )
    db.add(div)
    db.flush()
    record_audit_event(
        db=db,
        action="CONFIG_DIVISION_CREATED",
        entity_type="DIVISION",
        user_id=current_user.id,
        entity_id=div.id,
        payload={"academic_year_id": str(div.academic_year_id), "name": div.name, "strength": div.strength},
        request=request,
    )
    db.commit()
    db.refresh(div)
    return div


@router.get("", response_model=List[DivisionResponse])
def list_divisions(
    academic_year_id: Optional[UUID] = Query(None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lists divisions with strict role isolation:
    - Student: only their assigned division
    - Coordinator/Teacher: divisions in their own department
    - Admin: all divisions
    """
    query = db.query(Division).join(AcademicYear, Division.academic_year_id == AcademicYear.id)

    if current_user.role == "student":
        if not current_user.linked_entity_id:
            return []
        query = query.filter(Division.id == current_user.linked_entity_id)
    elif current_user.role != "admin" and current_user.department_id:
        query = query.filter(AcademicYear.department_id == current_user.department_id)

    if academic_year_id:
        query = query.filter(Division.academic_year_id == academic_year_id)
    return query.order_by(Division.name.asc()).all()


@router.get("/{div_id}", response_model=DivisionResponse)
def get_division(
    div_id: UUID,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves a division by ID (students cannot retrieve another division)."""
    div = db.query(Division).filter(Division.id == div_id).first()
    if not div:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Division with ID {div_id} not found.",
        )

    if current_user.role == "student":
        if not current_user.linked_entity_id or str(div.id) != str(current_user.linked_entity_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: students cannot access another division's data.",
            )
    elif current_user.role != "admin":
        ay = db.query(AcademicYear).filter(AcademicYear.id == div.academic_year_id).first()
        if ay:
            assert_department_access(current_user, ay.department_id)

    return div
