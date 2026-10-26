"""The human's end of the team, and the seam a GUI will later replace.

The actor here does one thing: it takes the messages addressed to the human and
hands them to a *channel*. It does not read from a terminal, does not print, and
never blocks waiting for an answer. That restraint is the whole point (§4.2):
the blog's infra chapter records that a blocking stdin proxy had to be thrown
away when the server arrived, and this is how that cost is avoided.

The answer does not come back through here. A client replies with
`TeamRuntime.send_from_to("@Human", "@Coordinator", decision)`, which works the
same whether the client is a terminal, an HTTP handler or a websocket. So this
module holds no reply logic to port.

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

from meeting_agents.messages import PlanCompleted, PlanFailed, SlotApprovalRequest

logger = logging.getLogger(__name__)


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

    def receiveMsg_PlanCompleted(  # noqa: N802
        self, message: PlanCompleted, sender: ActorAddress
    ) -> None:
        """Arrives only once the plan is stored, so it is safe to believe (§7.3)."""
        self._relay(message)

    def receiveMsg_PlanFailed(  # noqa: N802
        self, message: PlanFailed, sender: ActorAddress
    ) -> None:
        self._relay(message)

    def _relay(self, message: Message) -> None:
        logger.info("[%s] relaying %s", self.config.name, type(message).__name__)
        get_channel().deliver(message)
