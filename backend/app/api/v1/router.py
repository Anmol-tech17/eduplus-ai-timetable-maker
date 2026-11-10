"""
backend/app/api/v1/router.py
EduPlus AI Timetable Maker — API v1 Root Router
"""

from fastapi import APIRouter
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.departments import router as departments_router
from backend.app.api.v1.academic_years import router as academic_years_router
from backend.app.api.v1.divisions import router as divisions_router
from backend.app.api.v1.batches import router as batches_router
from backend.app.api.v1.subjects import router as subjects_router
from backend.app.api.v1.teachers import router as teachers_router
from backend.app.api.v1.rooms import router as rooms_router
from backend.app.api.v1.timetable import router as timetable_router

api_v1_router = APIRouter()

api_v1_router.include_router(health_router)
api_v1_router.include_router(departments_router)
api_v1_router.include_router(academic_years_router)
api_v1_router.include_router(divisions_router)
api_v1_router.include_router(batches_router)
api_v1_router.include_router(subjects_router)
api_v1_router.include_router(teachers_router)
api_v1_router.include_router(rooms_router)
api_v1_router.include_router(timetable_router)

