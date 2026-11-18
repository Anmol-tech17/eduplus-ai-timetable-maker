"""
backend/app/api/v1/subjects.py
EduPlus AI Timetable Maker — Subject Curriculum Endpoints (RBAC Protected)
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.app.api.deps import (
    assert_department_access,
    get_current_user,
    get_db,
    require_roles,
)
from backend.app.models.academic import Subject, Department
from backend.app.models.security import UserAccount
from backend.app.schemas.academic import SubjectCreate, SubjectResponse
from backend.app.services.audit import record_audit_event

router = APIRouter(prefix="/subjects", tags=["Subjects"])


@router.post("", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
def create_subject(
    sub_in: SubjectCreate,
    request: Request,
    current_user: UserAccount = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Creates a new subject under a department (Admin only)."""
    dept = db.query(Department).filter(Department.id == sub_in.department_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {sub_in.department_id} not found.",
        )

    existing = db.query(Subject).filter(
        Subject.department_id == sub_in.department_id,
        Subject.code == sub_in.code.upper(),
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Subject code '{sub_in.code}' already exists in this department.",
        )

    sub = Subject(
        department_id=sub_in.department_id,
        code=sub_in.code.upper(),
        name=sub_in.name,
        short_name=sub_in.short_name,
        year_number=sub_in.year_number,
        ltp_credits=sub_in.ltp_credits,
        is_elective=sub_in.is_elective,
    )
    db.add(sub)
    try:
        db.flush()
        record_audit_event(
            db=db,
            action="CONFIG_SUBJECT_CREATED",
            entity_type="SUBJECT",
            user_id=current_user.id,
            entity_id=sub.id,
            payload={"code": sub.code, "name": sub.name, "department_id": str(sub.department_id)},
            request=request,
        )
        db.commit()
        db.refresh(sub)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict creating subject.",
        )
    return sub


@router.get("", response_model=List[SubjectResponse])
def list_subjects(
    department_id: Optional[UUID] = Query(None),
    year_number: Optional[int] = Query(None, ge=1, le=4),
    is_elective: Optional[bool] = Query(None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists subjects with department scope isolation."""
    if department_id:
        assert_department_access(current_user, department_id)
    query = db.query(Subject)
    if current_user.role != "admin" and current_user.department_id:
        query = query.filter(Subject.department_id == current_user.department_id)
    elif department_id:
        query = query.filter(Subject.department_id == department_id)
    if year_number:
        query = query.filter(Subject.year_number == year_number)
    if is_elective is not None:
        query = query.filter(Subject.is_elective == is_elective)
    return query.order_by(Subject.code.asc()).all()


@router.get("/{sub_id}", response_model=SubjectResponse)
def get_subject(
    sub_id: UUID,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves subject by ID (department-isolated for non-admins)."""
    sub = db.query(Subject).filter(Subject.id == sub_id).first()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {sub_id} not found.",
        )
    assert_department_access(current_user, sub.department_id)
    return sub
