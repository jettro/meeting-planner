"""A stopped team comes back knowing what it was waiting for.

This is Appendix A of `design_cancel.md`, run again. That experiment restored a
finished team and found `@Coordinator` empty, because its state had no
observer and so was never snapshotted. With the observer attached
(`design_durability.md` R1) the same experiment must come out the other way: a
team stopped at the slot gate is resumed, the late answer is delivered to it,
and the meeting is booked.

It runs through `TeamManager` and the real YAML event store, the way the
server does, so it lives with the server's tests: writing a slot to that store
needs the server's YAML representers. The specialists are stubs - nothing here
should need a model.
"""

from __future__ import annotations

import queue
import time as clock
from datetime import date, time

import pytest
from akgentic.core import ActorAddress, ActorSystem, AgentCard, Akgent, BaseConfig, BaseState
from akgentic.team import TeamCard, TeamCardMember, TeamManager, YamlEventStore
from meeting_agents.coordinator import Coordinator, CoordinatorConfig
from meeting_agents.human import ChannelHuman, QueueChannel, get_channel, set_channel
from meeting_agents.messages import (
    MESSAGE_TYPES,
    BookFacilitiesAssignment,
    BookMeetingAssignment,
    CancelAssignment,
    Cancelled,
    CancelPlanRequest,
    FacilitiesBooked,
    FindSlotsAssignment,
    MeetingBooked,
    PlanCancelled,
    PlanCompleted,
    PlanMeetingRequest,
    ProposedSlot,
    SlotApprovalDecision,
    SlotApprovalRequest,
    SlotsFound,
)
from meeting_agents.plan import CompensationStep, PlanStatus
from meeting_server.yaml_types import install_yaml_representers

SLOT = ProposedSlot(start=time(10, 0), end=time(11, 0))


class Released:
    """What the stubs were asked to release, across a stop and a resume."""

    steps: list[CompensationStep] = []


class StubReleaser(Akgent[BaseConfig, BaseState]):
    def receiveMsg_CancelAssignment(  # noqa: N802
        self, message: CancelAssignment, sender: ActorAddress
    ) -> None:
        Released.steps.append(message.step)
        self.send(sender, Cancelled(plan_id=message.plan_id, step=message.step, succeeded=True))


class StubScheduler(StubReleaser):
    def receiveMsg_FindSlotsAssignment(  # noqa: N802
        self, message: FindSlotsAssignment, sender: ActorAddress
    ) -> None:
        self.send(sender, SlotsFound(plan_id=message.plan_id, candidates=[SLOT]))

    def receiveMsg_BookMeetingAssignment(  # noqa: N802
        self, message: BookMeetingAssignment, sender: ActorAddress
    ) -> None:
        self.send(sender, MeetingBooked(plan_id=message.plan_id, meeting_id=42))


class StubFacilityManager(StubReleaser):
    def receiveMsg_BookFacilitiesAssignment(  # noqa: N802
        self, message: BookFacilitiesAssignment, sender: ActorAddress
    ) -> None:
        self.send(sender, FacilitiesBooked(plan_id=message.plan_id, room_code="room-a", booking_id=7))


def member(agent_class, config, children=None) -> TeamCardMember:
    return TeamCardMember(
        card=AgentCard(agent_class=agent_class, description=config.role, config=config),
        headcount=1,
        members=children or [],
    )


def build_card() -> TeamCard:
    return TeamCard(
        name="restore-test",
        entry_point=member(
            ChannelHuman,
            BaseConfig(name="@Human", role="Human"),
            [
                member(
                    Coordinator,
                    CoordinatorConfig(),
                    [
                        member(StubScheduler, BaseConfig(name="@Scheduler", role="Scheduler")),
                        member(
                            StubFacilityManager,
                            BaseConfig(name="@FacilityManager", role="FacilityManager"),
                        ),
                    ],
                )
            ],
        ),
        members=[],
        message_types=MESSAGE_TYPES,
        agent_profiles=[],
    )


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
    system = ActorSystem()
    yield TeamManager(system, YamlEventStore(tmp_path / "events"))
    system.shutdown()


def expect(channel: QueueChannel, kind: type, timeout: float = 10.0):
    message = channel.take(timeout=timeout)
    assert isinstance(message, kind), f"expected {kind.__name__}, got {message!r}"
    return message


def coordinator_snapshot(manager: TeamManager, team_id, timeout: float = 5.0):
    """The coordinator's persisted state, once the gate has reached it.

    Snapshots are written by the orchestrator's persistence subscriber, which
    runs on the orchestrator's thread - so the test waits for the write rather
    than assuming it has happened by the time the human saw the question.
    """
    deadline = clock.monotonic() + timeout
    while clock.monotonic() < deadline:
        for snapshot in manager._event_store.load_agent_states(team_id):
            if snapshot.name == "@Coordinator" and snapshot.state.candidates:
                return snapshot.state
        clock.sleep(0.05)
    raise AssertionError("no coordinator snapshot with candidates was written")


def request() -> PlanMeetingRequest:
    return PlanMeetingRequest(
        title="Design review",
        participant_emails=["sanne@rag4p.org", "daan@rag4p.org"],
        day=date(2034, 6, 20),
        location_id="yuma",
        with_lunch=False,
    )


def test_the_coordinator_is_snapshotted_at_the_gate(manager, channel):
    runtime = manager.create_team(build_card())
    runtime.send_from_to("@Human", "@Coordinator", request())
    question = expect(channel, SlotApprovalRequest)

    state = coordinator_snapshot(manager, runtime.id)

    assert state.plan.plan_id == question.plan_id
    assert state.candidates == [SLOT]
    assert state.waiting_for_the_human()


def test_a_stopped_team_is_resumed_and_finishes_the_meeting(manager, channel):
    runtime = manager.create_team(build_card())
    runtime.send_from_to("@Human", "@Coordinator", request())
    question = expect(channel, SlotApprovalRequest)
    coordinator_snapshot(manager, runtime.id)

    manager.stop_team(runtime.id)
    resumed = manager.resume_team(runtime.id)
    resumed.send_from_to(
        "@Human",
        "@Coordinator",
        SlotApprovalDecision(plan_id=question.plan_id, approved=True, slot=SLOT),
    )

    completed = expect(channel, PlanCompleted)
    assert completed.plan.meeting_id == 42
    assert completed.plan.booking_id == 7
    assert completed.plan.status is PlanStatus.CONFIRMED


def test_nothing_is_asked_twice_on_resume(manager, channel):
    """Restore replays history to the orchestrator, never to the agents."""
    runtime = manager.create_team(build_card())
    runtime.send_from_to("@Human", "@Coordinator", request())
    expect(channel, SlotApprovalRequest)
    coordinator_snapshot(manager, runtime.id)

    manager.stop_team(runtime.id)
    manager.resume_team(runtime.id)

    with pytest.raises(queue.Empty):
        channel.take(timeout=1.0)


def test_a_stopped_team_releases_its_meeting_when_asked(manager, channel):
    """R4: the cancel goes to the team that made the meeting, revived to hear it.

    Its coordinator is the only record of what was booked, so there is nothing
    to load - the restored state already holds the meeting and the room.
    """
    Released.steps = []
    runtime = manager.create_team(build_card())
    runtime.send_from_to("@Human", "@Coordinator", request())
    question = expect(channel, SlotApprovalRequest)
    runtime.send_from_to(
        "@Human",
        "@Coordinator",
        SlotApprovalDecision(plan_id=question.plan_id, approved=True, slot=SLOT),
    )
    expect(channel, PlanCompleted)

    manager.stop_team(runtime.id)
    resumed = manager.resume_team(runtime.id)
    resumed.send_from_to("@Human", "@Coordinator", CancelPlanRequest(plan_id=question.plan_id))

    cancelled = expect(channel, PlanCancelled)
    assert cancelled.failures == []
    assert cancelled.plan.status is PlanStatus.CANCELLED
    assert Released.steps == [CompensationStep.CANCEL_ROOM_BOOKING, CompensationStep.CANCEL_MEETING]
