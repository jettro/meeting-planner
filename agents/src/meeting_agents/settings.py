"""Runtime settings, read from the environment.

Everything here is deployment detail that must not be baked into the catalog YAML:
MCP endpoints differ between a container on the compose network and a process on
the host, and the API keys are secrets. The catalog stores `${VAR}` placeholders
and these values resolve them at team-build time.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return default if value is None or value == "" else value


class McpEndpoint(BaseModel):
    """One service's agent-facing MCP server."""

    url: str
    api_key: str

    model_config = {"frozen": True}


class Settings(BaseModel):
    """Where the team runs and what it may talk to."""

    meeting_mcp: McpEndpoint
    location_mcp: McpEndpoint
    nomnom_mcp: McpEndpoint

    openai_api_key: str = ""
    model: str = "gpt-6-luna"

    plan_store_path: Path = Field(default=Path("data/plans.json"))
    catalog_path: Path = Field(default=Path("catalog"))

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from the environment.

        Defaults use the Docker Compose service names, since that is where the team
        normally runs. Override the `*_MCP_URL` vars to point at `localhost:810x`
        when running on the host instead.
        """
        return cls(
            meeting_mcp=McpEndpoint(
                url=_env("MEETING_MCP_URL", "http://meeting-service:8101/mcp"),
                api_key=_env("MEETING_MCP_API_KEY", "dev-meeting-mcp-key"),
            ),
            location_mcp=McpEndpoint(
                url=_env("LOCATION_MCP_URL", "http://location-service:8102/mcp"),
                api_key=_env("LOCATION_MCP_API_KEY", "dev-location-mcp-key"),
            ),
            nomnom_mcp=McpEndpoint(
                url=_env("NOMNOM_MCP_URL", "http://nomnom-service:8103/mcp"),
                api_key=_env("NOMNOM_MCP_API_KEY", "dev-nomnom-mcp-key"),
            ),
            openai_api_key=_env("OPENAI_API_KEY", ""),
            model=_env("AGENT_MODEL", "gpt-6-luna"),
            plan_store_path=Path(_env("PLAN_STORE_PATH", "data/plans.json")),
            catalog_path=Path(_env("CATALOG_PATH", "catalog")),
        )

    def as_catalog_env(self) -> dict[str, str]:
        """The `${VAR}` values the catalog YAML refers to."""
        return {
            "MEETING_MCP_URL": self.meeting_mcp.url,
            "MEETING_MCP_API_KEY": self.meeting_mcp.api_key,
            "LOCATION_MCP_URL": self.location_mcp.url,
            "LOCATION_MCP_API_KEY": self.location_mcp.api_key,
            "NOMNOM_MCP_URL": self.nomnom_mcp.url,
            "NOMNOM_MCP_API_KEY": self.nomnom_mcp.api_key,
            "PLAN_STORE_PATH": str(self.plan_store_path),
        }
