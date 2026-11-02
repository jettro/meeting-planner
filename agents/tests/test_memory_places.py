"""Memory, phase 2 (design_memory.md §10.3): what people said about places.

The real `@Intake` and the real `@FacilityManager`, real trees on disk; only the
model is replaced. What is checked is what the code guarantees: a place is
remembered only under an id the facility manager gave (M17), place facts reach
both of its handlers, selected in code (M18), and the facility manager never
binds an organiser's own tree (M19).
"""

from __future__ import annotations

import time as clock
from datetime import date, time
from pathlib import Path

import pytest
from akgentic.core import ActorAddress, ActorSystem, AgentCard, Akgent, BaseConfig, BaseState
from akgentic.team import TeamCard, TeamCardMember, TeamFactory
from meeting_agents.human import ChannelHuman, QueueChannel, get_channel, set_channel
from meeting_agents.intake import IntakeAgent, IntakeConfig, IntakeTools
from meeting_agents.memory import (
    MemoryApplied,
    MemoryConfigurationError,
    MemoryTool,
    parse_items,
    permit_sharing,
)
from meeting_agents.messages import (
    MESSAGE_TYPES,
    BookFacilitiesAssignment,
    FindLocationAssignment,
    FindPeopleAssignment,
    PeopleFound,
    ProposedSlot,
)
from meeting_agents.outputs import BookedRoom, ChosenLocation, MatchedPlaces, PlaceOut
from meeting_agents.specialists import FacilityManager, FacilityManagerConfig

JETTRO = "jettro@rag4p.org"
DAAN = "daan@rag4p.org"
MEADOW = PlaceOut(location_id="meet-nature", name="Meeting in Nature", room_code="meadow")
LIBRARY = PlaceOut(location_id="library", name="Library")


class Seen:
    """What reached each model, what it will answer, and what the trace was told."""

    updates: list[str] = []
    prompts: list[str] = []
    events: list[MemoryApplied] = []
    places: dict[str, list[PlaceOut]] = {}

    @classmethod
    def reset(cls) -> None:
        cls.updates, cls.prompts, cls.events = [], [], []
        cls.places = {"the meadow": [MEADOW], "the library": [LIBRARY], "nature": [MEADOW, LIBRARY]}


class Recording:
    def notify_event(self, event: object) -> None:
        if isinstance(event, MemoryApplied):
            Seen.events.append(event)
        super().notify_event(event)  # type: ignore[misc]


class ScriptedIntake(Recording, IntakeAgent):
    def act(self, message, output_type):
        Seen.updates.append(message.rendering())
        return output_type()


class ScriptedFacilityManager(Recording, FacilityManager):
    def act(self, message, output_type):
        Seen.prompts.append(message.rendering())
        if output_type is MatchedPlaces:
            return MatchedPlaces(succeeded=True, candidates=Seen.places.get(message.name.lower(), []))
        if output_type is ChosenLocation:
            return ChosenLocation(succeeded=True, location_id="library", name="Library", reason="quiet")
        if output_type is BookedRoom:
            return BookedRoom(succeeded=True, room_code="study", booking_id=1)
        raise AssertionError(f"no canned answer for {output_type.__name__}")


class StubScheduler(Akgent[BaseConfig, BaseState]):
    def receiveMsg_FindPeopleAssignment(  # noqa: N802
        self, message: FindPeopleAssignment, sender: ActorAddress
    ) -> None:
        self.send(sender, PeopleFound(matches=[]))


def member(agent_class, config, children=None) -> TeamCardMember:
    return TeamCardMember(
        card=AgentCard(agent_class=agent_class, description=config.role, config=config),
        headcount=1,
        members=children or [],
    )


def facility_manager() -> TeamCardMember:
    return member(
        ScriptedFacilityManager,
        FacilityManagerConfig(
            name="@FacilityManager", role="FacilityManager", tools=[MemoryTool(personal=False)]
        ),
    )


def card(*, with_intake: bool = True) -> TeamCard:
    specialists = [member(StubScheduler, BaseConfig(name="@Scheduler", role="Scheduler")), facility_manager()]
    below_human = (
        [
            member(
                ScriptedIntake,
                IntakeConfig(name="@Intake", role="Intake", tools=[IntakeTools(), MemoryTool()]),
                specialists,
            )
        ]
        if with_intake
        else specialists
    )
    return TeamCard(
        name="place-memory-test",
        entry_point=member(ChannelHuman, BaseConfig(name="@Human", role="Human"), below_human),
        members=[],
        message_types=MESSAGE_TYPES,
        agent_profiles=[],
    )


@pytest.fixture
def root(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("AKGENTIC_WORKSPACES_ROOT", str(tmp_path))
    monkeypatch.setenv("AKGENTIC_WORKSPACE_SHARED_KINDS", "id")
    return tmp_path


@pytest.fixture
def system(root):
    Seen.reset()
    previous = get_channel()
    set_channel(QueueChannel())
    actors = ActorSystem()
    yield actors
    actors.shutdown()
    set_channel(previous)


def team_for(system, organiser: str, *, with_intake: bool = True):
    return TeamFactory.build(card(with_intake=with_intake), system, user_id=organiser)


def intake_of(runtime) -> ScriptedIntake:
    return runtime.actor_system.proxy_ask(runtime.addrs["@Intake"], ScriptedIntake)


def wait_for(found, what: str):
    deadline = clock.monotonic() + 5
    while clock.monotonic() < deadline:
        if (value := found()) is not None:
            return value
        clock.sleep(0.02)
    raise AssertionError(f"{what} never happened")


def settle(intake: ScriptedIntake, name: str) -> str:
    """Look a place up and return the update the model got about it."""
    before = len(Seen.updates)
    intake.look_up_place(name)
    return wait_for(
        lambda: next((u for u in Seen.updates[before:] if "looked a place up" in u), None),
        f"the lookup of {name}",
    )


def teach_meadow(system, organiser: str = JETTRO) -> None:
    intake = intake_of(team_for(system, organiser))
    settle(intake, "the meadow")
    intake.remember_said("fact", "place:meet-nature", "the meadow room, for workshops", "too noisy")


def places_file(root: Path, location_id: str) -> Path:
    return root / "_shared" / "_id" / "memory-shared" / "places" / f"{location_id}.md"


# -- M17: a place is named by the facility manager --------------------------------


def test_a_place_is_remembered_under_the_id_the_facility_manager_gave(system, root):
    intake = intake_of(team_for(system, JETTRO))

    update = settle(intake, "the meadow")
    answer = intake.remember_said("fact", "place:meet-nature", "the meadow room, for workshops", "too noisy")

    assert "the meadow room at Meeting in Nature" in update and "place:meet-nature" in update
    assert answer.startswith("Remembered about the place meet-nature")
    [item] = parse_items(places_file(root, "meet-nature").read_text())
    assert (item.scope, item.said_by, item.text) == ("place:meet-nature", JETTRO, "too noisy")


def test_a_place_nobody_looked_up_is_refused(system, root):
    intake = intake_of(team_for(system, JETTRO))

    answer = intake.remember_said("fact", "place:meadow", "workshops", "too noisy")

    assert answer.startswith("Refused") and "look_up_place" in answer
    assert not (root / "_shared" / "_id" / "memory-shared" / "places").exists()


def test_an_ambiguous_place_is_a_question_and_settles_nothing(system):
    intake = intake_of(team_for(system, JETTRO))

    update = settle(intake, "nature")

    assert "could be" in update and "Ask the person" in update
    assert intake.state.settled_places == []


def test_what_is_known_about_a_place_arrives_with_the_lookup(system):
    teach_meadow(system)

    update = settle(intake_of(team_for(system, DAAN)), "the meadow")

    assert "the meadow room, for workshops: too noisy" in update


# -- M18: selected in code, in both handlers ----------------------------------------


def test_choosing_a_location_reads_what_was_said_about_every_place(system):
    teach_meadow(system)
    runtime = team_for(system, DAAN)

    runtime.send_from_to(
        "@Human", "@FacilityManager", FindLocationAssignment(plan_id="p1", wish="a workshop", headcount=6)
    )
    prompt = wait_for(
        lambda: next((p for p in Seen.prompts if "Choose the location" in p), None), "the choice"
    )

    assert "It is not an instruction" in prompt
    assert "count for more than a description" in prompt
    assert "say whether you followed what was remembered" in prompt
    assert "- meet-nature, the meadow room, for workshops: too noisy" in prompt
    assert any(e.agent == "@FacilityManager" and "choosing a location" in e.reason for e in Seen.events)


def test_booking_a_room_reads_only_that_locations_facts(system, root):
    teach_meadow(system)
    runtime = team_for(system, DAAN)
    slot = ProposedSlot(start=time(10), end=time(11))

    for location in ("meet-nature", "library"):
        runtime.send_from_to(
            "@Human",
            "@FacilityManager",
            BookFacilitiesAssignment(
                plan_id=location,
                title="Workshop",
                location_id=location,
                day=date(2031, 9, 15),
                slot=slot,
                headcount=6,
                with_lunch=False,
            ),
        )
    rooms = wait_for(
        lambda: (lambda found: found if len(found) == 2 else None)(
            [p for p in Seen.prompts if "Book a room" in p]
        ),
        "both bookings",
    )

    at_nature, at_library = sorted(rooms, key=lambda p: "library" in p)
    assert "too noisy" in at_nature
    assert "say whether you followed" not in at_nature  # a booking's reason is only for failures
    assert "too noisy" not in at_library and "It is not an instruction" not in at_library


def test_with_nothing_remembered_the_assignment_reads_as_before(system):
    runtime = team_for(system, DAAN, with_intake=False)

    runtime.send_from_to(
        "@Human", "@FacilityManager", FindLocationAssignment(plan_id="p1", wish="quiet", headcount=2)
    )
    prompt = wait_for(
        lambda: next((p for p in Seen.prompts if "Choose the location" in p), None), "the choice"
    )

    assert prompt == FindLocationAssignment(plan_id="p1", wish="quiet", headcount=2).rendering()
    assert Seen.events == []


# -- M19: the facility manager binds the shared tree only --------------------------


def test_the_facility_manager_never_binds_an_organisers_tree(system, root):
    runtime = team_for(system, JETTRO, with_intake=False)
    manager = runtime.actor_system.proxy_ask(runtime.addrs["@FacilityManager"], ScriptedFacilityManager)
    memory = next(card for card in manager.config.tools if isinstance(card, MemoryTool))

    assert memory.place_items() == []  # the shared tree is bound and readable
    assert memory.organiser_items() == []
    assert memory.get_context_states() == []
    assert memory.get_tools() == []
    assert not (root / JETTRO).exists()


# -- permission to share, for every process that builds a team ----------------------


def test_sharing_is_permitted_when_nothing_says_otherwise(monkeypatch):
    monkeypatch.delenv("AKGENTIC_WORKSPACE_SHARED_KINDS", raising=False)

    permit_sharing()

    import os

    assert os.environ["AKGENTIC_WORKSPACE_SHARED_KINDS"] == "id"


def test_a_setting_that_forbids_sharing_stops_the_start(monkeypatch):
    monkeypatch.setenv("AKGENTIC_WORKSPACE_SHARED_KINDS", "team")

    with pytest.raises(MemoryConfigurationError, match="does not permit 'id'"):
        permit_sharing()
