"""A conversation stopped at the slot gate comes back, and finishes.

The chat team stacks two durable agents: @Intake, a `BaseAgent` whose state and
conversation the framework snapshots, and the coordinator, durable since
design_durability.md R1. This runs the whole relay through `TeamManager` and the
real YAML event store, stops the team at the gate, resumes it, and answers the
relayed question the way the server's /human-input route does - then cancels,
which only works if @Intake still knows which meeting it requested.
"""

from __future__ import annotations

import time as clock
from datetime import date, time

import pytest
from akgentic.core import ActorAddress, ActorSystem, AgentCard, Akgent, BaseConfig, BaseState
from akgentic.team import TeamCard, TeamCardMember, TeamManager, YamlEventStore
from meeting_agents.coordinator import Coordinator, CoordinatorConfig
from meeting_agents.human import ChannelHuman, QueueChannel, get_channel, set_channel
from meeting_agents.intake import IntakeAgent, IntakeConfig, IntakeTools
from meeting_agents.messages import (
    MESSAGE_TYPES,
    BookFacilitiesAssignment,
    BookMeetingAssignment,
    CancelAssignment,
    Cancelled,
    FacilitiesBooked,
    FindLocationAssignment,
    FindPeopleAssignment,
    FindSlotsAssignment,
    LocationFound,
    MeetingBooked,
    NameMatch,
    PeopleFound,
    Person,
    PlanCancelled,
    PlanCompleted,
    PlanMeetingRequest,
    ProposedSlot,
    SlotApprovalRequest,
    SlotsFound,
)
from meeting_server.yaml_types import install_yaml_representers

SLOT = ProposedSlot(start=time(9, 0), end=time(10, 0))
PEOPLE = {"Sanne": Person(name="Sanne Visser", email="sanne@rag4p.org")}


class Model:
    updates: list[str] = []


class ScriptedIntake(IntakeAgent):
    """Only the model call replaced; it is told everything and says nothing."""

    def act(self, message, output_type):
        Model.updates.append(message.rendering())
        return output_type()


class StubReleaser(Akgent[BaseConfig, BaseState]):
    def receiveMsg_CancelAssignment(  # noqa: N802
        self, message: CancelAssignment, sender: ActorAddress
    ) -> None:
        self.send(sender, Cancelled(plan_id=message.plan_id, step=message.step, succeeded=True))


class StubScheduler(StubReleaser):
    def receiveMsg_FindPeopleAssignment(  # noqa: N802
        self, message: FindPeopleAssignment, sender: ActorAddress
    ) -> None:
        matches = [NameMatch(asked=n, candidates=[PEOPLE[n]] if n in PEOPLE else []) for n in message.names]
        self.send(sender, PeopleFound(matches=matches))

    def receiveMsg_FindSlotsAssignment(  # noqa: N802
        self, message: FindSlotsAssignment, sender: ActorAddress
    ) -> None:
        self.send(sender, SlotsFound(plan_id=message.plan_id, candidates=[SLOT]))

    def receiveMsg_BookMeetingAssignment(  # noqa: N802
        self, message: BookMeetingAssignment, sender: ActorAddress
    ) -> None:
        self.send(sender, MeetingBooked(plan_id=message.plan_id, meeting_id=42))


class StubFacilityManager(StubReleaser):
    def receiveMsg_FindLocationAssignment(  # noqa: N802
        self, message: FindLocationAssignment, sender: ActorAddress
    ) -> None:
        self.send(sender, LocationFound(plan_id=message.plan_id, location_id="library", name="Library"))

    def receiveMsg_BookFacilitiesAssignment(  # noqa: N802
        self, message: BookFacilitiesAssignment, sender: ActorAddress
    ) -> None:
        self.send(sender, FacilitiesBooked(plan_id=message.plan_id, room_code="study", booking_id=7))


def member(agent_class, config, children=None) -> TeamCardMember:
    return TeamCardMember(
        card=AgentCard(agent_class=agent_class, description=config.role, config=config),
        headcount=1,
        members=children or [],
    )


def build_card() -> TeamCard:
    return TeamCard(
        name="chat-restore-test",
        entry_point=member(
            ChannelHuman,
            BaseConfig(name="@Human", role="Human"),
            [
                member(
                    ScriptedIntake,
                    IntakeConfig(name="@Intake", role="Intake", tools=[IntakeTools()]),
                    [
                        member(
                            Coordinator,
                            CoordinatorConfig(human_name="@Intake"),
                            [
                                member(StubScheduler, BaseConfig(name="@Scheduler", role="Scheduler")),
                                member(
                                    StubFacilityManager,
                                    BaseConfig(name="@FacilityManager", role="FacilityManager"),
                                ),
                            ],
                        )
                    ],
                )
            ],
        ),
        members=[],
        message_types=MESSAGE_TYPES,
        agent_profiles=[],
    )


@pytest.fixture(autouse=True)
def _no_real_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")


@pytest.fixture
def channel():
    previous = get_channel()
    channel = QueueChannel()
    set_channel(channel)
    yield channel
    set_channel(previous)


@pytest.fixture
def manager(tmp_path):
    install_yaml_representers()
    Model.updates = []
    system = ActorSystem()
    yield TeamManager(system, YamlEventStore(tmp_path / "events"))
    system.shutdown()


def intake(runtime) -> IntakeAgent:
    return runtime.actor_system.proxy_ask(runtime.addrs["@Intake"], IntakeAgent)


def expect(channel: QueueChannel, kind: type, timeout: float = 10.0):
    message = channel.take(timeout=timeout)
    assert isinstance(message, kind), f"expected {kind.__name__}, got {message!r}"
    return message


def wait_for(condition, timeout: float = 5.0) -> None:
    deadline = clock.monotonic() + timeout
    while clock.monotonic() < deadline:
        if condition():
            return
        clock.sleep(0.05)
    raise AssertionError("never happened")


def snapshot_of(manager: TeamManager, team_id, name: str):
    for snapshot in manager._event_store.load_agent_states(team_id):
        if snapshot.name == name:
            return snapshot.state
    return None


def as_the_server_finds_it(manager: TeamManager, team_id, question):
    """The question as /human-input sees it: read back from the event store.

    The server never holds the live message. It finds the `SentMessage` by the
    question's inner id, and its addresses are stored snapshots that
    `process_human_input` rehydrates by name - which is what lets an answer
    reach a team that has been stopped and restored since it asked.
    """
    for persisted in manager._event_store.load_events(team_id):
        event = persisted.event
        if getattr(event, "message", None) is not None and event.message.id == question.id:
            return event.message
    raise AssertionError("the relayed question was never persisted")


def parked_at_the_gate(manager: TeamManager, channel: QueueChannel):
    """A conversation that has looked Sanne up, asked for a quiet place, and is waiting."""
    runtime = manager.create_team(build_card())
    intake(runtime).look_up(["Sanne"])
    wait_for(lambda: any("Sanne Visser" in update for update in Model.updates))
    answer = intake(runtime).request_meeting(
        PlanMeetingRequest(
            title="Focus session",
            participant_emails=["sanne@rag4p.org"],
            day=date(2034, 7, 12),
            location_wish="somewhere quiet",
            with_lunch=False,
        )
    )
    assert answer.startswith("Requested")
    question = expect(channel, SlotApprovalRequest)

    # Both durable agents have written what they are waiting for before the stop.
    wait_for(
        lambda: (snapshot_of(manager, runtime.id, "@Coordinator") or BaseState()).__dict__.get("candidates")
    )
    wait_for(lambda: getattr(snapshot_of(manager, runtime.id, "@Intake"), "plan_id", ""))
    return runtime, question


def test_intake_is_snapshotted_as_itself(manager, channel):
    runtime, question = parked_at_the_gate(manager, channel)

    state = snapshot_of(manager, runtime.id, "@Intake")

    assert type(state).__name__ == "IntakeState"
    assert state.requested is True
    assert state.plan_id == question.plan_id
    assert state.settled_emails == ["sanne@rag4p.org"]
    assert state.backstory, "the system prompt travelled with the state"


def test_a_stopped_conversation_is_resumed_and_the_relayed_gate_answered(manager, channel):
    runtime, question = parked_at_the_gate(manager, channel)

    manager.stop_team(runtime.id)
    resumed = manager.resume_team(runtime.id)
    # Exactly what /human-input does: find the question in the store, then route
    # the answer by its recipient - @Human, because the relay sent a fresh copy.
    resumed.process_human_input("1", as_the_server_finds_it(manager, runtime.id, question))

    completed = expect(channel, PlanCompleted)
    assert completed.plan.location_name == "Library"
    assert completed.plan.booking_id == 7


def test_a_resumed_conversation_still_knows_which_meeting_to_cancel(manager, channel):
    runtime, question = parked_at_the_gate(manager, channel)
    manager.stop_team(runtime.id)
    resumed = manager.resume_team(runtime.id)
    resumed.process_human_input("1", as_the_server_finds_it(manager, runtime.id, question))
    expect(channel, PlanCompleted)

    manager.stop_team(runtime.id)
    again = manager.resume_team(runtime.id)
    assert intake(again).cancel().startswith("Asked the team to cancel")

    assert expect(channel, PlanCancelled).plan.plan_id == question.plan_id
