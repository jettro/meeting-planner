"""FastMCP server exposing agent-facing tools for the NomNom ordering service.

This server implements **no business logic of its own** — every tool below is a
thin `httpx` wrapper around this service's own REST API (see design.md
section 3.1/3.2). The REST API stays the single source of truth for pricing
and order status; this module only reshapes REST responses into the
narrower, agent-oriented tool contracts from design.md section 3.4.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any, cast

import httpx
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

REST_BASE_URL = os.environ.get("NOMNOM_SERVICE_REST_URL", "http://localhost:8003")
MCP_API_KEY = os.environ.get("NOMNOM_MCP_API_KEY", "dev-nomnom-mcp-key")

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

mcp = FastMCP("nomnom-service-mcp", auth=auth)


@mcp.tool
async def get_menu(category: str | None = None) -> list[dict[str, Any]]:
    """List menu items, optionally filtered by category, for an agent to pick from."""
    params = {"category": category} if category else None
    resp = await get_client().get("/api/products", params=params)
    resp.raise_for_status()
    return [
        {
            "item_id": p["id"],
            "name": p["name"],
            "description": p["description"],
            "price": p["price"],
            "category": p["category"],
        }
        for p in resp.json()
    ]


@mcp.tool
async def search_product(query: str) -> dict[str, Any] | None:
    """Fuzzy-match a free-text request (e.g. 'a coffee') to a single menu item."""
    resp = await get_client().get("/api/products/search", params={"q": query})
    resp.raise_for_status()
    product = resp.json()
    if product is None:
        return None
    return {
        "item_id": product["id"],
        "name": product["name"],
        "price": product["price"],
        "description": product["description"],
    }


@mcp.tool
async def place_order(
    location: str, delivery_date: date, items: list[dict[str, int]], note: str = ""
) -> dict[str, Any]:
    """Place an order for the given location/date with a list of
    `{item_id, quantity}` entries.

    On failure, returns a human-readable `reason` (e.g. unknown item id).
    """
    resp = await get_client().post(
        "/api/orders",
        json={
            "location": location,
            "delivery_date": delivery_date.isoformat(),
            "items": [{"product_id": item["item_id"], "quantity": item["quantity"]} for item in items],
            "note": note,
        },
    )
    if resp.status_code >= 400:
        detail = resp.json().get("detail", "Could not place order")
        return {"success": False, "reason": detail}
    data = resp.json()
    return {
        "success": True,
        "order_id": data["order_id"],
        "total_amount": data["total_amount"],
        "status": data["status"],
    }


@mcp.tool
async def get_order_status(order_id: str) -> dict[str, Any]:
    """Get enough detail about an order to understand/act on its current state."""
    resp = await get_client().get(f"/api/orders/{order_id}")
    if resp.status_code == 404:
        return {"error": f"Unknown order: {order_id}"}
    resp.raise_for_status()
    data = resp.json()
    return {
        "order_id": data["order_id"],
        "status": data["status"],
        "delivery_date": data["delivery_date"],
        "total_amount": data["total_amount"],
        "items": [{"name": i["product_name"], "quantity": i["quantity"]} for i in data["items"]],
    }


@mcp.tool
async def cancel_order(order_id: str) -> dict[str, Any]:
    """Cancel a previously placed order.

    Requires the exact `order_id` returned by `place_order`.
    """
    resp = await get_client().post(f"/api/orders/{order_id}/cancel")
    if resp.status_code == 404:
        return {"success": False, "message": f"Unknown order: {order_id}"}
    resp.raise_for_status()
    return cast(dict[str, Any], resp.json())


def create_mcp_app() -> Any:
    """Build the ASGI app served by uvicorn for this service's MCP endpoint."""
    return mcp.http_app(path="/mcp")


mcp_app = create_mcp_app()
