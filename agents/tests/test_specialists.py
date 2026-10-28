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
    AssignmentFailed,
    CancelPlanRequest,
    FindPeopleAssignment,
    PeopleFound,
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
    ChosenLocation,
    FoundSlots,
    MatchedPeople,
    NameMatchOut,
    OrderedLunch,
    PersonOut,
    ReleasedBooking,
    SlotOut,
)
from meeting_agents.plan import PlanStatus
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

    # The people lookup answers whoever asked; in these tests that is @Human,
    # standing in for @Intake (design_chat.md §13.2).
    def receiveMsg_PeopleFound(self, message, sender) -> None:  # noqa: N802
        Inbox.messages.put(message)

    def receiveMsg_AssignmentFailed(self, message, sender) -> None:  # noqa: N802
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


def build_card(catering_class=ScriptedCatering) -> TeamCard:
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
def team():
    Inbox.reset()
    Script.reset()
    from akgentic.core import ActorSystem

    system = ActorSystem()
    runtime = TeamFactory.build(build_card(), system, user_id="test")
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


# -- a place described rather than named (design_chat.md §13.1) -----------


def ask_for_a_place(team, wish: str = "a natural environment") -> None:
    team.send_from_to(
        "@Human",
        "@Coordinator",
        PlanMeetingRequest(
            title="Offsite",
            participant_emails=["jettro@example.com", "daniel@example.com"],
            day=DAY,
            location_wish=wish,
            with_lunch=False,
        ),
    )


def nature() -> ChosenLocation:
    return ChosenLocation(
        succeeded=True,
        location_id="meet-nature",
        name="Meeting in Nature",
        reason="outdoor activities - closest to a natural environment",
    )


def test_a_described_place_is_chosen_before_the_slots(team):
    """The facility manager chooses, and the human sees the choice with the times."""
    Script.give(ChosenLocation, nature())
    Script.give(FoundSlots, good_slots())

    ask_for_a_place(team)
    question = Inbox.expect(SlotApprovalRequest)

    assert question.location_name == "Meeting in Nature"
    assert "outdoor activities" in question.location_reason
    assert "Meeting in Nature" in question.question()
    # The place was asked about first, in the requester's own words.
    assert "a natural environment" in Script.prompts[0]
    assert "Find every" in Script.prompts[1]


def test_the_meeting_is_booked_at_the_chosen_place(team):
    Script.give(ChosenLocation, nature())
    Script.give(FoundSlots, good_slots())
    Script.give(BookedMeeting, BookedMeeting(succeeded=True, meeting_id=MEETING_ID))
    Script.give(BookedRoom, BookedRoom(succeeded=True, room_code="forest", booking_id=BOOKING_ID))

    ask_for_a_place(team)
    question = Inbox.expect(SlotApprovalRequest)
    team.send_from_to(
        "@Human",
        "@Coordinator",
        SlotApprovalDecision(plan_id=question.plan_id, approved=True, slot=question.candidates[0]),
    )
    plan = Inbox.expect(PlanCompleted).plan

    assert plan.location_id == "meet-nature"
    assert plan.location_wish == "a natural environment"
    assert plan.location_name == "Meeting in Nature"
    assert any("location meet-nature" in prompt for prompt in Script.prompts)


def test_choosing_a_place_says_how_many_need_seating(team):
    Script.give(ChosenLocation, nature())
    Script.give(FoundSlots, good_slots())

    ask_for_a_place(team)
    Inbox.expect(SlotApprovalRequest)

    assert "for 2 people" in Script.prompts[0]


def test_nothing_fitting_is_an_honest_no_before_anything_is_booked(team):
    Script.give(ChosenLocation, ChosenLocation(succeeded=False, reason="no location has a sports hall"))

    ask_for_a_place(team, wish="somewhere sporty")
    failed = Inbox.expect(PlanFailed)

    assert failed.reason == "no location has a sports hall"
    assert failed.outstanding == []
    assert len(Script.prompts) == 1, "no slots were searched for a place that does not exist"


def test_a_choice_without_an_id_is_refused(team):
    """A name alone cannot be booked - and an invented id would be worse."""
    Script.give(ChosenLocation, ChosenLocation(succeeded=True, name="Somewhere nice"))

    ask_for_a_place(team)

    assert "no location fits" in Inbox.expect(PlanFailed).reason


def test_a_named_location_is_never_looked_up(team):
    """An id in the request means the saga runs exactly as it always did."""
    Script.give(FoundSlots, good_slots())

    request_meeting(team)
    question = Inbox.expect(SlotApprovalRequest)

    assert question.location_name == ""
    assert not any("Choose the location" in prompt for prompt in Script.prompts)


# -- people named rather than addressed (design_chat.md §13.2) -------------


SANNE = PersonOut(name="Sanne Visser", email="sanne@rag4p.org")
DAAN_V = PersonOut(name="Daan de Vries", email="daan@rag4p.org")
DAAN_J = PersonOut(name="Daan Jansen", email="daan.jansen@rag4p.org")


def look_up(team, *names: str) -> None:
    team.send_from_to("@Human", "@Scheduler", FindPeopleAssignment(names=list(names)))


def test_a_name_with_one_match_is_settled(team):
    Script.give(
        MatchedPeople,
        MatchedPeople(succeeded=True, matches=[NameMatchOut(asked="Sanne", candidates=[SANNE])]),
    )

    look_up(team, "Sanne")
    found = Inbox.expect(PeopleFound)

    assert [(m.asked, [p.email for p in m.candidates]) for m in found.matches] == [
        ("Sanne", ["sanne@rag4p.org"])
    ]


def test_an_ambiguous_name_reports_everyone_it_could_mean(team):
    """Never a pick: two Daans is a question for the person, not for the model."""
    Script.give(
        MatchedPeople,
        MatchedPeople(succeeded=True, matches=[NameMatchOut(asked="Daan", candidates=[DAAN_V, DAAN_J])]),
    )

    look_up(team, "Daan")

    assert len(Inbox.expect(PeopleFound).matches[0].candidates) == 2


def test_a_name_the_model_skipped_is_reported_as_nobody(team):
    """Every name asked gets an answer, in order - none is silently dropped."""
    Script.give(
        MatchedPeople,
        MatchedPeople(succeeded=True, matches=[NameMatchOut(asked="Sanne", candidates=[SANNE])]),
    )

    look_up(team, "Sanne", "Bram")
    found = Inbox.expect(PeopleFound)

    assert [m.asked for m in found.matches] == ["Sanne", "Bram"]
    assert found.matches[1].candidates == []


def test_the_lookup_frames_itself_as_one_that_books_nothing(team):
    Script.give(MatchedPeople, MatchedPeople(succeeded=True))

    look_up(team, "Sanne")
    Inbox.expect(PeopleFound)

    assert "book nothing" in Script.prompts[0]
    assert '"Sanne"' in Script.prompts[0]


def test_a_lookup_that_could_not_search_is_a_failure(team):
    Script.give(MatchedPeople, MatchedPeople(succeeded=False, reason="meeting service unreachable"))

    look_up(team, "Sanne")

    assert Inbox.expect(AssignmentFailed).reason == "meeting service unreachable"
