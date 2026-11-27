"""Moving a meeting to another day, run end to end in a real actor system.

The same bargain as `test_cancel.py`: the specialists are stubs, because which
bookings are made and released, and in what order, needs no model. What is
worth proving is design_move.md's promise: the new booking is made *before*
the old one is released (M3), everything asked for carries over by code (M2),
and a move that fails halfway leaves the meeting exactly as it was.

Every booking gets a fresh id, so the tests can tell the old booking from the
new one.
"""

from __future__ import annotations

import itertools
import queue
import time as clock
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
from meeting_agents.coordinator import Coordinator, CoordinatorConfig, CoordinatorState
from meeting_agents.messages import (
    MESSAGE_TYPES,
    AssignmentFailed,
    BookFacilitiesAssignment,
    BookMeetingAssignment,
    CancelAssignment,
    Cancelled,
    CancelPlanRequest,
    FacilitiesBooked,
    FindSlotsAssignment,
    MeetingBooked,
    MoveFailed,
    MovePlanRequest,
    PlanCancelled,
    PlanCompleted,
    PlanMeetingRequest,
    PlanMoved,
    ProposedSlot,
    SlotApprovalDecision,
    SlotApprovalRequest,
    SlotsFound,
)
from meeting_agents.plan import Compensation, CompensationStep

TUESDAY = date(2031, 9, 16)
THURSDAY = date(2031, 9, 18)
FRIDAY = date(2031, 9, 19)
SLOT = ProposedSlot(start=time(10, 0), end=time(11, 0))
LATER = ProposedSlot(start=time(14, 0), end=time(15, 0))


class World:
    """What the human saw, what the specialists were asked, and how they behave."""

    messages: queue.Queue = queue.Queue()
    released: list[Compensation] = []
    facilities_asked: list[BookFacilitiesAssignment] = []
    #: Days with no slot for everybody.
    full_days: set[date] = set()
    #: Days on which the facility manager fails: "room" before booking it,
    #: "lunch" after booking the room.
    failing: dict[date, str] = {}
    #: Bookings to take but not answer, so a cancel can overtake them.
    hold: set[type] = set()
    ids = itertools.count(100)

    @classmethod
    def reset(cls) -> None:
        cls.messages = queue.Queue()
        cls.released = []
        cls.facilities_asked = []
        cls.full_days = set()
        cls.failing = {}
        cls.hold = set()
        cls.ids = itertools.count(100)

    @classmethod
    def expect(cls, kind: type, timeout: float = 5.0):
        message = cls.messages.get(timeout=timeout)
        assert isinstance(message, kind), f"expected {kind.__name__}, got {message!r}"
        return message


class RecordingHuman(UserProxy):
    def _keep(self, message) -> None:
        World.messages.put(message)

    def receiveMsg_SlotApprovalRequest(self, message: SlotApprovalRequest, sender: ActorAddress) -> None:  # noqa: N802
        self._keep(message)

    def receiveMsg_PlanCompleted(self, message: PlanCompleted, sender: ActorAddress) -> None:  # noqa: N802
        self._keep(message)

    def receiveMsg_PlanCancelled(self, message: PlanCancelled, sender: ActorAddress) -> None:  # noqa: N802
        self._keep(message)

    def receiveMsg_PlanMoved(self, message: PlanMoved, sender: ActorAddress) -> None:  # noqa: N802
        self._keep(message)

    def receiveMsg_MoveFailed(self, message: MoveFailed, sender: ActorAddress) -> None:  # noqa: N802
        self._keep(message)


class StubSpecialist(Akgent[BaseConfig, BaseState]):
    def receiveMsg_CancelAssignment(self, message: CancelAssignment, sender: ActorAddress) -> None:  # noqa: N802
        World.released.append(Compensation(step=message.step, reference=message.reference))
        self.send(sender, Cancelled(plan_id=message.plan_id, step=message.step, succeeded=True))


class StubScheduler(StubSpecialist):
    def receiveMsg_FindSlotsAssignment(self, message: FindSlotsAssignment, sender: ActorAddress) -> None:  # noqa: N802
        candidates = [] if message.day in World.full_days else [SLOT, LATER]
        self.send(sender, SlotsFound(plan_id=message.plan_id, candidates=candidates))

    def receiveMsg_BookMeetingAssignment(self, message: BookMeetingAssignment, sender: ActorAddress) -> None:  # noqa: N802
        if BookMeetingAssignment in World.hold:
            return
        self.send(sender, MeetingBooked(plan_id=message.plan_id, meeting_id=next(World.ids)))


class StubFacilityManager(StubSpecialist):
    def receiveMsg_BookFacilitiesAssignment(  # noqa: N802
        self, message: BookFacilitiesAssignment, sender: ActorAddress
    ) -> None:
        World.facilities_asked.append(message)
        failing = World.failing.get(message.day)
        if failing == "room":
            self.send(sender, AssignmentFailed(plan_id=message.plan_id, reason="no room free that day"))
            return
        booking_id = next(World.ids)
        if failing == "lunch":
            self.send(
                sender,
                AssignmentFailed(
                    plan_id=message.plan_id,
                    reason="the menu is closed that day",
                    room_code="study",
                    booking_id=booking_id,
                ),
            )
            return
        if BookFacilitiesAssignment in World.hold:
            return
        self.send(
            sender,
            FacilitiesBooked(
                plan_id=message.plan_id,
                room_code="study",
                booking_id=booking_id,
                order_id=f"order-{next(World.ids)}",
                lunch_summary="2 x soup",
            ),
        )


def member(agent_class, config, children=None) -> TeamCardMember:
    return TeamCardMember(
        card=AgentCard(agent_class=agent_class, description=config.role, config=config),
        headcount=1,
        members=children or [],
    )


def build_card() -> TeamCard:
    return TeamCard(
        name="move-test",
        entry_point=member(
            RecordingHuman,
            BaseConfig(name="@Human", role="Human"),
            [
                member(
                    Coordinator,
                    CoordinatorConfig(),
                    [
                        member(StubScheduler, BaseConfig(name="@Scheduler", role="Scheduler")),
                        member(
                            StubFacilityManager, BaseConfig(name="@FacilityManager", role="FacilityManager")
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
def team():
    World.reset()
    system = ActorSystem()
    runtime = TeamFactory.build(build_card(), system, user_id="test")
    yield runtime
    system.shutdown()


def state(runtime) -> CoordinatorState:
    coordinator = runtime.addrs["@Coordinator"]
    return runtime.orchestrator_proxy.get_states()[str(coordinator.agent_id)]


def wait_until(runtime, condition, timeout: float = 5.0) -> None:
    deadline = clock.monotonic() + timeout
    while clock.monotonic() < deadline:
        if condition(state(runtime)):
            return
        clock.sleep(0.02)
    raise AssertionError("the coordinator never got there")


def send(team, message) -> None:
    team.send_from_to("@Human", "@Coordinator", message)


def book_on_tuesday(team) -> PlanCompleted:
    """The sample's meeting: a place chosen, lunch wished for in words."""
    send(
        team,
        PlanMeetingRequest(
            title="Design review",
            participant_emails=["sanne@example.com", "daan@example.com"],
            day=TUESDAY,
            location_id="library",
            lunch_wish="vegetarian, no bread",
        ),
    )
    question = World.expect(SlotApprovalRequest)
    send(team, SlotApprovalDecision(plan_id=question.plan_id, approved=True, slot=SLOT))
    return World.expect(PlanCompleted)


def ask_to_move(team, plan_id: str, day: date = THURSDAY) -> SlotApprovalRequest:
    send(team, MovePlanRequest(plan_id=plan_id, day=day))
    return World.expect(SlotApprovalRequest)


def test_a_move_books_the_new_day_then_releases_the_old_booking(team):
    old = book_on_tuesday(team).plan

    question = ask_to_move(team, old.plan_id)
    assert question.day == THURSDAY
    assert World.released == [], "nothing is released before the new day is booked"

    send(team, SlotApprovalDecision(plan_id=old.plan_id, approved=True, slot=LATER))
    moved = World.expect(PlanMoved)

    new = moved.plan
    assert (new.plan_id, new.day, new.proposed_start) == (old.plan_id, THURSDAY, LATER.start)
    assert {new.meeting_id, new.booking_id, new.order_id}.isdisjoint(
        {old.meeting_id, old.booking_id, old.order_id}
    )
    assert World.released == old.compensations(), "the old booking, in reverse booking order"
    assert moved.previous == old.booking()
    assert new.moved_from == [old.booking()]
    assert not new.cancelled and new.is_complete


def test_what_was_asked_for_carries_over(team):
    """M2: copied by code - the place, the lunch wish, who and how long."""
    old = book_on_tuesday(team).plan
    ask_to_move(team, old.plan_id)
    send(team, SlotApprovalDecision(plan_id=old.plan_id, approved=True, slot=SLOT))
    new = World.expect(PlanMoved).plan

    again = World.facilities_asked[-1]
    assert (again.day, again.location_id, again.lunch_wish, again.with_lunch) == (
        THURSDAY,
        "library",
        "vegetarian, no bread",
        True,
    )
    assert new.participant_emails == old.participant_emails
    assert new.duration_minutes == old.duration_minutes
    assert new.title == old.title


def test_the_move_asks_only_the_time(team):
    """M4: no lunch question - the wish is kept - and the record is written."""
    old = book_on_tuesday(team).plan
    ask_to_move(team, old.plan_id)
    send(team, SlotApprovalDecision(plan_id=old.plan_id, approved=True, slot=SLOT))
    World.expect(PlanMoved)
    wait_until(team, lambda s: s.moving is None and not s.cancelling and s.plan.day == THURSDAY)


def test_declining_the_new_time_keeps_the_meeting(team):
    old = book_on_tuesday(team).plan
    ask_to_move(team, old.plan_id)

    send(team, SlotApprovalDecision(plan_id=old.plan_id, approved=False))
    failed = World.expect(MoveFailed)

    assert failed.plan == old
    assert not failed.released
    assert World.released == []
    wait_until(team, lambda s: s.moving is None and s.plan == old and not s.candidates)


def test_no_time_on_the_new_day_keeps_the_meeting(team):
    old = book_on_tuesday(team).plan
    World.full_days.add(THURSDAY)

    send(team, MovePlanRequest(plan_id=old.plan_id, day=THURSDAY))
    failed = World.expect(MoveFailed)

    assert "2031-09-18" in failed.reason
    assert failed.plan == old and World.released == []


def test_no_room_on_the_new_day_releases_the_new_meeting_and_keeps_the_old(team):
    """M3: a failure halfway undoes the new day only."""
    old = book_on_tuesday(team).plan
    World.failing[THURSDAY] = "room"
    ask_to_move(team, old.plan_id)
    send(team, SlotApprovalDecision(plan_id=old.plan_id, approved=True, slot=SLOT))

    failed = World.expect(MoveFailed)

    assert failed.released and failed.reason == "no room free that day"
    assert [c.step for c in World.released] == [CompensationStep.CANCEL_MEETING]
    assert World.released[0].reference != str(old.meeting_id)
    assert failed.plan == old


def test_a_room_booked_before_a_failed_lunch_is_released_too(team):
    old = book_on_tuesday(team).plan
    World.failing[THURSDAY] = "lunch"
    ask_to_move(team, old.plan_id)
    send(team, SlotApprovalDecision(plan_id=old.plan_id, approved=True, slot=SLOT))

    failed = World.expect(MoveFailed)

    assert [c.step for c in World.released] == [
        CompensationStep.CANCEL_ROOM_BOOKING,
        CompensationStep.CANCEL_MEETING,
    ]
    assert str(old.booking_id) not in [c.reference for c in World.released]
    assert failed.plan == old


@pytest.mark.parametrize(
    ("setup", "reason"),
    [
        ("cancelled", "the meeting is cancelled"),
        ("moving", "the meeting is already being moved"),
    ],
)
def test_a_move_is_refused_when_it_cannot_happen(team, setup, reason):
    old = book_on_tuesday(team).plan
    if setup == "cancelled":
        send(team, CancelPlanRequest(plan_id=old.plan_id))
        World.expect(PlanCancelled)
    else:
        ask_to_move(team, old.plan_id)

    send(team, MovePlanRequest(plan_id=old.plan_id, day=FRIDAY))
    refused = World.expect(MoveFailed)

    assert refused.reason == reason


def test_a_meeting_that_is_not_booked_yet_cannot_move(team):
    send(
        team,
        PlanMeetingRequest(
            title="Design review",
            participant_emails=["sanne@example.com"],
            day=TUESDAY,
            location_id="library",
            lunch_wish="",
        ),
    )
    question = World.expect(SlotApprovalRequest)

    send(team, MovePlanRequest(plan_id=question.plan_id, day=THURSDAY))

    assert World.expect(MoveFailed).reason == "the meeting is not booked yet"


def test_cancelling_at_the_new_time_question_releases_the_old_meeting(team):
    """M11: nothing was booked for the new day yet, so only the old booking goes."""
    old = book_on_tuesday(team).plan
    ask_to_move(team, old.plan_id)

    send(team, CancelPlanRequest(plan_id=old.plan_id))
    cancelled = World.expect(PlanCancelled)

    assert World.released == old.compensations()
    assert cancelled.plan.cancelled
    wait_until(team, lambda s: s.moving is None and s.plan.cancelled)


def test_a_new_meeting_that_lands_after_a_cancel_is_released_too(team):
    """M11 with R5: the new day's meeting arrives late and is not left behind."""
    old = book_on_tuesday(team).plan
    World.hold.add(BookFacilitiesAssignment)
    ask_to_move(team, old.plan_id)
    send(team, SlotApprovalDecision(plan_id=old.plan_id, approved=True, slot=SLOT))
    wait_until(team, lambda s: s.moving is not None and s.moving.meeting_id is not None)
    new_meeting = state(team).moving.meeting_id

    send(team, CancelPlanRequest(plan_id=old.plan_id))
    World.expect(PlanCancelled)

    released = [c.reference for c in World.released]
    assert str(new_meeting) in released
    assert {str(old.meeting_id), str(old.booking_id), old.order_id} <= set(released)


def test_after_a_move_a_cancel_releases_the_new_bookings(team):
    old = book_on_tuesday(team).plan
    ask_to_move(team, old.plan_id)
    send(team, SlotApprovalDecision(plan_id=old.plan_id, approved=True, slot=SLOT))
    new = World.expect(PlanMoved).plan
    World.released.clear()

    send(team, CancelPlanRequest(plan_id=old.plan_id))
    World.expect(PlanCancelled)

    assert World.released == new.compensations()


def test_a_meeting_can_move_twice(team):
    first = book_on_tuesday(team).plan
    ask_to_move(team, first.plan_id, THURSDAY)
    send(team, SlotApprovalDecision(plan_id=first.plan_id, approved=True, slot=SLOT))
    second = World.expect(PlanMoved).plan

    ask_to_move(team, first.plan_id, FRIDAY)
    send(team, SlotApprovalDecision(plan_id=first.plan_id, approved=True, slot=SLOT))
    third = World.expect(PlanMoved).plan

    assert third.day == FRIDAY
    assert [b.day for b in third.moved_from] == [TUESDAY, THURSDAY]
    assert third.moved_from[1] == second.booking()
