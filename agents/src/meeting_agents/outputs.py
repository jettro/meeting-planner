"""What the specialists must return from a model run.

These are the contract between a model and the deterministic parts of the
system. Two rules shape them:

* **A failure must be sayable.** Every result carries `succeeded` and a
  `reason`, so a model that could not book something has a way to report that
  truthfully. Without it the only grammatical answer is an invented id, and an
  invented booking id is worse than an error - it would be stored, and later
  used to cancel something that does not exist.
* **Times are plain `HH:MM` strings.** Structured-output support for exotic
  formats varies by provider, and a time is the one field here we can validate
  ourselves. `parse_clock` is strict on the way back in.
"""

from __future__ import annotations

from datetime import time

from pydantic import BaseModel, Field


class ClockError(ValueError):
    """A model returned something that is not a time of day."""


def parse_clock(value: str) -> time:
    """`HH:MM` (or `HH:MM:SS`) to a `time`, strictly.

    Strict on purpose: a slot that cannot be parsed must stop the plan here,
    where the cause is obvious, rather than travel on as a wrong booking.
    """
    text = value.strip()
    parts = text.split(":")
    if len(parts) not in (2, 3):
        raise ClockError(f"not a time of day: {value!r}")
    try:
        hour, minute = int(parts[0]), int(parts[1])
        second = int(parts[2]) if len(parts) == 3 else 0
        return time(hour=hour, minute=minute, second=second)
    except ValueError as exc:
        raise ClockError(f"not a time of day: {value!r}") from exc


class SlotOut(BaseModel):
    """One window in which everybody is free."""

    start: str = Field(description="Start of the window, as HH:MM in 24-hour time.")
    end: str = Field(description="End of the window, as HH:MM in 24-hour time.")


class FoundSlots(BaseModel):
    """@Scheduler's answer to 'when is everyone free?'."""

    succeeded: bool = Field(description="True if you were able to search. False if a tool failed.")
    slots: list[SlotOut] = Field(
        default_factory=list,
        description=(
            "The common free windows, exactly as the tool reported them. "
            "Empty if there is no time that suits everyone - that is a valid answer."
        ),
    )
    reason: str = Field(default="", description="If succeeded is false, the failure the tool reported.")


class BookedMeeting(BaseModel):
    """@Scheduler's answer to 'book this slot'."""

    succeeded: bool
    meeting_id: int | None = Field(
        default=None,
        description="The exact meeting id the booking tool returned. Never invent one.",
    )
    reason: str = Field(default="", description="If succeeded is false, why not.")


class BookedRoom(BaseModel):
    """@FacilityManager's answer to 'book a room'."""

    succeeded: bool
    room_code: str | None = Field(default=None, description="The code of the room that was booked.")
    booking_id: int | None = Field(
        default=None,
        description="The exact booking id the tool returned. Never invent one.",
    )
    reason: str = Field(default="", description="If succeeded is false, why not.")


class PersonOut(BaseModel):
    name: str = Field(description="The person's name, as list_people gave it.")
    email: str = Field(description="Their email address, exactly as list_people gave it.")


class NameMatchOut(BaseModel):
    asked: str = Field(description="The name you were asked about, unchanged.")
    candidates: list[PersonOut] = Field(
        default_factory=list,
        description="Everyone this name could mean. Empty if nobody matches; several if it is ambiguous.",
    )


class MatchedPeople(BaseModel):
    """@Scheduler's answer to 'who are these people?'."""

    succeeded: bool = Field(description="True if you could search the address book. False if a tool failed.")
    matches: list[NameMatchOut] = Field(
        default_factory=list, description="One entry per name you were asked."
    )
    reason: str = Field(default="", description="If succeeded is false, the failure the tool reported.")


class PlaceOut(BaseModel):
    location_id: str = Field(description="The location id exactly as list_locations gave it.")
    name: str = Field(description="The location's name, as listed.")
    room_code: str = Field(
        default="", description="The room code as list_rooms gave it, only if a room was meant."
    )


class MatchedPlaces(BaseModel):
    """@FacilityManager's answer to 'which place is this?'."""

    succeeded: bool = Field(description="True if you could search the locations. False if a tool failed.")
    candidates: list[PlaceOut] = Field(
        default_factory=list,
        description="Every place the name could mean. Empty if none matches; several if it is ambiguous.",
    )
    reason: str = Field(default="", description="If succeeded is false, the failure the tool reported.")


class ChosenLocation(BaseModel):
    """@FacilityManager's answer to 'which location fits this description?'."""

    succeeded: bool = Field(
        description="True if a location fits reasonably. False if none does, or a tool failed."
    )
    location_id: str | None = Field(
        default=None, description="The location id exactly as list_locations gave it. Never invent one."
    )
    name: str = Field(default="", description="The location's name, as listed.")
    reason: str = Field(
        default="",
        description=(
            "Why this location, in a few words a person can check - or, if succeeded is "
            "false, why nothing fits."
        ),
    )


class OrderedLunch(BaseModel):
    """@Catering's answer to 'order lunch'."""

    succeeded: bool
    order_id: str | None = Field(
        default=None, description="The exact order id the tool returned. Never invent one."
    )
    summary: str = Field(
        default="",
        description=(
            "What you ordered, in one short line a person can read, naming the "
            "items and how many: '2 sandwiches, 1 salad, 2 coffees'. If a "
            "preference could not be met, say so here in a few words."
        ),
    )
    reason: str = Field(default="", description="If succeeded is false, why not.")


class ReleasedBooking(BaseModel):
    """Any specialist's answer to 'cancel this'.

    No id comes back from a cancellation, so this is the one result whose only
    content is whether it worked. `succeeded` is false for a reference the
    service does not recognise, which is a normal thing to meet when undoing a
    plan somebody has already been editing by hand.
    """

    succeeded: bool = Field(description="True only if the tool reported the booking was cancelled.")
    reason: str = Field(default="", description="If succeeded is false, exactly what the tool said.")
