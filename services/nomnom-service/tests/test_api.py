"""API-level tests for order creation/cancellation."""

from fastapi.testclient import TestClient
from nomnom_service.main import app


def test_place_order_then_cancel():
    with TestClient(app) as client:
        products = client.get("/api/products").json()
        product_id = products[0]["id"]

        payload = {
            "location": "yuma",
            "delivery_date": "2030-01-02",
            "items": [{"product_id": product_id, "quantity": 2}],
            "note": "test order",
        }

        created = client.post("/api/orders", json=payload)
        assert created.status_code == 200
        order = created.json()
        order_id = order["order_id"]
        assert order["status"] == "CONFIRMED"

        cancelled = client.post(f"/api/orders/{order_id}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["success"] is True

        # Status reflects the cancellation.
        fetched = client.get(f"/api/orders/{order_id}")
        assert fetched.json()["status"] == "CANCELLED"

        # Cancelling an already-cancelled order reports failure, not a hard error.
        again = client.post(f"/api/orders/{order_id}/cancel")
        assert again.status_code == 200
        assert again.json()["success"] is False

        # Cancelling an unknown order is a 404.
        missing = client.post("/api/orders/does-not-exist/cancel")
        assert missing.status_code == 404
