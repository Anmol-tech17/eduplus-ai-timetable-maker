"""
backend/app/api/v1/batches.py
EduPlus AI Timetable Maker — Lab Batch Cohort Endpoints (RBAC & Isolation Protected)
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db, require_roles
from backend.app.models.academic import AcademicYear, Batch, Division
from backend.app.models.security import UserAccount
from backend.app.schemas.academic import BatchCreate, BatchResponse
from backend.app.services.audit import record_audit_event

router = APIRouter(prefix="/batches", tags=["Batches"])


@router.post("", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
def create_batch(
    batch_in: BatchCreate,
    request: Request,
    current_user: UserAccount = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Creates a lab batch under a division (Admin only)."""
    div = db.query(Division).filter(Division.id == batch_in.division_id).first()
    if not div:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Division with ID {batch_in.division_id} not found.",
        )

    existing = db.query(Batch).filter(
        Batch.division_id == batch_in.division_id,
        Batch.name == batch_in.name.upper(),
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Batch '{batch_in.name}' already exists in this division.",
        )

    batch = Batch(
        division_id=batch_in.division_id,
        name=batch_in.name.upper(),
        capacity=batch_in.capacity,
    )
    db.add(batch)
    db.flush()
    record_audit_event(
        db=db,
        action="CONFIG_BATCH_CREATED",
        entity_type="BATCH",
        user_id=current_user.id,
        entity_id=batch.id,
        payload={"division_id": str(batch.division_id), "name": batch.name, "capacity": batch.capacity},
        request=request,
    )
    db.commit()
    db.refresh(batch)
    return batch


@router.get("", response_model=List[BatchResponse])
def list_batches(
    division_id: Optional[UUID] = Query(None),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists batches with role-based institutional isolation."""
    query = db.query(Batch).join(Division, Batch.division_id == Division.id).join(
        AcademicYear, Division.academic_year_id == AcademicYear.id
    )

    if current_user.role == "student":
        if not current_user.linked_entity_id:
            return []
        if division_id and str(division_id) != str(current_user.linked_entity_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: students cannot view another division's batches.",
            )
        query = query.filter(Batch.division_id == current_user.linked_entity_id)
    elif current_user.role != "admin" and current_user.department_id:
        query = query.filter(AcademicYear.department_id == current_user.department_id)
        if division_id:
            query = query.filter(Batch.division_id == division_id)
    else:
        if division_id:
            query = query.filter(Batch.division_id == division_id)

    return query.order_by(Batch.name.asc()).all()
