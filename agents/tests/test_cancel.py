"""Cancelling a meeting, run end to end in a real actor system.

The same bargain as `test_saga.py`: the specialists are stubs, because nothing
about *which* bookings to release or *in what order* needs a model. What is
worth proving here is the part that is easy to get wrong - that the list runs
one at a time, that a step which fails does not stop the ones behind it, and
that a booking still in flight when the cancel arrives is released when it
lands rather than left behind (R5).

A cancellation goes to the team that made the meeting (R4), so every test here
books first and cancels second, in the same team - which is exactly what the
browser does.
"""

from __future__ import annotations

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

DAY = date(2031, 9, 15)
SLOT = ProposedSlot(start=time(10, 0), end=time(11, 0))
MEETING_ID = 42
BOOKING_ID = 7
ORDER_ID = "order-abc"


class Inbox:
    """What the human saw, and what the specialists were asked to release."""

    messages: queue.Queue = queue.Queue()
    asked: list[CancelAssignment] = []
    #: Steps the stubs should refuse, so a partial failure can be set up.
    refuse: set[CompensationStep] = set()
    #: Bookings the stubs should take but not answer yet, so a cancel can
    #: overtake them. The test delivers the late answer itself.
    hold: set[type] = set()

    @classmethod
    def reset(cls) -> None:
        cls.messages = queue.Queue()
        cls.asked = []
        cls.refuse = set()
        cls.hold = set()

    @classmethod
    def expect(cls, kind: type, timeout: float = 5.0):
        message = cls.messages.get(timeout=timeout)
        assert isinstance(message, kind), f"expected {kind.__name__}, got {message!r}"
        return message

    @classmethod
    def steps(cls) -> list[CompensationStep]:
        return [assignment.step for assignment in cls.asked]


class RecordingHuman(UserProxy):
    def receiveMsg_SlotApprovalRequest(  # noqa: N802
        self, message: SlotApprovalRequest, sender: ActorAddress
    ) -> None:
        Inbox.messages.put(message)

    def receiveMsg_PlanCompleted(  # noqa: N802
        self, message: PlanCompleted, sender: ActorAddress
    ) -> None:
        Inbox.messages.put(message)

    def receiveMsg_PlanCancelled(  # noqa: N802
        self, message: PlanCancelled, sender: ActorAddress
    ) -> None:
        Inbox.messages.put(message)


class StubSpecialist(Akgent[BaseConfig, BaseState]):
    """Releases like a specialist: records what it was asked, then answers.

    It answers whether or not the release "worked", which is the contract the
    driver depends on - a step that never replies would stop the list.
    """

    def receiveMsg_CancelAssignment(  # noqa: N802
        self, message: CancelAssignment, sender: ActorAddress
    ) -> None:
        Inbox.asked.append(message)
        refused = message.step in Inbox.refuse
        self.send(
            sender,
            Cancelled(
                plan_id=message.plan_id,
                step=message.step,
                succeeded=not refused,
                reason="no such booking" if refused else "",
            ),
        )


class StubScheduler(StubSpecialist):
    def receiveMsg_FindSlotsAssignment(  # noqa: N802
        self, message: FindSlotsAssignment, sender: ActorAddress
    ) -> None:
        self.send(sender, SlotsFound(plan_id=message.plan_id, candidates=[SLOT]))

    def receiveMsg_BookMeetingAssignment(  # noqa: N802
        self, message: BookMeetingAssignment, sender: ActorAddress
    ) -> None:
        if BookMeetingAssignment in Inbox.hold:
            return
        self.send(sender, MeetingBooked(plan_id=message.plan_id, meeting_id=MEETING_ID))


class StubFacilityManager(StubSpecialist):
    def receiveMsg_BookFacilitiesAssignment(  # noqa: N802
        self, message: BookFacilitiesAssignment, sender: ActorAddress
    ) -> None:
        if BookFacilitiesAssignment in Inbox.hold:
            return
        self.send(sender, facilities_booked(message.plan_id))


def facilities_booked(plan_id: str) -> FacilitiesBooked:
    return FacilitiesBooked(plan_id=plan_id, room_code="room-a", booking_id=BOOKING_ID, order_id=ORDER_ID)


def member(agent_class, config, children=None) -> TeamCardMember:
    return TeamCardMember(
        card=AgentCard(agent_class=agent_class, description=config.role, config=config),
        headcount=1,
        members=children or [],
    )


def build_card() -> TeamCard:
    return TeamCard(
        name="cancel-test",
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
def team():
    Inbox.reset()
    system = ActorSystem()
    runtime = TeamFactory.build(build_card(), system, user_id="test")
    yield runtime
    system.shutdown()


def coordinator_state(runtime) -> CoordinatorState:
    coordinator = runtime.addrs["@Coordinator"]
    return runtime.orchestrator_proxy.get_states()[str(coordinator.agent_id)]


def wait_until(runtime, condition, timeout: float = 5.0) -> None:
    """Wait for the coordinator's record to say something, rather than guess when."""
    deadline = clock.monotonic() + timeout
    while clock.monotonic() < deadline:
        if condition(coordinator_state(runtime)):
            return
        clock.sleep(0.02)
    raise AssertionError("the coordinator never got there")


def ask_for_a_meeting(team) -> str:
    """Request a meeting with lunch settled, and approve the one slot offered."""
    team.send_from_to(
        "@Human",
        "@Coordinator",
        PlanMeetingRequest(
            title="Design review",
            participant_emails=["jettro@example.com", "daniel@example.com"],
            day=DAY,
            location_id="yuma",
            lunch_wish="",
        ),
    )
    question = Inbox.expect(SlotApprovalRequest)
    team.send_from_to(
        "@Human",
        "@Coordinator",
        SlotApprovalDecision(plan_id=question.plan_id, approved=True, slot=SLOT),
    )
    return question.plan_id


def book_a_meeting(team) -> str:
    plan_id = ask_for_a_meeting(team)
    Inbox.expect(PlanCompleted)
    return plan_id


def cancel(team, plan_id: str) -> None:
    team.send_from_to("@Human", "@Coordinator", CancelPlanRequest(plan_id=plan_id))


def test_cancelling_releases_everything_in_reverse_booking_order(team):
    cancel(team, book_a_meeting(team))

    Inbox.expect(PlanCancelled)
    assert Inbox.steps() == [
        CompensationStep.CANCEL_ORDER,
        CompensationStep.CANCEL_ROOM_BOOKING,
        CompensationStep.CANCEL_MEETING,
    ]


def test_lunch_is_released_through_the_facility_manager(team):
    """The coordinator does not deal in lunch (D2), so it asks for facilities."""
    cancel(team, book_a_meeting(team))
    Inbox.expect(PlanCancelled)

    asked = {assignment.step: assignment for assignment in Inbox.asked}
    assert asked[CompensationStep.CANCEL_ORDER].reference == ORDER_ID
    assert asked[CompensationStep.CANCEL_MEETING].reference == str(MEETING_ID)


def test_the_cancelled_meeting_is_reported_and_recorded(team):
    cancel(team, book_a_meeting(team))

    cancelled = Inbox.expect(PlanCancelled)
    assert cancelled.failures == []
    assert cancelled.plan.status is PlanStatus.CANCELLED
    assert coordinator_state(team).plan.status is PlanStatus.CANCELLED


def test_the_ids_survive_the_cancellation(team):
    """The plan is the record of what was booked. Erasing them loses that."""
    cancel(team, book_a_meeting(team))

    cancelled = Inbox.expect(PlanCancelled).plan
    assert (cancelled.meeting_id, cancelled.booking_id, cancelled.order_id) == (
        MEETING_ID,
        BOOKING_ID,
        ORDER_ID,
    )


def test_a_failed_step_does_not_stop_the_ones_behind_it(team):
    """A room somebody already released by hand must not strand the meeting."""
    Inbox.refuse = {CompensationStep.CANCEL_ROOM_BOOKING}
    cancel(team, book_a_meeting(team))

    cancelled = Inbox.expect(PlanCancelled)
    assert Inbox.steps() == [
        CompensationStep.CANCEL_ORDER,
        CompensationStep.CANCEL_ROOM_BOOKING,
        CompensationStep.CANCEL_MEETING,
    ]
    assert len(cancelled.failures) == 1
    assert "cancel_room_booking 7" in cancelled.failures[0]
    assert "no such booking" in cancelled.failures[0]


def test_what_could_not_be_released_stays_on_record(team):
    """The report is the only place that says something may still be held."""
    Inbox.refuse = {CompensationStep.CANCEL_ROOM_BOOKING}
    cancel(team, book_a_meeting(team))
    Inbox.expect(PlanCancelled)

    assert len(coordinator_state(team).cancel_failures) == 1


def test_a_meeting_that_could_not_be_fully_released_is_still_cancelled(team):
    """The intent was carried out as far as the services allowed."""
    Inbox.refuse = {CompensationStep.CANCEL_MEETING}
    cancel(team, book_a_meeting(team))

    assert Inbox.expect(PlanCancelled).plan.status is PlanStatus.CANCELLED


def test_a_meeting_waiting_at_the_gate_is_cancelled_without_asking_anyone(team):
    """Nothing is booked before approval, so there is nothing to release."""
    team.send_from_to(
        "@Human",
        "@Coordinator",
        PlanMeetingRequest(
            title="Never mind",
            participant_emails=["a@example.com"],
            day=DAY,
            location_id="yuma",
            with_lunch=False,
        ),
    )
    question = Inbox.expect(SlotApprovalRequest)
    cancel(team, question.plan_id)

    assert Inbox.expect(PlanCancelled).plan.status is PlanStatus.CANCELLED
    assert Inbox.asked == []
    assert not coordinator_state(team).waiting_for_the_human()


def test_a_cancelled_gate_cannot_be_answered(team):
    """A stale tab approving the slot afterwards must not book anything."""
    team.send_from_to(
        "@Human",
        "@Coordinator",
        PlanMeetingRequest(
            title="Never mind",
            participant_emails=["a@example.com"],
            day=DAY,
            location_id="yuma",
            with_lunch=False,
        ),
    )
    question = Inbox.expect(SlotApprovalRequest)
    cancel(team, question.plan_id)
    Inbox.expect(PlanCancelled)

    team.send_from_to(
        "@Human",
        "@Coordinator",
        SlotApprovalDecision(plan_id=question.plan_id, approved=True, slot=SLOT),
    )

    with pytest.raises(queue.Empty):
        Inbox.messages.get(timeout=1.0)
    assert coordinator_state(team).plan.meeting_id is None


def test_cancelling_twice_releases_nothing_the_second_time(team):
    """A repeat is harmless and must look harmless - not like three failures."""
    plan_id = book_a_meeting(team)
    cancel(team, plan_id)
    Inbox.expect(PlanCancelled)

    Inbox.asked = []
    cancel(team, plan_id)

    again = Inbox.expect(PlanCancelled)
    assert Inbox.asked == []
    assert again.failures == []
    assert again.plan.status is PlanStatus.CANCELLED


def test_an_unknown_plan_is_not_answered_for(team):
    """Nothing to release and nothing to report - and nothing invented."""
    book_a_meeting(team)
    cancel(team, "no-such-plan")

    with pytest.raises(queue.Empty):
        Inbox.messages.get(timeout=1.0)
    assert Inbox.asked == []


# -- a booking still in flight when the cancel arrives (R5) ----------------


def test_a_meeting_booked_after_the_cancel_is_released_when_it_lands(team):
    Inbox.hold = {BookMeetingAssignment}
    plan_id = ask_for_a_meeting(team)

    # The cancel overtakes the booking: nothing is booked yet, so it finishes.
    cancel(team, plan_id)
    assert Inbox.expect(PlanCancelled).plan.meeting_id is None

    # Then the booking lands anyway.
    team.send_from_to("@Scheduler", "@Coordinator", MeetingBooked(plan_id=plan_id, meeting_id=MEETING_ID))

    late = Inbox.expect(PlanCancelled)
    assert Inbox.steps() == [CompensationStep.CANCEL_MEETING]
    assert late.plan.meeting_id == MEETING_ID
    assert late.plan.status is PlanStatus.CANCELLED


def test_a_late_meeting_does_not_go_on_to_book_a_room(team):
    """Building on a booking for a cancelled meeting would make it worse."""
    Inbox.hold = {BookMeetingAssignment}
    plan_id = ask_for_a_meeting(team)
    cancel(team, plan_id)
    Inbox.expect(PlanCancelled)

    team.send_from_to("@Scheduler", "@Coordinator", MeetingBooked(plan_id=plan_id, meeting_id=MEETING_ID))
    Inbox.expect(PlanCancelled)

    assert coordinator_state(team).plan.booking_id is None


def test_late_facilities_are_released_lunch_first(team):
    Inbox.hold = {BookFacilitiesAssignment}
    plan_id = ask_for_a_meeting(team)
    wait_until(team, lambda state: state.plan.meeting_id is not None)

    # The meeting is booked; the room and lunch are still on their way.
    cancel(team, plan_id)
    Inbox.expect(PlanCancelled)
    assert Inbox.steps() == [CompensationStep.CANCEL_MEETING]

    team.send_from_to("@FacilityManager", "@Coordinator", facilities_booked(plan_id))

    late = Inbox.expect(PlanCancelled)
    assert Inbox.steps() == [
        CompensationStep.CANCEL_MEETING,
        CompensationStep.CANCEL_ORDER,
        CompensationStep.CANCEL_ROOM_BOOKING,
    ]
    assert (late.plan.booking_id, late.plan.order_id) == (BOOKING_ID, ORDER_ID)
    assert late.plan.status is PlanStatus.CANCELLED
