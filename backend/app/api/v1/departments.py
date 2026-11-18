"""
backend/app/api/v1/departments.py
EduPlus AI Timetable Maker — Department CRUD Endpoints (RBAC Protected)
"""

from typing import Optional
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
from backend.app.models.academic import Department
from backend.app.models.security import UserAccount
from backend.app.schemas.academic import DepartmentCreate, DepartmentUpdate, DepartmentResponse
from backend.app.schemas.common import PaginatedResponse, PaginationMeta
from backend.app.services.audit import record_audit_event

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
    dept_in: DepartmentCreate,
    request: Request,
    current_user: UserAccount = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Creates a new academic department (Admin only)."""
    existing = db.query(Department).filter(Department.code == dept_in.code.upper()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Department with code '{dept_in.code}' already exists.",
        )

    dept = Department(
        code=dept_in.code.upper(),
        name=dept_in.name,
        college_name=dept_in.college_name,
    )
    db.add(dept)
    try:
        db.flush()
        record_audit_event(
            db=db,
            action="CONFIG_DEPARTMENT_CREATED",
            entity_type="DEPARTMENT",
            user_id=current_user.id,
            entity_id=dept.id,
            payload={"code": dept.code, "name": dept.name},
            request=request,
        )
        db.commit()
        db.refresh(dept)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict creating department.",
        )
    return dept


@router.get("", response_model=PaginatedResponse[DepartmentResponse])
def list_departments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists departments with pagination (scoped to own department for non-admins)."""
    query = db.query(Department)
    if current_user.role != "admin" and current_user.department_id:
        query = query.filter(Department.id == current_user.department_id)
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
        ),
    )


@router.get("/{dept_id}", response_model=DepartmentResponse)
def get_department(
    dept_id: UUID,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves department by UUID (department-isolated for non-admins)."""
    assert_department_access(current_user, dept_id)
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {dept_id} not found.",
        )
    return dept


@router.put("/{dept_id}", response_model=DepartmentResponse)
def update_department(
    dept_id: UUID,
    dept_in: DepartmentUpdate,
    request: Request,
    current_user: UserAccount = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Updates an existing department (Admin only)."""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {dept_id} not found.",
        )

    changes = {}
    if dept_in.name is not None:
        dept.name = dept_in.name
        changes["name"] = dept_in.name
    if dept_in.college_name is not None:
        dept.college_name = dept_in.college_name
        changes["college_name"] = dept_in.college_name

    record_audit_event(
        db=db,
        action="CONFIG_DEPARTMENT_UPDATED",
        entity_type="DEPARTMENT",
        user_id=current_user.id,
        entity_id=dept.id,
        payload=changes,
        request=request,
    )
    db.commit()
    db.refresh(dept)
    return dept


@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    dept_id: UUID,
    request: Request,
    current_user: UserAccount = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Deletes a department if no child entities restrict it (Admin only)."""
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {dept_id} not found.",
        )
    try:
        code = dept.code
        db.delete(dept)
        record_audit_event(
            db=db,
            action="CONFIG_DEPARTMENT_DELETED",
            entity_type="DEPARTMENT",
            user_id=current_user.id,
            entity_id=dept_id,
            payload={"code": code},
            request=request,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete department: associated academic records exist.",
        )
    return None
