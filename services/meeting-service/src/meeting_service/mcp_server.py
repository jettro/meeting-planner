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


class ClockFormatError(ValueError):
    """A tool was given something that is not a local clock reading."""


def _clock(name: str, value: str) -> time:
    """Parse a local clock reading such as `14:30`.

    These parameters are plain strings rather than `time` on purpose. Declared
    as a time, the generated tool schema carries `format: time`, and in live
    runs models answered that with a full ISO value - `10:00:00+00:00` - which
    is not a thing this domain has. A venue has no timezone, so an offset
    cannot be converted, only ignored or refused.

    A trailing offset is therefore ignored and the clock reading taken at face
    value, which is what the model meant in every observed case; the caller
    reports that it did so. Anything that is not a clock reading is refused,
    because guessing an hour is how a meeting ends up in the wrong place.
    """
    text = value.strip()
    for marker in ("+", "-"):
        head = text.split(marker, 1)[0]
        if head != text and ":" in head:
            text = head
    if text.endswith("Z"):
        text = text[:-1]

    parts = text.split(":")
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        raise ClockFormatError(f"{name}={value!r} is not a local time; send it as HH:MM")
    try:
        return time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) == 3 else 0)
    except ValueError as exc:
        raise ClockFormatError(f"{name}={value!r} is not a local time: {exc}") from exc


def _clocks(**values: str) -> tuple[dict[str, time], str]:
    """Parse several clock readings, with a note if any offset was dropped."""
    parsed = {name: _clock(name, value) for name, value in values.items()}
    dropped = [name for name, value in values.items() if _has_offset(value)]
    note = ""
    if dropped:
        note = (
            f"{' and '.join(dropped)} arrived with a timezone offset, which was "
            "ignored: times here are local to the venue. Send HH:MM next time."
        )
    return parsed, note


def _has_offset(value: str) -> bool:
    body = value.strip()
    return body.endswith("Z") or "+" in body or body.count("-") > 0


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
    participant_emails: list[str], day: date, start: str, end: str
) -> dict[str, Any]:
    """Check whether all given participants are free for a proposed meeting slot,
    without booking anything.

    `start` and `end` are local clock readings such as `14:30`. Agendas carry no
    timezone, so do not add an offset.
    """
    try:
        times, note = _clocks(start=start, end=end)
    except ClockFormatError as exc:
        return {"feasible": False, "reason": str(exc)}

    resp = await get_client().post(
        "/api/meetings/check-availability",
        json={
            "participant_emails": participant_emails,
            "day": day.isoformat(),
            "start": times["start"].isoformat(),
            "end": times["end"].isoformat(),
        },
    )
    resp.raise_for_status()
    data = resp.json()
    unavailable = [r["email"] for r in data["results"] if not r["available"]]
    result = {"feasible": data["all_available"], "unavailable_people": unavailable}
    if note:
        result["note"] = note
    return result


@mcp.tool
async def book_meeting(
    participant_emails: list[str], day: date, start: str, end: str, title: str
) -> dict[str, Any]:
    """Book a meeting for the given participants if they are all available.

    On failure, returns a human-readable `reason` the agent can relay or act on
    (e.g. try a different slot) instead of a list of alternatives.

    `start` and `end` are local clock readings such as `14:30`. Agendas carry no
    timezone, so do not add an offset.
    """
    try:
        times, note = _clocks(start=start, end=end)
    except ClockFormatError as exc:
        return {"success": False, "reason": str(exc)}

    resp = await get_client().post(
        "/api/meetings/book",
        json={
            "title": title,
            "participant_emails": participant_emails,
            "day": day.isoformat(),
            "start": times["start"].isoformat(),
            "end": times["end"].isoformat(),
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
        **({"note": note} if note else {}),
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
