"""
backend/app/api/deps.py
EduPlus AI Timetable Maker — Shared API Dependencies
"""

from typing import Generator
from sqlalchemy.orm import Session
from backend.app.db.session import get_db

# Re-export get_db
__all__ = ["get_db"]

