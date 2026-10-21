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
    location_id: str, day: date, start: time, duration_minutes: int, number_of_people: int
) -> dict[str, Any]:
    """Check whether a room is available at a location for a given day/time/headcount.

    Picks the smallest suitable room by capacity; does not return a free-slot
    list for a specific room — if nothing fits, `available` is simply false.
    """
    resp = await get_client().post(
        "/api/rooms/check-availability",
        json={
            "location_id": location_id,
            "day": day.isoformat(),
            "start": start.isoformat(),
            "duration_minutes": duration_minutes,
            "number_of_people": number_of_people,
        },
    )
    resp.raise_for_status()
    return cast(dict[str, Any], resp.json())


@mcp.tool
async def book_room(
    location_id: str, room_code: str, day: date, start: time, end: time, title: str
) -> dict[str, Any]:
    """Book a specific room for a given day/time range.

    On failure, returns a human-readable `reason` the agent can relay or act on.
    """
    duration_minutes = (datetime.combine(day, end) - datetime.combine(day, start)).seconds // 60
    resp = await get_client().post(
        "/api/rooms/book",
        json={
            "location_id": location_id,
            "room_code": room_code,
            "day": day.isoformat(),
            "start": start.isoformat(),
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
        "start": start.isoformat(),
        "end": end.isoformat(),
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
