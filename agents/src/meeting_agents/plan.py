"""The MeetingPlan aggregate: what links a meeting, a room booking and a lunch order.

Each service only knows its own id. Nothing in the system records that
*meeting 12 <-> room booking 8 <-> order abc-123*, yet every cancellation and
rebooking needs exactly that mapping. This module owns it.

Two deliberate design choices, both from `design_akgents.md`:

* **Status is derived, not stored.** A stored status field drifts from the ids it
  is supposed to summarise. `MeetingPlan.status` is computed from which ids are
  present, so the two can never disagree. It is a `computed_field`, so it is
  serialised for readers without ever being an input.
* **Compensations are computed here, not decided by a model.** Handing an LLM the
  `cancel_*` tools and asking it to "also cancel the room and lunch" is not an
  authorization policy. `compensations()` returns the exact undo steps, in the
  right order, as plain data.
"""

from __future__ import annotations

import uuid
from datetime import date, time
from enum import Enum

from pydantic import BaseModel, Field, computed_field


class PlanStatus(str, Enum):
    """Where a plan has got to. Derived from the plan's contents - never stored."""

    DRAFT = "DRAFT"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    ROOM_BOOKED = "ROOM_BOOKED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class CompensationStep(str, Enum):
    """An undo action, named after the MCP tool that performs it."""

    CANCEL_ORDER = "cancel_order"
    CANCEL_ROOM_BOOKING = "cancel_room_booking"
    CANCEL_MEETING = "cancel_meeting"


class Compensation(BaseModel):
    """One undo action: which tool to call, and the id to call it with."""

    step: CompensationStep
    reference: str

    model_config = {"frozen": True}


class MeetingPlan(BaseModel):
    """One end-to-end attempt to arrange a meeting with a room and lunch.

    Fields are filled in as the saga progresses; the ids are what make the
    compensating actions possible later.
    """

    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # The request, fixed for the plan's lifetime.
    title: str
    participant_emails: list[str]
    day: date
    duration_minutes: int = Field(default=60, gt=0, le=480)
    location_id: str
    with_lunch: bool = True
    #: What the human asked for, in their own words. Kept on the plan so the
    #: record says what was wanted, not only what arrived (D5).
    lunch_wish: str = ""

    # Filled in by @Scheduler, then approved by the human.
    proposed_start: time | None = None
    proposed_end: time | None = None
    approved: bool = False

    # Service references, each returned by the booking call that created it.
    meeting_id: int | None = None
    room_code: str | None = None
    booking_id: int | None = None
    order_id: str | None = None
    #: What was ordered, in words. Derived from the order, not requested by
    #: anyone: the confirmation has to be readable by the person who asked.
    lunch_summary: str = ""

    cancelled: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> PlanStatus:
        """Derived from the plan's contents, in reverse order of the saga."""
        if self.cancelled:
            return PlanStatus.CANCELLED
        if self.order_id is not None:
            return PlanStatus.CONFIRMED
        if self.booking_id is not None:
            # With lunch, a booked room is only part-way; without it, we are done.
            return PlanStatus.ROOM_BOOKED if self.with_lunch else PlanStatus.CONFIRMED
        if self.meeting_id is not None:
            return PlanStatus.SCHEDULED
        if self.approved:
            return PlanStatus.APPROVED
        if self.proposed_start is not None:
            return PlanStatus.AWAITING_APPROVAL
        return PlanStatus.DRAFT

    @property
    def is_complete(self) -> bool:
        return self.status is PlanStatus.CONFIRMED

    def compensations(self) -> list[Compensation]:
        """The undo steps needed to retract this plan, in reverse booking order.

        Only the bookings that actually happened are included, so this is safe to
        call on a half-finished plan - which is exactly when it is needed most.
        """
        steps: list[Compensation] = []
        if self.order_id is not None:
            steps.append(Compensation(step=CompensationStep.CANCEL_ORDER, reference=self.order_id))
        if self.booking_id is not None:
            steps.append(
                Compensation(step=CompensationStep.CANCEL_ROOM_BOOKING, reference=str(self.booking_id))
            )
        if self.meeting_id is not None:
            steps.append(Compensation(step=CompensationStep.CANCEL_MEETING, reference=str(self.meeting_id)))
        return steps
