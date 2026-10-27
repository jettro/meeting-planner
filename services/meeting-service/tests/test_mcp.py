"""Tests for the meeting-service MCP tool layer.

Verifies that the MCP tools are thin, correctly-shaped wrappers around the
REST API: no network/HTTP server is started — the mcp_server's REST client is
pointed at the FastAPI app directly via an in-process ASGI transport, and the
MCP tools are called through FastMCP's in-memory client transport.
"""

import httpx
import pytest
from fastmcp import Client
from meeting_service import mcp_server
from meeting_service.db import engine, init_db
from meeting_service.main import app
from meeting_service.seed import seed
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


async def test_list_people():
    async with Client(mcp_server.mcp) as client:
        people = (await client.call_tool("list_people", {})).data
        assert {"email": "sanne@rag4p.org", "name": "Sanne de Vries"} in people


async def test_get_person_availability():
    async with Client(mcp_server.mcp) as client:
        result = (
            await client.call_tool(
                "get_person_availability", {"email": "sanne@rag4p.org", "day": "2030-01-02"}
            )
        ).data
        assert result["email"] == "sanne@rag4p.org"
        assert result["free_slots"] == [{"start": "09:00", "end": "17:00"}]


async def test_book_meeting_then_feasibility_then_cancel():
    async with Client(mcp_server.mcp) as client:
        booked = (
            await client.call_tool(
                "book_meeting",
                {
                    "participant_emails": ["sanne@rag4p.org"],
                    "day": "2030-01-02",
                    "start": "09:00:00",
                    "end": "09:30:00",
                    "title": "Standup",
                },
            )
        ).data
        assert booked["success"] is True
        meeting_id = booked["meeting_id"]

        feasibility = (
            await client.call_tool(
                "check_meeting_feasibility",
                {
                    "participant_emails": ["sanne@rag4p.org"],
                    "day": "2030-01-02",
                    "start": "09:00:00",
                    "end": "09:30:00",
                },
            )
        ).data
        assert feasibility == {"feasible": False, "unavailable_people": ["sanne@rag4p.org"]}

        cancelled = (await client.call_tool("cancel_meeting", {"meeting_id": meeting_id})).data
        assert cancelled["success"] is True

        feasibility_after = (
            await client.call_tool(
                "check_meeting_feasibility",
                {
                    "participant_emails": ["sanne@rag4p.org"],
                    "day": "2030-01-02",
                    "start": "09:00:00",
                    "end": "09:30:00",
                },
            )
        ).data
        assert feasibility_after == {"feasible": True, "unavailable_people": []}


async def test_book_meeting_conflict_returns_reason():
    async with Client(mcp_server.mcp) as client:
        first = (
            await client.call_tool(
                "book_meeting",
                {
                    "participant_emails": ["daan@rag4p.org"],
                    "day": "2030-02-02",
                    "start": "10:00:00",
                    "end": "11:00:00",
                    "title": "Planning",
                },
            )
        ).data
        assert first["success"] is True

        second = (
            await client.call_tool(
                "book_meeting",
                {
                    "participant_emails": ["daan@rag4p.org"],
                    "day": "2030-02-02",
                    "start": "10:00:00",
                    "end": "11:00:00",
                    "title": "Clash",
                },
            )
        ).data
        assert second["success"] is False
        assert "reason" in second


async def test_cancel_unknown_meeting_returns_failure_not_error():
    async with Client(mcp_server.mcp) as client:
        result = (await client.call_tool("cancel_meeting", {"meeting_id": 999999})).data
        assert result["success"] is False


async def test_find_common_slots():
    async with Client(mcp_server.mcp) as client:
        result = (
            await client.call_tool(
                "find_common_slots",
                {
                    "participant_emails": ["sanne@rag4p.org", "daan@rag4p.org"],
                    "day": "2033-05-10",
                    "duration_minutes": 60,
                },
            )
        ).data
        assert result["duration_minutes"] == 60
        assert result["slots"] == [{"start": "09:00:00", "end": "17:00:00", "latest_start": "16:00:00"}]


async def test_find_common_slots_unknown_person_returns_error():
    async with Client(mcp_server.mcp) as client:
        result = (
            await client.call_tool(
                "find_common_slots",
                {"participant_emails": ["nobody@rag4p.org"], "day": "2033-05-11"},
            )
        ).data
        assert "error" in result


async def test_an_offset_the_model_invented_is_ignored_and_reported():
    """Same as the location service: agendas are local wall-clock, so an offset
    is noise. The booking goes through at the clock reading given, and the
    answer says the offset was dropped."""
    async with Client(mcp_server.mcp) as client:
        result = (
            await client.call_tool(
                "book_meeting",
                {
                    "participant_emails": ["sanne@rag4p.org"],
                    "day": "2033-05-10",
                    "start": "14:00:00+02:00",
                    "end": "15:00:00+02:00",
                    "title": "Offset",
                },
            )
        ).data

        assert result["success"] is True
        assert result["start"] == "14:00:00"
        assert "local" in result["note"]


async def test_a_time_that_is_not_a_clock_reading_is_refused():
    async with Client(mcp_server.mcp) as client:
        result = (
            await client.call_tool(
                "book_meeting",
                {
                    "participant_emails": ["sanne@rag4p.org"],
                    "day": "2033-05-11",
                    "start": "after lunch",
                    "end": "15:00",
                    "title": "Vague",
                },
            )
        ).data

        assert result["success"] is False
        assert "HH:MM" in result["reason"]
