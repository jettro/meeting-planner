"""JSON REST API for the location service."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, select

from location_service.db import get_session
from location_service.models import Location, Room, RoomBooking, check_availability
from location_service.schemas import (
    BookingRead,
    BookRoomRequest,
    BookRoomResponse,
    LocationRead,
    RoomAvailabilityRequest,
    RoomAvailabilityResponse,
    RoomRead,
)

router = APIRouter(prefix="/api", tags=["location"])


def _get_location_or_404(session: Session, location_id: str) -> Location:
    location = session.exec(select(Location).where(Location.location_id == location_id)).first()
    if location is None:
        raise HTTPException(status_code=404, detail=f"Unknown location: {location_id}")
    return location


@router.get("/locations", response_model=list[LocationRead])
def list_locations(session: Session = Depends(get_session)) -> list[LocationRead]:
    locations = session.exec(select(Location)).all()
    return [
        LocationRead(location_id=loc.location_id, name=loc.name, description=loc.description)
        for loc in locations
    ]


@router.get("/locations/{location_id}/rooms", response_model=list[RoomRead])
def list_rooms(location_id: str, session: Session = Depends(get_session)) -> list[RoomRead]:
    _get_location_or_404(session, location_id)
    rooms = session.exec(select(Room).where(Room.location_id == location_id)).all()
    return [RoomRead(location_id=r.location_id, room_code=r.room_code, capacity=r.capacity) for r in rooms]


@router.post("/rooms/check-availability", response_model=RoomAvailabilityResponse)
def check_room_availability(
    request: RoomAvailabilityRequest, session: Session = Depends(get_session)
) -> RoomAvailabilityResponse:
    _get_location_or_404(session, request.location_id)
    rooms = session.exec(
        select(Room)
        .where(Room.location_id == request.location_id)
        .where(Room.capacity >= request.number_of_people)
        .order_by(col(Room.capacity))
    ).all()

    end_time = (
        datetime.combine(request.day, request.start) + timedelta(minutes=request.duration_minutes)
    ).time()

    for room in rooms:
        bookings = session.exec(select(RoomBooking).where(RoomBooking.room_id == room.id)).all()
        if check_availability(bookings, request.day, request.start, end_time):
            return RoomAvailabilityResponse(
                location_id=request.location_id,
                available=True,
                room_code=room.room_code,
                day=request.day,
                start=request.start,
                duration_minutes=request.duration_minutes,
            )

    return RoomAvailabilityResponse(
        location_id=request.location_id,
        available=False,
        room_code=None,
        day=None,
        start=None,
        duration_minutes=0,
    )


@router.post("/rooms/book", response_model=BookRoomResponse)
def book_room(request: BookRoomRequest, session: Session = Depends(get_session)) -> BookRoomResponse:
    _get_location_or_404(session, request.location_id)
    room = session.exec(
        select(Room).where(Room.location_id == request.location_id).where(Room.room_code == request.room_code)
    ).first()
    if room is None:
        return BookRoomResponse(
            location_id=request.location_id,
            room_code=request.room_code,
            success=False,
            message="You requested an unknown room",
        )

    start_dt = datetime.combine(request.day, request.start)
    end_time = (start_dt + timedelta(minutes=request.duration_minutes)).time()

    bookings = session.exec(select(RoomBooking).where(RoomBooking.room_id == room.id)).all()
    if not check_availability(bookings, request.day, request.start, end_time):
        return BookRoomResponse(
            location_id=request.location_id,
            room_code=request.room_code,
            success=False,
            message="No capacity at the requested time",
        )

    session.add(
        RoomBooking(
            room_id=room.id,  # type: ignore[arg-type]
            day=request.day,
            start=request.start,
            end=end_time,
            reference=request.reference,
            description=request.description,
        )
    )
    session.commit()

    return BookRoomResponse(
        location_id=request.location_id,
        room_code=request.room_code,
        success=True,
        message=f"Booking confirmed for {request.reference}",
    )


@router.get("/bookings", response_model=list[BookingRead])
def list_bookings(
    location_id: str | None = None, session: Session = Depends(get_session)
) -> list[BookingRead]:
    locations = {loc.location_id: loc for loc in session.exec(select(Location)).all()}
    query = select(Room)
    if location_id:
        query = query.where(Room.location_id == location_id)
    rooms = session.exec(query).all()

    results: list[BookingRead] = []
    for room in rooms:
        bookings = session.exec(select(RoomBooking).where(RoomBooking.room_id == room.id)).all()
        location = locations.get(room.location_id)
        for booking in bookings:
            results.append(
                BookingRead(
                    location_id=room.location_id,
                    location_name=location.name if location else room.location_id,
                    room_code=room.room_code,
                    day=booking.day,
                    start=booking.start,
                    end=booking.end,
                    reference=booking.reference,
                    description=booking.description,
                )
            )
    results.sort(key=lambda b: (b.day, b.start))
    return results
