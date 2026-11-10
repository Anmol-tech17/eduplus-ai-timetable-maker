"""
backend/tests/test_health.py
EduPlus AI Timetable Maker — Health & Root Endpoint Tests
"""

def test_root_endpoint(client):
    """Verifies that root '/' returns project metadata and endpoints."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert data["health"] == "/api/v1/health"


def test_health_check_endpoint(client):
    """Verifies that '/api/v1/health' reports connected database status."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["service"] == "EduPlus AI Timetable Maker"

