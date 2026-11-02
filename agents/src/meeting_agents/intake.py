"""@Intake: the agent you talk to, in front of the team that books (design_chat.md).

The goal is an easier way to ask for a meeting, not a model that runs the
saga. So this agent makes one call to the team - a typed `PlanMeetingRequest`,
exactly the one the form sends - and the deterministic coordinator behind it
does everything else, as it always has. The coordinator is configured to treat
this agent as its human (`human_name: "@Intake"`), so every question and every
outcome it produces arrives here.

*The model listens; the coordinator decides; the human approves.* Three
properties hold that sentence up:

* **There is no approval tool.** A gate is a typed question the human answers
  on its card in the page. "The second one" typed into the conversation is
  understood by the model and authorises nothing (I4).
* **The relay is code.** A question from the coordinator is passed to the human
  as a *fresh* message - a new id, addressed to `@Human` - because the server
  finds a question by its id and routes the answer by the question's recipient,
  which must be a `UserProxy`. The answer comes back here as the copy's sender,
  and is forwarded to the coordinator unchanged (I5).
* **The model writes only to `@Human`.** `TalkOnlyToHuman` refuses any other
  recipient: free text to the coordinator would be dropped, to a specialist it
  would reach that specialist's model and its write tools (I7).

What the model does get is the whole story: every relayed message is also an
"Update:" turn, so it can explain what is on the person's screen and say the
outcome in words (I6).

And it remembers (design_memory.md, phase 1): what the organiser said about how
they meet is always in front of it, what is known about a participant arrives
with the lookup that settles them, and `remember` stores what a person says -
only that, and only about someone this conversation knows.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from akgentic.agent import BaseAgent
from akgentic.agent.config import AgentConfig, AgentState
from akgentic.agent.messages import AgentMessage
from akgentic.agent.output_models import StructuredOutput
from akgentic.agent.recipients import can_retry
from akgentic.core import ActorAddress, Akgent
from akgentic.core.messages import Message
from akgentic.tool.core import ToolCard
from akgentic.tool.errors import RetriableError
from pydantic import Field, ValidationError
from pydantic_ai import AgentCapability, ModelRetry, RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.output import OutputContext

from meeting_agents.memory import MemoryItem, MemoryTool
from meeting_agents.messages import (
    AssignmentFailed,
    CancelPlanRequest,
    FindPeopleAssignment,
    LunchApprovalDecision,
    LunchApprovalRequest,
    PeopleFound,
    PlanCancelled,
    PlanCompleted,
    PlanFailed,
    PlanMeetingRequest,
    SlotApprovalDecision,
    SlotApprovalRequest,
)
from meeting_agents.plan import MeetingPlan

logger = logging.getLogger(__name__)


class IntakeConfig(AgentConfig):
    """Who to talk to, and who to ask."""

    human_name: str = "@Human"
    coordinator_name: str = "@Coordinator"
    scheduler_name: str = "@Scheduler"


class IntakeState(AgentState):
    """What this conversation has asked for - durable, so a resumed one still knows.

    `AgentState` carries the backstory the agent reasons with, so this extends it
    rather than replacing it: `on_start` copies the backstory across (the
    step-5 lesson was about a *fresh* state losing it).
    """

    #: True once `plan_meeting` has sent the request. One conversation, one meeting (I8).
    requested: bool = False
    #: The meeting's id, learned from the first thing the coordinator says about it.
    plan_id: str = ""
    cancelled: bool = False
    #: Email addresses a lookup settled - one person for one name. Only these
    #: may reach `plan_meeting`: a guessed address is a meeting in a stranger's
    #: agenda (§13.2).
    settled_emails: list[str] = Field(default_factory=list)


class IntakeAgent(BaseAgent, Akgent[IntakeConfig, IntakeState]):
    """Holds the conversation, sends one typed request, relays the rest."""

    #: Narrows the inherited `config` and `state` to this agent's own types.
    config: IntakeConfig
    state: IntakeState

    def on_start(self) -> None:
        super().on_start()
        # BaseAgent.on_start has just built a plain AgentState with the
        # backstory and attached its observer. Extend it, keeping both, so the
        # system prompt survives and every change here is snapshotted.
        self.state = IntakeState(backstory=self.state.backstory, tool_state=self.state.tool_state)
        self.state.observer(self)

    def extra_capabilities(self) -> list[AgentCapability[Any]]:
        return [TalkOnlyToHuman(human_name=self.config.human_name)]

    # -- helpers ---------------------------------------------------------

    def _member(self, name: str) -> ActorAddress | None:
        address = self.get_team_member(name)
        if address is None:
            logger.error("[%s] no team member named %s", self.config.name, name)
        return address

    def _update(self, **changes: object) -> None:
        self.init_state(self.state.model_copy(update=changes))

    def _remember(self, plan_id: str) -> None:
        if plan_id and not self.state.plan_id:
            self._update(plan_id=plan_id)

    def _relay(self, message: Message) -> None:
        """Pass a coordinator's message to the human as a fresh one (I5).

        A new id, and `@Human` as the recipient: the server finds a question by
        its id and routes the answer by its recipient, and the coordinator's own
        copy is addressed to this agent, which is not a `UserProxy`.
        """
        human = self._member(self.config.human_name)
        if human is None:
            return
        self.send(human, message.model_copy(update={"id": uuid.uuid4(), "recipient": human}))

    def _tell_the_model(self, text: str, sender: ActorAddress | None) -> None:
        """Make what happened the model's next turn (I6).

        A notification: the framework's reply protocol says no reply is
        expected, so the model may say something short or nothing at all. It
        is a real turn, so it is in the context the framework persists and
        restores with the team.
        """
        update = AgentMessage(type="notification", content=f"Update: {text}", sender=sender)
        super().receiveMsg_AgentMessage(update, sender)  # type: ignore[arg-type]

    # -- memory ------------------------------------------------------------

    def _memory(self) -> MemoryTool | None:
        """The team's memory, when this agent's card has one."""
        return next((card for card in self.config.tools if isinstance(card, MemoryTool)), None)

    def remember_said(self, kind: str, about: str, situation: str, text: str) -> str:
        """Store what the person said, as confirmed (M4).

        `about` is `organiser` for how this person arranges meetings, or the
        email of the person a fact is about - which must be someone this
        conversation settled, or the organiser: a guessed address would be a
        fact about a stranger.
        """
        memory = self._memory()
        if memory is None:
            return "Refused: this team has no memory."
        if kind not in ("fact", "preference"):
            return "Refused: kind is 'fact' or 'preference'."
        organiser = str(self.user_id or "anonymous")
        about = about.strip().lower()
        if about == "organiser":
            scope = "organiser"
        elif about == organiser or about in self.state.settled_emails:
            scope = f"person:{about}"
        else:
            return (
                f"Refused: {about} is not someone this conversation knows. Look them up first, "
                "or use 'organiser' for how the person you talk to likes to meet."
            )
        item = MemoryItem(
            kind=kind,  # type: ignore[arg-type]
            scope=scope,
            situation=situation,
            text=text,
            said_by=organiser,
            reason="said in conversation",
            evidence=f"team {self.team_id}",
        )
        answer: str = memory.remember(item)
        return answer

    def _remembered_about(self, emails: list[str]) -> list[str]:
        """What is remembered about people just settled - selected by the lookup, in code."""
        memory = self._memory()
        if memory is None:
            return []
        lines = []
        for email in emails:
            items = memory.person_items(email)
            if items:
                memory.applied(f"a lookup settled {email}", items)
                said = "; ".join(f"{i.situation}: {i.text}" for i in items)
                lines.append(f"Remembered about {email}: {said}.")
        return lines

    # -- what the tools do (kept here, so they are testable without a model) --

    def request_meeting(self, request: PlanMeetingRequest) -> str:
        """The one call this agent makes to the team that books."""
        if self.state.requested:
            return (
                "Refused: this conversation has already requested its meeting. A different "
                "meeting needs a new conversation."
            )
        unsettled = [email for email in request.participant_emails if email not in self.state.settled_emails]
        if unsettled:
            return (
                f"Refused: {', '.join(unsettled)} was not settled by look_up_people. Look every "
                "participant up first, and use the email address the lookup gave."
            )
        coordinator = self._member(self.config.coordinator_name)
        if coordinator is None:
            return "Refused: there is no coordinator on this team to send the request to."

        self._update(requested=True)
        self.send(coordinator, request)
        return (
            "Requested. The team is finding a place and times; updates will follow, and the "
            "person chooses a time on their screen."
        )

    def look_up(self, names: list[str]) -> str:
        scheduler = self._member(self.config.scheduler_name)
        if scheduler is None:
            return "Refused: there is no scheduler on this team to ask."
        self.send(scheduler, FindPeopleAssignment(names=names))
        return "Asked the scheduler. The answer will arrive as an update."

    def cancel(self) -> str:
        if not self.state.requested:
            return "Refused: nothing has been requested in this conversation, so there is nothing to cancel."
        if self.state.cancelled:
            return "Refused: the meeting is already cancelled."
        if not self.state.plan_id:
            return "Refused: the team has not said anything about the meeting yet. Try again in a moment."
        coordinator = self._member(self.config.coordinator_name)
        if coordinator is None:
            return "Refused: there is no coordinator on this team to send the cancellation to."
        self.send(coordinator, CancelPlanRequest(plan_id=self.state.plan_id))
        return "Asked the team to cancel. It releases everything that was booked; an update will follow."

    # -- the coordinator's questions and outcomes: relayed, then explained ----

    def receiveMsg_SlotApprovalRequest(  # noqa: N802
        self, message: SlotApprovalRequest, sender: ActorAddress
    ) -> None:
        self._remember(message.plan_id)
        self._relay(message)
        where = f" at {message.location_name} ({message.location_reason})" if message.location_name else ""
        options = ", ".join(slot.label() for slot in message.candidates)
        self._tell_the_model(
            f"the team asks the person to choose a time for '{message.title}'{where} on "
            f"{message.day.isoformat()}: {options}. The question is on their screen and they "
            "answer it there, not in this conversation.",
            sender,
        )

    def receiveMsg_LunchApprovalRequest(  # noqa: N802
        self, message: LunchApprovalRequest, sender: ActorAddress
    ) -> None:
        self._remember(message.plan_id)
        self._relay(message)
        self._tell_the_model(
            f"the team asks the person whether they want lunch for {message.headcount}, and "
            "what kind. The question is on their screen and they answer it there.",
            sender,
        )

    def receiveMsg_PlanCompleted(  # noqa: N802
        self, message: PlanCompleted, sender: ActorAddress
    ) -> None:
        self._remember(message.plan.plan_id)
        self._relay(message)
        self._tell_the_model(f"the meeting is booked. {describe(message.plan)}", sender)

    def receiveMsg_PlanFailed(  # noqa: N802
        self, message: PlanFailed, sender: ActorAddress
    ) -> None:
        self._remember(message.plan.plan_id)
        self._relay(message)
        held = ", ".join(f"{step.step.value} {step.reference}" for step in message.outstanding)
        still = f" Still booked: {held}." if held else " Nothing was booked."
        self._tell_the_model(f"the meeting could not be arranged: {message.reason}.{still}", sender)

    def receiveMsg_PlanCancelled(  # noqa: N802
        self, message: PlanCancelled, sender: ActorAddress
    ) -> None:
        self._update(cancelled=True)
        self._relay(message)
        left = f" Could not release: {'; '.join(message.failures)}." if message.failures else ""
        self._tell_the_model(f"the meeting is cancelled and its bookings released.{left}", sender)

    # -- the human's answers: forwarded unchanged ---------------------------

    def receiveMsg_SlotApprovalDecision(  # noqa: N802
        self, message: SlotApprovalDecision, sender: ActorAddress
    ) -> None:
        """The decision carries the plan id, which is all the coordinator correlates on."""
        self._forward(message)

    def receiveMsg_LunchApprovalDecision(  # noqa: N802
        self, message: LunchApprovalDecision, sender: ActorAddress
    ) -> None:
        self._forward(message)

    def _forward(self, message: Message) -> None:
        coordinator = self._member(self.config.coordinator_name)
        if coordinator is not None:
            self.send(coordinator, message)

    # -- the people lookup (§13.2) --------------------------------------------

    def receiveMsg_PeopleFound(  # noqa: N802
        self, message: PeopleFound, sender: ActorAddress
    ) -> None:
        """Settle what is unambiguous in code; put the rest to the model as a question."""
        settled = [match.candidates[0].email for match in message.matches if len(match.candidates) == 1]
        self._update(settled_emails=sorted({*self.state.settled_emails, *settled}))

        lines = []
        for match in message.matches:
            if len(match.candidates) == 1:
                person = match.candidates[0]
                lines.append(f'"{match.asked}" is {person.name} <{person.email}>.')
            elif match.candidates:
                options = "; ".join(f"{p.name} <{p.email}>" for p in match.candidates)
                lines.append(f'"{match.asked}" could be: {options}. Ask the person which one.')
            else:
                lines.append(f'Nobody called "{match.asked}" is known. Ask the person who they mean.')
        lines += self._remembered_about(settled)
        self._tell_the_model("the scheduler looked people up. " + " ".join(lines), sender)

    def receiveMsg_AssignmentFailed(  # noqa: N802
        self, message: AssignmentFailed, sender: ActorAddress
    ) -> None:
        """Only a lookup answers this agent with a failure; the saga reports through PlanFailed."""
        self._tell_the_model(f"a lookup failed: {message.reason}.", sender)


def describe(plan: MeetingPlan) -> str:
    """The booked meeting in one line, for the model to say in its own words."""
    time = f"{plan.proposed_start:%H:%M}-{plan.proposed_end:%H:%M}" if plan.proposed_start else "no time"
    place = plan.location_name or plan.location_id
    lunch = plan.lunch_summary or ("lunch ordered" if plan.order_id else "no lunch")
    return f"{plan.title} on {plan.day.isoformat()}, {time}, room {plan.room_code} at {place}; {lunch}."


# -- the tools ---------------------------------------------------------------


class IntakeTools(ToolCard):
    """The four things the model may do, and nothing that books (I3).

    The tools are thin: they validate what the model passed and hand it to the
    agent, whose methods hold the rules, so the rules are testable without a
    model. A refusal is a readable result, not a crash, so the model can tell
    the person why (§7.4 lesson 4).
    """

    def _agent(self) -> IntakeAgent:
        agent = self._observer
        assert isinstance(agent, IntakeAgent), "IntakeTools belongs on @Intake"
        return agent

    def get_tools(self) -> list[Callable[..., Any]]:
        def look_up_people(names: list[str]) -> str:
            """Find the people the person named, by name or email, in the address book.

            Args:
                names: The names or email addresses exactly as the person said them.
            """
            return self._agent().look_up(names)

        def plan_meeting(
            title: str,
            participant_emails: list[str],
            day: str,
            location_wish: str = "",
            location_id: str = "",
            duration_minutes: int = 60,
            with_lunch: bool = True,
            lunch_wish: str | None = None,
        ) -> str:
            """Request the meeting from the team. Call it once, when everything is known.

            Args:
                title: What the meeting is called.
                participant_emails: Every participant's email, as look_up_people settled it.
                day: The day, as YYYY-MM-DD.
                location_wish: What kind of place, in the person's own words. Use this or location_id.
                location_id: A location id, only if the person named one.
                duration_minutes: How long it lasts; 60 if nobody said.
                with_lunch: False if the person does not want lunch.
                lunch_wish: What lunch, in their own words; leave it out if lunch never came up.
            """
            try:
                request = PlanMeetingRequest(
                    title=title,
                    participant_emails=participant_emails,
                    day=day,  # type: ignore[arg-type]  # pydantic parses the ISO date
                    location_wish=location_wish,
                    location_id=location_id,
                    duration_minutes=duration_minutes,
                    with_lunch=with_lunch,
                    lunch_wish=lunch_wish,
                )
            except ValidationError as exc:
                raise RetriableError(f"That request is not valid: {exc.errors()[0]['msg']}") from exc
            return self._agent().request_meeting(request)

        def cancel_meeting() -> str:
            """Call the meeting off. Everything it booked is released."""
            return self._agent().cancel()

        def remember(kind: str, about: str, situation: str, text: str) -> str:
            """Remember, for next time, something the person told you that will still be true then.

            Only what they said, in their words - never a guess, a one-off, an id or a secret.
            Saying it again about the same situation replaces the earlier one.

            Args:
                kind: 'preference' for how something should be done, 'fact' for what is so.
                about: 'organiser' for how the person you talk to arranges meetings (who
                    "Daan" or "my team" is, how long their stand-ups are, where focus
                    sessions go); or the email of the person a fact is about, as
                    look_up_people settled it ("Sanne is vegetarian").
                situation: When it applies, in a few words: "who Daan is", "lunch", "stand-ups".
                text: What to remember, in the person's words.
            """
            return self._agent().remember_said(kind, about, situation, text)

        return [look_up_people, plan_meeting, cancel_meeting, remember]


# -- the guard ---------------------------------------------------------------


@dataclass
class TalkOnlyToHuman(AbstractCapability[Any]):
    """Send an output back while it addresses anyone but the human (I7).

    The tools bound what the model can *do*; this bounds whom it can *address*.
    It is the framework's own recipient check, narrowed: the same hook, the
    same rule about when a retry is still possible. When one is not, the stray
    requests are dropped rather than delivered.
    """

    human_name: str = "@Human"

    async def after_output_validate(
        self,
        ctx: RunContext[Any],
        *,
        output_context: OutputContext,
        output: Any,
    ) -> Any:
        if ctx.partial_output or not isinstance(output, StructuredOutput):
            return output
        strays = [request.recipient for request in output.messages if request.recipient != self.human_name]
        if not strays:
            return output
        if can_retry(ctx):
            raise ModelRetry(
                f"You write only to {self.human_name}, never to {', '.join(strays)}. "
                "Reach the team through your tools."
            )
        kept = [request for request in output.messages if request.recipient == self.human_name]
        return output.model_copy(update={"messages": kept})
