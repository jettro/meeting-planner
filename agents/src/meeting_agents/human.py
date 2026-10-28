"""The human's end of the team, and the seam a GUI will later replace.

The actor here does one thing: it takes the messages addressed to the human and
hands them to a *channel*. It does not read from a terminal, does not print, and
never blocks waiting for an answer. That restraint is the whole point (§4.2):
the blog's infra chapter records that a blocking stdin proxy had to be thrown
away when the server arrived, and this is how that cost is avoided.

Answers arrive by one of two routes, and both are here. A client that can build
a typed message replies with `send_from_to("@Human", "@Coordinator", decision)`
and never touches this class - that is what the terminal does. A client that
only has text - the browser, through the server's human-input endpoint - hands
it to `process_human_input`, which reads it against the question that is being
answered.

That second route is why no separate server proxy class exists. The design
expected one, named in `human.yaml` (§4.2 rule 3), but the framework validates
`agent_class` when the catalog loads, so it cannot be a `${VAR}`, and a second
class would have duplicated every handler above for the sake of one method.
One bridge with two reply vocabularies is less to keep in step.

A channel is used rather than config because config carries plain, serialisable
data only - no live queues, no sockets (framework rule, §4.2). The actor looks
its channel up at the moment it delivers.
"""

from __future__ import annotations

import logging
import queue
from typing import Protocol, runtime_checkable

from akgentic.agent import HumanProxy
from akgentic.core import ActorAddress
from akgentic.core.messages import Message

from meeting_agents.answers import interpret_lunch_answer, interpret_slot_answer
from meeting_agents.messages import (
    LunchApprovalRequest,
    PlanCancelled,
    PlanCompleted,
    PlanFailed,
    SlotApprovalRequest,
)

logger = logging.getLogger(__name__)

#: Where an answer goes when the question did not record who asked it. Both
#: gates are opened by the coordinator, which is the only agent that may talk
#: to the human at all (D1).
COORDINATOR = "@Coordinator"


@runtime_checkable
class HumanChannel(Protocol):
    """Where messages for the human go.

    One method, deliberately: a websocket bridge, an HTTP event stream and a
    terminal all implement the same thing, so swapping them is not a refactor.
    """

    def deliver(self, message: Message) -> None:
        """Hand a message to whatever is representing the human right now."""


class QueueChannel:
    """The default channel: a thread-safe queue.

    The actor runs in its own thread, so the client cannot simply be called -
    it has to be handed something it can wait on. `take()` blocks on the
    client's thread, which is allowed; blocking inside the actor is not.
    """

    def __init__(self) -> None:
        self._messages: queue.Queue[Message] = queue.Queue()

    def deliver(self, message: Message) -> None:
        self._messages.put(message)

    def take(self, timeout: float | None = None) -> Message:
        """The next message for the human. Raises `queue.Empty` on timeout."""
        return self._messages.get(timeout=timeout)


_channel: HumanChannel = QueueChannel()


def set_channel(channel: HumanChannel) -> None:
    """Point the human agent at a different client. The GUI swap point."""
    global _channel
    _channel = channel


def get_channel() -> HumanChannel:
    return _channel


class ChannelHuman(HumanProxy):
    """@Human: receives the team's questions and results, and relays them.

    `HumanProxy` already handles the framework's free-text `AgentMessage`. The
    handlers below add this team's typed vocabulary - which is why the class
    exists at all, since an unhandled message type is logged and dropped.
    """

    def receiveMsg_SlotApprovalRequest(  # noqa: N802
        self, message: SlotApprovalRequest, sender: ActorAddress
    ) -> None:
        """The one question the team asks. Nothing is booked yet (D4)."""
        self._relay(message)

    def receiveMsg_LunchApprovalRequest(  # noqa: N802
        self, message: LunchApprovalRequest, sender: ActorAddress
    ) -> None:
        """The second question (D9). Still nothing booked when it is asked."""
        self._relay(message)

    def receiveMsg_PlanCompleted(  # noqa: N802
        self, message: PlanCompleted, sender: ActorAddress
    ) -> None:
        """Arrives only once the plan is stored, so it is safe to believe (§7.3)."""
        self._relay(message)

    def receiveMsg_PlanFailed(  # noqa: N802
        self, message: PlanFailed, sender: ActorAddress
    ) -> None:
        self._relay(message)

    def receiveMsg_PlanCancelled(  # noqa: N802
        self, message: PlanCancelled, sender: ActorAddress
    ) -> None:
        """Everything the plan held has been released, or named as still held."""
        self._relay(message)

    def _relay(self, message: Message) -> None:
        logger.info("[%s] relaying %s", self.config.name, type(message).__name__)
        get_channel().deliver(message)

    def process_human_input(self, content: str, message: Message) -> None:
        """Answer a question with text, the way a browser has to.

        The framework hands back the *original* question object, not just its
        id, and that is what makes this work: the structure lives in the
        question, so the answer only has to be read against it. A free-text
        `AgentMessage` is still the framework's business, so it is delegated.

        `UnreadableAnswer` is allowed out. Guessing which slot somebody meant
        would be worse than a 4xx.
        """
        if isinstance(message, SlotApprovalRequest):
            decision: Message = interpret_slot_answer(message, content)
        elif isinstance(message, LunchApprovalRequest):
            decision = interpret_lunch_answer(message, content)
        else:
            super().process_human_input(content, message)
            return

        recipient = message.sender or self.get_team_member(COORDINATOR)
        if recipient is None:
            logger.error("[%s] nowhere to send a %s", self.config.name, type(decision).__name__)
            return
        logger.info("[%s] answering with %s", self.config.name, type(decision).__name__)
        # Borrowed from HumanProxy: send() reads _current_message to keep the
        # answer attached to the question in the trace.
        self._current_message = message
        try:
            self.send(recipient, decision)
        finally:
            self._current_message = None
