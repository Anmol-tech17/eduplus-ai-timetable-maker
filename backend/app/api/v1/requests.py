"""
backend/app/api/v1/requests.py
EduPlus AI Timetable Maker — Teacher Availability & Schedule Change Request Endpoints

Endpoints:
- POST /api/v1/requests             (Teacher only — own teacher_id enforced)
- GET  /api/v1/requests             (Teacher: own only | Coordinator: own dept | Admin: all)
- GET  /api/v1/requests/{id}        (Strict owner / dept scope isolation)
- POST /api/v1/requests/{id}/review (Admin & Coordinator only)
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from backend.app.api.deps import (
    assert_department_access,
    get_db,
    require_roles,
)
from backend.app.models.faculty import Teacher
from backend.app.models.security import TeacherRequest, UserAccount
from backend.app.schemas.security import (
    TeacherRequestCreate,
    TeacherRequestOut,
    TeacherRequestReview,
)
from backend.app.services.audit import record_audit_event

router = APIRouter(prefix="/requests", tags=["Teacher Requests"])


def _resolve_teacher_for_user(user: UserAccount, db: Session) -> Teacher:
    teacher = None
    if user.linked_entity_id:
        teacher = db.query(Teacher).filter(Teacher.id == user.linked_entity_id).first()
    if teacher is None:
        teacher = db.query(Teacher).filter(Teacher.email == user.email).first()
    if teacher is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No faculty profile linked to this teacher account.",
        )
    return teacher


def _to_out(req: TeacherRequest) -> TeacherRequestOut:
    return TeacherRequestOut(
        id=req.id,
        teacher_id=req.teacher_id,
        teacher_name=req.teacher.name if req.teacher else None,
        department_id=req.department_id,
        submitted_by=req.submitted_by,
        request_type=req.request_type,
        day_name=req.day_name,
        time_slot_code=req.time_slot_code,
        reason=req.reason,
        status=req.status,
        reviewed_by=req.reviewed_by,
        review_comment=req.review_comment,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


@router.post("", response_model=TeacherRequestOut, status_code=status.HTTP_201_CREATED)
def submit_teacher_request(
    payload: TeacherRequestCreate,
    request: Request,
    current_user: UserAccount = Depends(require_roles("teacher")),
    db: Session = Depends(get_db),
):
    """Submit a faculty availability or schedule change request (Teacher only, own identity)."""
    teacher = _resolve_teacher_for_user(current_user, db)

    req = TeacherRequest(
        teacher_id=teacher.id,
        department_id=teacher.department_id,
        submitted_by=current_user.id,
        request_type=payload.request_type,
        day_name=payload.day_name,
        time_slot_code=payload.time_slot_code,
        reason=payload.reason,
        status="pending",
    )
    db.add(req)
    db.flush()

    record_audit_event(
        db=db,
        action="TEACHER_REQUEST_CREATED",
        entity_type="TEACHER_REQUEST",
        user_id=current_user.id,
        entity_id=req.id,
        payload={
            "teacher_id": str(teacher.id),
            "request_type": req.request_type,
            "day_name": req.day_name,
            "time_slot_code": req.time_slot_code,
        },
        request=request,
    )
    db.commit()
    db.refresh(req)
    return _to_out(req)


@router.get("", response_model=List[TeacherRequestOut])
def list_teacher_requests(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    department_id: Optional[UUID] = Query(default=None),
    current_user: UserAccount = Depends(require_roles("admin", "coordinator", "teacher")),
    db: Session = Depends(get_db),
):
    """
    List teacher requests with strict role-based isolation:
    - Teacher: only own submitted requests
    - Coordinator: requests within own department
    - Admin: all requests (optionally filtered by department)
    """
    q = db.query(TeacherRequest)

    if current_user.role == "teacher":
        teacher = _resolve_teacher_for_user(current_user, db)
        q = q.filter(TeacherRequest.teacher_id == teacher.id)
    elif current_user.role == "coordinator":
        if current_user.department_id is None:
            return []
        if department_id and str(department_id) != str(current_user.department_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: cannot view requests for another department.",
            )
        q = q.filter(TeacherRequest.department_id == current_user.department_id)
    else:
        if department_id:
            q = q.filter(TeacherRequest.department_id == department_id)

    if status_filter:
        q = q.filter(TeacherRequest.status == status_filter)

    items = q.order_by(TeacherRequest.created_at.desc()).all()
    return [_to_out(item) for item in items]


@router.get("/{request_id}", response_model=TeacherRequestOut)
def get_teacher_request(
    request_id: UUID,
    current_user: UserAccount = Depends(require_roles("admin", "coordinator", "teacher")),
    db: Session = Depends(get_db),
):
    """Retrieve a single teacher request with strict ownership/department isolation."""
    req = db.query(TeacherRequest).filter(TeacherRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")

    if current_user.role == "teacher":
        teacher = _resolve_teacher_for_user(current_user, db)
        if req.teacher_id != teacher.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: you may only view your own requests.",
            )
    else:
        assert_department_access(current_user, req.department_id)

    return _to_out(req)


@router.post("/{request_id}/review", response_model=TeacherRequestOut)
def review_teacher_request(
    request_id: UUID,
    payload: TeacherRequestReview,
    request: Request,
    current_user: UserAccount = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    """Approve or reject a pending teacher request (Admin or Coordinator in dept)."""
    req = db.query(TeacherRequest).filter(TeacherRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")

    assert_department_access(current_user, req.department_id)

    if req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Request has already been {req.status}.",
        )

    req.status = payload.decision
    req.reviewed_by = current_user.id
    req.review_comment = payload.comment

    record_audit_event(
        db=db,
        action="TEACHER_REQUEST_REVIEWED",
        entity_type="TEACHER_REQUEST",
        user_id=current_user.id,
        entity_id=req.id,
        payload={
            "teacher_id": str(req.teacher_id),
            "decision": payload.decision,
            "comment": payload.comment,
        },
        request=request,
    )
    db.commit()
    db.refresh(req)
    return _to_out(req)
