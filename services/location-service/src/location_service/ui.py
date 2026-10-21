"""Server-rendered UI (Jinja2 + HTMX) for the location service."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, col, select

from location_service.db import get_session
from location_service.models import Location, Room, RoomBooking, check_availability

router = APIRouter(tags=["ui"])
templates = Jinja2Templates(directory="src/location_service/templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")


@router.get("/locations", response_class=HTMLResponse)
def locations_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    locations = session.exec(select(Location)).all()
    return templates.TemplateResponse(request, "locations.html", {"locations": locations})


@router.get("/locations/{location_id}", response_class=HTMLResponse)
def location_detail_page(
    request: Request, location_id: str, session: Session = Depends(get_session)
) -> HTMLResponse:
    location = session.exec(select(Location).where(Location.location_id == location_id)).first()
    rooms = session.exec(select(Room).where(Room.location_id == location_id)).all()

    bookings_by_room: dict[str, Sequence[RoomBooking]] = {}
    for room in rooms:
        bookings_by_room[room.room_code] = session.exec(
            select(RoomBooking).where(RoomBooking.room_id == room.id)
        ).all()

    return templates.TemplateResponse(
        request,
        "location_detail.html",
        {"location": location, "rooms": rooms, "bookings_by_room": bookings_by_room},
    )


@router.get("/rooms/book", response_class=HTMLResponse)
def book_room_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    locations = session.exec(select(Location)).all()
    return templates.TemplateResponse(request, "book_room.html", {"locations": locations, "result": None})


@router.post("/rooms/book", response_class=HTMLResponse)
def book_room_submit(
    request: Request,
    location_id: str = Form(...),
    day: str = Form(...),
    start: str = Form(...),
    duration_minutes: int = Form(...),
    number_of_people: int = Form(...),
    reference: str = Form(""),
    description: str = Form(""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    booking_day = date.fromisoformat(day)
    start_t = datetime.strptime(start, "%H:%M").time()
    end_t = (datetime.combine(booking_day, start_t) + timedelta(minutes=duration_minutes)).time()

    rooms = session.exec(
        select(Room)
        .where(Room.location_id == location_id)
        .where(Room.capacity >= number_of_people)
        .order_by(col(Room.capacity))
    ).all()

    booked_room: Room | None = None
    for room in rooms:
        bookings = session.exec(select(RoomBooking).where(RoomBooking.room_id == room.id)).all()
        if check_availability(bookings, booking_day, start_t, end_t):
            booked_room = room
            break

    if booked_room is None:
        result = {"success": False, "message": "No room available for that request."}
    else:
        session.add(
            RoomBooking(
                room_id=booked_room.id,  # type: ignore[arg-type]
                day=booking_day,
                start=start_t,
                end=end_t,
                reference=reference,
                description=description,
            )
        )
        session.commit()
        result = {
            "success": True,
            "message": f"Booked room '{booked_room.room_code}' (capacity {booked_room.capacity}).",
        }

    locations = session.exec(select(Location)).all()
    return templates.TemplateResponse(request, "book_room.html", {"locations": locations, "result": result})
