"""The plans the team has made, readable without talking to the team.

The agents' own record of a plan lives in `@PlanRepository`'s store, written
through the saga (§7.3). A browser wants to read that record directly: after a
team has been stopped there is no actor left to ask, and a history screen that
only works while a team is alive is not a history screen.

Read-only on purpose. Nothing here books, cancels or edits anything - every
change to a plan goes through the agents, because every change to a plan has
compensations attached to it.
"""

from __future__ import annotations

from akgentic.infra.server.assembly import BaseAppModule, RouteSpec
from fastapi import APIRouter, HTTPException
from meeting_agents.plan import MeetingPlan
from meeting_agents.store import PlanNotFoundError, PlanStore


def build_router(store: PlanStore) -> APIRouter:
    router = APIRouter(tags=["plans"])

    @router.get("/plans", response_model=list[MeetingPlan])
    def list_plans() -> list[MeetingPlan]:
        plans: list[MeetingPlan] = store.list_plans()
        return plans

    @router.get("/plans/{plan_id}", response_model=MeetingPlan)
    def get_plan(plan_id: str) -> MeetingPlan:
        try:
            plan: MeetingPlan = store.get(plan_id)
        except PlanNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return plan

    return router


class PlansModule(BaseAppModule):
    """Splices `/plans` into the community composition."""

    name = "meeting-plans"

    def __init__(self, store: PlanStore) -> None:
        self._store = store

    def contribute_routes(self) -> list[RouteSpec]:
        return [RouteSpec(router=build_router(self._store))]
