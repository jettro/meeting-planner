"""Tests for the MeetingPlan aggregate: derived status and compensation steps."""

from datetime import date, time

import pytest
from meeting_agents.plan import CompensationStep, MeetingPlan, PlanStatus


def make_plan(**overrides) -> MeetingPlan:
    base = {
        "title": "Jettro & Daniel",
        "participant_emails": ["jettro@rag4j.org", "daniel@rag4j.org"],
        "day": date(2030, 6, 4),
        "duration_minutes": 60,
        "location_id": "luminis",
    }
    return MeetingPlan(**{**base, **overrides})


def test_status_progresses_through_the_saga():
    plan = make_plan()
    assert plan.status is PlanStatus.DRAFT

    plan = plan.model_copy(update={"proposed_start": time(11, 0), "proposed_end": time(12, 0)})
    assert plan.status is PlanStatus.AWAITING_APPROVAL

    plan = plan.model_copy(update={"approved": True})
    assert plan.status is PlanStatus.APPROVED

    plan = plan.model_copy(update={"meeting_id": 12})
    assert plan.status is PlanStatus.SCHEDULED

    plan = plan.model_copy(update={"booking_id": 8, "room_code": "room-a"})
    assert plan.status is PlanStatus.ROOM_BOOKED
    assert plan.is_complete is False

    plan = plan.model_copy(update={"order_id": "abc-123"})
    assert plan.status is PlanStatus.CONFIRMED
    assert plan.is_complete is True


def test_a_room_booking_completes_a_plan_without_lunch():
    plan = make_plan(with_lunch=False, approved=True, meeting_id=12, booking_id=8)
    assert plan.status is PlanStatus.CONFIRMED


def test_cancelled_overrides_every_other_status():
    plan = make_plan(meeting_id=12, booking_id=8, order_id="abc-123", cancelled=True)
    assert plan.status is PlanStatus.CANCELLED


def test_compensations_are_in_reverse_booking_order():
    plan = make_plan(meeting_id=12, booking_id=8, order_id="abc-123")
    assert [(c.step, c.reference) for c in plan.compensations()] == [
        (CompensationStep.CANCEL_ORDER, "abc-123"),
        (CompensationStep.CANCEL_ROOM_BOOKING, "8"),
        (CompensationStep.CANCEL_MEETING, "12"),
    ]


def test_compensations_skip_bookings_that_never_happened():
    """The half-finished case: a room was booked but lunch failed."""
    plan = make_plan(meeting_id=12, booking_id=8)
    assert [c.step for c in plan.compensations()] == [
        CompensationStep.CANCEL_ROOM_BOOKING,
        CompensationStep.CANCEL_MEETING,
    ]


def test_a_draft_plan_has_nothing_to_compensate():
    assert make_plan().compensations() == []


def test_moving_rooms_within_a_location_keeps_the_lunch_order():
    plan = make_plan(meeting_id=12, booking_id=8, room_code="room-a", order_id="abc-123")
    steps = plan.relocation_compensations("luminis")
    assert [c.step for c in steps] == [CompensationStep.CANCEL_ROOM_BOOKING]


def test_moving_to_another_location_rebooks_the_lunch():
    plan = make_plan(meeting_id=12, booking_id=8, room_code="room-a", order_id="abc-123")
    steps = plan.relocation_compensations("amsterdam")
    assert [c.step for c in steps] == [
        CompensationStep.CANCEL_ORDER,
        CompensationStep.CANCEL_ROOM_BOOKING,
    ]


def test_plan_ids_are_unique():
    assert make_plan().plan_id != make_plan().plan_id


def test_duration_must_be_positive():
    with pytest.raises(ValueError):
        make_plan(duration_minutes=0)
