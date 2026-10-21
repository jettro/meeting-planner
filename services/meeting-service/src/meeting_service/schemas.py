"""Pure Pydantic request/response schemas for the meeting service API."""

from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel, EmailStr


class PersonRead(BaseModel):
    email: str
    name: str


class AvailabilityCheckRequest(BaseModel):
    participant_emails: list[EmailStr]
    day: date
    start: time
    end: time


class PersonAvailability(BaseModel):
    email: str
    name: str
    available: bool


class AvailabilityCheckResponse(BaseModel):
    day: date
    start: time
    end: time
    results: list[PersonAvailability]
    all_available: bool


class DayAvailability(BaseModel):
    email: str
    name: str
    free_slots: list[str]


class MeetingRequest(BaseModel):
    title: str
    description: str = ""
    participant_emails: list[EmailStr]
    day: date
    start: time
    end: time


class MeetingRead(BaseModel):
    id: int
    title: str
    description: str
    day: date
    start: time
    end: time
    participant_emails: list[str]


class MeetingResponse(BaseModel):
    booked: bool
    message: str
    meeting: MeetingRead | None = None
