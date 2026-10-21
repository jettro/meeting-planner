"""Domain and persistence models for the meeting service.

Everything is built on Pydantic / SQLModel. The availability algorithm is a direct
port of the old Java `Agenda` class: a day runs from 09:00 to 17:00, and a slot is
available when it does not overlap an existing booking.
"""

from collections.abc import Sequence
from datetime import date, time

from sqlmodel import Field, SQLModel

DAY_START = time(9, 0)
DAY_END = time(17, 0)


class Person(SQLModel, table=True):
    """A meeting participant."""

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: str


class AgendaItem(SQLModel, table=True):
    """A single booked slot in a person's agenda.

    Looked up by `person_id` (no ORM relationship is declared on purpose -
    callers query agenda items explicitly, keeping the model simple).
    """

    id: int | None = Field(default=None, primary_key=True)
    person_id: int = Field(foreign_key="person.id")
    day: date
    start: time
    end: time
    title: str

    def model_post_init(self, __context: object) -> None:
        if self.end <= self.start:
            raise ValueError("End time must be after start time")


class Meeting(SQLModel, table=True):
    """A booked meeting, independent of the participants' individual agendas."""

    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str = ""
    day: date
    start: time
    end: time
    participant_emails_csv: str = ""

    @property
    def participant_emails(self) -> list[str]:
        return [e for e in self.participant_emails_csv.split(",") if e]


def check_availability(items: Sequence[AgendaItem], day: date, start: time, end: time) -> bool:
    """True if no existing item on `day` overlaps [start, end)."""
    for item in items:
        if item.day == day and start < item.end and end > item.start:
            return False
    return True


def availability_for_day(items: Sequence[AgendaItem], day: date) -> list[str]:
    """Return free slots ("HH:MM-HH:MM") within the 09:00-17:00 working day."""
    day_items = sorted(
        (i for i in items if i.day == day),
        key=lambda i: i.start,
    )

    slots: list[str] = []
    current_start = DAY_START

    for item in day_items:
        item_start = max(item.start, DAY_START)
        item_end = min(item.end, DAY_END)

        if item_end < DAY_START or item_start > DAY_END:
            continue

        if current_start < item_start:
            slots.append(f"{current_start.strftime('%H:%M')}-{item_start.strftime('%H:%M')}")
        if item_end > current_start:
            current_start = item_end

    if current_start < DAY_END:
        slots.append(f"{current_start.strftime('%H:%M')}-{DAY_END.strftime('%H:%M')}")

    return slots
