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
    FacilitiesBooked,
    FindSlotsAssignment,
    LunchApprovalDecision,
    LunchApprovalRequest,
    MeetingBooked,
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
from meeting_agents.plan import MeetingPlan

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


class Coordinator(Akgent[CoordinatorConfig, CoordinatorState]):
    """Sequences the saga: slots -> approval -> meeting -> room -> lunch."""

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
        plans = {**self.state.plans, plan.plan_id: plan}
        self.init_state(self.state.model_copy(update={"plans": plans}))
        repository = self._member(self.config.repository_name)
        if repository is not None:
            self.send(repository, SavePlan(plan=plan))

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

        The steps are computed and reported but not yet dispatched: running
        compensations is iteration 2 (§7.1). Reporting them now means a failure
        is never silent about what it left behind.
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
        """@PlanRepository confirming a write.

        Every save is acknowledged, so most of these are routine. The one that
        matters is the save of a *finished* plan - that is the moment the
        result became durable, and so the moment it is honest to report it.

        The check is on the snapshot's own status rather than on the plan id
        alone, and deliberately so: acknowledgements of the earlier saves are
        still in flight when the last one is sent, and a plan id matches all of
        them. The derived status is what distinguishes the final write from its
        predecessors, which makes the correlation self-evident rather than
        dependent on arrival order.
        """
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
