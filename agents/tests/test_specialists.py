"""The specialists' own logic, with the model replaced and nothing else.

`test_saga.py` stubs the specialists entirely to prove the coordinator is
deterministic. These tests do the opposite: the specialists are the real
classes, and only `act()` - the single call that reaches a model - is replaced
with a canned answer.

That boundary is the interesting one. Everything a specialist does around the
model run is ours and must be verified: refusing an invented id, parsing a
time, and the hop to @Catering that keeps lunch out of the coordinator's view.
"""

from __future__ import annotations

import queue
from datetime import date, time

import pytest
from akgentic.agent.config import AgentConfig
from akgentic.core import AgentCard, Akgent, BaseConfig, BaseState, UserProxy
from akgentic.team import TeamCard, TeamCardMember, TeamFactory
from meeting_agents.coordinator import Coordinator, CoordinatorConfig
from meeting_agents.messages import (
    MESSAGE_TYPES,
    CancelPlanRequest,
    PlanCancelled,
    PlanCompleted,
    PlanFailed,
    PlanMeetingRequest,
    ProposedSlot,
    SlotApprovalDecision,
    SlotApprovalRequest,
)
from meeting_agents.outputs import (
    BookedMeeting,
    BookedRoom,
    FoundSlots,
    OrderedLunch,
    ReleasedBooking,
    SlotOut,
)
from meeting_agents.plan import PlanStatus
from meeting_agents.plan_repository import PlanRepository, PlanRepositoryConfig
from meeting_agents.specialists import (
    MAX_CANDIDATES,
    Catering,
    FacilityManager,
    FacilityManagerConfig,
    Scheduler,
    meeting_slots,
)

DAY = date(2031, 9, 15)
MEETING_ID = 42
BOOKING_ID = 7
ROOM_CODE = "AMS-1.14"
ORDER_ID = "order-abc"


class Script:
    """Canned model answers, and a record of what the model was asked.

    A class attribute because the framework constructs the actors: config
    carries plain data only, so there is nowhere to pass a live object.
    """

    answers: dict[type, list] = {}
    prompts: list[str] = []

    @classmethod
    def reset(cls) -> None:
        cls.answers = {}
        cls.prompts = []

    @classmethod
    def give(cls, output_type: type, *values) -> None:
        cls.answers.setdefault(output_type, []).extend(values)

    @classmethod
    def take(cls, output_type: type):
        queued = cls.answers.get(output_type)
        if not queued:
            raise AssertionError(f"no canned answer for {output_type.__name__}")
        return queued.pop(0)


class ScriptedModel:
    """Replaces exactly one thing: the call that reaches a model."""

    def act(self, message, output_type):
        Script.prompts.append(message.rendering())
        return Script.take(output_type)


class ScriptedScheduler(ScriptedModel, Scheduler):
    pass


class ScriptedFacilityManager(ScriptedModel, FacilityManager):
    pass


class ScriptedCatering(ScriptedModel, Catering):
    pass


class Inbox:
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
    def receiveMsg_SlotApprovalRequest(self, message, sender) -> None:  # noqa: N802
        Inbox.messages.put(message)

    def receiveMsg_PlanCompleted(self, message, sender) -> None:  # noqa: N802
        Inbox.messages.put(message)

    def receiveMsg_PlanFailed(self, message, sender) -> None:  # noqa: N802
        Inbox.messages.put(message)

    def receiveMsg_PlanCancelled(self, message, sender) -> None:  # noqa: N802
        Inbox.messages.put(message)


class Watcher(Akgent[BaseConfig, BaseState]):
    """Stands in for a specialist so we can see what it was sent."""

    def on_receive(self, message):
        Inbox.messages.put(message)


def member(agent_class, config, children=None) -> TeamCardMember:
    return TeamCardMember(
        card=AgentCard(agent_class=agent_class, description=config.role, config=config),
        headcount=1,
        members=children or [],
    )


def specialist_config(name: str, cls=AgentConfig, **extra):
    """A config good enough to build the agent; the model is never reached."""
    return cls(name=name, role=name.lstrip("@"), **extra)


def build_card(store_path, catering_class=ScriptedCatering) -> TeamCard:
    return TeamCard(
        name="specialist-test",
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
                            PlanRepositoryConfig(store_path=str(store_path)),
                        ),
                        member(ScriptedScheduler, specialist_config("@Scheduler")),
                        member(
                            ScriptedFacilityManager,
                            specialist_config("@FacilityManager", FacilityManagerConfig),
                            [member(catering_class, specialist_config("@Catering"))],
                        ),
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
    """Never the real key: these tests must not be able to reach a provider."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")


@pytest.fixture
def team(tmp_path):
    Inbox.reset()
    Script.reset()
    from akgentic.core import ActorSystem

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
            lunch_wish="",
        ),
    )


def good_slots() -> FoundSlots:
    return FoundSlots(succeeded=True, slots=[SlotOut(start="10:00", end="11:00")])


def run_to_completion(team, with_lunch: bool = True):
    request_meeting(team, with_lunch=with_lunch)
    request = Inbox.expect(SlotApprovalRequest)
    team.send_from_to(
        "@Human",
        "@Coordinator",
        SlotApprovalDecision(plan_id=request.plan_id, approved=True, slot=request.candidates[0]),
    )
    return request


def test_the_whole_team_completes_a_plan(team):
    """The real specialists, the real coordinator, only the model replaced."""
    Script.give(FoundSlots, good_slots())
    Script.give(BookedMeeting, BookedMeeting(succeeded=True, meeting_id=MEETING_ID))
    Script.give(BookedRoom, BookedRoom(succeeded=True, room_code=ROOM_CODE, booking_id=BOOKING_ID))
    Script.give(OrderedLunch, OrderedLunch(succeeded=True, order_id=ORDER_ID))

    run_to_completion(team)
    plan = Inbox.expect(PlanCompleted).plan

    assert plan.meeting_id == MEETING_ID
    assert plan.room_code == ROOM_CODE
    assert plan.booking_id == BOOKING_ID
    assert plan.order_id == ORDER_ID
    assert plan.status is PlanStatus.CONFIRMED


def test_the_scheduler_parses_the_times_it_is_given(team):
    """A 90-minute window yields one bookable hour, not the window itself."""
    Script.give(FoundSlots, FoundSlots(succeeded=True, slots=[SlotOut(start="9:05", end="10:35")]))
    request_meeting(team)
    request = Inbox.expect(SlotApprovalRequest)
    assert request.candidates[0].start == time(9, 5)
    assert request.candidates[0].end == time(10, 5)


def test_a_window_too_short_to_hold_the_meeting_stops_the_plan(team):
    """Found live: a window is not a meeting. Half an hour of overlap cannot
    host an hour-long meeting, and proposing it would book a bad slot."""
    Script.give(FoundSlots, FoundSlots(succeeded=True, slots=[SlotOut(start="09:00", end="09:30")]))
    request_meeting(team)
    failed = Inbox.expect(PlanFailed)
    assert "60 minutes" in failed.reason


def test_an_unparseable_time_stops_the_plan(team):
    """Better to fail here than to book something at a guessed time."""
    Script.give(FoundSlots, FoundSlots(succeeded=True, slots=[SlotOut(start="elevenish", end="?")]))
    request_meeting(team)
    failed = Inbox.expect(PlanFailed)
    assert "elevenish" in failed.reason


def test_a_failed_search_is_reported_as_a_failure(team):
    Script.give(FoundSlots, FoundSlots(succeeded=False, reason="the agenda service is down"))
    request_meeting(team)
    failed = Inbox.expect(PlanFailed)
    assert "agenda service is down" in failed.reason


def test_no_common_slot_is_a_plain_answer_not_an_error(team):
    Script.give(FoundSlots, FoundSlots(succeeded=True, slots=[]))
    request_meeting(team)
    failed = Inbox.expect(PlanFailed)
    assert "no time slot works" in failed.reason
    assert failed.outstanding == []


def test_a_booking_without_an_id_is_refused(team):
    """`succeeded` with no id is not a booking. Nothing may be stored from it."""
    Script.give(FoundSlots, good_slots())
    Script.give(BookedMeeting, BookedMeeting(succeeded=True, meeting_id=None))

    run_to_completion(team)
    failed = Inbox.expect(PlanFailed)
    assert failed.plan.meeting_id is None


def test_a_model_run_that_raises_becomes_a_reported_failure(team):
    """A provider error must reach the human, not die in an actor thread."""
    request_meeting(team)
    failed = Inbox.expect(PlanFailed)
    assert "no canned answer" in failed.reason


def test_without_lunch_catering_is_never_asked(team, tmp_path):
    """Build a team whose @Catering records anything it receives."""
    Script.give(FoundSlots, good_slots())
    Script.give(BookedMeeting, BookedMeeting(succeeded=True, meeting_id=MEETING_ID))
    Script.give(BookedRoom, BookedRoom(succeeded=True, room_code=ROOM_CODE, booking_id=BOOKING_ID))

    run_to_completion(team, with_lunch=False)
    plan = Inbox.expect(PlanCompleted).plan
    assert plan.order_id is None
    assert plan.status is PlanStatus.CONFIRMED


def test_the_coordinator_never_mentions_lunch_to_the_facility_manager(team):
    """D2 again, observed in the prompts the model actually received."""
    Script.give(FoundSlots, good_slots())
    Script.give(BookedMeeting, BookedMeeting(succeeded=True, meeting_id=MEETING_ID))
    Script.give(BookedRoom, BookedRoom(succeeded=True, room_code=ROOM_CODE, booking_id=BOOKING_ID))
    Script.give(OrderedLunch, OrderedLunch(succeeded=True, order_id=ORDER_ID))

    run_to_completion(team)
    Inbox.expect(PlanCompleted)

    room_prompts = [p for p in Script.prompts if "Book a room" in p]
    assert room_prompts and all("lunch" not in p.lower() for p in room_prompts)
    assert any("Order lunch" in p for p in Script.prompts)


def test_failed_lunch_names_the_room_that_is_still_booked(team):
    """The room is already taken by then, so the failure must say so."""
    Script.give(FoundSlots, good_slots())
    Script.give(BookedMeeting, BookedMeeting(succeeded=True, meeting_id=MEETING_ID))
    Script.give(BookedRoom, BookedRoom(succeeded=True, room_code=ROOM_CODE, booking_id=BOOKING_ID))
    Script.give(OrderedLunch, OrderedLunch(succeeded=False, reason="the kitchen is closed"))

    run_to_completion(team)
    failed = Inbox.expect(PlanFailed)

    assert "kitchen is closed" in failed.reason
    assert ROOM_CODE in failed.reason
    assert str(BOOKING_ID) in failed.reason


def test_a_failed_room_booking_never_orders_lunch(team):
    Script.give(FoundSlots, good_slots())
    Script.give(BookedMeeting, BookedMeeting(succeeded=True, meeting_id=MEETING_ID))
    Script.give(BookedRoom, BookedRoom(succeeded=False, reason="no room is free"))

    run_to_completion(team)
    failed = Inbox.expect(PlanFailed)

    assert "no room is free" in failed.reason
    assert not any("Order lunch" in p for p in Script.prompts)


def test_the_assignment_reaches_the_model_with_its_facts(team):
    Script.give(FoundSlots, good_slots())
    request_meeting(team)
    Inbox.expect(SlotApprovalRequest)

    assert any(
        "jettro@example.com" in p and "daniel@example.com" in p and "2031-09-15" in p for p in Script.prompts
    )


# --------------------------------------------------------------------------
# Turning free windows into bookable slots - pure arithmetic, no actors.
# --------------------------------------------------------------------------


def window(start: str, end: str) -> ProposedSlot:
    h1, m1 = (int(p) for p in start.split(":"))
    h2, m2 = (int(p) for p in end.split(":"))
    return ProposedSlot(start=time(h1, m1), end=time(h2, m2))


def test_a_long_window_is_cut_into_meeting_length_slots():
    slots = meeting_slots([window("09:00", "17:00")], 60)
    assert [(s.start, s.end) for s in slots] == [
        (time(9, 0), time(10, 0)),
        (time(10, 0), time(11, 0)),
        (time(11, 0), time(12, 0)),
    ]


def test_the_choice_offered_to_a_human_stays_short():
    assert len(meeting_slots([window("08:00", "18:00")], 30)) == MAX_CANDIDATES


def test_every_slot_fits_inside_its_window():
    slots = meeting_slots([window("09:00", "10:20")], 45)
    assert [(s.start, s.end) for s in slots] == [(time(9, 0), time(9, 45))]


def test_a_window_shorter_than_the_meeting_yields_nothing():
    assert meeting_slots([window("09:00", "09:30")], 60) == []


def test_later_windows_are_used_when_the_first_is_too_short():
    slots = meeting_slots([window("09:00", "09:15"), window("14:00", "15:00")], 60)
    assert [(s.start, s.end) for s in slots] == [(time(14, 0), time(15, 0))]


def test_no_windows_means_no_slots():
    assert meeting_slots([], 60) == []


def book_then_cancel(team, *releases):
    """Run a plan to CONFIRMED with the real agents, then call it off."""
    Script.give(FoundSlots, good_slots())
    Script.give(BookedMeeting, BookedMeeting(succeeded=True, meeting_id=MEETING_ID))
    Script.give(BookedRoom, BookedRoom(succeeded=True, room_code=ROOM_CODE, booking_id=BOOKING_ID))
    Script.give(OrderedLunch, OrderedLunch(succeeded=True, order_id=ORDER_ID))
    run_to_completion(team)
    plan = Inbox.expect(PlanCompleted).plan

    Script.give(ReleasedBooking, *releases)
    Script.prompts.clear()
    team.send_from_to("@Human", "@Coordinator", CancelPlanRequest(plan_id=plan.plan_id))
    return Inbox.expect(PlanCancelled)


def test_the_whole_team_cancels_a_plan(team):
    """The real agents again, including the hop the coordinator cannot make.

    @Catering is the only agent that can reach the nomnom service, and the
    coordinator may not address it (D2) - so a released order proves the
    assignment travelled through @FacilityManager and the answer came back.
    """
    released = [ReleasedBooking(succeeded=True) for _ in range(3)]
    cancelled = book_then_cancel(team, *released)

    assert cancelled.failures == []
    assert cancelled.plan.status is PlanStatus.CANCELLED
    assert any(ORDER_ID in prompt for prompt in Script.prompts)
    assert any(str(BOOKING_ID) in prompt for prompt in Script.prompts)
    assert any(str(MEETING_ID) in prompt for prompt in Script.prompts)


def test_a_cancellation_the_tool_refused_is_named_and_the_rest_still_run(team):
    cancelled = book_then_cancel(
        team,
        ReleasedBooking(succeeded=True),
        ReleasedBooking(succeeded=False, reason="booking 7 does not exist"),
        ReleasedBooking(succeeded=True),
    )

    assert len(cancelled.failures) == 1
    assert "does not exist" in cancelled.failures[0]
    assert cancelled.plan.status is PlanStatus.CANCELLED
    assert any(str(MEETING_ID) in prompt for prompt in Script.prompts)


def test_a_cancel_run_that_raises_becomes_a_named_failure(team):
    """Two answers for three steps: the last model call blows up.

    A booking handler turns that into `AssignmentFailed` and stops. A cancel
    handler must not - an exception here is one line of the report, and the
    list it belongs to has already finished.
    """
    cancelled = book_then_cancel(
        team,
        ReleasedBooking(succeeded=True),
        ReleasedBooking(succeeded=True),
    )

    assert len(cancelled.failures) == 1
    assert "cancel_meeting" in cancelled.failures[0]
    assert cancelled.plan.status is PlanStatus.CANCELLED
