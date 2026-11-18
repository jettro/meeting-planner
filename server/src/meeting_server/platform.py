"""Is the platform actually up? Asked once, answered for all three services.

The framework's `GET /readiness` answers for the server alone. That is not the
question somebody standing in front of a demo has: a server that is perfectly
ready will still fail to book a room if nomnom-service is down, and the failure
will arrive several agent turns later dressed as a tool error.

So this module asks the three `/health` endpoints and reports what it finds,
in two shapes:

- `GET /platform/services` lists the three without asking any of them, so the
  screen can draw its frame at once, and `GET /platform/health/{name}` asks one.
  The browser asks the three in parallel and colours each dot as its answer
  arrives: a service that hangs delays its own dot, not the page.
- `GET /platform/health` asks all three concurrently and answers once, for
  anything that wants the whole picture in one call.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from akgentic.infra.server.assembly import BaseAppModule, RouteSpec
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from meeting_server.settings import ServerSettings, ServiceEndpoint

logger = logging.getLogger(__name__)


class ServiceInfo(BaseModel):
    """One service as the screen lists it, before anybody has asked it anything."""

    name: str
    url: str

    #: Where a browser can open it - not `url`, which is a compose name.
    link: str


class ServiceHealth(ServiceInfo):
    """One service's answer, or the reason there wasn't one."""

    status: str
    detail: str | None = None


class PlatformHealth(BaseModel):
    """`up` only when every service is. A partial platform is not a working one."""

    status: str
    services: list[ServiceHealth]


async def _probe(client: httpx.AsyncClient, service: ServiceEndpoint, timeout: float) -> ServiceHealth:
    """Ask one service how it is. Never raises: a probe that fails is a result."""
    who = {"name": service.name, "url": service.url, "link": service.link()}
    try:
        # httpx's timeout is per phase (connect, read, ...), so a service that
        # trickles its answer could outlast it. The outer cap is the promise.
        response = await asyncio.wait_for(client.get(f"{service.url}/health", timeout=timeout), timeout)
    except TimeoutError:
        logger.info("health probe timed out for %s", service.name)
        return ServiceHealth(**who, status="unreachable", detail=f"no answer within {timeout:g}s")
    except httpx.HTTPError as error:
        logger.info("health probe failed for %s: %s", service.name, error)
        return ServiceHealth(**who, status="unreachable", detail=str(error) or type(error).__name__)

    if response.status_code != 200:
        # A service answers 503 when its database is gone. That is a different
        # thing from not answering at all, and worth saying so.
        return ServiceHealth(**who, status="degraded", detail=f"HTTP {response.status_code}")
    return ServiceHealth(**who, status="up")


def build_router(settings: ServerSettings) -> APIRouter:
    router = APIRouter(tags=["platform"])
    by_name = {service.name: service for service in settings.services}

    @router.get("/platform/services", response_model=list[ServiceInfo])
    async def platform_services() -> list[ServiceInfo]:
        """The services the screen shows, without asking them. Instant by design."""
        return [ServiceInfo(name=s.name, url=s.url, link=s.link()) for s in settings.services]

    @router.get("/platform/health/{name}", response_model=ServiceHealth)
    async def service_health(name: str) -> ServiceHealth:
        """One service, so one slow answer holds up nothing but itself."""
        service = by_name.get(name)
        if service is None:
            raise HTTPException(status_code=404, detail=f"no service called {name!r}")
        async with httpx.AsyncClient() as client:
            return await _probe(client, service, settings.health_timeout_seconds)

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
