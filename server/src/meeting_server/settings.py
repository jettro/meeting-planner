"""What the server needs to know that the framework does not configure.

`CommunitySettings` covers the server itself. These are the things that are
ours: where the three services live, so the browser can be told whether they
are up, and who may log in (design_auth.md). There is no plan store: a
meeting's record is its team's coordinator state, kept by the framework's own
event store (design_durability.md).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


class ServiceEndpoint(BaseModel):
    """One of the three services, as the platform screen needs to see it."""

    name: str
    url: str


class AuthSettings(BaseModel):
    """Who is asking (design_auth.md A1-A7, A14).

    `off` is the framework's own behaviour: every request is `anonymous`. It is
    the default for a settings object built in code, so a test states when it
    wants a login; the deployed server reads `AUTH` and defaults to `demo`.
    """

    mode: Literal["demo", "off"] = "off"

    #: Signs the session cookie. Empty means a fresh key per process: sessions
    #: then end at every restart, which is acceptable for a demo and needs no
    #: secret in anybody's `.env`.
    secret: SecretStr = SecretStr("")

    #: Principals that get the `admin` role, and with it every team (A7).
    admin_emails: frozenset[str] = frozenset()

    #: API key -> the email it logs in as (A14). Never in the repo.
    api_keys: dict[str, str] = Field(default_factory=dict)

    session_max_age_seconds: int = 8 * 3600


def _api_keys(raw: str) -> dict[str, str]:
    """`key=email,key=email` - the shape a compose variable can hold."""
    pairs = (item.split("=", 1) for item in raw.split(",") if "=" in item)
    return {key.strip(): email.strip().lower() for key, email in pairs if key.strip() and email.strip()}


class ServerSettings(BaseModel):
    """Configuration read once at startup.

    Defaults are the compose names, because that is how this runs for real. A
    host run overrides them, the same way the agents' own settings work.
    """

    catalog_path: Path = Field(default=Path("catalog"))
    event_store_path: Path = Field(default=Path("data/events"))
    workspaces_root: Path = Field(default=Path("data/workspaces"))

    #: Where the SPA is served from. The browser is a second origin by
    #: construction (G2), so this is not optional extra hardening.
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    services: list[ServiceEndpoint] = Field(default_factory=list)

    #: How long the platform screen waits on a service before calling it down.
    #: Short on purpose: an unreachable service should colour the dot quickly,
    #: not make the whole screen hang on the slowest one.
    health_timeout_seconds: float = 3.0

    auth: AuthSettings = Field(default_factory=AuthSettings)

    host: str = "0.0.0.0"  # noqa: S104 - a container port is published deliberately
    port: int = 8200

    def service_url(self, name: str) -> str | None:
        """The REST base of one of the services, by name."""
        return next((service.url for service in self.services if service.name == name), None)

    @classmethod
    def from_env(cls) -> ServerSettings:
        return cls(
            catalog_path=Path(_env("CATALOG_PATH", "catalog")),
            event_store_path=Path(_env("EVENT_STORE_PATH", "data/events")),
            workspaces_root=Path(_env("WORKSPACES_ROOT", "data/workspaces")),
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
            auth=AuthSettings(
                mode="off" if _env("AUTH", "demo") == "off" else "demo",
                secret=SecretStr(_env("AUTH_SECRET", "")),
                admin_emails=frozenset(
                    email.strip().lower() for email in _env("ADMIN_EMAILS", "").split(",") if email.strip()
                ),
                api_keys=_api_keys(_env("API_KEYS", "")),
                session_max_age_seconds=int(_env("SESSION_MAX_AGE_SECONDS", str(8 * 3600))),
            ),
            host=_env("SERVER_HOST", "0.0.0.0"),  # noqa: S104
            port=int(_env("SERVER_PORT", "8200")),
        )
