"""Tests for plan storage. Both implementations must satisfy the same contract."""

from datetime import date, time
from pathlib import Path

import pytest
from meeting_agents.plan import MeetingPlan
from meeting_agents.store import (
    InMemoryPlanStore,
    JsonPlanStore,
    PlanNotFoundError,
    PlanStore,
)


def make_plan(**overrides) -> MeetingPlan:
    base = {
        "title": "Jettro & Daniel",
        "participant_emails": ["sanne@rag4p.org", "daan@rag4p.org"],
        "day": date(2030, 6, 4),
        "location_id": "yuma",
    }
    return MeetingPlan(**{**base, **overrides})


@pytest.fixture(params=["memory", "json"])
def store(request, tmp_path: Path) -> PlanStore:
    if request.param == "memory":
        return InMemoryPlanStore()
    return JsonPlanStore(tmp_path / "plans.json")


def test_save_then_get_round_trips(store: PlanStore):
    plan = make_plan(proposed_start=time(11, 0), proposed_end=time(12, 0), meeting_id=12)
    store.save(plan)

    loaded = store.get(plan.plan_id)
    assert loaded.plan_id == plan.plan_id
    assert loaded.participant_emails == plan.participant_emails
    assert loaded.day == plan.day
    assert loaded.proposed_start == time(11, 0)
    assert loaded.meeting_id == 12
    assert loaded.status is plan.status


def test_save_replaces_an_existing_plan(store: PlanStore):
    plan = store.save(make_plan())
    store.save(plan.model_copy(update={"meeting_id": 12}))

    assert store.get(plan.plan_id).meeting_id == 12
    assert len(store.list_plans()) == 1


def test_get_unknown_plan_raises(store: PlanStore):
    with pytest.raises(PlanNotFoundError):
        store.get("does-not-exist")


def test_list_plans_returns_everything(store: PlanStore):
    ids = {store.save(make_plan()).plan_id for _ in range(3)}
    assert {p.plan_id for p in store.list_plans()} == ids


def test_stored_plans_are_isolated_from_later_mutation(store: PlanStore):
    """A caller mutating its copy must not silently change what is stored."""
    plan = store.save(make_plan())
    plan.meeting_id = 99
    assert store.get(plan.plan_id).meeting_id is None


def test_json_store_survives_a_restart(tmp_path: Path):
    path = tmp_path / "nested" / "plans.json"
    plan = JsonPlanStore(path).save(make_plan(meeting_id=12, booking_id=8))

    reopened = JsonPlanStore(path).get(plan.plan_id)
    assert reopened.meeting_id == 12
    assert reopened.booking_id == 8


def test_json_store_leaves_no_temporary_files(tmp_path: Path):
    store = JsonPlanStore(tmp_path / "plans.json")
    store.save(make_plan())
    store.save(make_plan())
    assert [p.name for p in tmp_path.iterdir()] == ["plans.json"]


def test_both_implementations_satisfy_the_protocol(tmp_path: Path):
    assert isinstance(InMemoryPlanStore(), PlanStore)
    assert isinstance(JsonPlanStore(tmp_path / "plans.json"), PlanStore)
