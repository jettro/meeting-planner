"""API-level tests for room booking/cancellation."""

from fastapi.testclient import TestClient
from location_service.main import app

# Far enough in the future to never collide with the seeded sample bookings
# (which are generated relative to "today").
FUTURE_DAY = "2030-01-02"


def test_book_room_then_cancel_frees_the_slot():
    with TestClient(app) as client:
        locations = client.get("/api/locations").json()
        location_id = locations[0]["location_id"]
        rooms = client.get(f"/api/locations/{location_id}/rooms").json()
        room_code = rooms[0]["room_code"]

        payload = {
            "location_id": location_id,
            "room_code": room_code,
            "day": FUTURE_DAY,
            "start": "09:00:00",
            "duration_minutes": 30,
            "reference": "test-ref",
            "description": "Test booking",
        }

        booked = client.post("/api/rooms/book", json=payload)
        assert booked.status_code == 200
        body = booked.json()
        assert body["success"] is True
        booking_id = body["booking_id"]
        assert booking_id is not None

        # Same slot is now unavailable.
        conflict = client.post("/api/rooms/book", json=payload)
        assert conflict.json()["success"] is False

        # Cancel the booking.
        cancelled = client.delete(f"/api/rooms/bookings/{booking_id}")
        assert cancelled.status_code == 200
        assert cancelled.json()["success"] is True

        # Cancelling again is a 404 (already gone).
        missing = client.delete(f"/api/rooms/bookings/{booking_id}")
        assert missing.status_code == 404

        # Slot is free again after cancellation.
        rebooked = client.post("/api/rooms/book", json=payload)
        assert rebooked.json()["success"] is True
