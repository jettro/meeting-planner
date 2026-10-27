"""@PlanRepository: the one actor allowed to write the plan store.

Why an actor and not a shared object: the plan store is the only mutable state
the team has, and it is the thing that makes compensation possible. Reached
directly it would be written from several threads at once. As an actor its
mailbox serialises every write for free, and the store never leaks into another
agent's reach.

It holds no judgement of any kind, so it has no model and no MCP tool. It is
addressed by name like every other member (`@PlanRepository`).
"""

from __future__ import annotations

import logging

from akgentic.core import ActorAddress, Akgent, BaseConfig, BaseState
from akgentic.core.utils import import_class

from meeting_agents.messages import LoadPlan, PlanSnapshot, SavePlan
from meeting_agents.store import PlanNotFoundError, PlanStore

logger = logging.getLogger(__name__)


class PlanRepositoryConfig(BaseConfig):
    """Which store to use, named by dotted path (§4.2 rule 7).

    The path is a string, never a constructed store: config is serialised into
    telemetry, so a live file handle has no business being in it. Swapping
    JSON for Postgres later is a change to these two values.
    """

    name: str = "@PlanRepository"
    role: str = "PlanRepository"
    store_class: str = "meeting_agents.store.JsonPlanStore"
    store_path: str = "plans.json"


class PlanRepositoryState(BaseState):
    """Counters only - the plans themselves live in the store, not in state."""

    saved: int = 0
    loaded: int = 0


class PlanRepository(Akgent[PlanRepositoryConfig, PlanRepositoryState]):
    """Serialises all access to the plan store behind a mailbox."""

    def on_start(self) -> None:
        self.init_state(PlanRepositoryState())
        self._store: PlanStore = self._build_store()
        logger.info("[%s] plan store ready: %s", self.config.name, self.config.store_class)

    def _build_store(self) -> PlanStore:
        """Construct the store named by `store_class`.

        `InMemoryPlanStore` takes no arguments and `JsonPlanStore` takes a path,
        so the call is chosen by what the class accepts rather than by hardcoding
        either one.
        """
        store_cls = import_class(self.config.store_class)
        try:
            return store_cls(self.config.store_path)  # type: ignore[no-any-return]
        except TypeError:
            return store_cls()  # type: ignore[no-any-return]

    def receiveMsg_SavePlan(  # noqa: N802
        self, message: SavePlan, sender: ActorAddress
    ) -> None:
        """Persist a plan and acknowledge with the stored copy."""
        stored = self._store.save(message.plan)
        self.init_state(self.state.model_copy(update={"saved": self.state.saved + 1}))
        self.send(sender, PlanSnapshot(plan_id=stored.plan_id, plan=stored))

    def receiveMsg_LoadPlan(  # noqa: N802
        self, message: LoadPlan, sender: ActorAddress
    ) -> None:
        """Answer with the plan, or with `plan=None` when the id is unknown.

        A missing plan is an ordinary answer rather than an error: the caller
        asked a question and gets one reply either way, which keeps the
        coordinator's handling of it straight-line.
        """
        try:
            plan = self._store.get(message.plan_id)
        except PlanNotFoundError:
            self.send(sender, PlanSnapshot(plan_id=message.plan_id, plan=None))
            return
        self.init_state(self.state.model_copy(update={"loaded": self.state.loaded + 1}))
        self.send(sender, PlanSnapshot(plan_id=plan.plan_id, plan=plan))
