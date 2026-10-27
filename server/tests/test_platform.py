"""The platform screen's one question, and the three answers behind it.

The distinction being tested is the one a person staring at a failing demo
needs: a service that answers 503 (its database is gone) is a different
problem from one that does not answer at all, and collapsing them into "down"
throws away the only clue.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from meeting_server import platform
from meeting_server.settings import ServerSettings, ServiceEndpoint

SERVICES = [
    ServiceEndpoint(name="meeting-service", url="http://meeting-service:8101"),
    ServiceEndpoint(name="location-service", url="http://location-service:8102"),
    ServiceEndpoint(name="nomnom-service", url="http://nomnom-service:8103"),
]


@pytest.fixture
def settings():
    return ServerSettings(services=SERVICES, health_timeout_seconds=0.5)


def client_for(monkeypatch, settings, handler):
    """A platform router whose outbound calls are answered by `handler`."""
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def fake_client(**kwargs):
        return original(transport=transport, **kwargs)

    monkeypatch.setattr(platform.httpx, "AsyncClient", fake_client)
    app = FastAPI()
    app.include_router(platform.build_router(settings))
    return TestClient(app)


def test_everything_up_is_reported_as_up(monkeypatch, settings):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/health"
        return httpx.Response(200, json={"service": "x", "status": "ok"})

    body = client_for(monkeypatch, settings, handler).get("/platform/health").json()

    assert body["status"] == "up"
    assert [service["status"] for service in body["services"]] == ["up", "up", "up"]
    assert [service["name"] for service in body["services"]] == [s.name for s in SERVICES]


def test_one_service_down_degrades_the_platform(monkeypatch, settings):
    """A platform that is 2/3 up cannot plan a meeting, so it is not up."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "nomnom-service":
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(200, json={"status": "ok"})

    body = client_for(monkeypatch, settings, handler).get("/platform/health").json()

    assert body["status"] == "degraded"
    unreachable = [s for s in body["services"] if s["status"] == "unreachable"]
    assert [s["name"] for s in unreachable] == ["nomnom-service"]
    assert "connection refused" in unreachable[0]["detail"]


def test_a_service_with_a_broken_database_is_degraded_not_unreachable(monkeypatch, settings):
    """503 is the answer a service gives when its own `/health` finds no
    database. It answered, so saying "unreachable" would point at the network."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "location-service":
            return httpx.Response(503, json={"status": "unavailable"})
        return httpx.Response(200, json={"status": "ok"})

    body = client_for(monkeypatch, settings, handler).get("/platform/health").json()

    broken = next(s for s in body["services"] if s["name"] == "location-service")
    assert body["status"] == "degraded"
    assert broken["status"] == "degraded"
    assert broken["detail"] == "HTTP 503"


def test_the_probe_reports_every_service_even_when_all_fail(monkeypatch, settings):
    """The screen lists three dots whatever happens. A fan-out that gave up on
    the first failure would leave the other two unexplained."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    body = client_for(monkeypatch, settings, handler).get("/platform/health").json()

    assert len(body["services"]) == 3
    assert {s["status"] for s in body["services"]} == {"unreachable"}
