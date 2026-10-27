"""Reading plans back without an agent in the room.

A team is stopped once its plan is done (G3), so by the time anybody opens a
history screen there is no actor left to ask. These routes read the same store
the agents write through.
"""

from __future__ import annotations

from datetime import date, time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from meeting_agents.messages import PlanMeetingRequest
from meeting_agents.store import InMemoryPlanStore
from meeting_server.plans import build_router

DAY = date(2032, 4, 7)


def a_plan(title="Design review"):
    plan = PlanMeetingRequest(
        title=title,
        participant_emails=["sanne@rag4p.org", "daan@rag4p.org"],
        day=DAY,
        duration_minutes=60,
        location_id="yuma",
    ).to_plan()
    plan.proposed_start = time(10, 0)
    plan.proposed_end = time(11, 0)
    plan.approved = True
    return plan


@pytest.fixture
def store():
    return InMemoryPlanStore()


@pytest.fixture
def client(store):
    app = FastAPI()
    app.include_router(build_router(store))
    return TestClient(app)


def test_an_empty_store_lists_nothing(client):
    assert client.get("/plans").json() == []


def test_stored_plans_are_listed(client, store):
    store.save(a_plan("Design review"))
    store.save(a_plan("Retrospective"))

    titles = [plan["title"] for plan in client.get("/plans").json()]

    assert sorted(titles) == ["Design review", "Retrospective"]


def test_a_plan_is_readable_by_id(client, store):
    plan = store.save(a_plan())

    body = client.get(f"/plans/{plan.plan_id}").json()

    assert body["plan_id"] == plan.plan_id
    assert body["participant_emails"] == ["sanne@rag4p.org", "daan@rag4p.org"]
    assert body["proposed_start"] == "10:00:00"


def test_an_unknown_plan_is_a_404(client):
    """Not a 500, and not an empty 200. The browser asks for plans by id from
    a link that may be older than the store it is pointing at."""
    response = client.get("/plans/does-not-exist")

    assert response.status_code == 404


def test_the_routes_are_read_only(client, store):
    """Every change to a plan has compensations attached, so every change goes
    through the agents. A writable plan endpoint would be a way to strand a
    booking that nothing knows how to cancel."""
    plan = store.save(a_plan())

    for call in (
        client.post("/plans", json={}),
        client.delete(f"/plans/{plan.plan_id}"),
        client.put(f"/plans/{plan.plan_id}", json={}),
    ):
        assert call.status_code == 405
