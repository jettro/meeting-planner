"""Pure Pydantic request/response schemas for the location service API."""

from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel


class LocationRead(BaseModel):
    location_id: str
    name: str
    description: str


class RoomRead(BaseModel):
    location_id: str
    room_code: str
    capacity: int


class RoomAvailabilityRequest(BaseModel):
    location_id: str
    day: date
    start: time
    duration_minutes: int
    number_of_people: int


class RoomAvailabilityResponse(BaseModel):
    location_id: str
    available: bool
    room_code: str | None
    day: date | None
    start: time | None
    duration_minutes: int


class BookRoomRequest(BaseModel):
    location_id: str
    room_code: str
    day: date
    start: time
    duration_minutes: int
    reference: str = ""
    description: str = ""


class BookRoomResponse(BaseModel):
    location_id: str
    room_code: str
    success: bool
    message: str


class BookingRead(BaseModel):
    location_id: str
    location_name: str
    room_code: str
    day: date
    start: time
    end: time
    reference: str
    description: str
