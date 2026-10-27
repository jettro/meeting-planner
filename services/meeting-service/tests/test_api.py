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


def test_common_slots_reflects_both_agendas():
    with TestClient(app) as client:
        persons = client.get("/api/persons").json()
        jettro, daniel = persons[0]["email"], persons[1]["email"]
        day = "2032-04-06"

        # Nobody is busy yet: the whole working day is one window.
        body = client.post(
            "/api/meetings/common-slots",
            json={"participant_emails": [jettro, daniel], "day": day, "duration_minutes": 60},
        ).json()
        assert body["slots"] == [{"start": "09:00:00", "end": "17:00:00", "latest_start": "16:00:00"}]

        # Book each of them separately; the common windows shrink accordingly.
        for email, start, end in ((jettro, "09:00:00", "11:00:00"), (daniel, "13:00:00", "14:00:00")):
            booked = client.post(
                "/api/meetings/book",
                json={
                    "title": "Busy",
                    "participant_emails": [email],
                    "day": day,
                    "start": start,
                    "end": end,
                },
            )
            assert booked.json()["booked"] is True

        slots = client.post(
            "/api/meetings/common-slots",
            json={"participant_emails": [jettro, daniel], "day": day, "duration_minutes": 60},
        ).json()["slots"]
        assert [(s["start"], s["end"]) for s in slots] == [
            ("11:00:00", "13:00:00"),
            ("14:00:00", "17:00:00"),
        ]

        # A 150-minute meeting no longer fits in the first window.
        long_slots = client.post(
            "/api/meetings/common-slots",
            json={"participant_emails": [jettro, daniel], "day": day, "duration_minutes": 150},
        ).json()["slots"]
        assert [s["start"] for s in long_slots] == ["14:00:00"]


def test_common_slots_unknown_person_is_404():
    with TestClient(app) as client:
        response = client.post(
            "/api/meetings/common-slots",
            json={"participant_emails": ["nobody@rag4p.org"], "day": "2032-04-07"},
        )
        assert response.status_code == 404


def test_booking_with_a_timezone_offset_is_refused_clearly():
    """Agendas are local wall-clock, so an offset is ambiguous rather than
    helpful; refusing beats guessing an hour. See location-service for the
    live failure that found this."""
    with TestClient(app) as client:
        response = client.post(
            "/api/meetings/book",
            json={
                "title": "Offset",
                "participant_emails": ["sanne@rag4p.org"],
                "day": "2032-04-06",
                "start": "09:00:00+02:00",
                "end": "10:00:00+02:00",
            },
        )

        assert response.status_code == 422
        assert "timezone" in response.text
