"""Tests for the NomNom MCP tool layer.

Verifies that the MCP tools are thin, correctly-shaped wrappers around the
REST API: no network/HTTP server is started — the mcp_server's REST client is
pointed at the FastAPI app directly via an in-process ASGI transport, and the
MCP tools are called through FastMCP's in-memory client transport.
"""

import httpx
import pytest
from fastmcp import Client
from nomnom_service import mcp_server
from nomnom_service.db import engine, init_db
from nomnom_service.main import app
from nomnom_service.seed import seed
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


async def test_get_menu_and_search_product():
    async with Client(mcp_server.mcp) as client:
        menu = (await client.call_tool("get_menu", {})).data
        assert len(menu) > 0
        assert {"item_id", "name", "description", "price", "category"} <= menu[0].keys()

        match = (await client.call_tool("search_product", {"query": menu[0]["name"]})).data
        assert match is not None
        assert match["item_id"] == menu[0]["item_id"]


async def test_place_order_get_status_and_cancel():
    async with Client(mcp_server.mcp) as client:
        menu = (await client.call_tool("get_menu", {})).data
        item_id = menu[0]["item_id"]

        placed = (
            await client.call_tool(
                "place_order",
                {
                    "location": "yuma",
                    "delivery_date": "2030-01-02",
                    "items": [{"item_id": item_id, "quantity": 2}],
                },
            )
        ).data
        assert placed["success"] is True
        order_id = placed["order_id"]

        status = (await client.call_tool("get_order_status", {"order_id": order_id})).data
        assert status["status"] == "CONFIRMED"
        assert status["items"] == [{"name": menu[0]["name"], "quantity": 2}]

        cancelled = (await client.call_tool("cancel_order", {"order_id": order_id})).data
        assert cancelled["success"] is True

        status_after = (await client.call_tool("get_order_status", {"order_id": order_id})).data
        assert status_after["status"] == "CANCELLED"


async def test_place_order_with_unknown_item_fails():
    async with Client(mcp_server.mcp) as client:
        result = (
            await client.call_tool(
                "place_order",
                {
                    "location": "yuma",
                    "delivery_date": "2030-01-02",
                    "items": [{"item_id": 999999, "quantity": 1}],
                },
            )
        ).data
        assert result["success"] is False
        assert "reason" in result


async def test_cancel_unknown_order_returns_failure_not_error():
    async with Client(mcp_server.mcp) as client:
        result = (
            await client.call_tool("cancel_order", {"order_id": "does-not-exist"})
        ).data
        assert result["success"] is False
