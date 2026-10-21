"""JSON REST API for the meeting service."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from meeting_service.db import get_session
from meeting_service.models import (
    AgendaItem,
    Meeting,
    Person,
    availability_for_day,
    check_availability,
)
from meeting_service.schemas import (
    AvailabilityCheckRequest,
    AvailabilityCheckResponse,
    DayAvailability,
    MeetingCancelResponse,
    MeetingRead,
    MeetingRequest,
    MeetingResponse,
    PersonAvailability,
    PersonRead,
)

router = APIRouter(prefix="/api", tags=["meeting"])


def _get_person_or_404(session: Session, email: str) -> Person:
    person = session.exec(select(Person).where(Person.email == email)).first()
    if person is None:
        raise HTTPException(status_code=404, detail=f"Unknown person: {email}")
    return person


def _to_meeting_read(meeting: Meeting) -> MeetingRead:
    return MeetingRead(
        id=meeting.id,  # type: ignore[arg-type]
        title=meeting.title,
        description=meeting.description,
        day=meeting.day,
        start=meeting.start,
        end=meeting.end,
        participant_emails=meeting.participant_emails,
    )


@router.get("/persons", response_model=list[PersonRead])
def list_persons(session: Session = Depends(get_session)) -> list[PersonRead]:
    persons = session.exec(select(Person)).all()
    return [PersonRead(email=p.email, name=p.name) for p in persons]


@router.get("/persons/{email}", response_model=PersonRead)
def get_person(email: str, session: Session = Depends(get_session)) -> PersonRead:
    person = _get_person_or_404(session, email)
    return PersonRead(email=person.email, name=person.name)


@router.get("/persons/{email}/agenda", response_model=DayAvailability)
def get_person_agenda(email: str, day: date, session: Session = Depends(get_session)) -> DayAvailability:
    person = _get_person_or_404(session, email)
    items = session.exec(select(AgendaItem).where(AgendaItem.person_id == person.id)).all()
    return DayAvailability(
        email=person.email,
        name=person.name,
        free_slots=availability_for_day(items, day),
    )


@router.post("/meetings/check-availability", response_model=AvailabilityCheckResponse)
def check_meeting_availability(
    request: AvailabilityCheckRequest, session: Session = Depends(get_session)
) -> AvailabilityCheckResponse:
    results: list[PersonAvailability] = []
    for email in request.participant_emails:
        person = _get_person_or_404(session, email)
        items = session.exec(select(AgendaItem).where(AgendaItem.person_id == person.id)).all()
        available = check_availability(items, request.day, request.start, request.end)
        results.append(PersonAvailability(email=person.email, name=person.name, available=available))

    return AvailabilityCheckResponse(
        day=request.day,
        start=request.start,
        end=request.end,
        results=results,
        all_available=all(r.available for r in results),
    )


@router.post("/meetings/book", response_model=MeetingResponse)
def book_meeting(request: MeetingRequest, session: Session = Depends(get_session)) -> MeetingResponse:
    persons = [_get_person_or_404(session, email) for email in request.participant_emails]

    for person in persons:
        items = session.exec(select(AgendaItem).where(AgendaItem.person_id == person.id)).all()
        if not check_availability(items, request.day, request.start, request.end):
            return MeetingResponse(
                booked=False,
                message=f"No common availability found: {person.name} is not available.",
                meeting=None,
            )

    meeting = Meeting(
        title=request.title,
        description=request.description,
        day=request.day,
        start=request.start,
        end=request.end,
        participant_emails_csv=",".join(request.participant_emails),
    )
    session.add(meeting)
    session.commit()
    session.refresh(meeting)

    for person in persons:
        session.add(
            AgendaItem(
                person_id=person.id,  # type: ignore[arg-type]
                meeting_id=meeting.id,
                day=request.day,
                start=request.start,
                end=request.end,
                title=request.title,
            )
        )
    session.commit()

    return MeetingResponse(
        booked=True,
        message=f"Meeting '{meeting.title}' booked for {len(persons)} participant(s).",
        meeting=_to_meeting_read(meeting),
    )


@router.get("/meetings", response_model=list[MeetingRead])
def list_meetings(session: Session = Depends(get_session)) -> list[MeetingRead]:
    meetings = session.exec(select(Meeting)).all()
    return [_to_meeting_read(m) for m in meetings]


@router.delete("/meetings/{meeting_id}", response_model=MeetingCancelResponse)
def cancel_meeting(meeting_id: int, session: Session = Depends(get_session)) -> MeetingCancelResponse:
    meeting = session.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail=f"Unknown meeting id: {meeting_id}")

    items = session.exec(select(AgendaItem).where(AgendaItem.meeting_id == meeting_id)).all()
    for item in items:
        session.delete(item)
    session.delete(meeting)
    session.commit()

    return MeetingCancelResponse(success=True, message=f"Meeting '{meeting.title}' cancelled.")
