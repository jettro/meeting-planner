"""Server-rendered UI (Jinja2 + HTMX) for the meeting service."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from meeting_service.db import get_session
from meeting_service.models import (
    AgendaItem,
    Meeting,
    Person,
    availability_for_day,
    check_availability,
)

router = APIRouter(tags=["ui"])
templates = Jinja2Templates(directory="src/meeting_service/templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")


@router.get("/persons", response_class=HTMLResponse)
def persons_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    persons = session.exec(select(Person)).all()
    return templates.TemplateResponse(request, "persons.html", {"persons": persons})


@router.get("/persons/{email}/agenda", response_class=HTMLResponse)
def person_agenda_page(
    request: Request,
    email: str,
    day: str | None = None,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    person = session.exec(select(Person).where(Person.email == email)).first()
    selected_day = date.fromisoformat(day) if day else date.today()
    free_slots: list[str] = []
    if person is not None:
        items = session.exec(select(AgendaItem).where(AgendaItem.person_id == person.id)).all()
        free_slots = availability_for_day(items, selected_day)
    return templates.TemplateResponse(
        request,
        "person_agenda.html",
        {"person": person, "day": selected_day.isoformat(), "free_slots": free_slots},
    )


@router.get("/meetings", response_class=HTMLResponse)
def meetings_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    meetings = session.exec(select(Meeting)).all()
    return templates.TemplateResponse(request, "meetings.html", {"meetings": meetings})


@router.get("/meetings/new", response_class=HTMLResponse)
def new_meeting_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    persons = session.exec(select(Person)).all()
    return templates.TemplateResponse(request, "meeting_form.html", {"persons": persons, "result": None})


@router.post("/meetings/new", response_class=HTMLResponse)
def create_meeting(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    participant_emails: list[str] = Form(...),
    day: str = Form(...),
    start: str = Form(...),
    end: str = Form(...),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    meeting_day = date.fromisoformat(day)
    start_t = datetime.strptime(start, "%H:%M").time()
    end_t = datetime.strptime(end, "%H:%M").time()

    maybe_persons = [
        session.exec(select(Person).where(Person.email == email)).first() for email in participant_emails
    ]
    persons: list[Person] = [p for p in maybe_persons if p is not None]

    unavailable = []
    for person in persons:
        items = session.exec(select(AgendaItem).where(AgendaItem.person_id == person.id)).all()
        if not check_availability(items, meeting_day, start_t, end_t):
            unavailable.append(person.name)

    result: dict[str, object]
    if unavailable:
        result = {
            "booked": False,
            "message": f"Not available: {', '.join(unavailable)}",
        }
    else:
        for person in persons:
            session.add(
                AgendaItem(
                    person_id=person.id,  # type: ignore[arg-type]
                    day=meeting_day,
                    start=start_t,
                    end=end_t,
                    title=title,
                )
            )
        meeting = Meeting(
            title=title,
            description=description,
            day=meeting_day,
            start=start_t,
            end=end_t,
            participant_emails_csv=",".join(participant_emails),
        )
        session.add(meeting)
        session.commit()
        result = {"booked": True, "message": f"Meeting '{title}' booked successfully."}

    all_persons = session.exec(select(Person)).all()
    return templates.TemplateResponse(
        request, "meeting_form.html", {"persons": all_persons, "result": result}
    )
