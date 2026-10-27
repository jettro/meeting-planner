"""The health endpoint is only useful if it can report bad news."""

from unittest.mock import patch

from fastapi.testclient import TestClient
from nomnom_service.main import app


def test_health_reports_the_service_and_its_database():
    with TestClient(app) as client:
        body = client.get("/health").json()

    assert body["service"] == "nomnom-service"
    assert body["status"] == "ok"
    assert body["database"]["reachable"] is True


def test_an_unreachable_database_is_a_503():
    """A process that answers 200 while its database is gone is worse than no
    health check at all, because something downstream will believe it."""
    with TestClient(app) as client:
        with patch("nomnom_service.health._database_status", return_value=(False, "disk I/O error")):
            response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
    assert response.json()["database"]["error"] == "disk I/O error"
