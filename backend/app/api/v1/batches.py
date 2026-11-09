"""
backend/app/api/v1/batches.py
EduPlus AI Timetable Maker — Lab Batch Cohort Endpoints
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.api.deps import get_db
from backend.app.models.academic import Batch, Division
from backend.app.schemas.academic import BatchCreate, BatchResponse

router = APIRouter(prefix="/batches", tags=["Batches"])


@router.post("", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
def create_batch(batch_in: BatchCreate, db: Session = Depends(get_db)):
    """Creates a lab batch under a division."""
    div = db.query(Division).filter(Division.id == batch_in.division_id).first()
    if not div:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Division with ID {batch_in.division_id} not found."
        )

    existing = db.query(Batch).filter(
        Batch.division_id == batch_in.division_id,
        Batch.name == batch_in.name
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Batch '{batch_in.name}' already exists in this division."
        )

    batch = Batch(
        division_id=batch_in.division_id,
        name=batch_in.name.upper(),
        capacity=batch_in.capacity,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.get("", response_model=List[BatchResponse])
def list_batches(
    division_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db)
):
    """Lists batches, optionally filtered by division."""
    query = db.query(Batch)
    if division_id:
        query = query.filter(Batch.division_id == division_id)
    return query.order_by(Batch.name.asc()).all()
