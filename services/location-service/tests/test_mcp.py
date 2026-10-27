"""Tests for the location-service MCP tool layer.

Verifies that the MCP tools are thin, correctly-shaped wrappers around the
REST API: no network/HTTP server is started — the mcp_server's REST client is
pointed at the FastAPI app directly via an in-process ASGI transport, and the
MCP tools are called through FastMCP's in-memory client transport.
"""

import httpx
import pytest
from fastmcp import Client
from location_service import mcp_server
from location_service.db import engine, init_db
from location_service.main import app
from location_service.seed import seed
from sqlmodel import Session


@pytest.fixture(autouse=True)
def _wire_mcp_to_in_process_app():
    """Point the MCP server's REST client at the FastAPI app in-process."""
    init_db()
    with Session(engine) as session:
        seed(session)
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    mcp_server.set_client(client)
    yield
    mcp_server.set_client(None)  # type: ignore[arg-type]


async def test_list_locations_and_rooms():
    async with Client(mcp_server.mcp) as client:
        locations = (await client.call_tool("list_locations", {})).data
        assert any(loc["location_id"] == "yuma" for loc in locations)

        rooms = (await client.call_tool("list_rooms", {"location_id": "yuma"})).data
        assert {"room_code": "room-a", "capacity": 4} in rooms


async def test_book_room_then_cancel():
    async with Client(mcp_server.mcp) as client:
        booked = (
            await client.call_tool(
                "book_room",
                {
                    "location_id": "yuma",
                    "room_code": "room-a",
                    "day": "2031-01-02",
                    "start": "09:00:00",
                    "end": "09:30:00",
                    "title": "Smoke test",
                },
            )
        ).data
        assert booked["success"] is True
        booking_id = booked["booking_id"]

        cancelled = (
            await client.call_tool("cancel_room_booking", {"booking_id": booking_id})
        ).data
        assert cancelled["success"] is True


async def test_book_room_conflict_returns_reason():
    async with Client(mcp_server.mcp) as client:
        first = (
            await client.call_tool(
                "book_room",
                {
                    "location_id": "yuma",
                    "room_code": "room-b",
                    "day": "2030-02-02",
                    "start": "10:00:00",
                    "end": "11:00:00",
                    "title": "First",
                },
            )
        ).data
        assert first["success"] is True

        second = (
            await client.call_tool(
                "book_room",
                {
                    "location_id": "yuma",
                    "room_code": "room-b",
                    "day": "2030-02-02",
                    "start": "10:00:00",
                    "end": "11:00:00",
                    "title": "Clash",
                },
            )
        ).data
        assert second["success"] is False
        assert "reason" in second


async def test_get_room_availability():
    async with Client(mcp_server.mcp) as client:
        available = (
            await client.call_tool(
                "get_room_availability",
                {
                    "location_id": "yuma",
                    "day": "2030-03-03",
                    "start": "09:00:00",
                    "duration_minutes": 30,
                    "number_of_people": 3,
                },
            )
        ).data
        assert available["available"] is True

        too_big = (
            await client.call_tool(
                "get_room_availability",
                {
                    "location_id": "yuma",
                    "day": "2030-03-03",
                    "start": "09:00:00",
                    "duration_minutes": 30,
                    "number_of_people": 999,
                },
            )
        ).data
        assert too_big["available"] is False


async def test_cancel_unknown_booking_returns_failure_not_error():
    async with Client(mcp_server.mcp) as client:
        result = (
            await client.call_tool("cancel_room_booking", {"booking_id": 999999})
        ).data
        assert result["success"] is False


async def test_an_offset_the_model_invented_is_ignored_and_reported():
    """Live runs showed models answering a `format: time` schema with
    `11:00:00+00:00`. A venue has no timezone, so the offset is meaningless
    rather than a conversion request - the clock reading is taken at face value
    and the agent is told, instead of the plan dying over punctuation."""
    async with Client(mcp_server.mcp) as client:
        result = (
            await client.call_tool(
                "book_room",
                {
                    "location_id": "yuma",
                    "room_code": "room-a",
                    "day": "2031-01-02",
                    "start": "11:00:00+00:00",
                    "end": "12:00:00+00:00",
                    "title": "Offset",
                },
            )
        ).data

        assert result["success"] is True
        assert result["start"] == "11:00:00"
        assert result["end"] == "12:00:00"
        assert "local" in result["note"]


async def test_a_time_that_is_not_a_clock_reading_is_refused():
    """Ignoring an offset is safe; guessing at nonsense is not."""
    async with Client(mcp_server.mcp) as client:
        result = (
            await client.call_tool(
                "book_room",
                {
                    "location_id": "yuma",
                    "room_code": "room-a",
                    "day": "2031-01-02",
                    "start": "elevenish",
                    "end": "12:00",
                    "title": "Vague",
                },
            )
        ).data

        assert result["success"] is False
        assert "HH:MM" in result["reason"]
