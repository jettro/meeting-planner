"""Memory through the server: the trees land where the login says (design_memory.md).

The chat team is created through `POST /teams` as a logged-in person, the way
the browser does it, and nothing is said to it - so no model is called. What is
checked is where the trees are, and what the framework's routes let a browser
see of them (spike S3, S4).
"""

from __future__ import annotations

import pytest
from akgentic.infra.server import state_keys
from fastapi.testclient import TestClient
from meeting_server.app import create_meeting_app
from meeting_server.auth import Person
from meeting_server.settings import AuthSettings, ServerSettings
from pydantic import SecretStr

JETTRO = "jettro@rag4p.org"
DAAN = "daan@rag4p.org"


async def people() -> list[Person]:
    return [Person(email=JETTRO, name="Jettro Coenradie"), Person(email=DAAN, name="Daan Jansen")]


@pytest.fixture
def root(tmp_path):
    return tmp_path / "workspaces"


@pytest.fixture
def app(tmp_path, root, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "not-used-by-these-tests")
    monkeypatch.delenv("AKGENTIC_WORKSPACE_SHARED_KINDS", raising=False)
    monkeypatch.delenv("AKGENTIC_WORKSPACES_ROOT", raising=False)
    built = create_meeting_app(
        ServerSettings(
            catalog_path="agents/catalog",
            event_store_path=tmp_path / "events",
            workspaces_root=root,
            cors_origins=["http://localhost:5173"],
            auth=AuthSettings(mode="demo", secret=SecretStr("a-secret-for-tests-only")),
        ),
        people=people,
    )
    yield built
    state_keys.SERVICES.require(built).actor_system.shutdown()


def conversation(app, email: str) -> tuple[TestClient, str]:
    client = TestClient(app)
    assert client.post("/auth/login/person", json={"email": email}).status_code == 200
    response = client.post("/teams", json={"catalog_namespace": "meeting-planner-chat"})
    assert response.status_code == 201, response.text
    return client, response.json()["team_id"]


def test_the_trees_are_under_the_server_root_and_the_logged_in_person(app, root):
    """M12: not ./workspaces, and not anonymous."""
    with TestClient(app):
        conversation(app, JETTRO)

        assert (root / JETTRO / "_id" / "memory").is_dir()
        assert (root / JETTRO / "_id" / "memory.git").is_dir()
        assert (root / "_shared" / "_id" / "memory-shared").is_dir()


def test_the_console_can_see_your_own_tree(app):
    with TestClient(app):
        client, team = conversation(app, JETTRO)

        response = client.get(f"/workspace/{team}/tree", params={"workspace_id": "memory"})

        assert response.status_code == 200, response.text


def test_the_framework_never_shows_the_shared_tree(app):
    """404: the shared tree is held inside MemoryTool, so no card declares it to
    the server. Declaring it would only change this to the framework's 403 for
    every `_shared` path (spike S4) - either way the Memory page will need a
    route of its own for it."""
    with TestClient(app):
        client, team = conversation(app, JETTRO)

        response = client.get(f"/workspace/{team}/tree", params={"workspace_id": "memory-shared"})

        assert response.status_code == 404, response.text


def test_another_person_cannot_read_your_tree(app):
    with TestClient(app):
        _, team = conversation(app, JETTRO)
        daan, _ = conversation(app, DAAN)

        response = daan.get(f"/workspace/{team}/tree", params={"workspace_id": "memory"})

        assert response.status_code == 404
