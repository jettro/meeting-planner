"""A person's own meetings, in date order (`GET /api/persons/{email}/meetings`).

The free-slot view answers the agents' question - when is this person free on
one day. This one answers the person's: what am I in. The tests share one
database with the rest of the suite, so each picks days nobody else uses.
"""

from fastapi.testclient import TestClient
from meeting_service.main import app

SANNE = "sanne@rag4p.org"
DAAN = "daan@rag4p.org"


def book(client: TestClient, title: str, emails: list[str], day: str, start: str, end: str) -> int:
    response = client.post(
        "/api/meetings/book",
        json={"title": title, "participant_emails": emails, "day": day, "start": start, "end": end},
    )
    assert response.json()["booked"] is True, response.text
    return response.json()["meeting"]["id"]


def meetings(client: TestClient, email: str, **window: str) -> list[dict]:
    response = client.get(f"/api/persons/{email}/meetings", params=window)
    assert response.status_code == 200, response.text
    return response.json()["meetings"]


def test_a_person_sees_their_meetings_in_the_order_they_happen():
    with TestClient(app) as client:
        later = book(client, "Retro", [SANNE, DAAN], "2041-03-06", "14:00:00", "15:00:00")
        first = book(client, "Stand-up", [SANNE], "2041-03-05", "09:00:00", "09:15:00")
        same_day = book(client, "Review", [SANNE, DAAN], "2041-03-05", "11:00:00", "12:00:00")

        found = meetings(client, SANNE, from_day="2041-03-01", to_day="2041-03-31")

        assert [m["meeting_id"] for m in found] == [first, same_day, later]
        assert found[1] == {
            "meeting_id": same_day,
            "title": "Review",
            "day": "2041-03-05",
            "start": "11:00:00",
            "end": "12:00:00",
            "participant_emails": [SANNE, DAAN],
        }


def test_only_the_meetings_the_person_is_in():
    with TestClient(app) as client:
        book(client, "Sanne alone", [SANNE], "2041-04-02", "09:00:00", "10:00:00")
        together = book(client, "Together", [SANNE, DAAN], "2041-04-02", "10:00:00", "11:00:00")

        found = meetings(client, DAAN, from_day="2041-04-01", to_day="2041-04-30")

        assert [m["meeting_id"] for m in found] == [together]


def test_the_window_bounds_both_ends():
    with TestClient(app) as client:
        book(client, "Before", [SANNE], "2041-05-01", "09:00:00", "10:00:00")
        inside = book(client, "Inside", [SANNE], "2041-05-15", "09:00:00", "10:00:00")
        book(client, "After", [SANNE], "2041-05-31", "09:00:00", "10:00:00")

        found = meetings(client, SANNE, from_day="2041-05-02", to_day="2041-05-30")

        assert [m["meeting_id"] for m in found] == [inside]


def test_by_default_only_what_is_still_to_come():
    with TestClient(app) as client:
        book(client, "Long ago", [DAAN], "2001-01-02", "09:00:00", "10:00:00")

        assert "Long ago" not in [m["title"] for m in meetings(client, DAAN)]


def test_a_cancelled_meeting_leaves_the_list():
    with TestClient(app) as client:
        meeting = book(client, "Cancelled", [SANNE], "2041-06-03", "09:00:00", "10:00:00")
        client.delete(f"/api/meetings/{meeting}")

        assert meetings(client, SANNE, from_day="2041-06-01", to_day="2041-06-30") == []


def test_an_unknown_person_is_404():
    with TestClient(app) as client:
        assert client.get("/api/persons/nobody@rag4p.org/meetings").status_code == 404


def test_the_route_is_in_the_openapi_document():
    with TestClient(app) as client:
        assert "/api/persons/{email}/meetings" in client.get("/openapi.json").json()["paths"]


def test_the_agenda_page_lists_the_upcoming_meetings_and_keeps_the_free_slots():
    with TestClient(app) as client:
        book(client, "Page check", [SANNE, DAAN], "2041-07-04", "10:00:00", "11:00:00")

        page = client.get(f"/persons/{SANNE}/agenda", params={"day": "2041-07-04"}).text

        assert "Upcoming meetings" in page
        assert "Page check" in page
        assert DAAN in page
        assert "09:00-10:00" in page  # the free slot before it, for the agents' view


def test_a_meeting_booked_in_the_ui_is_linked_to_its_agenda_entries():
    with TestClient(app) as client:
        client.post(
            "/meetings/new",
            data={
                "title": "From the form",
                "participant_emails": [SANNE, DAAN],
                "day": "2041-08-07",
                "start": "13:00",
                "end": "14:00",
            },
        )

        found = meetings(client, DAAN, from_day="2041-08-07", to_day="2041-08-07")

        assert found[0]["meeting_id"] is not None
        assert found[0]["participant_emails"] == [SANNE, DAAN]
