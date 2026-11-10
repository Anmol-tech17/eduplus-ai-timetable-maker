"""
backend/app/api/v1/rooms.py
EduPlus AI Timetable Maker — Classroom & Laboratory Endpoints
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from backend.app.api.deps import get_db
from backend.app.models.room import Room
from backend.app.models.academic import Department
from backend.app.schemas.room import RoomCreate, RoomUpdate, RoomResponse

router = APIRouter(prefix="/rooms", tags=["Rooms"])


@router.post("", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room(room_in: RoomCreate, db: Session = Depends(get_db)):
    """Creates a new classroom or laboratory."""
    dept = db.query(Department).filter(Department.id == room_in.department_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {room_in.department_id} not found."
        )

    existing = db.query(Room).filter(
        Room.department_id == room_in.department_id,
        Room.name == room_in.name
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Room '{room_in.name}' already exists in this department."
        )

    room = Room(
        department_id=room_in.department_id,
        name=room_in.name,
        type=room_in.type.lower(),
        capacity=room_in.capacity,
        floor=room_in.floor,
    )
    db.add(room)
    try:
        db.commit()
        db.refresh(room)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict creating room."
        )
    return room


@router.get("", response_model=List[RoomResponse])
def list_rooms(
    department_id: Optional[UUID] = Query(None),
    type: Optional[str] = Query(None, description="'classroom' or 'laboratory'"),
    db: Session = Depends(get_db)
):
    """Lists rooms with optional department and type filters."""
    query = db.query(Room)
    if department_id:
        query = query.filter(Room.department_id == department_id)
    if type:
        query = query.filter(Room.type == type.lower())
    return query.order_by(Room.floor.asc(), Room.name.asc()).all()


@router.get("/{room_id}", response_model=RoomResponse)
def get_room(room_id: UUID, db: Session = Depends(get_db)):
    """Retrieves room by ID."""
    r = db.query(Room).filter(Room.id == room_id).first()
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room with ID {room_id} not found."
        )
    return r

