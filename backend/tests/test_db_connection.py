"""
backend/tests/test_db_connection.py
EduPlus AI Timetable Maker — Database Connection & Dialect Tests
"""

from sqlalchemy import text
from backend.app.db.session import engine


def test_database_connection(db_session):
    """Verifies low-level database roundtrip execution."""
    result = db_session.execute(text("SELECT 1 AS test_val")).fetchone()
    assert result[0] == 1


def test_postgresql_dialect(db_session):
    """Verifies that the target database dialect is PostgreSQL."""
    assert db_session.bind.dialect.name == "postgresql"
    version_row = db_session.execute(text("SHOW server_version")).fetchone()
    assert version_row is not None
    assert "18" in version_row[0]  # PostgreSQL 18

