"""The composed app: ours spliced into the framework's, nothing displaced.

The framework warns that a client must splice into `server_modules` rather
than retype the community composition, because a retyped copy drifts silently
at the next upgrade. These tests are the alarm for that drift: they assert the
stock routes the SPA depends on are still there, alongside the two we add.
"""

from __future__ import annotations

import pytest
from akgentic.infra.server import state_keys
from fastapi.testclient import TestClient
from meeting_server.app import create_meeting_app
from meeting_server.settings import ServerSettings

#: The stock routes the browser uses. Not the whole surface - just the ones a
#: plan cannot be made without.
REQUIRED = {
    "POST /teams",
    "GET /teams/{team_id}/events",
    "POST /teams/{team_id}/human-input",
    "POST /teams/{team_id}/message/from/{sender_name}/to/{recipient_name}",
    "DELETE /teams/{team_id}",
}


@pytest.fixture
def app(tmp_path):
    built = create_meeting_app(
        ServerSettings(
            catalog_path="agents/catalog",
            event_store_path=tmp_path / "events",
            workspaces_root=tmp_path / "workspaces",
            plan_store_path=tmp_path / "plans.json",
            cors_origins=["http://localhost:5173"],
        )
    )
    yield built
    # The actor system is a thread pool; leaving it running leaks it into the
    # next test module.
    state_keys.SERVICES.require(built).actor_system.shutdown()


def routes(app) -> set[str]:
    found = set()
    for route in app.routes:
        for method in getattr(route, "methods", set()) or set():
            found.add(f"{method} {route.path}")
    return found


def test_the_stock_team_routes_survive_the_splice(app):
    assert REQUIRED <= routes(app)


def test_our_routes_are_mounted(app):
    assert {"GET /platform/health", "GET /plans", "GET /plans/{plan_id}"} <= routes(app)


def test_the_plans_route_answers(app):
    """Not a smoke test of FastAPI: it proves the route is reachable without a
    principal. The community tier runs on `NoAuth`, and a 401 here would mean
    the SPA needs a login screen nobody designed."""
    with TestClient(app) as client:
        response = client.get("/plans")

    assert response.status_code == 200
    assert response.json() == []
