"""Who is asking (design_auth.md): the login, the gate, and what it buys.

The framework already decides who may see which team; these tests hold it to
that once there is somebody to decide about. They run the real catalog and the
real `meeting-planner` team through the composed app, and nothing here sends
the team a message, so no model is ever called.
"""

from __future__ import annotations

import pytest
from akgentic.infra.server import state_keys
from fastapi.testclient import TestClient
from meeting_server.app import create_meeting_app
from meeting_server.auth import COOKIE, Person
from meeting_server.settings import AuthSettings, ServerSettings
from pydantic import SecretStr
from starlette.websockets import WebSocketDisconnect

SANNE = "sanne@rag4p.org"
DAAN = "daan@rag4p.org"
ADMIN = "femke@rag4p.org"
#: Made up for the test; the real ones live only in the environment.
KEY = "ak_test_console"

PEOPLE = [
    Person(email=SANNE, name="Sanne de Vries"),
    Person(email=DAAN, name="Daan Jansen"),
    Person(email=ADMIN, name="Femke Bakker"),
]

META = {"title": "Design review", "day": "2034-06-20", "location_id": "yuma", "participants": 2}


async def people() -> list[Person]:
    return PEOPLE


@pytest.fixture
def app(tmp_path, monkeypatch):
    # The specialists are built when a team is created, and building one wants
    # a key to exist; nothing in these tests makes a call with it.
    monkeypatch.setenv("OPENAI_API_KEY", "not-used-by-these-tests")
    built = create_meeting_app(
        ServerSettings(
            catalog_path="agents/catalog",
            event_store_path=tmp_path / "events",
            workspaces_root=tmp_path / "workspaces",
            cors_origins=["http://localhost:5173"],
            auth=AuthSettings(
                mode="demo",
                secret=SecretStr("a-secret-for-tests-only"),
                admin_emails=frozenset({ADMIN}),
                api_keys={KEY: SANNE},
            ),
        ),
        people=people,
    )
    yield built
    state_keys.SERVICES.require(built).actor_system.shutdown()


def logged_in(app, email: str) -> TestClient:
    client = TestClient(app)
    response = client.post("/auth/login/person", json={"email": email})
    assert response.status_code == 200, response.text
    return client


def create_team(client: TestClient) -> str:
    response = client.post("/teams", json={"catalog_namespace": "meeting-planner", "metadata": META})
    assert response.status_code == 201, response.text
    return response.json()["team_id"]


def team_ids(client: TestClient) -> list[str]:
    return [team["team_id"] for team in client.get("/teams").json()["teams"]]


# --- the login --------------------------------------------------------------


def test_without_a_session_the_teams_are_closed(app):
    with TestClient(app) as client:
        assert client.get("/teams").status_code == 401


def test_the_login_page_and_health_need_no_session(app):
    with TestClient(app) as client:
        assert [p["email"] for p in client.get("/auth/users").json()] == [SANNE, DAAN, ADMIN]
        assert client.get("/readiness").status_code == 200
        assert client.get("/auth/me").status_code == 401


def test_picking_a_person_logs_in_as_them(app):
    with TestClient(app):
        client = logged_in(app, SANNE)
        me = client.get("/auth/me").json()

    assert me == {"user_id": SANNE, "email": SANNE, "name": "Sanne de Vries", "roles": []}


def test_somebody_the_meeting_service_does_not_know_cannot_log_in(app):
    with TestClient(app) as client:
        response = client.post("/auth/login/person", json={"email": "mallory@example.com"})

    assert response.status_code == 401
    assert COOKIE not in response.cookies


def test_the_cookie_cannot_be_read_by_scripts(app):
    with TestClient(app) as client:
        response = client.post("/auth/login/person", json={"email": SANNE})

    header = response.headers["set-cookie"].lower()
    assert "httponly" in header
    assert "samesite=lax" in header


def test_a_forged_cookie_is_nobody(app):
    with TestClient(app) as client:
        client.cookies.set(COOKIE, "eyJlbWFpbCI6ICJzYW5uZUByYWc0cC5vcmcifQ==.forged")
        assert client.get("/teams").status_code == 401


def test_logging_out_ends_the_session(app):
    with TestClient(app):
        client = logged_in(app, SANNE)
        assert client.get("/auth/logout").json() == {"success": True}
        assert client.get("/teams").status_code == 401


def test_an_admin_is_named_in_configuration(app):
    with TestClient(app):
        assert logged_in(app, ADMIN).get("/auth/me").json()["roles"] == ["admin"]


# --- the console's API key (A14) --------------------------------------------


def test_an_api_key_logs_in_the_way_the_console_expects(app):
    with TestClient(app) as client:
        response = client.post("/auth/login/apikey", json={"apikey": KEY})
        body = response.json()

        assert response.status_code == 200
        assert body["success"] is True
        assert body["user"]["user_id"] == SANNE
        # From then on the cookie is all it sends.
        assert client.get("/teams").status_code == 200


def test_an_unknown_api_key_is_refused(app):
    with TestClient(app) as client:
        assert client.post("/auth/login/apikey", json={"apikey": "ak_wrong"}).status_code == 401
        assert client.get("/teams", headers={"X-API-Key": "ak_wrong"}).status_code == 401


def test_a_script_may_send_its_key_on_every_request(app):
    with TestClient(app) as client:
        assert client.get("/teams", headers={"X-API-Key": KEY}).status_code == 200


# --- what the framework does with a principal --------------------------------


def test_a_team_belongs_to_whoever_created_it(app):
    with TestClient(app):
        sanne = logged_in(app, SANNE)
        team = create_team(sanne)

        assert sanne.get(f"/teams/{team}").json()["user_id"] == SANNE
        assert team_ids(sanne) == [team]


def test_another_person_cannot_even_see_it(app):
    """404, not 403: somebody else's meeting does not exist for you."""
    with TestClient(app):
        team = create_team(logged_in(app, SANNE))
        daan = logged_in(app, DAAN)

        assert team_ids(daan) == []
        assert daan.get(f"/teams/{team}").status_code == 404
        assert daan.get(f"/teams/{team}/agent-states").status_code == 404
        assert daan.post(f"/teams/{team}/restore").status_code == 404
        assert daan.delete(f"/teams/{team}").status_code == 404


def test_an_admin_sees_every_team(app):
    with TestClient(app):
        team = create_team(logged_in(app, SANNE))

        assert team_ids(logged_in(app, ADMIN)) == [team]


def test_only_the_owner_can_watch_the_trace(app):
    with TestClient(app) as anonymous:
        sanne = logged_in(app, SANNE)
        team = create_team(sanne)

        with sanne.websocket_connect(f"/ws/{team}") as socket:
            assert socket.receive_json()

        for client in (logged_in(app, DAAN), anonymous):
            with pytest.raises(WebSocketDisconnect) as closed:
                with client.websocket_connect(f"/ws/{team}") as socket:
                    socket.receive_json()
            assert closed.value.code == 1008


def test_a_restored_team_still_belongs_to_its_owner(app):
    with TestClient(app):
        sanne = logged_in(app, SANNE)
        team = create_team(sanne)

        assert sanne.post(f"/teams/{team}/stop").status_code == 204
        assert sanne.post(f"/teams/{team}/restore").status_code == 200
        assert sanne.get(f"/teams/{team}").json()["user_id"] == SANNE


# --- configuration -----------------------------------------------------------


def test_the_deployed_server_logs_in_by_default(monkeypatch):
    monkeypatch.delenv("AUTH", raising=False)
    assert ServerSettings.from_env().auth.mode == "demo"


def test_the_login_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("AUTH", "off")
    assert ServerSettings.from_env().auth.mode == "off"


def test_admins_and_keys_are_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", " Femke@rag4p.org , ")
    monkeypatch.setenv("API_KEYS", "ak_one=Sanne@rag4p.org, ak_two = daan@rag4p.org, junk")

    auth = ServerSettings.from_env().auth

    assert auth.admin_emails == {ADMIN}
    assert auth.api_keys == {"ak_one": SANNE, "ak_two": DAAN}
