"""Tests for the team card: the hierarchy, and what each member may reach.

`test_catalog.py` checks the specialists one entry at a time. These tests check
the assembled team - who spawns whom, and the structural guarantee that the two
deterministic agents have no way to reach a service at all.
"""

from pathlib import Path

import pytest
from akgentic.team import TeamCard, TeamCardMember
from meeting_agents.bootstrap import load_team_card
from meeting_agents.memory import MemoryTool
from meeting_agents.messages import MESSAGE_TYPES
from meeting_agents.settings import Settings
from meeting_agents.team_metadata import MeetingTeamMetadata

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "catalog"


@pytest.fixture
def settings() -> Settings:
    return Settings.from_env().model_copy(update={"catalog_path": CATALOG_ROOT})


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
        "@Scheduler",
        "@FacilityManager",
        "@Catering",
    }


def test_entry_point_is_the_human_and_is_singular(card: TeamCard):
    """The human is the way in, and there is exactly one seat.

    The class is asserted because it is the GUI swap point (§4.2 rule 3): a
    websocket proxy is named here instead, and nothing else changes.
    """
    assert card.entry_point.card.agent_class == "meeting_agents.human.ChannelHuman"
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
        "@Scheduler",
        "@FacilityManager",
    }


def test_the_coordinator_cannot_reach_any_service(card: TeamCard):
    """The strongest form of the isolation guarantee.

    The coordinator has no `tools` field at all - not an empty one - because
    its config type is not `AgentConfig`. There is no configuration mistake
    that could give it an MCP server.
    """
    config = by_name(card)["@Coordinator"].card.config
    assert not hasattr(config, "tools")
    assert not hasattr(config, "model_cfg")


@pytest.mark.parametrize("name", ["@Scheduler", "@Catering"])
def test_each_specialist_still_has_exactly_one_tool(card: TeamCard, name: str):
    assert len(by_name(card)[name].card.config.tools) == 1


def test_the_facility_manager_has_its_server_and_the_shared_memory_only(card: TeamCard):
    """M19: place facts, and never an organiser's own tree or block."""
    tools = by_name(card)["@FacilityManager"].card.config.tools
    assert len(tools) == 2
    memory = tools[1]
    assert isinstance(memory, MemoryTool)
    assert memory.personal is False
    assert memory.get_tools() == []


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


def test_message_types_match_the_declared_vocabulary(card: TeamCard):
    """The team may only exchange messages it declares."""
    assert set(card.message_types) == set(MESSAGE_TYPES)


def test_the_card_declares_what_a_run_is_about(card: TeamCard):
    """Without this the catalog loads happily and every run looks identical.

    `metadata_type` is a type reference in YAML, so a typo in the dotted path is
    a load error rather than a silent `None` - but a card that simply forgets
    the field is not an error anywhere, which is what this test is for.
    """
    assert card.metadata_type is MeetingTeamMetadata


def test_the_filterable_fields_are_the_ones_worth_filtering(card: TeamCard):
    """A field is filterable only if it is marked indexed, and the mark is easy
    to drop in a refactor: nothing fails, the field just stops being a filter."""
    assert card.metadata_type is not None
    assert card.metadata_type.indexed_fields() == ["title", "day", "location_id"]


def test_missing_env_var_fails_loudly(settings: Settings, monkeypatch):
    """A missing variable must name itself, not surface as a connection error."""
    monkeypatch.delenv("MEETING_MCP_URL", raising=False)
    monkeypatch.setattr(Settings, "as_catalog_env", lambda self: {})
    with pytest.raises(OSError, match="MEETING_MCP_URL"):
        load_team_card(settings)
