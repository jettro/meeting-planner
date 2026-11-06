"""The booking rules (design_guardrails.md §5, GR1, GR5, GR6).

Three layers, from the inside out: each rule on its own; the capability, with the
agent replaced by a stand-in that holds the assignment and records the events;
and a real pydantic-ai run, with the model scripted, so a refusal is seen to
reach the model as a retry and a second one to end the run (spike S1).
"""

from __future__ import annotations

import asyncio
from datetime import date, time
from types import SimpleNamespace
from typing import Any

import pytest
from meeting_agents.guardrails import (
    BOOK_MEETING,
    BOOK_ROOM,
    PLACE_ORDER,
    ApprovalRules,
    BookingRules,
    GuardrailChecked,
    RefusedTwice,
    meeting_rules,
    order_rules,
    room_rules,
)
from meeting_agents.messages import (
    BookFacilitiesAssignment,
    BookMeetingAssignment,
    CancelAssignment,
    OrderLunchAssignment,
    ProposedSlot,
)
from meeting_agents.plan import CompensationStep
from pydantic_ai import Agent, ModelRetry
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.toolsets import FunctionToolset

DAY = date(2031, 9, 16)
SLOT = ProposedSlot(start=time(10, 0), end=time(11, 0))
CARD = BookingRules()

MEETING = BookMeetingAssignment(
    plan_id="p1",
    title="Review",
    participant_emails=["sanne@example.com", "daan@example.com"],
    day=DAY,
    slot=SLOT,
)
ROOM = BookFacilitiesAssignment(
    plan_id="p1",
    title="Review",
    location_id="library",
    day=DAY,
    slot=SLOT,
    headcount=3,
    with_lunch=True,
)
LUNCH = OrderLunchAssignment(plan_id="p1", location_id="library", day=DAY, headcount=3, wish="soup")


def meeting_call(**changes: Any) -> dict[str, Any]:
    args = {
        "participant_emails": ["daan@example.com", "Sanne@example.com"],
        "day": DAY,
        "start": "10:00",
        "end": "11:00",
        "title": "Review",
    }
    return args | changes


def room_call(**changes: Any) -> dict[str, Any]:
    args = {
        "location_id": "library",
        "room_code": "LIB-2",
        "day": "2031-09-16",
        "start": "10:00",
        "end": "11:00",
        "title": "Review",
    }
    return args | changes


def order_call(**changes: Any) -> dict[str, Any]:
    args = {
        "location": "library",
        "delivery_date": DAY,
        "items": [{"item_id": 1, "quantity": 3}, {"item_id": 9, "quantity": 3}],
    }
    return args | changes


# -- the rules on their own -----------------------------------------------------


def test_the_approved_meeting_passes_whatever_the_order_and_case_of_the_emails():
    assert meeting_rules(MEETING, meeting_call(), CARD) == []


def test_a_meeting_on_another_day_is_refused_and_names_both_days():
    broken = meeting_rules(MEETING, meeting_call(day=date(2031, 9, 17)), CARD)
    assert broken == [
        "book_meeting was called for Wednesday 17 September; the approved day is Tuesday 16 September"
    ]


def test_a_meeting_at_another_time_is_refused():
    broken = meeting_rules(MEETING, meeting_call(start="11:00", end="12:00"), CARD)
    assert len(broken) == 2
    assert "the approved start is 10:00" in broken[0]


def test_a_participant_added_or_left_out_is_named():
    broken = meeting_rules(
        MEETING, meeting_call(participant_emails=["sanne@example.com", "eve@example.com"]), CARD
    )
    assert broken == [
        "book_meeting added eve@example.com and left out daan@example.com; "
        "book exactly the approved participants"
    ]


def test_a_timezone_offset_is_read_as_the_service_reads_it():
    """The services take 10:00:00+00:00 as 10:00; refusing it would refuse a correct booking."""
    assert meeting_rules(MEETING, meeting_call(start="10:00:00+00:00", end="11:00Z"), CARD) == []


def test_a_time_that_is_not_a_time_is_refused():
    broken = meeting_rules(MEETING, meeting_call(start="ten"), CARD)
    assert broken == ["book_meeting was called with start 'ten'; the approved start is 10:00"]


def test_the_approved_room_passes_and_the_room_itself_is_the_models_choice():
    assert room_rules(ROOM, room_call(room_code="LIB-9"), CARD) == []


def test_a_room_at_another_location_is_refused():
    broken = room_rules(ROOM, room_call(location_id="meadow"), CARD)
    assert broken == ["book_room was called for location 'meadow'; the approved location is 'library'"]


def test_a_sensible_order_passes():
    assert order_rules(LUNCH, order_call(), CARD) == []


def test_twelve_items_for_three_people_is_a_slip():
    broken = order_rules(LUNCH, order_call(items=[{"item_id": 1, "quantity": 12}]), CARD)
    assert broken == ["place_order holds 12 items for 3 people; at most 3 per person (9) may be ordered"]


def test_the_card_sets_how_many_items_per_person():
    assert order_rules(LUNCH, order_call(), BookingRules(max_items_per_person=1)) != []


def test_an_order_for_another_place_or_day_is_refused():
    broken = order_rules(LUNCH, order_call(location="meadow", delivery_date="2031-09-17"), CARD)
    assert len(broken) == 2


@pytest.mark.parametrize(
    ("rules", "args"),
    [(meeting_rules, meeting_call()), (room_rules, room_call()), (order_rules, order_call())],
)
def test_a_booking_call_with_no_booking_asked_is_refused(rules, args):
    """During a lookup or a cancel, nothing may be booked - not even the right thing."""
    cancel = CancelAssignment(plan_id="p1", step=CompensationStep.CANCEL_MEETING, reference="42")
    for assignment in (None, cancel):
        (reason,) = rules(assignment, args, CARD)
        assert "was asked" in reason


# -- the capability, with the agent stood in for --------------------------------


class StandIn:
    """What the capability needs from the agent: its assignment, its name, the trace."""

    def __init__(self, assignment: Any) -> None:
        self.assignment = assignment
        self.config = SimpleNamespace(name="@FacilityManager")
        self.events: list[GuardrailChecked] = []

    def current_message(self) -> Any:
        return self.assignment

    def notify_event(self, event: GuardrailChecked) -> None:
        self.events.append(event)


def check(capability: ApprovalRules, agent: StandIn, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    ctx = SimpleNamespace(deps=agent)
    return asyncio.run(
        capability.before_tool_execute(ctx, call=None, tool_def=SimpleNamespace(name=tool), args=args)
    )


def test_a_passing_call_goes_through_unchanged_and_is_in_the_trace():
    agent = StandIn(ROOM)
    args = room_call()
    assert check(ApprovalRules(card=CARD), agent, BOOK_ROOM, args) is args
    assert agent.events == [GuardrailChecked(agent="@FacilityManager", tool=BOOK_ROOM, outcome="passed")]


def test_other_tools_are_not_checked_and_not_announced():
    agent = StandIn(ROOM)
    check(ApprovalRules(card=CARD), agent, "facility_list_rooms", {"location_id": "meadow"})
    assert agent.events == []


def test_a_first_refusal_is_a_retry_with_the_rule_and_a_second_ends_the_run():
    agent, capability = StandIn(MEETING), ApprovalRules(card=CARD)

    with pytest.raises(ModelRetry, match="the approved day is Tuesday 16 September"):
        check(capability, agent, BOOK_MEETING, meeting_call(day="2031-09-17"))
    with pytest.raises(RefusedTwice, match="refused 2 times"):
        check(capability, agent, BOOK_MEETING, meeting_call(day="2031-09-17"))

    assert [event.outcome for event in agent.events] == ["refused", "failed"]
    assert "Tuesday 16 September" in agent.events[0].reason


def test_refusals_are_counted_per_run():
    capability = ApprovalRules(card=CARD)
    with pytest.raises(ModelRetry):
        check(capability, StandIn(LUNCH), PLACE_ORDER, order_call(location="meadow"))

    fresh = asyncio.run(capability.for_run(SimpleNamespace()))
    with pytest.raises(ModelRetry):  # a retry again, not the end of the run
        check(fresh, StandIn(LUNCH), PLACE_ORDER, order_call(location="meadow"))


# -- a real run, with the model scripted (spike S1) -----------------------------


def booking_toolset() -> tuple[FunctionToolset, list[dict[str, Any]]]:
    booked: list[dict[str, Any]] = []
    tools = FunctionToolset()

    @tools.tool_plain
    def book_room(location_id: str, room_code: str, day: date, start: str, end: str, title: str) -> str:
        booked.append({"location_id": location_id, "day": day})
        return "booked"

    return tools, booked


def scripted(locations: list[str], seen: list[str]) -> FunctionModel:
    """Call book_room once per location, then stop; record what each retry said."""
    turns = iter(locations)

    def answer(messages, info):
        last = messages[-1].parts[-1]
        if getattr(last, "outcome", None) == "retried":
            seen.append(str(last.content))
        location = next(turns, None)
        if location is None:
            return ModelResponse(parts=[TextPart("done")])
        return ModelResponse(parts=[ToolCallPart("facility_book_room", room_call(location_id=location))])

    return FunctionModel(answer)


def test_in_a_real_run_a_slip_is_corrected_and_only_the_approved_room_is_booked():
    tools, booked = booking_toolset()
    seen: list[str] = []
    agent = Agent(
        scripted(["meadow", "library"], seen),
        toolsets=[tools.prefixed("facility")],
        capabilities=[ApprovalRules(card=CARD)],
        deps_type=StandIn,
        retries=3,
    )

    result = asyncio.run(agent.run("book it", deps=StandIn(ROOM)))

    assert result.output == "done"
    assert booked == [{"location_id": "library", "day": DAY}]
    assert seen and "the approved location is 'library'" in seen[0]


def test_in_a_real_run_a_stubborn_model_books_nothing_and_the_run_ends():
    tools, booked = booking_toolset()
    agent = Agent(
        scripted(["meadow", "meadow"], []),
        toolsets=[tools.prefixed("facility")],
        capabilities=[ApprovalRules(card=CARD)],
        deps_type=StandIn,
        retries=3,
    )

    with pytest.raises(RefusedTwice):
        asyncio.run(agent.run("book it", deps=StandIn(ROOM)))
    assert booked == []
