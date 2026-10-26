"""Storage for `MeetingPlan` aggregates.

`PlanStore` is a Protocol so the implementation can be swapped without touching the
agents: a JSON file is enough for the CLI, but running the team behind a server
(see `design_akgents.md` §4.2) needs a shared backend. Agents therefore hold a
`PlanStore`, never `JsonPlanStore`, and the concrete class is named by dotted path
in configuration - a live store object must never go into an agent's config or
state, because both are serialised into telemetry.

Concurrency is deliberately not handled here. `@PlanRepository` is the single actor
that owns this store, and an actor processes one message at a time, so there is no
second writer to guard against.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Protocol, runtime_checkable

from meeting_agents.plan import MeetingPlan


class PlanNotFoundError(KeyError):
    """Raised when a plan id does not exist."""


@runtime_checkable
class PlanStore(Protocol):
    """What the agents need from plan storage, and nothing more."""

    def save(self, plan: MeetingPlan) -> MeetingPlan:
        """Create or replace `plan`, returning what was stored."""

    def get(self, plan_id: str) -> MeetingPlan:
        """Return a plan, or raise `PlanNotFoundError`."""

    def list_plans(self) -> list[MeetingPlan]:
        """Return every stored plan."""


class InMemoryPlanStore:
    """A plan store that keeps everything in memory. Used by tests."""

    def __init__(self) -> None:
        self._plans: dict[str, MeetingPlan] = {}

    def save(self, plan: MeetingPlan) -> MeetingPlan:
        self._plans[plan.plan_id] = plan.model_copy(deep=True)
        return plan

    def get(self, plan_id: str) -> MeetingPlan:
        if plan_id not in self._plans:
            raise PlanNotFoundError(plan_id)
        return self._plans[plan_id].model_copy(deep=True)

    def list_plans(self) -> list[MeetingPlan]:
        return [p.model_copy(deep=True) for p in self._plans.values()]


class JsonPlanStore:
    """A plan store backed by a single JSON file.

    Writes go through a temporary file in the same directory and an atomic
    `os.replace`, so an interrupted write cannot leave a half-written file - the
    plans are the only record of what has been booked, and losing them would strand
    real bookings in the three services with nothing left to cancel them by.
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def _read_all(self) -> dict[str, MeetingPlan]:
        if not self._path.exists():
            return {}
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return {plan_id: MeetingPlan.model_validate(data) for plan_id, data in raw.items()}

    def _write_all(self, plans: dict[str, MeetingPlan]) -> None:
        payload = {plan_id: plan.model_dump(mode="json") for plan_id, plan in plans.items()}
        fd, tmp_name = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
            os.replace(tmp_name, self._path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    def save(self, plan: MeetingPlan) -> MeetingPlan:
        plans = self._read_all()
        plans[plan.plan_id] = plan
        self._write_all(plans)
        return plan

    def get(self, plan_id: str) -> MeetingPlan:
        plans = self._read_all()
        if plan_id not in plans:
            raise PlanNotFoundError(plan_id)
        return plans[plan_id]

    def list_plans(self) -> list[MeetingPlan]:
        return list(self._read_all().values())
