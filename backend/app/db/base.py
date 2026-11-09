"""
backend/app/db/base.py
EduPlus AI Timetable Maker — Aggregated Base for Alembic Autogenerate
"""

from backend.app.db.session import Base
# Import all models to ensure they are registered on Base.metadata
from backend.app.models import *  # noqa: F401, F403
