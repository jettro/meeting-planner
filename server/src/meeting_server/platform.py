"""Is the platform actually up? Asked once, answered for all three services.

The framework's `GET /readiness` answers for the server alone. That is not the
question somebody standing in front of a demo has: a server that is perfectly
ready will still fail to book a room if nomnom-service is down, and the failure
will arrive several agent turns later dressed as a tool error.

So this module fans out to the three `/health` endpoints and reports what it
finds. The browser asks one question and gets the whole picture.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from akgentic.infra.server.assembly import BaseAppModule, RouteSpec
from fastapi import APIRouter
from pydantic import BaseModel

from meeting_server.settings import ServerSettings, ServiceEndpoint

logger = logging.getLogger(__name__)


class ServiceHealth(BaseModel):
    """One service's answer, or the reason there wasn't one."""

    name: str
    url: str
    status: str
    detail: str | None = None


class PlatformHealth(BaseModel):
    """`up` only when every service is. A partial platform is not a working one."""

    status: str
    services: list[ServiceHealth]


async def _probe(client: httpx.AsyncClient, service: ServiceEndpoint, timeout: float) -> ServiceHealth:
    """Ask one service how it is. Never raises: a probe that fails is a result."""
    try:
        response = await client.get(f"{service.url}/health", timeout=timeout)
    except httpx.HTTPError as error:
        logger.info("health probe failed for %s: %s", service.name, error)
        return ServiceHealth(name=service.name, url=service.url, status="unreachable", detail=str(error))

    if response.status_code != 200:
        # A service answers 503 when its database is gone. That is a different
        # thing from not answering at all, and worth saying so.
        return ServiceHealth(
            name=service.name,
            url=service.url,
            status="degraded",
            detail=f"HTTP {response.status_code}",
        )
    return ServiceHealth(name=service.name, url=service.url, status="up")


def build_router(settings: ServerSettings) -> APIRouter:
    router = APIRouter(tags=["platform"])

    @router.get("/platform/health", response_model=PlatformHealth)
    async def platform_health() -> PlatformHealth:
        """The three services, probed concurrently.

        Concurrently because three sequential timeouts would be three times the
        wait for the one screen a person looks at while wondering why nothing
        is happening.
        """
        async with httpx.AsyncClient() as client:
            results = await asyncio.gather(
                *(_probe(client, service, settings.health_timeout_seconds) for service in settings.services)
            )
        status = "up" if all(result.status == "up" for result in results) else "degraded"
        return PlatformHealth(status=status, services=list(results))

    return router


class PlatformModule(BaseAppModule):
    """Splices `/platform/health` into the community composition."""

    name = "meeting-platform"

    def __init__(self, settings: ServerSettings) -> None:
        self._settings = settings

    def contribute_routes(self) -> list[RouteSpec]:
        return [RouteSpec(router=build_router(self._settings))]
