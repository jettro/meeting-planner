"""FastMCP server exposing agent-facing tools for the location service.

This server implements **no business logic of its own** — every tool below is a
thin `httpx` wrapper around this service's own REST API (see design.md
section 3.1/3.2). The REST API stays the single source of truth for room
capacity/overlap checks; this module only reshapes REST responses into the
narrower, agent-oriented tool contracts from design.md section 3.4.
"""

from __future__ import annotations

import os
from datetime import date, datetime, time
from typing import Any, cast

import httpx
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

REST_BASE_URL = os.environ.get("LOCATION_SERVICE_REST_URL", "http://localhost:8002")
MCP_API_KEY = os.environ.get("LOCATION_MCP_API_KEY", "dev-location-mcp-key")

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


auth = StaticTokenVerifier(tokens={MCP_API_KEY: {"client_id": "agent", "scopes": []}})

mcp = FastMCP("location-service-mcp", auth=auth)


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
async def list_locations() -> list[dict[str, str]]:
    """List all known locations an agent can book a room or request a menu for."""
    resp = await get_client().get("/api/locations")
    resp.raise_for_status()
    return cast(list[dict[str, str]], resp.json())


@mcp.tool
async def list_rooms(location_id: str) -> list[dict[str, Any]]:
    """List the bookable rooms (code + capacity) at a given location."""
    resp = await get_client().get(f"/api/locations/{location_id}/rooms")
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return [{"room_code": r["room_code"], "capacity": r["capacity"]} for r in resp.json()]


@mcp.tool
async def get_room_availability(
    location_id: str,
    day: date,
    start: str,
    duration_minutes: int,
    number_of_people: int,
) -> dict[str, Any]:
    """Check whether a room is available at a location for a given day/time/headcount.

    Picks the smallest suitable room by capacity; does not return a free-slot
    list for a specific room — if nothing fits, `available` is simply false.

    `start` is a local clock reading such as `14:30`. The venue has no timezone,
    so do not add an offset.
    """
    try:
        times, note = _clocks(start=start)
    except ClockFormatError as exc:
        return {"available": False, "reason": str(exc)}

    resp = await get_client().post(
        "/api/rooms/check-availability",
        json={
            "location_id": location_id,
            "day": day.isoformat(),
            "start": times["start"].isoformat(),
            "duration_minutes": duration_minutes,
            "number_of_people": number_of_people,
        },
    )
    resp.raise_for_status()
    result = cast(dict[str, Any], resp.json())
    if note:
        result["note"] = note
    return result


@mcp.tool
async def book_room(
    location_id: str, room_code: str, day: date, start: str, end: str, title: str
) -> dict[str, Any]:
    """Book a specific room for a given day/time range.

    On failure, returns a human-readable `reason` the agent can relay or act on.

    `start` and `end` are local clock readings such as `14:30`. The venue has no
    timezone, so do not add an offset.
    """
    try:
        times, note = _clocks(start=start, end=end)
    except ClockFormatError as exc:
        return {"success": False, "reason": str(exc)}

    begins, finishes = times["start"], times["end"]
    duration_minutes = (
        datetime.combine(day, finishes) - datetime.combine(day, begins)
    ).seconds // 60
    resp = await get_client().post(
        "/api/rooms/book",
        json={
            "location_id": location_id,
            "room_code": room_code,
            "day": day.isoformat(),
            "start": begins.isoformat(),
            "duration_minutes": duration_minutes,
            "reference": title,
            "description": title,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    if not data["success"]:
        return {"success": False, "reason": data["message"]}
    return {
        "success": True,
        "booking_id": data["booking_id"],
        "location_id": data["location_id"],
        "room_code": data["room_code"],
        "day": day.isoformat(),
        "start": begins.isoformat(),
        "end": finishes.isoformat(),
        **({"note": note} if note else {}),
    }


@mcp.tool
async def cancel_room_booking(booking_id: int) -> dict[str, Any]:
    """Cancel a previously made room booking.

    Requires the exact `booking_id` returned by `book_room`.
    """
    resp = await get_client().delete(f"/api/rooms/bookings/{booking_id}")
    if resp.status_code == 404:
        return {"success": False, "message": f"Unknown booking id: {booking_id}"}
    resp.raise_for_status()
    return cast(dict[str, Any], resp.json())


def create_mcp_app() -> Any:
    """Build the ASGI app served by uvicorn for this service's MCP endpoint."""
    return mcp.http_app(path="/mcp")


mcp_app = create_mcp_app()
