"""The booking saga, run end to end in a real actor system.

The specialists are stubs here, and that is the point: @Coordinator and
@PlanRepository contain no judgement, so the whole flow - slots, approval,
meeting, room, lunch - must be reproducible without a model, a network call or
an API key. If this test ever needs an LLM, something that should be
deterministic has stopped being deterministic.

The approval gate is exercised the way a GUI would drive it: a message goes out
to the human, the test does something else, and the answer arrives later as a
separate message. Nothing blocks.
"""

from __future__ import annotations

import queue
from datetime import date, time

import pytest
from akgentic.core import (
    ActorAddress,
    ActorSystem,
    AgentCard,
    Akgent,
    BaseConfig,
    BaseState,
    UserProxy,
)
from akgentic.team import TeamCard, TeamCardMember, TeamFactory
from meeting_agents.coordinator import Coordinator, CoordinatorConfig
from meeting_agents.messages import (
    MESSAGE_TYPES,
    BookFacilitiesAssignment,
    BookMeetingAssignment,
    FacilitiesBooked,
    FindSlotsAssignment,
    MeetingBooked,
    PlanCompleted,
    PlanFailed,
    PlanMeetingRequest,
    ProposedSlot,
    SlotApprovalDecision,
    SlotApprovalRequest,
    SlotsFound,
)
from meeting_agents.plan import PlanStatus
from meeting_agents.plan_repository import PlanRepository, PlanRepositoryConfig

DAY = date(2031, 9, 15)
SLOT = ProposedSlot(start=time(10, 0), end=time(11, 0))
OTHER_SLOT = ProposedSlot(start=time(14, 0), end=time(15, 0))
MEETING_ID = 42
BOOKING_ID = 7
ROOM_CODE = "AMS-1.14"
ORDER_ID = "order-abc"


class Inbox:
    """What the human saw. A class attribute because actors are built by the
    framework - config carries plain data only, never a live queue."""

    messages: queue.Queue = queue.Queue()

    @classmethod
    def reset(cls) -> None:
        cls.messages = queue.Queue()

    @classmethod
    def expect(cls, kind: type, timeout: float = 5.0):
        message = cls.messages.get(timeout=timeout)
        assert isinstance(message, kind), f"expected {kind.__name__}, got {message!r}"
        return message


class RecordingHuman(UserProxy):
    """Stands in for the CLI or the GUI: records, never blocks."""

    def receiveMsg_SlotApprovalRequest(  # noqa: N802
        self, message: SlotApprovalRequest, sender: ActorAddress
    ) -> None:
        Inbox.messages.put(message)

    def receiveMsg_PlanCompleted(  # noqa: N802
        self, message: PlanCompleted, sender: ActorAddress
    ) -> None:
        Inbox.messages.put(message)

    def receiveMsg_PlanFailed(  # noqa: N802
        self, message: PlanFailed, sender: ActorAddress
    ) -> None:
        Inbox.messages.put(message)


class StubScheduler(Akgent[BaseConfig, BaseState]):
    """@Scheduler without the model: canned answers, real messages."""

    def receiveMsg_FindSlotsAssignment(  # noqa: N802
        self, message: FindSlotsAssignment, sender: ActorAddress
    ) -> None:
        self.send(sender, SlotsFound(plan_id=message.plan_id, candidates=[SLOT, OTHER_SLOT]))

    def receiveMsg_BookMeetingAssignment(  # noqa: N802
        self, message: BookMeetingAssignment, sender: ActorAddress
    ) -> None:
        self.send(sender, MeetingBooked(plan_id=message.plan_id, meeting_id=MEETING_ID))


class StubFacilityManager(Akgent[BaseConfig, BaseState]):
    """@FacilityManager without the model. Lunch is its business, so it
    answers for the order too - the coordinator never asks for one."""

    def receiveMsg_BookFacilitiesAssignment(  # noqa: N802
        self, message: BookFacilitiesAssignment, sender: ActorAddress
    ) -> None:
        self.send(
            sender,
            FacilitiesBooked(
                plan_id=message.plan_id,
                room_code=ROOM_CODE,
                booking_id=BOOKING_ID,
                order_id=ORDER_ID if message.with_lunch else None,
            ),
        )


class SilentScheduler(Akgent[BaseConfig, BaseState]):
    """Never answers - used to prove nothing is booked before approval."""

    def receiveMsg_FindSlotsAssignment(  # noqa: N802
        self, message: FindSlotsAssignment, sender: ActorAddress
    ) -> None:
        self.send(sender, SlotsFound(plan_id=message.plan_id, candidates=[SLOT]))


def member(agent_class, config, children=None) -> TeamCardMember:
    return TeamCardMember(
        card=AgentCard(agent_class=agent_class, description=config.role, config=config),
        headcount=1,
        members=children or [],
    )


def build_card(store_path, scheduler_class=StubScheduler) -> TeamCard:
    return TeamCard(
        name="saga-test",
        entry_point=member(
            RecordingHuman,
            BaseConfig(name="@Human", role="Human"),
            [
                member(
                    Coordinator,
                    CoordinatorConfig(),
                    [
                        member(
                            PlanRepository,
                            PlanRepositoryConfig(
                                store_class="meeting_agents.store.JsonPlanStore",
                                store_path=str(store_path),
                            ),
                        ),
                        member(
                            scheduler_class, BaseConfig(name="@Scheduler", role="Scheduler")
                        ),
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
def team(tmp_path):
    Inbox.reset()
    system = ActorSystem()
    runtime = TeamFactory.build(build_card(tmp_path / "plans.json"), system, user_id="test")
    yield runtime
    system.shutdown()


def request_meeting(runtime, with_lunch: bool = True) -> None:
    runtime.send_from_to(
        "@Human",
        "@Coordinator",
        PlanMeetingRequest(
            title="Jettro and Daniel",
            participant_emails=["jettro@example.com", "daniel@example.com"],
            day=DAY,
            duration_minutes=60,
            location_id="AMS",
            with_lunch=with_lunch,
        ),
    )


def test_the_human_is_asked_to_approve_a_slot(team):
    request_meeting(team)
    request = Inbox.expect(SlotApprovalRequest)
    assert request.candidates == [SLOT, OTHER_SLOT]
    assert request.title == "Jettro and Daniel"


def test_approval_request_carries_the_plan_id(team):
    """A GUI correlates the answer on this, never on actor plumbing."""
    request_meeting(team)
    request = Inbox.expect(SlotApprovalRequest)
    assert request.plan_id
    assert "10:00-11:00" in request.question()


def test_happy_path_books_meeting_room_and_lunch(team):
    request_meeting(team)
    request = Inbox.expect(SlotApprovalRequest)

    team.send_from_to(
        "@Human",
        "@Coordinator",
        SlotApprovalDecision(plan_id=request.plan_id, approved=True, slot=SLOT),
    )

    completed = Inbox.expect(PlanCompleted)
    plan = completed.plan
    assert plan.meeting_id == MEETING_ID
    assert plan.room_code == ROOM_CODE
    assert plan.booking_id == BOOKING_ID
    assert plan.order_id == ORDER_ID
    assert plan.status is PlanStatus.CONFIRMED


def test_the_approved_slot_is_the_one_that_gets_booked(team):
    """The human picked the second window, so that is what must be used."""
    request_meeting(team)
    request = Inbox.expect(SlotApprovalRequest)
    team.send_from_to(
        "@Human",
        "@Coordinator",
        SlotApprovalDecision(plan_id=request.plan_id, approved=True, slot=OTHER_SLOT),
    )
    plan = Inbox.expect(PlanCompleted).plan
    assert (plan.proposed_start, plan.proposed_end) == (OTHER_SLOT.start, OTHER_SLOT.end)


def test_without_lunch_the_plan_still_completes(team):
    request_meeting(team, with_lunch=False)
    request = Inbox.expect(SlotApprovalRequest)
    team.send_from_to(
        "@Human",
        "@Coordinator",
        SlotApprovalDecision(plan_id=request.plan_id, approved=True, slot=SLOT),
    )
    plan = Inbox.expect(PlanCompleted).plan
    assert plan.order_id is None
    assert plan.status is PlanStatus.CONFIRMED


def test_rejection_books_nothing_and_needs_no_compensation(team):
    """D4: the gate sits before the first write, so 'no' is free."""
    request_meeting(team)
    request = Inbox.expect(SlotApprovalRequest)
    team.send_from_to(
        "@Human",
        "@Coordinator",
        SlotApprovalDecision(plan_id=request.plan_id, approved=False),
    )

    failed = Inbox.expect(PlanFailed)
    assert failed.plan.meeting_id is None
    assert failed.plan.booking_id is None
    assert failed.plan.order_id is None
    assert failed.outstanding == []


def test_the_plan_is_persisted_by_the_repository(team, tmp_path):
    """The store is written by @PlanRepository, so a completed plan is durable."""
    request_meeting(team)
    request = Inbox.expect(SlotApprovalRequest)
    team.send_from_to(
        "@Human",
        "@Coordinator",
        SlotApprovalDecision(plan_id=request.plan_id, approved=True, slot=SLOT),
    )
    completed = Inbox.expect(PlanCompleted)

    from meeting_agents.store import JsonPlanStore

    stored = JsonPlanStore(tmp_path / "plans.json").get(completed.plan.plan_id)
    assert stored.meeting_id == MEETING_ID
    assert stored.status is PlanStatus.CONFIRMED


def test_an_unknown_plan_id_is_ignored(team):
    """A stale answer from a reloaded page must not start anything."""
    request_meeting(team)
    Inbox.expect(SlotApprovalRequest)
    team.send_from_to(
        "@Human",
        "@Coordinator",
        SlotApprovalDecision(plan_id="no-such-plan", approved=True, slot=SLOT),
    )
    with pytest.raises(queue.Empty):
        Inbox.messages.get(timeout=1.0)


def test_a_failure_after_booking_reports_what_is_still_booked(team):
    """`outstanding` is what the plan left behind, not what was undone.

    A live run booked a meeting, failed on the room, and reported
    `cancel_meeting` - and the meeting was still in the service afterwards,
    because running the undo steps is iteration 2. The name has to say that.
    """
    Inbox.reset()
    plan = PlanMeetingRequest(
        title="Leftovers",
        participant_emails=["a@example.com"],
        day=DAY,
        duration_minutes=60,
        location_id="AMS",
        with_lunch=False,
    ).to_plan()
    booked = plan.model_copy(
        update={
            "proposed_start": SLOT.start,
            "proposed_end": SLOT.end,
            "approved": True,
            "meeting_id": MEETING_ID,
        }
    )

    steps = booked.compensations()

    assert [s.step for s in steps] == ["cancel_meeting"]
    assert steps[0].reference == str(MEETING_ID)
    assert booked.meeting_id == MEETING_ID, "nothing was undone by asking what to undo"
