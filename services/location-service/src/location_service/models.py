"""Domain and persistence models for the location service.

Mirrors the old Java `mcp-location` module: locations contain rooms, rooms carry
their own availability (same overlap algorithm as the meeting service's agenda).
"""

from collections.abc import Sequence
from datetime import date, time

from sqlmodel import Field, SQLModel

DAY_START = time(9, 0)
DAY_END = time(17, 0)


class Location(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    location_id: str = Field(index=True, unique=True)
    name: str
    description: str = ""


class Room(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    location_id: str = Field(index=True, foreign_key="location.location_id")
    room_code: str
    capacity: int


class RoomBooking(SQLModel, table=True):
    """A single booked slot for a room (the room's "agenda")."""

    id: int | None = Field(default=None, primary_key=True)
    room_id: int = Field(foreign_key="room.id")
    day: date
    start: time
    end: time
    reference: str = ""
    description: str = ""

    def model_post_init(self, __context: object) -> None:
        if self.end <= self.start:
            raise ValueError("End time must be after start time")


def check_availability(bookings: Sequence[RoomBooking], day: date, start: time, end: time) -> bool:
    """True if no existing booking on `day` overlaps [start, end)."""
    for booking in bookings:
        if booking.day == day and start < booking.end and end > booking.start:
            return False
    return True
