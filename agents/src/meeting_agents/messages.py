"""The typed messages the team exchanges.

A message is an assignment: it names what is being asked and carries exactly the
facts needed to do it. That is the whole reason the coordinator can be
deterministic - it never has to phrase a request, only fill one in.

Two rules from `design_akgents.md` §4.2 are enforced here rather than remembered:

* **Every question to a human carries an explicit `recipient`.** A GUI needs to
  know which plan a prompt belongs to without inspecting actor plumbing, so the
  plan id travels on the message itself.
* **Assignments bound for a model implement `rendering()`.** That is the entire
  `LlmRenderable` contract (`act()` needs a prompt and nothing else), so these
  messages can be handed to an LLM agent without also joining a mailbox.

Messages are serialised into the event store, so they carry plain data only -
never a live store, a client, or a key.
"""

from __future__ import annotations

from datetime import date, time

from akgentic.core.messages import Message
from pydantic import BaseModel, Field, model_validator

from meeting_agents.plan import Compensation, MeetingPlan


class ProposedSlot(BaseModel):
    """One candidate window in which every participant is free."""

    start: time
    end: time

    model_config = {"frozen": True}

    def label(self) -> str:
        return f"{self.start.strftime('%H:%M')}-{self.end.strftime('%H:%M')}"


# --------------------------------------------------------------------------
# Human -> @Coordinator
# --------------------------------------------------------------------------


class PlanMeetingRequest(Message):
    """The v1 entry point (§7.1): structured, not free text.

    Free-format input is explicitly planned, and arrives as an *additional*
    message type parsed into this one - never by loosening these fields.
    """

    title: str
    participant_emails: list[str]
    day: date
    duration_minutes: int = Field(default=60, gt=0, le=480)
    location_id: str
    with_lunch: bool = True

    def to_plan(self) -> MeetingPlan:
        """The aggregate this request starts. The plan id is created here."""
        return MeetingPlan(
            title=self.title,
            participant_emails=list(self.participant_emails),
            day=self.day,
            duration_minutes=self.duration_minutes,
            location_id=self.location_id,
            with_lunch=self.with_lunch,
        )


class SlotApprovalDecision(Message):
    """The human's answer to the one approval gate in the flow (D4)."""

    plan_id: str
    approved: bool
    slot: ProposedSlot | None = None

    @model_validator(mode="after")
    def _approval_names_its_slot(self) -> SlotApprovalDecision:
        """An approval without a slot is rejected here rather than downstream.

        The coordinator reads a missing slot as a refusal, so such a message
        would quietly cancel the plan and tell the human it was not approved -
        a confusing lie. A client that gets the field name wrong should hear
        about it at the point of the mistake.
        """
        if self.approved and self.slot is None:
            raise ValueError("an approved decision must carry the slot it approved")
        return self


# --------------------------------------------------------------------------
# @Coordinator -> human
# --------------------------------------------------------------------------


class SlotApprovalRequest(Message):
    """Ask the human to approve a time slot. Nothing has been booked yet (D4).

    `plan_id` is what lets an answer be correlated back to a plan by a CLI, a
    websocket, or a REST call, without any of them knowing about actors.
    """

    plan_id: str
    title: str
    day: date
    candidates: list[ProposedSlot]

    def question(self) -> str:
        options = ", ".join(c.label() for c in self.candidates)
        return f"'{self.title}' on {self.day.isoformat()} - approve a slot: {options}"


class PlanCompleted(Message):
    """The plan reached CONFIRMED. Carries the ids, so a UI can show them."""

    plan: MeetingPlan


class PlanFailed(Message):
    """The plan could not be completed, and what it left behind."""

    plan: MeetingPlan
    reason: str
    #: What is still booked and needs undoing - *not* what has been undone.
    #: Running these is iteration 2 (§7.1); until then a failure at least says
    #: plainly what it left behind. A live run read the old name, `compensated`,
    #: as "already cancelled" and trusted a meeting to be gone when it was not.
    outstanding: list[Compensation] = Field(default_factory=list)


# --------------------------------------------------------------------------
# @Coordinator -> specialists  (assignments: rendered for a model)
# --------------------------------------------------------------------------


class FindSlotsAssignment(Message):
    """@Scheduler: when are all of these people free?"""

    plan_id: str
    participant_emails: list[str]
    day: date
    duration_minutes: int

    def rendering(self) -> str:
        people = ", ".join(self.participant_emails)
        return (
            f"Find every {self.duration_minutes}-minute window on "
            f"{self.day.isoformat()} when all of these people are free: {people}. "
            "Use your find_common_slots tool. Report the windows you find."
        )


class SlotsFound(Message):
    """@Scheduler -> @Coordinator."""

    plan_id: str
    candidates: list[ProposedSlot]


class BookMeetingAssignment(Message):
    """@Scheduler: the human approved this slot; put it in the agendas."""

    plan_id: str
    title: str
    participant_emails: list[str]
    day: date
    slot: ProposedSlot

    def rendering(self) -> str:
        people = ", ".join(self.participant_emails)
        return (
            f"Book '{self.title}' on {self.day.isoformat()} from "
            f"{self.slot.start.strftime('%H:%M')} to {self.slot.end.strftime('%H:%M')} "
            f"for: {people}. Report the meeting id you get back."
        )


class MeetingBooked(Message):
    """@Scheduler -> @Coordinator."""

    plan_id: str
    meeting_id: int


class BookFacilitiesAssignment(Message):
    """@FacilityManager: a room, and lunch if asked for.

    The coordinator does not say where lunch comes from - that is the facility
    manager's business, and @Catering reports to it (D2).
    """

    plan_id: str
    title: str
    location_id: str
    day: date
    slot: ProposedSlot
    headcount: int
    with_lunch: bool

    def rendering(self) -> str:
        return (
            f"Book a room for {self.headcount} people at location "
            f"{self.location_id} on {self.day.isoformat()} from "
            f"{self.slot.start.strftime('%H:%M')} to {self.slot.end.strftime('%H:%M')}. "
            f"The meeting is called '{self.title}'; book it under that title so the "
            "room calendar says what the room is for. "
            "Report the room code and booking id you get back."
        )


class FacilitiesBooked(Message):
    """@FacilityManager -> @Coordinator."""

    plan_id: str
    room_code: str
    booking_id: int
    order_id: str | None = None


class OrderLunchAssignment(Message):
    """@FacilityManager -> @Catering."""

    plan_id: str
    location_id: str
    day: date
    headcount: int

    def rendering(self) -> str:
        return (
            f"Order lunch for {self.headcount} people at location "
            f"{self.location_id} on {self.day.isoformat()}. Choose from the menu "
            "available there. Report the order id you get back."
        )


class LunchOrdered(Message):
    """@Catering -> @FacilityManager."""

    plan_id: str
    order_id: str


class AssignmentFailed(Message):
    """Any specialist -> its requester. Triggers compensation upstream."""

    plan_id: str
    reason: str


# --------------------------------------------------------------------------
# @PlanRepository
# --------------------------------------------------------------------------


class SavePlan(Message):
    """Persist the plan. The repository owns the store; nobody else writes."""

    plan: MeetingPlan


class LoadPlan(Message):
    """Fetch a plan by id."""

    plan_id: str


class PlanSnapshot(Message):
    """@PlanRepository -> requester. `plan` is None when the id is unknown."""

    plan_id: str
    plan: MeetingPlan | None = None


#: Every message the team may exchange. `TeamCard.message_types` is a list, so
#: adding free-text input later is an addition here, not a change anywhere else.
MESSAGE_TYPES: list[type] = [
    PlanMeetingRequest,
    SlotApprovalDecision,
    SlotApprovalRequest,
    PlanCompleted,
    PlanFailed,
    FindSlotsAssignment,
    SlotsFound,
    BookMeetingAssignment,
    MeetingBooked,
    BookFacilitiesAssignment,
    FacilitiesBooked,
    OrderLunchAssignment,
    LunchOrdered,
    AssignmentFailed,
    SavePlan,
    LoadPlan,
    PlanSnapshot,
]
