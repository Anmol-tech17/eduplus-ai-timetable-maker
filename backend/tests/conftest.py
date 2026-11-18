"""
backend/tests/conftest.py
EduPlus AI Timetable Maker — Test Configuration & Fixtures
"""

import os
import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.app.core.config import settings
from backend.app.core.security import (
    create_access_token,
    get_password_hash,
    login_rate_limiter,
    token_revocation_store,
)
from backend.app.db.session import Base, get_db
from backend.app.main import app
from backend.app.models.security import UserAccount

# Use isolated PostgreSQL test database
TEST_DB_URL = os.getenv("TEST_DATABASE_URL", settings.TEST_DATABASE_URL)

test_engine = create_engine(
    TEST_DB_URL,
    pool_pre_ping=True,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Ensure all tables are created on the test database."""
    Base.metadata.create_all(bind=test_engine)
    yield


@pytest.fixture(autouse=True)
def reset_security_stores():
    """Ensure token revocation and rate limit state do not leak across tests."""
    token_revocation_store.clear()
    login_rate_limiter.clear()
    yield
    token_revocation_store.clear()
    login_rate_limiter.clear()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provides a transactional database session rolled back after each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def unauth_client(db_session: Session) -> Generator[TestClient, None, None]:
    """Unauthenticated TestClient with overridden get_db dependency (no Authorization header)."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    Authenticated Admin TestClient with overridden get_db dependency.
    Uses a genuine signed JWT access token backed by a UserAccount row in db_session.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    admin = db_session.query(UserAccount).filter(UserAccount.email == "admin@eduplus.demo").first()
    if admin is None:
        admin = UserAccount(
            email="admin@eduplus.demo",
            full_name="Test Admin",
            password_hash=get_password_hash("admin123"),
            role="admin",
            can_approve_timetable=True,
            is_active=True,
        )
        db_session.add(admin)
        db_session.flush()

    token, _jti, _exp = create_access_token(
        subject=str(admin.id),
        role=admin.role,
        email=admin.email,
        department_id=str(admin.department_id) if admin.department_id else None,
    )

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as test_client:
        yield test_client
    app.dependency_overrides.clear()
