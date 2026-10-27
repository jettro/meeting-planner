"""What the server needs to know that the framework does not configure.

`CommunitySettings` covers the server itself. These are the two things that are
ours: where the three services live (so the browser can be told whether they
are up) and where plans are stored.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


class ServiceEndpoint(BaseModel):
    """One of the three services, as the platform screen needs to see it."""

    name: str
    url: str


class ServerSettings(BaseModel):
    """Configuration read once at startup.

    Defaults are the compose names, because that is how this runs for real. A
    host run overrides them, the same way the agents' own settings work.
    """

    catalog_path: Path = Field(default=Path("catalog"))
    event_store_path: Path = Field(default=Path("data/events"))
    workspaces_root: Path = Field(default=Path("data/workspaces"))
    plan_store_path: Path = Field(default=Path("data/plans.json"))

    #: Where the SPA is served from. The browser is a second origin by
    #: construction (G2), so this is not optional extra hardening.
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    services: list[ServiceEndpoint] = Field(default_factory=list)

    #: How long the platform screen waits on a service before calling it down.
    #: Short on purpose: an unreachable service should colour the dot quickly,
    #: not make the whole screen hang on the slowest one.
    health_timeout_seconds: float = 3.0

    host: str = "0.0.0.0"  # noqa: S104 - a container port is published deliberately
    port: int = 8200

    @classmethod
    def from_env(cls) -> ServerSettings:
        return cls(
            catalog_path=Path(_env("CATALOG_PATH", "catalog")),
            event_store_path=Path(_env("EVENT_STORE_PATH", "data/events")),
            workspaces_root=Path(_env("WORKSPACES_ROOT", "data/workspaces")),
            plan_store_path=Path(_env("PLAN_STORE_PATH", "data/plans.json")),
            cors_origins=[
                origin.strip()
                for origin in _env("CORS_ORIGINS", "http://localhost:5173").split(",")
                if origin.strip()
            ],
            services=[
                ServiceEndpoint(
                    name="meeting-service",
                    url=_env("MEETING_SERVICE_URL", "http://meeting-service:8101"),
                ),
                ServiceEndpoint(
                    name="location-service",
                    url=_env("LOCATION_SERVICE_URL", "http://location-service:8102"),
                ),
                ServiceEndpoint(
                    name="nomnom-service",
                    url=_env("NOMNOM_SERVICE_URL", "http://nomnom-service:8103"),
                ),
            ],
            health_timeout_seconds=float(_env("HEALTH_TIMEOUT_SECONDS", "3.0")),
            host=_env("SERVER_HOST", "0.0.0.0"),  # noqa: S104
            port=int(_env("SERVER_PORT", "8200")),
        )
