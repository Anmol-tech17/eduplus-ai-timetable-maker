"""
backend/app/api/v1/teachers.py
EduPlus AI Timetable Maker — Faculty Profile Endpoints (RBAC & IDOR Protected)
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.app.api.deps import (
    assert_department_access,
    get_db,
    require_roles,
)
from backend.app.models.faculty import Teacher
from backend.app.models.academic import Department
from backend.app.models.security import UserAccount
from backend.app.schemas.faculty import TeacherCreate, TeacherUpdate, TeacherResponse
from backend.app.schemas.common import PaginatedResponse, PaginationMeta
from backend.app.services.audit import record_audit_event

router = APIRouter(prefix="/teachers", tags=["Teachers"])


def _is_own_teacher_profile(user: UserAccount, teacher: Teacher) -> bool:
    if user.linked_entity_id and str(user.linked_entity_id) == str(teacher.id):
        return True
    if teacher.email.lower() == user.email.lower():
        return True
    return False


@router.post("", response_model=TeacherResponse, status_code=status.HTTP_201_CREATED)
def create_teacher(
    teacher_in: TeacherCreate,
    request: Request,
    current_user: UserAccount = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Creates a new faculty member profile (Admin only)."""
    dept = db.query(Department).filter(Department.id == teacher_in.department_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {teacher_in.department_id} not found.",
        )

    existing = db.query(Teacher).filter(Teacher.email == teacher_in.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Teacher with email '{teacher_in.email}' already exists.",
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
        db.flush()
        record_audit_event(
            db=db,
            action="CONFIG_TEACHER_CREATED",
            entity_type="TEACHER",
            user_id=current_user.id,
            entity_id=teacher.id,
            payload={"name": teacher.name, "email": teacher.email, "department_id": str(teacher.department_id)},
            request=request,
        )
        db.commit()
        db.refresh(teacher)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict creating faculty profile.",
        )
    return teacher


@router.get("", response_model=PaginatedResponse[TeacherResponse])
def list_teachers(
    department_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserAccount = Depends(require_roles("admin", "coordinator", "teacher")),
    db: Session = Depends(get_db),
):
    """
    Lists teachers with strict institutional isolation:
    - Teacher: only own faculty profile
    - Coordinator: own department teachers
    - Admin: all teachers
    """
    query = db.query(Teacher)
    if current_user.role == "teacher":
        if current_user.linked_entity_id:
            query = query.filter(Teacher.id == current_user.linked_entity_id)
        else:
            query = query.filter(Teacher.email == current_user.email)
    elif current_user.role == "coordinator":
        if department_id:
            assert_department_access(current_user, department_id)
        if current_user.department_id:
            query = query.filter(Teacher.department_id == current_user.department_id)
    else:
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
        ),
    )


@router.get("/{teacher_id}", response_model=TeacherResponse)
def get_teacher(
    teacher_id: UUID,
    current_user: UserAccount = Depends(require_roles("admin", "coordinator", "teacher")),
    db: Session = Depends(get_db),
):
    """Retrieves teacher by ID (IDOR protected: teachers can only retrieve own profile)."""
    t = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not t:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Teacher with ID {teacher_id} not found.",
        )

    if current_user.role == "teacher":
        if not _is_own_teacher_profile(current_user, t):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: teachers cannot access other teachers' private records.",
            )
    else:
        assert_department_access(current_user, t.department_id)
    return t


@router.put("/{teacher_id}", response_model=TeacherResponse)
def update_teacher(
    teacher_id: UUID,
    teacher_in: TeacherUpdate,
    request: Request,
    current_user: UserAccount = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Updates faculty details (Admin only)."""
    t = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not t:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Teacher with ID {teacher_id} not found.",
        )

    changes = {}
    if teacher_in.name is not None:
        t.name = teacher_in.name
        changes["name"] = teacher_in.name
    if teacher_in.designation is not None:
        t.designation = teacher_in.designation
        changes["designation"] = teacher_in.designation
    if teacher_in.weekly_workload_cap is not None:
        t.weekly_workload_cap = teacher_in.weekly_workload_cap
        changes["weekly_workload_cap"] = teacher_in.weekly_workload_cap

    record_audit_event(
        db=db,
        action="CONFIG_TEACHER_UPDATED",
        entity_type="TEACHER",
        user_id=current_user.id,
        entity_id=t.id,
        payload=changes,
        request=request,
    )
    db.commit()
    db.refresh(t)
    return t
