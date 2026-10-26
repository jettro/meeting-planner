"""Tests for the message vocabulary.

Assignments are what let the coordinator stay deterministic: it fills in a
message rather than phrasing a request. These tests pin down the two things
that depend on: a request becomes a plan unchanged, and an assignment renders
into a prompt that actually carries its facts.
"""

from datetime import date, time

import pytest
from meeting_agents.messages import (
    MESSAGE_TYPES,
    BookFacilitiesAssignment,
    BookMeetingAssignment,
    FindSlotsAssignment,
    LunchApprovalDecision,
    LunchApprovalRequest,
    OrderLunchAssignment,
    PlanMeetingRequest,
    ProposedSlot,
    SlotApprovalDecision,
    SlotApprovalRequest,
)
from meeting_agents.plan import PlanStatus
from pydantic import ValidationError

DAY = date(2031, 9, 15)
SLOT = ProposedSlot(start=time(10, 0), end=time(11, 0))


def request() -> PlanMeetingRequest:
    return PlanMeetingRequest(
        title="Jettro and Daniel",
        participant_emails=["jettro@example.com", "daniel@example.com"],
        day=DAY,
        duration_minutes=45,
        location_id="AMS",
    )


def test_a_request_becomes_a_draft_plan():
    plan = request().to_plan()
    assert plan.status is PlanStatus.DRAFT
    assert plan.title == "Jettro and Daniel"
    assert plan.duration_minutes == 45
    assert plan.plan_id


def test_each_request_starts_its_own_plan():
    assert request().to_plan().plan_id != request().to_plan().plan_id


def test_a_request_must_have_a_workable_duration():
    with pytest.raises(ValueError):
        PlanMeetingRequest(
            title="x", participant_emails=["a@b.c"], day=DAY, duration_minutes=0, location_id="AMS"
        )


def test_slot_label_is_human_readable():
    assert SLOT.label() == "10:00-11:00"


def test_find_slots_assignment_carries_everyone():
    rendered = FindSlotsAssignment(
        plan_id="p1",
        participant_emails=["jettro@example.com", "daniel@example.com"],
        day=DAY,
        duration_minutes=45,
    ).rendering()
    assert "jettro@example.com" in rendered
    assert "daniel@example.com" in rendered
    assert "45-minute" in rendered
    assert "2031-09-15" in rendered


def test_book_meeting_assignment_names_the_approved_slot():
    rendered = BookMeetingAssignment(
        plan_id="p1",
        title="Jettro and Daniel",
        participant_emails=["jettro@example.com"],
        day=DAY,
        slot=SLOT,
    ).rendering()
    assert "10:00" in rendered and "11:00" in rendered
    assert "Jettro and Daniel" in rendered


def test_facilities_assignment_never_mentions_lunch():
    """D2: where lunch comes from is the facility manager's business.

    The coordinator asks for a room; @Catering is reached by @FacilityManager,
    so the word must not appear in what the coordinator sends.
    """
    rendered = BookFacilitiesAssignment(
        plan_id="p1",
        title="Design review",
        location_id="AMS",
        day=DAY,
        slot=SLOT,
        headcount=2,
        with_lunch=True,
    ).rendering()
    assert "lunch" not in rendered.lower()
    assert "AMS" in rendered
    assert "2 people" in rendered


def test_facilities_assignment_carries_the_title():
    """A room booked as "Meeting" tells the people reading the room calendar
    nothing. The title is the coordinator's to pass on; a live run booked a
    generic reference because this field did not exist."""
    rendered = BookFacilitiesAssignment(
        plan_id="p1",
        title="Design review",
        location_id="AMS",
        day=DAY,
        slot=SLOT,
        headcount=2,
        with_lunch=False,
    ).rendering()
    assert "Design review" in rendered


def test_lunch_assignment_carries_location_and_headcount():
    rendered = OrderLunchAssignment(
        plan_id="p1", location_id="AMS", day=DAY, headcount=4
    ).rendering()
    assert "4 people" in rendered
    assert "AMS" in rendered


def test_approval_question_lists_every_candidate():
    question = SlotApprovalRequest(
        plan_id="p1",
        title="Jettro and Daniel",
        day=DAY,
        candidates=[SLOT, ProposedSlot(start=time(14, 0), end=time(15, 0))],
    ).question()
    assert "10:00-11:00" in question
    assert "14:00-15:00" in question


def test_the_declared_vocabulary_has_no_duplicates():
    assert len(MESSAGE_TYPES) == len(set(MESSAGE_TYPES))


def test_approval_must_name_its_slot():
    """Found live: a client sending `approved=True` with the slot under the
    wrong field name was read as a refusal and the plan was cancelled."""
    with pytest.raises(ValidationError):
        SlotApprovalDecision(plan_id="p1", approved=True)

    refusal = SlotApprovalDecision(plan_id="p1", approved=False)
    assert refusal.slot is None


def test_a_request_without_a_lunch_wish_is_a_question_to_ask():
    """Tri-state: `None` is the only value that stops the team to ask (D9)."""
    assert not request().lunch_is_settled()


def test_a_stated_wish_settles_lunch_up_front():
    settled = request().model_copy(update={"lunch_wish": "something vegetarian"})
    assert settled.lunch_is_settled()
    assert settled.to_plan().lunch_wish == "something vegetarian"


def test_declining_lunch_settles_it_too():
    """`--no-lunch` must not block a scripted run on a prompt."""
    assert request().model_copy(update={"with_lunch": False, "lunch_wish": ""}).lunch_is_settled()


def test_a_refusal_carries_no_wish():
    """A client that says no and describes a lunch has its fields confused,
    and should hear about it here rather than order something by accident."""
    with pytest.raises(ValidationError):
        LunchApprovalDecision(plan_id="p1", wants_lunch=False, wish="sandwiches")


def test_lunch_may_be_left_to_the_kitchen():
    """An empty wish is a real answer: @Catering holds the menu, not the human."""
    decision = LunchApprovalDecision(plan_id="p1", wants_lunch=True)
    assert decision.wants_lunch
    assert decision.wish == ""


def test_the_lunch_question_says_who_it_is_for():
    question = LunchApprovalRequest(
        plan_id="p1", title="Jettro and Daniel", day=DAY, headcount=2
    ).question()
    assert "Jettro and Daniel" in question
    assert "2" in question


def test_the_lunch_wish_reaches_catering_verbatim():
    rendered = OrderLunchAssignment(
        plan_id="p1",
        location_id="AMS",
        day=DAY,
        headcount=2,
        wish="something vegetarian",
    ).rendering()
    assert "something vegetarian" in rendered
