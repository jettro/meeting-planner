"""The three LLM specialists: @Scheduler, @FacilityManager and @Catering.

Each one owns a single service and does the part of the job that genuinely
needs judgement - reading a menu, picking a room, deciding which window to
report. Everything around that is deterministic and lives elsewhere.

The shape of every handler is the same, and deliberately so:

    assignment in  ->  act(assignment, OutputType)  ->  typed message out

The model is given a message to reason about and a type to answer in. It never
decides *who* to tell, and it never writes to the plan: the handler sends the
reply and @PlanRepository does the writing. A model that could not do its job
says so through `succeeded`, and the handler turns that into an
`AssignmentFailed` - so a failure is reported as a failure rather than as a
plausible-looking id.
"""

from __future__ import annotations

import logging
from datetime import date as date_type
from datetime import datetime, timedelta
from typing import TypeVar

from akgentic.agent import BaseAgent
from akgentic.agent.config import AgentConfig, AgentState
from akgentic.core import ActorAddress, Akgent
from pydantic import BaseModel

from meeting_agents.messages import (
    AssignmentFailed,
    BookFacilitiesAssignment,
    BookMeetingAssignment,
    FacilitiesBooked,
    FindSlotsAssignment,
    LunchOrdered,
    MeetingBooked,
    OrderLunchAssignment,
    ProposedSlot,
    SlotsFound,
)
from meeting_agents.outputs import (
    BookedMeeting,
    BookedRoom,
    ClockError,
    FoundSlots,
    OrderedLunch,
    parse_clock,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class SpecialistAgent(BaseAgent):
    """Shared failure handling for an agent that runs one assignment at a time."""

    def attempt(self, message, output_type: type[T], plan_id: str, sender) -> T | None:
        """Run the model, or report the failure upstream and answer `None`.

        An exception here is not exceptional in the ordinary sense - a model
        run can fail for a dozen reasons, and every one of them must reach the
        coordinator as a plain `AssignmentFailed` rather than die in this
        actor's thread and leave a plan waiting forever.
        """
        try:
            return self.act(message, output_type)
        except Exception as exc:  # noqa: BLE001 - deliberately broad; see docstring
            # The traceback is a debug detail, not news for the person at the
            # terminal: a provider timeout used to bury the one line that
            # mattered under two hundred lines of frames. The reason travels to
            # the coordinator and is reported there; `--verbose` still has the
            # full stack for when the cause is not obvious.
            logger.error("[%s] assignment failed: %s", self.config.name, exc)
            logger.debug("[%s] assignment failed", self.config.name, exc_info=True)
            self.fail(plan_id, f"{type(exc).__name__}: {exc}", sender)
            return None

    def fail(self, plan_id: str, reason: str, recipient: ActorAddress | None) -> None:
        if recipient is not None:
            self.send(recipient, AssignmentFailed(plan_id=plan_id, reason=reason))


MAX_CANDIDATES = 3


def meeting_slots(
    windows: list[ProposedSlot], duration_minutes: int, limit: int = MAX_CANDIDATES
) -> list[ProposedSlot]:
    """Turn free *windows* into slots of exactly `duration_minutes`.

    `find_common_slots` answers with windows - "everyone is free from 09:00 to
    17:00" - and the prompt tells the model to relay them untouched, because
    arithmetic is where a model goes wrong. But a window is not a meeting: a
    live run proposed 09:00-17:00 for a one-hour meeting, and nothing between
    the agent and the booking call disagreed. Cutting windows into bookable
    slots is pure arithmetic, so it happens here where it can be tested.

    Slots start at the window's own start and step forward by the meeting's
    length, so every one of them fits inside the window it came from. The list
    is capped because these become a question for a human, and a choice of
    three is a question while a choice of eight is a chore.
    """
    step = timedelta(minutes=duration_minutes)
    day = date_type.min
    slots: list[ProposedSlot] = []

    for window in windows:
        start = datetime.combine(day, window.start)
        closes = datetime.combine(day, window.end)
        while start + step <= closes and len(slots) < limit:
            finish = start + step
            slots.append(ProposedSlot(start=start.time(), end=finish.time()))
            start = finish
        if len(slots) >= limit:
            break

    return slots


class Scheduler(SpecialistAgent):
    """Owns people's agendas, through the meeting service and nothing else."""

    def receiveMsg_FindSlotsAssignment(  # noqa: N802
        self, message: FindSlotsAssignment, sender: ActorAddress
    ) -> None:
        found = self.attempt(message, FoundSlots, message.plan_id, sender)
        if found is None:
            return
        if not found.succeeded:
            self.fail(message.plan_id, found.reason or "could not search agendas", sender)
            return

        try:
            windows = [
                ProposedSlot(start=parse_clock(s.start), end=parse_clock(s.end))
                for s in found.slots
            ]
        except ClockError as exc:
            self.fail(message.plan_id, str(exc), sender)
            return

        candidates = meeting_slots(windows, message.duration_minutes)
        if windows and not candidates:
            self.fail(
                message.plan_id,
                f"no common window is long enough for {message.duration_minutes} minutes",
                sender,
            )
            return

        self.send(sender, SlotsFound(plan_id=message.plan_id, candidates=candidates))

    def receiveMsg_BookMeetingAssignment(  # noqa: N802
        self, message: BookMeetingAssignment, sender: ActorAddress
    ) -> None:
        booked = self.attempt(message, BookedMeeting, message.plan_id, sender)
        if booked is None:
            return
        if not booked.succeeded or booked.meeting_id is None:
            self.fail(message.plan_id, booked.reason or "the meeting was not booked", sender)
            return

        self.send(
            sender, MeetingBooked(plan_id=message.plan_id, meeting_id=booked.meeting_id)
        )


class FacilityManagerConfig(AgentConfig):
    """Who to ask for lunch, and who to report back to."""

    catering_name: str = "@Catering"
    coordinator_name: str = "@Coordinator"


class PendingFacilities(BaseModel):
    """A room that is booked while its lunch order is still being placed."""

    room_code: str
    booking_id: int


class FacilityManager(SpecialistAgent, Akgent[FacilityManagerConfig, AgentState]):
    """Books rooms, and owns lunch as part of arranging a meeting (D2).

    The coordinator asks for *facilities* and is told when they are ready. That
    lunch is involved at all, and that someone else orders it, is this agent's
    business - which is why @Catering reports here and not to the coordinator.
    """

    #: Narrows the inherited `config` to this agent's own type. The framework
    #: already builds it from `agent_class`; this tells the type checker so.
    config: FacilityManagerConfig

    def on_start(self) -> None:
        super().on_start()
        # Deliberately an instance attribute, not agent state. `AgentState`
        # carries the backstory this agent reasons with, so replacing it with a
        # subclass would silently drop the system prompt. This is in-flight
        # bookkeeping for the seconds between booking a room and hearing back
        # about lunch - it is not part of the agent's replayable state, and the
        # durable record of a plan belongs to @PlanRepository regardless.
        self._pending: dict[str, PendingFacilities] = {}

    def receiveMsg_BookFacilitiesAssignment(  # noqa: N802
        self, message: BookFacilitiesAssignment, sender: ActorAddress
    ) -> None:
        booked = self.attempt(message, BookedRoom, message.plan_id, sender)
        if booked is None:
            return
        if not booked.succeeded or booked.room_code is None or booked.booking_id is None:
            self.fail(message.plan_id, booked.reason or "no room was booked", sender)
            return

        if not message.with_lunch:
            self.send(
                sender,
                FacilitiesBooked(
                    plan_id=message.plan_id,
                    room_code=booked.room_code,
                    booking_id=booked.booking_id,
                ),
            )
            return

        catering = self.get_team_member(self.config.catering_name)
        if catering is None:
            self.fail(message.plan_id, f"no {self.config.catering_name} on the team", sender)
            return

        self._pending[message.plan_id] = PendingFacilities(
            room_code=booked.room_code, booking_id=booked.booking_id
        )

        self.send(
            catering,
            OrderLunchAssignment(
                plan_id=message.plan_id,
                location_id=message.location_id,
                day=message.day,
                headcount=message.headcount,
            ),
        )

    def receiveMsg_LunchOrdered(  # noqa: N802
        self, message: LunchOrdered, sender: ActorAddress
    ) -> None:
        """Lunch is placed - now the facilities as a whole are ready."""
        room = self._take_pending(message.plan_id)
        if room is None:
            return

        coordinator = self.get_team_member(self.config.coordinator_name)
        if coordinator is None:
            logger.error("[%s] no %s to report to", self.config.name, self.config.coordinator_name)
            return

        self.send(
            coordinator,
            FacilitiesBooked(
                plan_id=message.plan_id,
                room_code=room.room_code,
                booking_id=room.booking_id,
                order_id=message.order_id,
            ),
        )

    def receiveMsg_AssignmentFailed(  # noqa: N802
        self, message: AssignmentFailed, sender: ActorAddress
    ) -> None:
        """@Catering could not order lunch.

        The room is already booked at this point, so this is the first place a
        compensation is genuinely owed. Running it is iteration 2; what matters
        now is that the coordinator is told rather than left waiting, and that
        the booked room is named in the reason so it is never silently lost.
        """
        room = self._take_pending(message.plan_id)
        detail = f" (room {room.room_code}, booking {room.booking_id} still booked)" if room else ""
        coordinator = self.get_team_member(self.config.coordinator_name)
        self.fail(message.plan_id, f"{message.reason}{detail}", coordinator)

    def _take_pending(self, plan_id: str) -> PendingFacilities | None:
        room = self._pending.pop(plan_id, None)
        if room is None:
            logger.error("[%s] no pending room for plan %s", self.config.name, plan_id)
        return room


class Catering(SpecialistAgent):
    """Orders lunch, through the nomnom service and nothing else."""

    def receiveMsg_OrderLunchAssignment(  # noqa: N802
        self, message: OrderLunchAssignment, sender: ActorAddress
    ) -> None:
        ordered = self.attempt(message, OrderedLunch, message.plan_id, sender)
        if ordered is None:
            return
        if not ordered.succeeded or ordered.order_id is None:
            self.fail(message.plan_id, ordered.reason or "no lunch was ordered", sender)
            return

        self.send(sender, LunchOrdered(plan_id=message.plan_id, order_id=ordered.order_id))
