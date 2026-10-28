"""The event store must be able to write a slot, or the browser never sees one.

This is a regression test for a failure that was invisible from inside the
team: the actors ran the whole saga correctly while the persistence subscriber
dropped every message carrying a `time`, so the trace the browser reads simply
had no approval question in it.
"""

from __future__ import annotations

import datetime
from enum import Enum

import pytest
import yaml
from meeting_agents.messages import ProposedSlot, SlotApprovalRequest
from meeting_agents.plan import CompensationStep, MeetingPlan, PlanStatus
from meeting_server.yaml_types import install_yaml_representers

SLOT = ProposedSlot(start=datetime.time(10, 0), end=datetime.time(11, 0))


def test_pyyaml_does_not_know_times_by_itself():
    """The fact the module exists for: `date` and `datetime` have representers
    in pyyaml's own table, `time` does not. Asserted against that table rather
    than by dumping, because the representer this package installs is global
    once anything has imported it."""
    representers = yaml.representer.SafeRepresenter.yaml_representers

    assert datetime.date in representers
    assert datetime.datetime in representers
    assert datetime.time not in representers


def test_a_time_is_written_as_iso_8601():
    install_yaml_representers()

    assert yaml.safe_dump({"start": datetime.time(10, 0)}).strip() == "start: '10:00:00'"


def test_a_whole_approval_question_survives_the_round_trip():
    """The message that was being lost, dumped and read back as the store does."""
    install_yaml_representers()
    question = SlotApprovalRequest(
        plan_id="p1", title="Design review", day=datetime.date(2035, 3, 12), candidates=[SLOT]
    )

    restored = SlotApprovalRequest.model_validate(yaml.safe_load(yaml.safe_dump(question.model_dump())))

    assert restored.candidates[0].start == datetime.time(10, 0)
    assert restored.candidates[0].end == datetime.time(11, 0)
    assert restored.day == datetime.date(2035, 3, 12)


def test_installing_twice_is_harmless():
    install_yaml_representers()
    install_yaml_representers()

    assert yaml.safe_dump({"t": datetime.time(9, 30)}).strip() == "t: '09:30:00'"


def test_a_time_is_quoted_so_yaml_cannot_read_it_as_a_number():
    """Without the quotes `10:00:00` is a YAML 1.1 sexagesimal integer - 36000
    - and the slot comes back as a number. The damage is subtle because
    pydantic reads 36000 as seconds since midnight and lands on the right
    time, so the bug would only ever show up somewhere else."""
    install_yaml_representers()

    restored = yaml.safe_load(yaml.safe_dump({"t": datetime.time(10, 0)}))

    assert restored["t"] == "10:00:00"


def test_pyyaml_does_not_know_a_str_enum_by_itself():
    """A `str` subclass is not a `str` to the dumper - it dispatches on exact type."""
    yaml.SafeDumper.yaml_representers.pop(PlanStatus, None)
    yaml.SafeDumper.yaml_multi_representers.pop(Enum, None)
    with pytest.raises(yaml.representer.RepresenterError):
        yaml.safe_dump({"status": PlanStatus.CONFIRMED})


def test_a_plan_with_a_status_can_be_written_after_installing():
    """The second time this bit: `status` became a computed field and vanished."""
    install_yaml_representers()
    plan = MeetingPlan(
        title="Design review",
        participant_emails=["sanne@rag4p.org"],
        day=datetime.date(2035, 3, 12),
        location_id="yuma",
        meeting_id=12,
        booking_id=8,
        order_id="abc-123",
    )
    written = yaml.safe_dump(plan.model_dump())
    assert yaml.safe_load(written)["status"] == "CONFIRMED"


def test_an_enum_round_trips_as_its_value():
    install_yaml_representers()
    assert yaml.safe_load(yaml.safe_dump({"step": CompensationStep.CANCEL_ORDER})) == {"step": "cancel_order"}
