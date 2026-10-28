"""Tests for what a team run says about itself.

The point of these is that nothing else fails when this goes wrong. A missing
or mis-marked field does not break a run, a plan, or the trace - it only makes
a list of runs less useful, which no test notices and no exception reports.
"""

from __future__ import annotations

from datetime import date

import pytest
from meeting_agents.team_metadata import MeetingTeamMetadata
from pydantic import ValidationError


def make(**overrides) -> MeetingTeamMetadata:
    return MeetingTeamMetadata(
        **{
            "title": "Design review",
            "day": date(2026, 10, 28),
            "location_id": "yuma",
            "participants": 3,
            **overrides,
        }
    )


def test_every_field_is_required():
    """All of it comes from the request, so there is no partial state to allow."""
    with pytest.raises(ValidationError):
        MeetingTeamMetadata(title="Design review")  # type: ignore[call-arg]


def test_a_run_without_people_is_rejected():
    with pytest.raises(ValidationError):
        make(participants=0)


def test_the_indexed_fields_become_filter_entries():
    """`key|value`, with the value half casefolded - that fold is what makes a
    filter case-insensitive without a case-insensitive query."""
    assert make().index_entries() == [
        "title|design review",
        "day|2026-10-28",
        "location_id|yuma",
    ]


def test_participants_is_not_filterable():
    """Filtering is an anchored prefix match, so a count would match by digit:
    a filter of `1` would return 1, 10 and 12 alike."""
    assert "participants" not in MeetingTeamMetadata.indexed_fields()
    assert not any(entry.startswith("participants") for entry in make().index_entries())


def test_a_pipe_in_a_title_cannot_forge_a_second_entry():
    """The separator is escaped on the way in, so a title is a title."""
    entries = make(title="Design | yuma").index_entries()
    assert entries[0] == "title|design \\| yuma"
    assert len(entries) == 3
