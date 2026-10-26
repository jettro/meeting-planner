"""The one time type this service accepts from the outside.

Rooms, agendas and lunches are all local wall-clock affairs: a meeting at 09:00
is at 09:00 in the building. Nothing here stores a timezone, and nothing should
be asked to guess one.

A live agent found the gap by sending `09:00:00+00:00`. Pydantic parsed it into
an offset-aware `time`, which then met a naive one in a comparison and raised
`TypeError: can't compare offset-naive and offset-aware times` - a 500 whose
message said nothing useful to the caller. Converting instead of refusing would
be worse: an offset we did not ask for cannot be shifted into local time
without knowing the building's zone, so a wrong hour would get booked silently.
"""

from __future__ import annotations

from datetime import time
from typing import Annotated

from pydantic import AfterValidator


def reject_timezone(value: time) -> time:
    if value.tzinfo is not None:
        raise ValueError(
            "times are local to the venue and must be sent without a timezone "
            f"offset - use HH:MM, not {value.isoformat()}"
        )
    return value


WallClock = Annotated[time, AfterValidator(reject_timezone)]
