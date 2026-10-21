"""API-level tests for meeting booking/cancellation."""

from fastapi.testclient import TestClient
from meeting_service.main import app


def test_book_meeting_then_cancel_frees_the_slot():
    with TestClient(app) as client:
        persons = client.get("/api/persons").json()
        email = persons[0]["email"]
        day = "2026-03-02"
        payload = {
            "title": "Sync",
            "participant_emails": [email],
            "day": day,
            "start": "09:00:00",
            "end": "09:30:00",
        }

        booked = client.post("/api/meetings/book", json=payload)
        assert booked.status_code == 200
        body = booked.json()
        assert body["booked"] is True
        meeting_id = body["meeting"]["id"]

        # Same slot is now unavailable.
        conflict = client.post("/api/meetings/book", json=payload)
        assert conflict.json()["booked"] is False

        # Cancel the meeting.
        cancelled = client.delete(f"/api/meetings/{meeting_id}")
        assert cancelled.status_code == 200
        assert cancelled.json()["success"] is True

        # Cancelling again is a 404 (already gone).
        missing = client.delete(f"/api/meetings/{meeting_id}")
        assert missing.status_code == 404

        # Slot is free again after cancellation.
        rebooked = client.post("/api/meetings/book", json=payload)
        assert rebooked.json()["booked"] is True
