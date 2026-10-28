"""@Coordinator: the deterministic actor that drives the booking saga.

This agent has no model and no MCP tool, and that is the point (D1). The order
of the steps, which step follows which answer, and what has to be undone when
one fails are all facts the system already knows - so nothing here requires
judgement, and nothing here should reach a model. The specialists do the parts
that genuinely need one: reading a menu, choosing a room, phrasing a search.

Two properties matter beyond correctness, both from §4.2:

* **It never blocks on the human.** The approval gate is a message out and a
  separate message in. A blocking `input()` here is exactly the mistake the
  infra post warns about - it is what had to be thrown away to get a server.
  Because the wait is just an absent message, a CLI, a websocket and a REST
  call all drive this same actor unchanged.
* **It addresses everyone by name, from config.** No member's address is
  captured in state, so swapping the human bridge for a GUI proxy is a YAML
  edit rather than a code change.
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
    FindSlotsAssignment,
    LoadPlan,
    LunchApprovalDecision,
    LunchApprovalRequest,
    MeetingBooked,
    PlanCancelled,
    PlanCompleted,
    PlanFailed,
    PlanMeetingRequest,
    PlanSnapshot,
    ProposedSlot,
    SavePlan,
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
    repository_name: str = "@PlanRepository"


class CoordinatorState(BaseState):
    """In-flight plans, keyed by plan id.

    The durable copy belongs to @PlanRepository; this is the working copy that
    lets the coordinator decide the next step without an extra round trip.
    Everything here is plain data, so the state stays serialisable.
    """

    plans: dict[str, MeetingPlan] = {}
    candidates: dict[str, list[ProposedSlot]] = {}
    #: Plans that are finished but not yet known to be stored. The human is
    #: told only once @PlanRepository confirms the write, so "completed" never
    #: means "completed, probably".
    awaiting_durability: list[str] = []
    #: Plans whose requester left lunch undecided, so the lunch gate applies.
    #: A request that settled it up front never reaches the gate, which is what
    #: keeps a scripted run from blocking on a question (D9).
    awaiting_lunch: list[str] = []
    #: Cancellations in flight: the steps still to run, head first. The head is
    #: the one that has been sent and is being waited on, so arrival of its
    #: `Cancelled` pops it and sends the next. Empty list means the last step
    #: has come back and the plan can be closed.
    cancelling: dict[str, list[Compensation]] = {}
    #: What went wrong while cancelling, one readable line per failed step.
    #: Kept here rather than on the plan: the plan records what was *booked*,
    #: and this is the report of one attempt to undo it.
    cancel_failures: dict[str, list[str]] = {}
    #: Plans asked to be cancelled whose contents are still being fetched. A
    #: plan is normally cancelled from a team that never made it, so there is
    #: usually nothing in `plans` to cancel until the repository answers.
    loading_to_cancel: list[str] = []
    #: Cancelled plans not yet known to be stored, with the failures to report
    #: once they are. Same rule as `awaiting_durability`: the human hears
    #: "cancelled" only when the store says so, because a browser that reloads
    #: the list on that word must not find the plan still confirmed.
    awaiting_cancel_durability: dict[str, list[str]] = {}


class Coordinator(Akgent[CoordinatorConfig, CoordinatorState]):
    """Sequences the saga: slots -> approval -> meeting -> room -> lunch.

    And the other direction: a cancellation releases the lunch, the room and
    the meeting, in that order. There is no third thing - this system has no
    way to *change* a plan, by decision. A meeting that is wrong is cancelled
    and a new one is planned.
    """

    def on_start(self) -> None:
        self.init_state(CoordinatorState())

    # -- helpers ---------------------------------------------------------

    def _member(self, name: str) -> ActorAddress | None:
        address = self.get_team_member(name)
        if address is None:
            logger.error("[%s] no team member named %s", self.config.name, name)
        return address

    def _remember(self, plan: MeetingPlan) -> None:
        """Update the working copy and ask the repository to persist it."""
        self._hold(plan)
        repository = self._member(self.config.repository_name)
        if repository is not None:
            self.send(repository, SavePlan(plan=plan))

    def _hold(self, plan: MeetingPlan) -> None:
        """Update the working copy only.

        Separate from `_remember` because a plan that has just been *read* is
        already stored, and saving it again would be a write that says nothing
        - and would add this team to its list of runs before the team has done
        anything.
        """
        plans = {**self.state.plans, plan.plan_id: plan}
        self.init_state(self.state.model_copy(update={"plans": plans}))

    def _stop_awaiting_lunch(self, plan_id: str) -> None:
        remaining = [p for p in self.state.awaiting_lunch if p != plan_id]
        self.init_state(self.state.model_copy(update={"awaiting_lunch": remaining}))

    def _plan(self, plan_id: str) -> MeetingPlan | None:
        plan = self.state.plans.get(plan_id)
        if plan is None:
            logger.error("[%s] unknown plan %s", self.config.name, plan_id)
        return plan

    def _fail(self, plan: MeetingPlan, reason: str) -> None:
        """Report failure with the undo steps this plan would need.

        The steps are reported, not run. A cancellation is something the human
        asks for (`CancelPlanRequest`), and a failure that quietly released
        three bookings on its own would hide the thing worth seeing - the mess
        a half-finished saga leaves behind, and then the undoing of it.
        """
        logger.warning("[%s] plan %s failed: %s", self.config.name, plan.plan_id, reason)
        human = self._member(self.config.human_name)
        if human is not None:
            self.send(
                human,
                PlanFailed(plan=plan, reason=reason, outstanding=plan.compensations()),
            )

    # -- human -> coordinator --------------------------------------------

    def receiveMsg_PlanMeetingRequest(  # noqa: N802
        self, message: PlanMeetingRequest, sender: ActorAddress
    ) -> None:
        """Start a plan and ask @Scheduler for the common free windows."""
        plan = message.to_plan()
        self._remember(plan)
        if not message.lunch_is_settled():
            self.init_state(
                self.state.model_copy(update={"awaiting_lunch": [*self.state.awaiting_lunch, plan.plan_id]})
            )

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

    def receiveMsg_SlotApprovalDecision(  # noqa: N802
        self, message: SlotApprovalDecision, sender: ActorAddress
    ) -> None:
        """The only human decision in the flow (D4).

        Nothing has been booked at this point, so a rejection costs nothing to
        honour - there is no compensation to run.
        """
        plan = self._plan(message.plan_id)
        if plan is None:
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
        self._remember(plan)

        if plan.plan_id in self.state.awaiting_lunch:
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

        self._stop_awaiting_lunch(plan.plan_id)
        plan = plan.model_copy(
            update={
                "with_lunch": message.wants_lunch,
                "lunch_wish": message.wish if message.wants_lunch else "",
            }
        )
        self._remember(plan)
        self._book_the_meeting(plan)

    def receiveMsg_CancelPlanRequest(  # noqa: N802
        self, message: CancelPlanRequest, sender: ActorAddress
    ) -> None:
        """Call the meeting off, releasing everything it holds.

        The plan is almost never one this coordinator made - a cancellation
        arrives days later, in a new team, because the team that booked it is
        long stopped and its coordinator kept nothing anyway. So the ordinary
        path is to ask @PlanRepository for it and continue when it answers.
        """
        plan = self.state.plans.get(message.plan_id)
        if plan is not None:
            self._start_cancelling(plan)
            return

        repository = self._member(self.config.repository_name)
        if repository is None:
            return
        self.init_state(
            self.state.model_copy(
                update={"loading_to_cancel": [*self.state.loading_to_cancel, message.plan_id]}
            )
        )
        self.send(repository, LoadPlan(plan_id=message.plan_id))

    # -- saga steps -------------------------------------------------------

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

    def _start_cancelling(self, plan: MeetingPlan) -> None:
        """Begin releasing everything this plan holds, one step at a time.

        A plan that is already cancelled is answered immediately rather than
        run again. Cancelling twice would try to release ids the services have
        already let go, which reads as a failure and would make a correct,
        harmless repeat look like a problem.
        """
        self._hold(plan)
        if plan.cancelled:
            self._report_cancelled(plan, [])
            return

        steps = plan.compensations()
        self.init_state(
            self.state.model_copy(
                update={
                    "cancelling": {**self.state.cancelling, plan.plan_id: steps},
                    "cancel_failures": {**self.state.cancel_failures, plan.plan_id: []},
                }
            )
        )
        logger.info("[%s] cancelling plan %s: %d step(s)", self.config.name, plan.plan_id, len(steps))
        self._run_next_cancellation(plan.plan_id)

    def _run_next_cancellation(self, plan_id: str) -> None:
        """Send the step at the head of the queue, or finish.

        One at a time, and in `compensations()` order - reverse booking order,
        which is the order the services expect and the only order in which a
        partial result can be described as a sentence.
        """
        steps = self.state.cancelling.get(plan_id, [])
        if not steps:
            self._finish_cancelling(plan_id)
            return

        step = steps[0]
        member = self._member(self._owner_of(step.step))
        if member is None:
            self._record_cancel_failure(plan_id, step, "nobody on the team can reach that service")
            self._pop_cancellation(plan_id)
            self._run_next_cancellation(plan_id)
            return

        self.send(
            member,
            CancelAssignment(plan_id=plan_id, step=step.step, reference=step.reference),
        )

    def _owner_of(self, step: CompensationStep) -> str:
        """Which member to ask. Lunch goes through @FacilityManager (D2)."""
        if step is CompensationStep.CANCEL_MEETING:
            return self.config.scheduler_name
        return self.config.facility_name

    def _pop_cancellation(self, plan_id: str) -> None:
        remaining = self.state.cancelling.get(plan_id, [])[1:]
        self.init_state(
            self.state.model_copy(update={"cancelling": {**self.state.cancelling, plan_id: remaining}})
        )

    def _record_cancel_failure(self, plan_id: str, step: Compensation, reason: str) -> None:
        line = f"{step.step.value} {step.reference}: {reason or 'the service refused'}"
        logger.warning("[%s] %s", self.config.name, line)
        failures = [*self.state.cancel_failures.get(plan_id, []), line]
        self.init_state(
            self.state.model_copy(
                update={"cancel_failures": {**self.state.cancel_failures, plan_id: failures}}
            )
        )

    def _finish_cancelling(self, plan_id: str) -> None:
        """Mark the plan cancelled, store it, and report once it is stored.

        The ids stay on the plan. It is the record of what was booked, and a
        reference that could not be released is the one thing a person will
        need to chase by hand.
        """
        plan = self._plan(plan_id)
        if plan is None:
            return

        failures = self.state.cancel_failures.get(plan_id, [])
        self.init_state(
            self.state.model_copy(
                update={
                    "cancelling": {k: v for k, v in self.state.cancelling.items() if k != plan_id},
                    "cancel_failures": {
                        k: v for k, v in self.state.cancel_failures.items() if k != plan_id
                    },
                    "awaiting_cancel_durability": {
                        **self.state.awaiting_cancel_durability,
                        plan_id: failures,
                    },
                }
            )
        )
        self._remember(plan.model_copy(update={"cancelled": True}))

    def _report_cancelled(self, plan: MeetingPlan, failures: list[str]) -> None:
        human = self._member(self.config.human_name)
        if human is not None:
            self.send(human, PlanCancelled(plan=plan, failures=failures))

    def receiveMsg_Cancelled(  # noqa: N802
        self, message: Cancelled, sender: ActorAddress
    ) -> None:
        """One release came back. Record it and move on, success or not.

        A failed step does not stop the run. One stale reference - a room
        somebody already released by hand - must not strand the other two.
        """
        steps = self.state.cancelling.get(message.plan_id)
        if not steps:
            logger.error("[%s] unexpected %s for %s", self.config.name, message.step, message.plan_id)
            return

        if not message.succeeded:
            self._record_cancel_failure(message.plan_id, steps[0], message.reason)

        self._pop_cancellation(message.plan_id)
        self._run_next_cancellation(message.plan_id)

    # -- specialists -> coordinator ---------------------------------------

    def receiveMsg_SlotsFound(  # noqa: N802
        self, message: SlotsFound, sender: ActorAddress
    ) -> None:
        """Put the candidates to the human, then stop and wait for a message.

        This returns immediately. The plan sits at AWAITING_APPROVAL with no
        thread held open, which is what lets a GUI answer it minutes later.
        """
        plan = self._plan(message.plan_id)
        if plan is None:
            return

        if not message.candidates:
            self._fail(plan, "no time slot works for all participants")
            return

        plan = plan.model_copy(
            update={
                "proposed_start": message.candidates[0].start,
                "proposed_end": message.candidates[0].end,
            }
        )
        candidates = {**self.state.candidates, plan.plan_id: message.candidates}
        self.init_state(self.state.model_copy(update={"candidates": candidates}))
        self._remember(plan)

        human = self._member(self.config.human_name)
        if human is None:
            self._fail(plan, f"no {self.config.human_name} to approve the slot")
            return

        self.send(
            human,
            SlotApprovalRequest(
                plan_id=plan.plan_id,
                title=plan.title,
                day=plan.day,
                candidates=message.candidates,
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
        self._remember(plan)

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
        """Room and lunch are done. Tell the human once the plan is stored."""
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
        self.init_state(
            self.state.model_copy(
                update={"awaiting_durability": [*self.state.awaiting_durability, plan.plan_id]}
            )
        )
        self._remember(plan)

    def receiveMsg_PlanSnapshot(  # noqa: N802
        self, message: PlanSnapshot, sender: ActorAddress
    ) -> None:
        """@PlanRepository answering, about a load or a write.

        Three things arrive here and they are told apart by what the snapshot
        says, never by arrival order - acknowledgements of earlier saves are
        still in flight when the last one is sent, and a plan id matches all of
        them:

        * a plan that was *loaded* in order to be cancelled, which is the only
          case this coordinator asked a question rather than made a statement;
        * the write of a *cancelled* plan, which is when it becomes honest to
          say the meeting is off;
        * the write of a *finished* plan, which is when it becomes honest to
          say it is booked.

        Everything else is a routine acknowledgement and is ignored.
        """
        if message.plan_id in self.state.loading_to_cancel:
            remaining = [p for p in self.state.loading_to_cancel if p != message.plan_id]
            self.init_state(self.state.model_copy(update={"loading_to_cancel": remaining}))
            if message.plan is None:
                logger.error("[%s] cannot cancel unknown plan %s", self.config.name, message.plan_id)
                return
            self._start_cancelling(message.plan)
            return

        if message.plan is not None and message.plan.cancelled:
            failures = self.state.awaiting_cancel_durability.get(message.plan_id)
            if failures is None:
                return
            self.init_state(
                self.state.model_copy(
                    update={
                        "awaiting_cancel_durability": {
                            k: v
                            for k, v in self.state.awaiting_cancel_durability.items()
                            if k != message.plan_id
                        }
                    }
                )
            )
            self._report_cancelled(message.plan, failures)
            return

        if message.plan is None or not message.plan.is_complete:
            return
        if message.plan_id not in self.state.awaiting_durability:
            return

        remaining = [p for p in self.state.awaiting_durability if p != message.plan_id]
        self.init_state(self.state.model_copy(update={"awaiting_durability": remaining}))

        human = self._member(self.config.human_name)
        if human is not None:
            self.send(human, PlanCompleted(plan=message.plan))

    def receiveMsg_AssignmentFailed(  # noqa: N802
        self, message: AssignmentFailed, sender: ActorAddress
    ) -> None:
        """A specialist could not do its part."""
        plan = self._plan(message.plan_id)
        if plan is None:
            return
        self._fail(plan, message.reason)
