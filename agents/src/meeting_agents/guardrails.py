"""Guardrails: checks between a model's tool call and the service (design_guardrails.md).

This module holds the first layer, the **rules** (GR1, GR2): what code can know
exactly is never asked of a model. After the person approves Tuesday 10:00 at the
Library, the specialists' models fill in the booking calls themselves; nothing
between the model and the service checked that the call was the approved one.

`BookingRules` is the catalog card - which numbers the rules use - and
`ApprovalRules` the pydantic-ai capability that applies them in
`before_tool_execute`. The approval is the assignment the agent is handling:
`current_message()`, which the framework sets for the whole of a handler and
clears after it, so a check can never read the previous plan (spike S3).

A broken rule is a `ModelRetry` with the rule in plain words, so the model can
correct a slip. A second refusal in the same run ends it (GR5): the exception
leaves `act()`, and the specialist reports it as an `AssignmentFailed` like any
other run that failed. Every check, passed or not, is a `GuardrailChecked` event
in the trace (GR6).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, time
from typing import Any

from akgentic.tool.core import ToolCard
from pydantic import Field
from pydantic_ai import ModelRetry
from pydantic_ai.capabilities import AbstractCapability

from meeting_agents.messages import (
    BookFacilitiesAssignment,
    BookMeetingAssignment,
    OrderLunchAssignment,
)

BOOK_MEETING = "meeting_book_meeting"
BOOK_ROOM = "facility_book_room"
PLACE_ORDER = "catering_place_order"

CHECK = "booking rules"


# -- what the trace shows (GR6) -------------------------------------------------


@dataclass(frozen=True)
class GuardrailChecked:
    """A guardrail looked at a tool call, and what it decided.

    Keep it a module top-level class: the event store persists its dotted name,
    and replay resolves it back to this class. The fields are in the order the
    trace's one-line summary shows them: the outcome first, and the agent last,
    since the trace already shows who sent it.
    """

    outcome: str  # passed | refused | failed
    tool: str
    reason: str = ""
    check: str = CHECK
    agent: str = ""


# -- the card (GR7) -------------------------------------------------------------


class BookingRules(ToolCard):
    """The booking rules, as a card an agent lists under its tools.

    It gives the model no tools; the agent finds it in its config and turns it
    into `ApprovalRules`.
    """

    name: str = "Booking rules"
    description: str = "Checks that a booking call is the one the person approved."
    max_items_per_person: int = Field(
        default=3,
        ge=1,
        description="The most lunch items an order may hold per person: a main, a side, a drink.",
    )
    refusals_per_run: int = Field(
        default=2,
        ge=1,
        description="Refusals in one model run before the run ends as a failure.",
    )

    def get_tools(self) -> list[Callable[..., Any]]:
        return []


def booking_rules_in(tools: list[Any]) -> BookingRules | None:
    """The booking rules an agent's card lists, if it lists them."""
    return next((card for card in tools if isinstance(card, BookingRules)), None)


# -- the rules (§5) -------------------------------------------------------------


def _day(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def _clock(value: Any) -> time | None:
    """A local clock reading, read as leniently as the services read it.

    The services take `10:00:00+00:00` as 10:00 (an offset means nothing at a
    venue), so the rules must too, or they would refuse what would be booked
    correctly.
    """
    text = str(value).strip().removesuffix("Z")
    for marker in ("+", "-"):
        head = text.split(marker, 1)[0]
        if head != text and ":" in head:
            text = head
    parts = text.split(":")
    if len(parts) not in (2, 3) or not all(part.isdigit() for part in parts):
        return None
    try:
        return time(int(parts[0]), int(parts[1]))
    except ValueError:
        return None


def _say_day(day: date) -> str:
    return f"{day:%A} {day.day} {day:%B}"


def _say_clock(value: time) -> str:
    return f"{value:%H:%M}"


def _same_day(tool: str, args: dict[str, Any], key: str, approved: date) -> list[str]:
    called = _day(args.get(key))
    if called == approved:
        return []
    shown = _say_day(called) if called else repr(args.get(key))
    return [f"{tool} was called for {shown}; the approved day is {_say_day(approved)}"]


def _same_times(tool: str, args: dict[str, Any], start: time, end: time) -> list[str]:
    broken = []
    for key, approved in (("start", start), ("end", end)):
        called = _clock(args.get(key))
        if called != approved:
            shown = _say_clock(called) if called else repr(args.get(key))
            broken.append(
                f"{tool} was called with {key} {shown}; the approved {key} is {_say_clock(approved)}"
            )
    return broken


def _emails(values: Any) -> set[str]:
    return {str(value).strip().lower() for value in values or []}


def meeting_rules(assignment: Any, args: dict[str, Any], card: BookingRules) -> list[str]:
    """`book_meeting`: the approved people, day and slot."""
    tool = "book_meeting"
    if not isinstance(assignment, BookMeetingAssignment):
        return [f"{tool} was called, but no meeting was asked to be booked here"]
    broken = []
    called, approved = _emails(args.get("participant_emails")), _emails(assignment.participant_emails)
    if called != approved:
        said = []
        if extra := sorted(called - approved):
            said.append(f"added {', '.join(extra)}")
        if missing := sorted(approved - called):
            said.append(f"left out {', '.join(missing)}")
        broken.append(f"{tool} {' and '.join(said)}; book exactly the approved participants")
    broken += _same_day(tool, args, "day", assignment.day)
    broken += _same_times(tool, args, assignment.slot.start, assignment.slot.end)
    return broken


def room_rules(assignment: Any, args: dict[str, Any], card: BookingRules) -> list[str]:
    """`book_room`: the approved location, day and slot. The room is the model's choice."""
    tool = "book_room"
    if not isinstance(assignment, BookFacilitiesAssignment):
        return [f"{tool} was called, but no room was asked to be booked here"]
    broken = []
    if str(args.get("location_id", "")).strip() != assignment.location_id:
        broken.append(
            f"{tool} was called for location {args.get('location_id')!r}; "
            f"the approved location is {assignment.location_id!r}"
        )
    broken += _same_day(tool, args, "day", assignment.day)
    broken += _same_times(tool, args, assignment.slot.start, assignment.slot.end)
    return broken


def order_rules(assignment: Any, args: dict[str, Any], card: BookingRules) -> list[str]:
    """`place_order`: the meeting's location and date, and no more than is sensible."""
    tool = "place_order"
    if not isinstance(assignment, OrderLunchAssignment):
        return [f"{tool} was called, but no lunch was asked to be ordered here"]
    broken = []
    if str(args.get("location", "")).strip() != assignment.location_id:
        broken.append(
            f"{tool} was called for location {args.get('location')!r}; "
            f"the meeting is at {assignment.location_id!r}"
        )
    broken += _same_day(tool, args, "delivery_date", assignment.day)
    items = args.get("items") or []
    count = sum(int(item.get("quantity", 0)) for item in items if isinstance(item, dict))
    most = assignment.headcount * card.max_items_per_person
    if count > most:
        broken.append(
            f"{tool} holds {count} items for {assignment.headcount} people; "
            f"at most {card.max_items_per_person} per person ({most}) may be ordered"
        )
    return broken


RULES: dict[str, Callable[[Any, dict[str, Any], BookingRules], list[str]]] = {
    BOOK_MEETING: meeting_rules,
    BOOK_ROOM: room_rules,
    PLACE_ORDER: order_rules,
}


# -- the capability (GR1, GR5) --------------------------------------------------


class RefusedTwice(RuntimeError):
    """A model kept making a call the rules refuse; the run ends here."""


@dataclass
class ApprovalRules(AbstractCapability[Any]):
    """Refuse a booking call that is not the approved one.

    `ctx.deps` is the agent itself (`BaseAgent.act()` runs with `deps=self`):
    its `current_message()` is the assignment, and `notify_event()` reaches the
    trace. One instance per run (`for_run`), so refusals are counted per run.
    """

    card: BookingRules = dataclasses.field(default_factory=BookingRules)
    refusals: int = 0

    async def for_run(self, ctx: Any) -> ApprovalRules:
        return dataclasses.replace(self, refusals=0)

    async def before_tool_execute(
        self, ctx: Any, *, call: Any, tool_def: Any, args: dict[str, Any]
    ) -> dict[str, Any]:
        rules = RULES.get(tool_def.name)
        if rules is None:
            return args

        agent = ctx.deps
        assignment = agent.current_message() if hasattr(agent, "current_message") else None
        broken = rules(assignment, args, self.card)
        reason = "; ".join(broken)

        if not broken:
            _announce(agent, tool_def.name, "passed")
            return args

        self.refusals += 1
        if self.refusals >= self.card.refusals_per_run:
            _announce(agent, tool_def.name, "failed", reason)
            raise RefusedTwice(f"refused {self.refusals} times by the booking rules: {reason}")
        _announce(agent, tool_def.name, "refused", reason)
        raise ModelRetry(f"Refused by the booking rules: {reason}. Call it again with the approved values.")


def _announce(agent: Any, tool: str, outcome: str, reason: str = "") -> None:
    name = getattr(getattr(agent, "config", None), "name", "") or ""
    notify = getattr(agent, "notify_event", None)
    if notify is not None:
        notify(GuardrailChecked(agent=name, tool=tool, outcome=outcome, reason=reason))
