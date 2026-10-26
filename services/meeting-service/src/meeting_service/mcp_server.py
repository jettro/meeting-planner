"""FastMCP server exposing agent-facing tools for the meeting service.

This server implements **no business logic of its own** — every tool below is a
thin `httpx` wrapper around this service's own REST API (see design.md
section 3.1/3.2). The REST API stays the single source of truth for
availability checks and booking rules; this module only reshapes REST
responses into the narrower, agent-oriented tool contracts from design.md
section 3.4.
"""

from __future__ import annotations

import os
from datetime import date, time
from typing import Any, cast

import httpx
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

REST_BASE_URL = os.environ.get("MEETING_SERVICE_REST_URL", "http://localhost:8001")
MCP_API_KEY = os.environ.get("MEETING_MCP_API_KEY", "dev-meeting-mcp-key")

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    """Return the shared REST client, creating a real network client lazily."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=REST_BASE_URL, timeout=10.0)
    return _client


def set_client(client: httpx.AsyncClient) -> None:
    """Override the REST client. Used by tests to inject an in-process transport."""
    global _client
    _client = client


def _slot_to_dict(slot: str) -> dict[str, str]:
    start, end = slot.split("-")
    return {"start": start, "end": end}


auth = StaticTokenVerifier(tokens={MCP_API_KEY: {"client_id": "agent", "scopes": []}})

mcp = FastMCP("meeting-service-mcp", auth=auth)


@mcp.tool
async def list_people() -> list[dict[str, str]]:
    """List all known people (email + name) so an agent can resolve names to the
    emails the other tools need."""
    resp = await get_client().get("/api/persons")
    resp.raise_for_status()
    return cast(list[dict[str, str]], resp.json())


@mcp.tool
async def get_person_availability(email: str, day: date) -> dict[str, Any]:
    """Get a person's free time slots on a given day.

    Only returns free gaps, never the content of their other meetings.
    """
    resp = await get_client().get(f"/api/persons/{email}/agenda", params={"day": day.isoformat()})
    if resp.status_code == 404:
        return {"error": f"Unknown person: {email}"}
    resp.raise_for_status()
    data = resp.json()
    return {
        "email": data["email"],
        "name": data["name"],
        "free_slots": [_slot_to_dict(s) for s in data["free_slots"]],
    }


@mcp.tool
async def find_common_slots(
    participant_emails: list[str], day: date, duration_minutes: int = 60
) -> dict[str, Any]:
    """Find every window on `day` in which ALL participants are free for at least
    `duration_minutes`.

    Prefer this over calling `get_person_availability` per person and intersecting
    the results yourself. Each returned slot gives the window `start` and `end` plus
    `latest_start`, the last moment a meeting of this duration can begin - so no
    arithmetic is needed. An empty `slots` list means there is no common window.
    """
    resp = await get_client().post(
        "/api/meetings/common-slots",
        json={
            "participant_emails": participant_emails,
            "day": day.isoformat(),
            "duration_minutes": duration_minutes,
        },
    )
    if resp.status_code == 404:
        return {"error": resp.json().get("detail", "Unknown person")}
    resp.raise_for_status()
    data = resp.json()
    return {"day": data["day"], "duration_minutes": data["duration_minutes"], "slots": data["slots"]}


@mcp.tool
async def check_meeting_feasibility(
    participant_emails: list[str], day: date, start: time, end: time
) -> dict[str, Any]:
    """Check whether all given participants are free for a proposed meeting slot,
    without booking anything."""
    resp = await get_client().post(
        "/api/meetings/check-availability",
        json={
            "participant_emails": participant_emails,
            "day": day.isoformat(),
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
    )
    resp.raise_for_status()
    data = resp.json()
    unavailable = [r["email"] for r in data["results"] if not r["available"]]
    return {"feasible": data["all_available"], "unavailable_people": unavailable}


@mcp.tool
async def book_meeting(
    participant_emails: list[str], day: date, start: time, end: time, title: str
) -> dict[str, Any]:
    """Book a meeting for the given participants if they are all available.

    On failure, returns a human-readable `reason` the agent can relay or act on
    (e.g. try a different slot) instead of a list of alternatives.
    """
    resp = await get_client().post(
        "/api/meetings/book",
        json={
            "title": title,
            "participant_emails": participant_emails,
            "day": day.isoformat(),
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
    )
    resp.raise_for_status()
    data = resp.json()
    if not data["booked"]:
        return {"success": False, "reason": data["message"]}
    meeting = data["meeting"]
    return {
        "success": True,
        "meeting_id": meeting["id"],
        "day": meeting["day"],
        "start": meeting["start"],
        "end": meeting["end"],
        "participant_emails": meeting["participant_emails"],
    }


@mcp.tool
async def cancel_meeting(meeting_id: int) -> dict[str, Any]:
    """Cancel a previously booked meeting.

    Requires the exact `meeting_id` returned by `book_meeting` — there is no
    lookup by title/description.
    """
    resp = await get_client().delete(f"/api/meetings/{meeting_id}")
    if resp.status_code == 404:
        return {"success": False, "message": f"Unknown meeting id: {meeting_id}"}
    resp.raise_for_status()
    return cast(dict[str, Any], resp.json())


def create_mcp_app() -> Any:
    """Build the ASGI app served by uvicorn for this service's MCP endpoint."""
    return mcp.http_app(path="/mcp")


mcp_app = create_mcp_app()
