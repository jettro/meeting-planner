"""Tests for the team card: the hierarchy, and what each member may reach.

`test_catalog.py` checks the specialists one entry at a time. These tests check
the assembled team - who spawns whom, and the structural guarantee that the two
deterministic agents have no way to reach a service at all.
"""

from pathlib import Path

import pytest
from akgentic.team import TeamCard, TeamCardMember
from meeting_agents.bootstrap import load_team_card
from meeting_agents.messages import MESSAGE_TYPES
from meeting_agents.settings import Settings

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "catalog"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings.from_env().model_copy(
        update={"catalog_path": CATALOG_ROOT, "plan_store_path": tmp_path / "plans.json"}
    )


@pytest.fixture
def card(settings: Settings) -> TeamCard:
    return load_team_card(settings)


def walk(member: TeamCardMember):
    yield member
    for child in member.members:
        yield from walk(child)


def by_name(card: TeamCard) -> dict[str, TeamCardMember]:
    return {m.card.config.name: m for m in walk(card.entry_point)}


def test_team_card_loads(card: TeamCard):
    assert card.name == "meeting-planner"
    assert card.entry_point.card.config.name == "@Human"


def test_every_member_is_present(card: TeamCard):
    assert set(by_name(card)) == {
        "@Human",
        "@Coordinator",
        "@PlanRepository",
        "@Scheduler",
        "@FacilityManager",
        "@Catering",
    }


def test_entry_point_is_the_human_and_is_singular(card: TeamCard):
    """The human is the way in, and there is exactly one seat."""
    assert card.entry_point.card.agent_class == "akgentic.agent.HumanProxy"
    assert card.entry_point.headcount == 1


def test_coordinator_is_spawned_by_the_human(card: TeamCard):
    children = [m.card.config.name for m in card.entry_point.members]
    assert children == ["@Coordinator"]


def test_catering_reports_to_the_facility_manager(card: TeamCard):
    """D2: the coordinator never asks for lunch - it asks for facilities."""
    facility = by_name(card)["@FacilityManager"]
    assert [m.card.config.name for m in facility.members] == ["@Catering"]

    coordinator = by_name(card)["@Coordinator"]
    assert "@Catering" not in [m.card.config.name for m in coordinator.members]


def test_coordinator_spawns_the_agents_it_assigns_work_to(card: TeamCard):
    coordinator = by_name(card)["@Coordinator"]
    assert set(m.card.config.name for m in coordinator.members) == {
        "@PlanRepository",
        "@Scheduler",
        "@FacilityManager",
    }


@pytest.mark.parametrize("name", ["@Coordinator", "@PlanRepository"])
def test_deterministic_agents_cannot_reach_any_service(card: TeamCard, name: str):
    """The strongest form of the isolation guarantee.

    These two have no `tools` field at all - not an empty one - because their
    config type is not `AgentConfig`. There is no configuration mistake that
    could give either of them an MCP server.
    """
    config = by_name(card)[name].card.config
    assert not hasattr(config, "tools")
    assert not hasattr(config, "model_cfg")


@pytest.mark.parametrize("name", ["@Scheduler", "@FacilityManager", "@Catering"])
def test_each_specialist_still_has_exactly_one_tool(card: TeamCard, name: str):
    assert len(by_name(card)[name].card.config.tools) == 1


def test_no_placeholder_survives_loading(card: TeamCard):
    """Every `${VAR}` must be real by the time the card is built.

    The framework resolves none of these for us, so this asserts the one job
    `bootstrap` exists to do.
    """
    assert "${" not in card.model_dump_json()


def test_specialist_urls_are_resolved_and_distinct(card: TeamCard):
    urls = [
        by_name(card)[n].card.config.tools[0].connection.url
        for n in ("@Scheduler", "@FacilityManager", "@Catering")
    ]
    assert all(u.startswith("http") for u in urls)
    assert len(set(urls)) == 3


def test_plan_store_path_is_resolved(card: TeamCard, settings: Settings):
    repository = by_name(card)["@PlanRepository"].card.config
    assert repository.store_path == str(settings.plan_store_path)


def test_message_types_match_the_declared_vocabulary(card: TeamCard):
    """The team may only exchange messages it declares."""
    assert set(card.message_types) == set(MESSAGE_TYPES)


def test_missing_env_var_fails_loudly(settings: Settings, monkeypatch):
    """A missing variable must name itself, not surface as a connection error."""
    monkeypatch.delenv("MEETING_MCP_URL", raising=False)
    monkeypatch.setattr(
        Settings, "as_catalog_env", lambda self: {"PLAN_STORE_PATH": "x.json"}
    )
    with pytest.raises(OSError, match="MEETING_MCP_URL"):
        load_team_card(settings)
