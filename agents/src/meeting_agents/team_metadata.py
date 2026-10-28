"""What a team run is *about*, for anything that lists runs.

A team run is one meeting. Without this, every row in a list of runs says
`meeting-planner` and nothing else, and the only way to tell two runs apart is
by the minute they started.

This is deliberately the **request**, not the outcome. Every field is known at
the moment the team is created and never changes, which is what lets it be set
once, in the same call that creates the team, with nothing to keep in sync
afterwards. The outcome - which room, which slot, whether lunch was ordered -
lives in `MeetingPlan`, is rewritten repeatedly as the saga proceeds, and is
reached from a plan rather than from a run (`MeetingPlan.team_ids`).

Three fields are indexed, which is what makes them filterable. The framework
flattens them into `"key|value"` entries matched by anchored prefix, so a
filter on `title` is a "starts with" search and a filter on `day` can be a
whole date or just its year. `participants` is left out: an anchored prefix on
a number matches by digit, so filtering `1` would return 1, 10 and 12.

`with_lunch` is not here either, for a duller reason - every request the
browser sends leaves it at its default, so the field would be true on every row
and distinguish nothing. It belongs here the day something can ask for a
meeting without lunch.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from akgentic.team.metadata import TeamMetadata
from pydantic import Field

#: The mark that makes a field filterable. Annotated, because pydantic takes
#: `json_schema_extra` as a mapping of arbitrary JSON and an inferred
#: `dict[str, bool]` is not that - dicts are invariant in their value type.
INDEXED: dict[str, Any] = {"indexed": True}


class MeetingTeamMetadata(TeamMetadata):
    """The meeting a team run was asked to arrange.

    Every field is mandatory and non-nullable on purpose: all of it comes from
    `PlanMeetingRequest`, so there is no state in which a run exists and this is
    unknown. The framework's rule about nullable fields needing `= None` does
    not apply, because none of them are nullable.
    """

    title: str = Field(description="What the meeting is called", json_schema_extra=INDEXED)
    day: date = Field(description="The day it should happen", json_schema_extra=INDEXED)
    location_id: str = Field(description="Where it should happen", json_schema_extra=INDEXED)
    participants: int = Field(description="How many people were invited", ge=1)
