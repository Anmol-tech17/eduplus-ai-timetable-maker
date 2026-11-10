"""
backend/app/api/v1/divisions.py
EduPlus AI Timetable Maker — Division Cohort Endpoints
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.api.deps import get_db
from backend.app.models.academic import Division, AcademicYear
from backend.app.models.room import Room
from backend.app.schemas.academic import DivisionCreate, DivisionResponse

router = APIRouter(prefix="/divisions", tags=["Divisions"])


@router.post("", response_model=DivisionResponse, status_code=status.HTTP_201_CREATED)
def create_division(div_in: DivisionCreate, db: Session = Depends(get_db)):
    """Creates a new division under an academic year."""
    ay = db.query(AcademicYear).filter(AcademicYear.id == div_in.academic_year_id).first()
    if not ay:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Academic Year with ID {div_in.academic_year_id} not found."
        )

    if div_in.home_room_id:
        room = db.query(Room).filter(Room.id == div_in.home_room_id).first()
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Home room with ID {div_in.home_room_id} not found."
            )

    existing = db.query(Division).filter(
        Division.academic_year_id == div_in.academic_year_id,
        Division.name == div_in.name
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Division '{div_in.name}' already exists in this academic year."
        )

    div = Division(
        academic_year_id=div_in.academic_year_id,
        name=div_in.name.upper(),
        strength=div_in.strength,
        home_room_id=div_in.home_room_id,
    )
    db.add(div)
    db.commit()
    db.refresh(div)
    return div


@router.get("", response_model=List[DivisionResponse])
def list_divisions(
    academic_year_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db)
):
    """Lists divisions, optionally filtered by academic year."""
    query = db.query(Division)
    if academic_year_id:
        query = query.filter(Division.academic_year_id == academic_year_id)
    return query.order_by(Division.name.asc()).all()


@router.get("/{div_id}", response_model=DivisionResponse)
def get_division(div_id: UUID, db: Session = Depends(get_db)):
    """Retrieves a division by ID."""
    div = db.query(Division).filter(Division.id == div_id).first()
    if not div:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Division with ID {div_id} not found."
        )
    return div

