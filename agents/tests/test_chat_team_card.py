"""The chat team, as the catalog defines it (design_chat.md §9).

It is the form team with one agent added in front, so most of what matters is
what did *not* change: the specialists are the form team's own entries by
reference, the coordinator differs in one config value, and @Intake can reach
no service at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from akgentic.agent.messages import AgentMessage
from akgentic.team import TeamCard, TeamCardMember
from akgentic.tool.mcp import MCPTool
from akgentic.tool.workspace import WorkspaceTool
from meeting_agents.bootstrap import load_team_card
from meeting_agents.intake import IntakeTools
from meeting_agents.memory import MemoryTool
from meeting_agents.messages import MESSAGE_TYPES
from meeting_agents.settings import Settings

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "catalog"


@pytest.fixture
def settings() -> Settings:
    return Settings.from_env().model_copy(update={"catalog_path": CATALOG_ROOT})


@pytest.fixture
def chat(settings: Settings) -> TeamCard:
    return load_team_card(settings, "meeting-planner-chat")


@pytest.fixture
def form(settings: Settings) -> TeamCard:
    return load_team_card(settings, "meeting-planner")


def walk(member: TeamCardMember):
    yield member
    for child in member.members:
        yield from walk(child)


def by_name(card: TeamCard) -> dict[str, TeamCardMember]:
    return {m.card.config.name: m for m in walk(card.entry_point)}


def children(card: TeamCard, name: str) -> list[str]:
    return [m.card.config.name for m in by_name(card)[name].members]


def test_the_chat_team_loads(chat: TeamCard):
    assert chat.name == "meeting-planner-chat"


def test_intake_sits_between_the_human_and_the_coordinator(chat: TeamCard):
    assert chat.entry_point.card.config.name == "@Human"
    assert children(chat, "@Human") == ["@Intake"]
    assert children(chat, "@Intake") == ["@Coordinator"]


def test_below_the_coordinator_it_is_the_form_team(chat: TeamCard, form: TeamCard):
    assert children(chat, "@Coordinator") == children(form, "@Coordinator")
    assert children(chat, "@FacilityManager") == ["@Catering"]


@pytest.mark.parametrize("name", ["@Human", "@Scheduler", "@FacilityManager", "@Catering"])
def test_the_shared_agents_are_the_form_teams_own(chat: TeamCard, form: TeamCard, name: str):
    """By reference, not by copy - so the two teams cannot drift apart."""
    assert by_name(chat)[name].card == by_name(form)[name].card


def test_the_coordinator_differs_only_in_who_its_human_is(chat: TeamCard, form: TeamCard):
    """I2: configured, not changed."""
    ours = by_name(chat)["@Coordinator"].card
    theirs = by_name(form)["@Coordinator"].card
    assert ours.agent_class == theirs.agent_class
    assert ours.config.human_name == "@Intake"
    assert ours.config.model_copy(update={"human_name": "@Human"}) == theirs.config


def test_intake_reaches_no_service(chat: TeamCard):
    """Its own tools and its memory, and none of it books anything (I3)."""
    tools = by_name(chat)["@Intake"].card.config.tools
    assert [type(tool) for tool in tools] == [IntakeTools, MemoryTool, WorkspaceTool]
    assert not any(isinstance(tool, MCPTool) for tool in tools)


def test_the_declared_memory_tree_gives_the_model_no_file_tools(chat: TeamCard):
    """It is there so the console finds the organiser's tree (design_memory.md S4);
    reading and writing is MemoryTool's, in code."""
    tree = next(t for t in by_name(chat)["@Intake"].card.config.tools if isinstance(t, WorkspaceTool))
    assert tree.workspace_id == "memory"
    assert tree.read_only
    assert tree.get_tools() == []
    assert tree.get_commands() == {}


def test_memory_is_the_organisers_tree_and_one_shared_tree(chat: TeamCard):
    memory = next(t for t in by_name(chat)["@Intake"].card.config.tools if isinstance(t, MemoryTool))
    assert (memory.personal_workspace, memory.shared_workspace) == ("memory", "memory-shared")
    assert memory.get_tools() == []


def test_intake_talks_to_the_human_and_asks_the_coordinator(chat: TeamCard):
    config = by_name(chat)["@Intake"].card.config
    assert (config.human_name, config.coordinator_name, config.scheduler_name) == (
        "@Human",
        "@Coordinator",
        "@Scheduler",
    )


def test_the_intake_prompt_renders(chat: TeamCard):
    """A prompt is a format string; a literal brace would fail inside on_start."""
    prompt = by_name(chat)["@Intake"].card.config.prompt.render()
    assert "You write" in prompt
    assert "only to @Human" in prompt


def test_intake_offers_once_after_the_booking_and_uses_a_remembered_meal(chat: TeamCard):
    """The conversation's one offer (design_memory.md M45-M47): a question, after the booking."""
    prompt = " ".join(by_name(chat)["@Intake"].card.config.prompt.render().split())
    assert "When an update says the meeting is booked - not before" in prompt
    assert "once in this conversation" in prompt
    for offer in (
        "where this kind of meeting goes",
        "lunch for this kind of meeting",
        "lunch for these people",
        "a team",
    ):
        assert f"- {offer}" in prompt
    assert "Offer nothing about the time" in prompt
    assert '"Nothing new to remember from this one."' in prompt
    assert 'Call remember only on a clear yes, with about "organiser"' in prompt
    assert "or for meetings with these people" in prompt
    assert '"with soup, as remembered for workshops"' in prompt


def test_intake_allows_a_slow_model_call(chat: TeamCard):
    assert by_name(chat)["@Intake"].card.config.runtime_cfg.http_client_config.timeout == 240.0


def test_free_text_is_the_default_message_type(chat: TeamCard):
    """What any client - the console included - sends unless it says otherwise."""
    assert chat.message_types[0] is AgentMessage
    assert set(chat.message_types[1:]) == set(MESSAGE_TYPES)


def test_no_placeholder_survives_loading(chat: TeamCard):
    assert "${" not in chat.model_dump_json()
