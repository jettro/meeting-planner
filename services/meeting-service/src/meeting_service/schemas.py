"""Pure Pydantic request/response schemas for the meeting service API."""

from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel, EmailStr, Field

from meeting_service.clock import WallClock


class PersonRead(BaseModel):
    email: str
    name: str


class AvailabilityCheckRequest(BaseModel):
    participant_emails: list[EmailStr]
    day: date
    start: WallClock
    end: WallClock


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


class CommonSlotsRequest(BaseModel):
    participant_emails: list[EmailStr]
    day: date
    duration_minutes: int = Field(default=60, gt=0, le=480)


class CommonSlot(BaseModel):
    start: time
    end: time
    latest_start: time


class CommonSlotsResponse(BaseModel):
    day: date
    duration_minutes: int
    participant_emails: list[str]
    slots: list[CommonSlot]


class MeetingRequest(BaseModel):
    title: str
    description: str = ""
    participant_emails: list[EmailStr]
    day: date
    start: WallClock
    end: WallClock


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


class MeetingCancelResponse(BaseModel):
    success: bool
    message: str
