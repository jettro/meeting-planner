"""Cancelling a meeting, run end to end in a real actor system.

The same bargain as `test_saga.py`: the specialists are stubs, because nothing
about *which* bookings to release or *in what order* needs a model. What is
worth proving here is the part that is easy to get wrong - that the list runs
one at a time, that a step which fails does not stop the ones behind it, and
that a plan this team never made can still be cancelled, which is the normal
case rather than the exception.
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
    CancelAssignment,
    Cancelled,
    CancelPlanRequest,
    PlanCancelled,
)
from meeting_agents.plan import CompensationStep, MeetingPlan, PlanStatus
from meeting_agents.plan_repository import PlanRepository, PlanRepositoryConfig
from meeting_agents.store import JsonPlanStore

DAY = date(2031, 9, 15)
MEETING_ID = 42
BOOKING_ID = 7
ORDER_ID = "order-abc"


class Inbox:
    """What the human saw, and what the specialists were asked to release."""

    messages: queue.Queue = queue.Queue()
    asked: list[CancelAssignment] = []
    #: Steps the stubs should refuse, so a partial failure can be set up.
    refuse: set[CompensationStep] = set()

    @classmethod
    def reset(cls) -> None:
        cls.messages = queue.Queue()
        cls.asked = []
        cls.refuse = set()

    @classmethod
    def expect(cls, kind: type, timeout: float = 5.0):
        message = cls.messages.get(timeout=timeout)
        assert isinstance(message, kind), f"expected {kind.__name__}, got {message!r}"
        return message

    @classmethod
    def steps(cls) -> list[CompensationStep]:
        return [assignment.step for assignment in cls.asked]


class RecordingHuman(UserProxy):
    def receiveMsg_PlanCancelled(  # noqa: N802
        self, message: PlanCancelled, sender: ActorAddress
    ) -> None:
        Inbox.messages.put(message)


class StubReleaser(Akgent[BaseConfig, BaseState]):
    """A specialist without the model: records what it was asked, then answers.

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


def member(agent_class, config, children=None) -> TeamCardMember:
    return TeamCardMember(
        card=AgentCard(agent_class=agent_class, description=config.role, config=config),
        headcount=1,
        members=children or [],
    )


def build_card(store_path) -> TeamCard:
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
                        member(
                            PlanRepository,
                            PlanRepositoryConfig(
                                store_class="meeting_agents.store.JsonPlanStore",
                                store_path=str(store_path),
                            ),
                        ),
                        member(StubReleaser, BaseConfig(name="@Scheduler", role="Scheduler")),
                        member(
                            StubReleaser,
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
def store_path(tmp_path):
    return tmp_path / "plans.json"


@pytest.fixture
def team(store_path):
    Inbox.reset()
    system = ActorSystem()
    runtime = TeamFactory.build(build_card(store_path), system, user_id="test")
    yield runtime
    system.shutdown()


def booked_plan(**overrides) -> MeetingPlan:
    fields = {
        "title": "Design review",
        "participant_emails": ["jettro@example.com", "daniel@example.com"],
        "day": DAY,
        "location_id": "yuma",
        "proposed_start": time(10, 0),
        "proposed_end": time(11, 0),
        "approved": True,
        "meeting_id": MEETING_ID,
        "room_code": "room-a",
        "booking_id": BOOKING_ID,
        "order_id": ORDER_ID,
    }
    return MeetingPlan(**{**fields, **overrides})


def given_stored(store_path, plan: MeetingPlan) -> MeetingPlan:
    """A plan made by some earlier team, which is how they always arrive."""
    return JsonPlanStore(str(store_path)).save(plan)


def cancel(team, plan_id: str) -> None:
    team.send_from_to("@Human", "@Coordinator", CancelPlanRequest(plan_id=plan_id))


def test_cancelling_releases_everything_in_reverse_booking_order(team, store_path):
    plan = given_stored(store_path, booked_plan())
    cancel(team, plan.plan_id)

    Inbox.expect(PlanCancelled)
    assert Inbox.steps() == [
        CompensationStep.CANCEL_ORDER,
        CompensationStep.CANCEL_ROOM_BOOKING,
        CompensationStep.CANCEL_MEETING,
    ]


def test_lunch_is_released_through_the_facility_manager(team, store_path):
    """The coordinator does not deal in lunch (D2), so it asks for facilities."""
    plan = given_stored(store_path, booked_plan())
    cancel(team, plan.plan_id)
    Inbox.expect(PlanCancelled)

    asked = {assignment.step: assignment for assignment in Inbox.asked}
    order = asked[CompensationStep.CANCEL_ORDER]
    assert order.reference == ORDER_ID
    assert asked[CompensationStep.CANCEL_MEETING].reference == str(MEETING_ID)


def test_the_cancelled_plan_is_reported_and_stored(team, store_path):
    plan = given_stored(store_path, booked_plan())
    cancel(team, plan.plan_id)

    cancelled = Inbox.expect(PlanCancelled)
    assert cancelled.failures == []
    assert cancelled.plan.status is PlanStatus.CANCELLED
    assert JsonPlanStore(str(store_path)).get(plan.plan_id).cancelled is True


def test_the_ids_survive_the_cancellation(team, store_path):
    """The plan is the record of what was booked. Erasing them loses that."""
    plan = given_stored(store_path, booked_plan())
    cancel(team, plan.plan_id)

    cancelled = Inbox.expect(PlanCancelled).plan
    assert (cancelled.meeting_id, cancelled.booking_id, cancelled.order_id) == (
        MEETING_ID,
        BOOKING_ID,
        ORDER_ID,
    )


def test_a_failed_step_does_not_stop_the_ones_behind_it(team, store_path):
    """A room somebody already released by hand must not strand the meeting."""
    Inbox.refuse = {CompensationStep.CANCEL_ROOM_BOOKING}
    plan = given_stored(store_path, booked_plan())
    cancel(team, plan.plan_id)

    cancelled = Inbox.expect(PlanCancelled)
    assert Inbox.steps() == [
        CompensationStep.CANCEL_ORDER,
        CompensationStep.CANCEL_ROOM_BOOKING,
        CompensationStep.CANCEL_MEETING,
    ]
    assert len(cancelled.failures) == 1
    assert "cancel_room_booking 7" in cancelled.failures[0]
    assert "no such booking" in cancelled.failures[0]


def test_a_plan_that_could_not_be_fully_released_is_still_cancelled(team, store_path):
    """The intent was carried out as far as the services allowed."""
    Inbox.refuse = {CompensationStep.CANCEL_MEETING}
    plan = given_stored(store_path, booked_plan())
    cancel(team, plan.plan_id)

    assert Inbox.expect(PlanCancelled).plan.status is PlanStatus.CANCELLED


def test_a_plan_with_nothing_booked_is_cancelled_without_asking_anyone(team, store_path):
    plan = given_stored(store_path, booked_plan(meeting_id=None, booking_id=None, order_id=None))
    cancel(team, plan.plan_id)

    assert Inbox.expect(PlanCancelled).plan.status is PlanStatus.CANCELLED
    assert Inbox.asked == []


def test_cancelling_twice_releases_nothing_the_second_time(team, store_path):
    """A repeat is harmless and must look harmless - not like three failures."""
    plan = given_stored(store_path, booked_plan())
    cancel(team, plan.plan_id)
    Inbox.expect(PlanCancelled)

    Inbox.asked = []
    cancel(team, plan.plan_id)

    again = Inbox.expect(PlanCancelled)
    assert Inbox.asked == []
    assert again.failures == []
    assert again.plan.status is PlanStatus.CANCELLED


def test_an_unknown_plan_is_not_answered_for(team):
    """Nothing to release and nothing to report - and nothing invented."""
    cancel(team, "no-such-plan")

    with pytest.raises(queue.Empty):
        Inbox.messages.get(timeout=1.0)
    assert Inbox.asked == []
