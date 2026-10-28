"""@Coordinator: the deterministic actor that drives the booking saga.

This agent has no model and no MCP tool, and that is the point (D1). The order
of the steps, which step follows which answer, and what has to be undone when
one fails are all facts the system already knows - so nothing here requires
judgement, and nothing here should reach a model. The specialists do the parts
that genuinely need one: reading a menu, choosing a room, phrasing a search.

**The team is the meeting** (`design_durability.md`). One team arranges one
meeting, and this agent's state is the only record of it: which meeting, room
booking and lunch order belong together, and what the saga is waiting for. The
state is snapshotted by the framework on every change and restored when a
stopped team is revived, so there is no separate plan store to keep in step.

Three properties matter beyond correctness:

* **It never blocks on the human.** The approval gate is a message out and a
  separate message in. A blocking `input()` here is exactly the mistake the
  infra post warns about - it is what had to be thrown away to get a server.
  Because the wait is just an absent message, a CLI, a websocket and a REST
  call all drive this same actor unchanged - and a revived team picks the wait
  up where it was left.
* **State first, then send** (R8). Every handler records what changed before it
  sends the message that reports it. The orchestrator handles one agent's
  telemetry in order, so anyone reading the event stream sees "booked" only
  after the snapshot that says so has been written.
* **It addresses everyone by name, from config.** No member's address is
  captured in state, so a restored team finds its members again by name.
"""

from __future__ import annotations

import logging

from akgentic.core import ActorAddress, Akgent, BaseConfig, BaseState

from meeting_agents.messages import (
    AssignmentFailed,
    BookFacilitiesAssignment,
    BookMeetingAssignment,
    CancelAssignment,
    Cancelled,
    CancelPlanRequest,
    FacilitiesBooked,
    FindLocationAssignment,
    FindSlotsAssignment,
    LocationFound,
    LunchApprovalDecision,
    LunchApprovalRequest,
    MeetingBooked,
    PlanCancelled,
    PlanCompleted,
    PlanFailed,
    PlanMeetingRequest,
    ProposedSlot,
    SlotApprovalDecision,
    SlotApprovalRequest,
    SlotsFound,
)
from meeting_agents.plan import Compensation, CompensationStep, MeetingPlan

logger = logging.getLogger(__name__)


class CoordinatorConfig(BaseConfig):
    """Team member names, so routing is configuration rather than code."""

    name: str = "@Coordinator"
    role: str = "Coordinator"
    human_name: str = "@Human"
    scheduler_name: str = "@Scheduler"
    facility_name: str = "@FacilityManager"


class CoordinatorState(BaseState):
    """The meeting, and what the saga is waiting for.

    This is the record (R2): there is no other copy of the plan anywhere. It is
    plain data so the framework can snapshot it, and it holds one meeting
    because one team arranges one meeting (G3).
    """

    #: The meeting. `None` until a request arrives.
    plan: MeetingPlan | None = None
    #: The slots put to the human. Non-empty exactly while the slot gate is open.
    candidates: list[ProposedSlot] = []
    #: True while the lunch gate is open. A request that settled lunch up front
    #: never sets it, which is what keeps a scripted run from blocking (D9).
    awaiting_lunch: bool = False
    #: Why the meeting could not be arranged, once it could not. A failed plan
    #: is finished - it is never resumed, though what it booked can be released.
    failure: str = ""
    #: Releases still to run, head first. The head has been sent and is being
    #: waited on, so its `Cancelled` pops it and sends the next.
    cancelling: list[Compensation] = []
    #: What went wrong while releasing, one readable line per failed step.
    #: Kept after the cancellation finishes: it is the report of what may still
    #: be held, and the only place that says so.
    cancel_failures: list[str] = []

    def waiting_for_the_human(self) -> bool:
        """True when the next move is the human's: a gate is open (R6)."""
        if self.plan is None or self.plan.cancelled or self.failure:
            return False
        return bool(self.candidates) or self.awaiting_lunch


class Coordinator(Akgent[CoordinatorConfig, CoordinatorState]):
    """Sequences the saga: slots -> approval -> meeting -> room -> lunch.

    And the other direction: a cancellation releases the lunch, the room and
    the meeting, in that order. There is no third thing - this system has no
    way to *change* a plan, by decision. A meeting that is wrong is cancelled
    and a new one is planned.
    """

    def on_start(self) -> None:
        # Attach the observer here, once. `init_state` carries the observer of
        # the state it replaces and never creates one, so a state started
        # without it is never snapshotted - and a restored team would bring
        # this coordinator back empty (design_durability.md §1).
        self.state = CoordinatorState()
        self.state.observer(self)

    # -- helpers ---------------------------------------------------------

    def _member(self, name: str) -> ActorAddress | None:
        address = self.get_team_member(name)
        if address is None:
            logger.error("[%s] no team member named %s", self.config.name, name)
        return address

    def _update(self, **changes: object) -> None:
        """Replace the state. Every change is a snapshot, so this is the write."""
        self.init_state(self.state.model_copy(update=changes))

    def _plan(self, plan_id: str) -> MeetingPlan | None:
        """The meeting, if `plan_id` names it. Anything else is a stale message."""
        plan = self.state.plan
        if plan is None or plan.plan_id != plan_id:
            logger.error("[%s] unknown plan %s", self.config.name, plan_id)
            return None
        return plan

    def _being_cancelled(self, plan: MeetingPlan) -> bool:
        """Cancelled, or on its way there. Either way, nothing more is booked."""
        return plan.cancelled or bool(self.state.cancelling)

    def _fail(self, plan: MeetingPlan, reason: str) -> None:
        """Record the failure, then report it with what is still booked.

        The undo steps are reported, not run. A cancellation is something the
        human asks for (`CancelPlanRequest`), and a failure that quietly
        released three bookings on its own would hide the thing worth seeing -
        the mess a half-finished saga leaves behind, and then the undoing of it.
        """
        logger.warning("[%s] plan %s failed: %s", self.config.name, plan.plan_id, reason)
        self._update(plan=plan, failure=reason, candidates=[], awaiting_lunch=False)
        human = self._member(self.config.human_name)
        if human is not None:
            self.send(human, PlanFailed(plan=plan, reason=reason, outstanding=plan.compensations()))

    # -- human -> coordinator --------------------------------------------

    def receiveMsg_PlanMeetingRequest(  # noqa: N802
        self, message: PlanMeetingRequest, sender: ActorAddress
    ) -> None:
        """Start the meeting: find the place if it was described, then the time."""
        plan = message.to_plan()
        if self.state.plan is not None:
            # One team, one meeting. Answered rather than dropped, so a client
            # that reused a team hears why nothing happened.
            human = self._member(self.config.human_name)
            if human is not None:
                self.send(
                    human,
                    PlanFailed(
                        plan=plan,
                        reason="this team already arranges a meeting; start a new team for another",
                    ),
                )
            return

        self._update(plan=plan, awaiting_lunch=not message.lunch_is_settled())

        if plan.location_id:
            self._find_slots(plan)
            return

        # The place was described, not named. @FacilityManager is the only
        # agent that sees the locations, so it chooses - before the slots, so
        # the human approves the place together with the time (§13.1).
        facility = self._member(self.config.facility_name)
        if facility is None:
            self._fail(plan, f"no {self.config.facility_name} to choose a location")
            return
        self.send(
            facility,
            FindLocationAssignment(
                plan_id=plan.plan_id,
                wish=plan.location_wish,
                headcount=len(plan.participant_emails),
            ),
        )

    def receiveMsg_SlotApprovalDecision(  # noqa: N802
        self, message: SlotApprovalDecision, sender: ActorAddress
    ) -> None:
        """The first human decision in the flow (D4).

        Nothing has been booked at this point, so a rejection costs nothing to
        honour - there is no compensation to run.
        """
        plan = self._plan(message.plan_id)
        if plan is None:
            return
        if not self.state.candidates:
            # The gate is not open: answered already, or the meeting was called
            # off. A stale tab must not book anything.
            logger.warning("[%s] no slot question open for %s", self.config.name, plan.plan_id)
            return

        if not message.approved or message.slot is None:
            self._fail(plan, "the proposed time slot was not approved")
            return

        plan = plan.model_copy(
            update={
                "proposed_start": message.slot.start,
                "proposed_end": message.slot.end,
                "approved": True,
            }
        )
        self._update(plan=plan, candidates=[])

        if self.state.awaiting_lunch:
            self._ask_about_lunch(plan)
            return
        self._book_the_meeting(plan)

    def receiveMsg_LunchApprovalDecision(  # noqa: N802
        self, message: LunchApprovalDecision, sender: ActorAddress
    ) -> None:
        """The second gate (D9), and the last thing asked before anything is booked.

        Declining lunch is not a failure - it is a smaller meeting. Only the
        slot can fail a plan by being refused, because a meeting with no agreed
        time is not a meeting.
        """
        plan = self._plan(message.plan_id)
        if plan is None:
            return
        if not self.state.awaiting_lunch:
            logger.warning("[%s] no lunch question open for %s", self.config.name, plan.plan_id)
            return

        plan = plan.model_copy(
            update={
                "with_lunch": message.wants_lunch,
                "lunch_wish": message.wish if message.wants_lunch else "",
            }
        )
        self._update(plan=plan, awaiting_lunch=False)
        self._book_the_meeting(plan)

    def receiveMsg_CancelPlanRequest(  # noqa: N802
        self, message: CancelPlanRequest, sender: ActorAddress
    ) -> None:
        """Call the meeting off, releasing everything it holds.

        It arrives at the team that made the meeting (R4) - revived first if it
        had stopped, which is why this coordinator can simply look at its own
        state. A booking that is still in flight is released when it lands
        (R5), so the cancel never has to wait for it.
        """
        plan = self._plan(message.plan_id)
        if plan is None:
            return

        if plan.cancelled:
            # Cancelling twice would try to release ids the services have
            # already let go, which reads as a failure and would make a
            # correct, harmless repeat look like a problem.
            self._report_cancelled(plan)
            return
        if self.state.cancelling:
            logger.info("[%s] plan %s is already being cancelled", self.config.name, plan.plan_id)
            return

        steps = plan.compensations()
        logger.info("[%s] cancelling plan %s: %d step(s)", self.config.name, plan.plan_id, len(steps))
        self._update(candidates=[], awaiting_lunch=False, cancel_failures=[])
        self._release(steps)

    # -- saga steps -------------------------------------------------------

    def _find_slots(self, plan: MeetingPlan) -> None:
        """Ask @Scheduler for the windows in which everybody is free."""
        scheduler = self._member(self.config.scheduler_name)
        if scheduler is None:
            self._fail(plan, f"no {self.config.scheduler_name} on the team")
            return

        self.send(
            scheduler,
            FindSlotsAssignment(
                plan_id=plan.plan_id,
                participant_emails=plan.participant_emails,
                day=plan.day,
                duration_minutes=plan.duration_minutes,
            ),
        )

    def _ask_about_lunch(self, plan: MeetingPlan) -> None:
        """Put the lunch question to the human and return, holding no thread."""
        human = self._member(self.config.human_name)
        if human is None:
            self._fail(plan, f"no {self.config.human_name} to ask about lunch")
            return

        self.send(
            human,
            LunchApprovalRequest(
                plan_id=plan.plan_id,
                title=plan.title,
                day=plan.day,
                headcount=len(plan.participant_emails),
                recipient=human,
            ),
        )

    def _book_the_meeting(self, plan: MeetingPlan) -> None:
        """Put the approved slot in the agendas. The first thing that is real."""
        if plan.proposed_start is None or plan.proposed_end is None:
            self._fail(plan, "no approved slot recorded for this plan")
            return

        scheduler = self._member(self.config.scheduler_name)
        if scheduler is None:
            self._fail(plan, f"no {self.config.scheduler_name} on the team")
            return

        self.send(
            scheduler,
            BookMeetingAssignment(
                plan_id=plan.plan_id,
                title=plan.title,
                participant_emails=plan.participant_emails,
                day=plan.day,
                slot=ProposedSlot(start=plan.proposed_start, end=plan.proposed_end),
            ),
        )

    # -- cancelling -------------------------------------------------------

    def _release(self, steps: list[Compensation]) -> None:
        """Queue releases behind any still running, and start if nothing is.

        One queue serves both a cancellation and a booking that landed after
        one (R5), so both are released one at a time and both end in the same
        report.
        """
        running = bool(self.state.cancelling)
        self._update(cancelling=[*self.state.cancelling, *steps])
        if not running:
            self._run_next_cancellation()

    def _run_next_cancellation(self) -> None:
        """Send the step at the head of the queue, or finish.

        One at a time, and in `compensations()` order - reverse booking order,
        which is the order the services expect and the only order in which a
        partial result can be described as a sentence.
        """
        steps = self.state.cancelling
        if not steps:
            self._finish_cancelling()
            return

        plan = self.state.plan
        assert plan is not None, "a release always belongs to a plan"
        step = steps[0]
        member = self._member(self._owner_of(step.step))
        if member is None:
            self._record_cancel_failure(step, "nobody on the team can reach that service")
            self._update(cancelling=steps[1:])
            self._run_next_cancellation()
            return

        self.send(
            member,
            CancelAssignment(plan_id=plan.plan_id, step=step.step, reference=step.reference),
        )

    def _owner_of(self, step: CompensationStep) -> str:
        """Which member to ask. Lunch goes through @FacilityManager (D2)."""
        if step is CompensationStep.CANCEL_MEETING:
            return self.config.scheduler_name
        return self.config.facility_name

    def _record_cancel_failure(self, step: Compensation, reason: str) -> None:
        line = f"{step.step.value} {step.reference}: {reason or 'the service refused'}"
        logger.warning("[%s] %s", self.config.name, line)
        self._update(cancel_failures=[*self.state.cancel_failures, line])

    def _finish_cancelling(self) -> None:
        """Mark the meeting cancelled, then report it.

        The ids stay on the plan. It is the record of what was booked, and a
        reference that could not be released is the one thing a person will
        need to chase by hand.
        """
        plan = self.state.plan
        assert plan is not None, "a release always belongs to a plan"
        plan = plan.model_copy(update={"cancelled": True})
        self._update(plan=plan)
        self._report_cancelled(plan)

    def _report_cancelled(self, plan: MeetingPlan) -> None:
        human = self._member(self.config.human_name)
        if human is not None:
            self.send(human, PlanCancelled(plan=plan, failures=self.state.cancel_failures))

    def receiveMsg_Cancelled(  # noqa: N802
        self, message: Cancelled, sender: ActorAddress
    ) -> None:
        """One release came back. Record it and move on, success or not.

        A failed step does not stop the run. One stale reference - a room
        somebody already released by hand - must not strand the other two.
        """
        steps = self.state.cancelling
        if not steps or self._plan(message.plan_id) is None:
            logger.error("[%s] unexpected %s for %s", self.config.name, message.step, message.plan_id)
            return

        if not message.succeeded:
            self._record_cancel_failure(steps[0], message.reason)

        self._update(cancelling=steps[1:])
        self._run_next_cancellation()

    # -- specialists -> coordinator ---------------------------------------

    def receiveMsg_LocationFound(  # noqa: N802
        self, message: LocationFound, sender: ActorAddress
    ) -> None:
        """The place is chosen. Record it, then look for a time.

        Nothing is booked by choosing: the human sees the place with the slots,
        and a "no" to those costs nothing.
        """
        plan = self._plan(message.plan_id)
        if plan is None or self._being_cancelled(plan):
            return

        plan = plan.model_copy(
            update={
                "location_id": message.location_id,
                "location_name": message.name,
                "location_reason": message.reason,
            }
        )
        self._update(plan=plan)
        self._find_slots(plan)

    def receiveMsg_SlotsFound(  # noqa: N802
        self, message: SlotsFound, sender: ActorAddress
    ) -> None:
        """Put the candidates to the human, then stop and wait for a message.

        This returns immediately. The meeting sits at AWAITING_APPROVAL with no
        thread held open, which is what lets a GUI answer it minutes later - or
        a revived team the next morning.
        """
        plan = self._plan(message.plan_id)
        if plan is None or self._being_cancelled(plan):
            return

        if not message.candidates:
            self._fail(plan, "no time slot works for all participants")
            return

        human = self._member(self.config.human_name)
        if human is None:
            self._fail(plan, f"no {self.config.human_name} to approve the slot")
            return

        plan = plan.model_copy(
            update={
                "proposed_start": message.candidates[0].start,
                "proposed_end": message.candidates[0].end,
            }
        )
        self._update(plan=plan, candidates=message.candidates)

        self.send(
            human,
            SlotApprovalRequest(
                plan_id=plan.plan_id,
                title=plan.title,
                day=plan.day,
                candidates=message.candidates,
                location_name=plan.location_name,
                location_reason=plan.location_reason,
                recipient=human,
            ),
        )

    def receiveMsg_MeetingBooked(  # noqa: N802
        self, message: MeetingBooked, sender: ActorAddress
    ) -> None:
        """The agendas are set; now get a room (and lunch, via @FacilityManager)."""
        plan = self._plan(message.plan_id)
        if plan is None:
            return

        plan = plan.model_copy(update={"meeting_id": message.meeting_id})
        if self._being_cancelled(plan):
            # Booked after the cancel went out (R5). Record it - it is real -
            # and release it rather than build on it.
            self._update(plan=plan.model_copy(update={"cancelled": False}))
            self._release(
                [Compensation(step=CompensationStep.CANCEL_MEETING, reference=str(message.meeting_id))]
            )
            return

        self._update(plan=plan)

        if plan.proposed_start is None or plan.proposed_end is None:
            self._fail(plan, "no approved slot recorded for this plan")
            return

        facility = self._member(self.config.facility_name)
        if facility is None:
            self._fail(plan, f"no {self.config.facility_name} on the team")
            return

        self.send(
            facility,
            BookFacilitiesAssignment(
                plan_id=plan.plan_id,
                title=plan.title,
                location_id=plan.location_id,
                day=plan.day,
                slot=ProposedSlot(start=plan.proposed_start, end=plan.proposed_end),
                headcount=len(plan.participant_emails),
                with_lunch=plan.with_lunch,
                lunch_wish=plan.lunch_wish,
            ),
        )

    def receiveMsg_FacilitiesBooked(  # noqa: N802
        self, message: FacilitiesBooked, sender: ActorAddress
    ) -> None:
        """Room and lunch are done. Record them, then say so - in that order."""
        plan = self._plan(message.plan_id)
        if plan is None:
            return

        plan = plan.model_copy(
            update={
                "room_code": message.room_code,
                "booking_id": message.booking_id,
                "order_id": message.order_id,
                "lunch_summary": message.lunch_summary,
            }
        )
        if self._being_cancelled(plan):
            # Same as a late meeting (R5): the lunch first, then the room,
            # because that is the order the services expect.
            late = [c for c in plan.compensations() if c.step is not CompensationStep.CANCEL_MEETING]
            self._update(plan=plan.model_copy(update={"cancelled": False}))
            self._release(late)
            return

        # R8: the snapshot that records the booking goes out before the message
        # that announces it.
        self._update(plan=plan)
        human = self._member(self.config.human_name)
        if human is not None:
            self.send(human, PlanCompleted(plan=plan))

    def receiveMsg_AssignmentFailed(  # noqa: N802
        self, message: AssignmentFailed, sender: ActorAddress
    ) -> None:
        """A specialist could not do its part."""
        plan = self._plan(message.plan_id)
        if plan is None:
            return
        if self._being_cancelled(plan):
            # Nothing was booked by the step that failed, so there is nothing
            # to add to the release - only a note that it was still running.
            logger.info("[%s] %s failed after the cancel: %s", self.config.name, plan.plan_id, message.reason)
            return
        self._fail(plan, message.reason)
