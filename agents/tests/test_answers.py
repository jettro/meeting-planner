"""Reading a human's answer.

These used to live in the CLI tests. They moved here when the server needed
the same interpretation (design_gui.md G6): the rules belong to the questions,
not to whichever client collected the words.
"""

from __future__ import annotations

from datetime import date, time

import pytest
from meeting_agents.answers import (
    UnreadableAnswer,
    interpret_lunch_answer,
    interpret_slot_answer,
)
from meeting_agents.messages import LunchApprovalRequest, ProposedSlot, SlotApprovalRequest

DAY = date(2031, 9, 15)
MORNING = ProposedSlot(start=time(9, 0), end=time(10, 0))
LATER = ProposedSlot(start=time(14, 0), end=time(15, 0))


def a_slot_question() -> SlotApprovalRequest:
    return SlotApprovalRequest(plan_id="p1", title="Design review", day=DAY, candidates=[MORNING, LATER])


def a_lunch_question() -> LunchApprovalRequest:
    return LunchApprovalRequest(plan_id="p1", title="Design review", day=DAY, headcount=2)


# -- the slot gate ----------------------------------------------------------


def test_a_number_picks_that_slot():
    """The structure is in the question: the answer is only an index into the
    candidates that travelled with it. That is what lets a browser render
    radio buttons and still send a string."""
    decision = interpret_slot_answer(a_slot_question(), "2")

    assert decision.approved is True
    assert decision.slot == LATER
    assert decision.plan_id == "p1"


def test_declining_carries_no_slot():
    decision = interpret_slot_answer(a_slot_question(), "n")

    assert decision.approved is False
    assert decision.slot is None


def test_silence_declines_the_slot():
    """Nothing is booked at this point, so the safe reading of silence is no."""
    assert interpret_slot_answer(a_slot_question(), "   ").approved is False


@pytest.mark.parametrize("answer", ["banana", "0", "3", "-1", "1.5"])
def test_an_unreadable_answer_is_refused_rather_than_guessed(answer):
    """A terminal asks again and a server answers 4xx, but neither may pick a
    time on someone's behalf because they typed nonsense."""
    with pytest.raises(UnreadableAnswer):
        interpret_slot_answer(a_slot_question(), answer)


def test_the_refusal_explains_what_would_work():
    with pytest.raises(UnreadableAnswer, match="1-2"):
        interpret_slot_answer(a_slot_question(), "banana")


# -- the lunch gate ---------------------------------------------------------


def test_a_described_lunch_is_passed_on_untouched():
    """Reading "something warm" is @Catering's job - it holds the menu."""
    decision = interpret_lunch_answer(a_lunch_question(), "  something warm, no bread ")

    assert decision.wants_lunch is True
    assert decision.wish == "something warm, no bread"


def test_saying_no_to_lunch_carries_no_wish():
    decision = interpret_lunch_answer(a_lunch_question(), "No")

    assert decision.wants_lunch is False
    assert decision.wish == ""


def test_silence_leaves_the_lunch_to_the_kitchen():
    """Silence means the opposite of what it means at the slot gate, on
    purpose: lunch has already been asked for, only the kind is open."""
    decision = interpret_lunch_answer(a_lunch_question(), "")

    assert decision.wants_lunch is True
    assert decision.wish == ""


@pytest.mark.parametrize("answer", ["yes", "surprise me", "you choose"])
def test_a_shrug_is_not_mistaken_for_an_order(answer):
    assert interpret_lunch_answer(a_lunch_question(), answer).wish == ""


def test_an_unreadable_lunch_answer_does_not_exist():
    """There is nothing to fail to understand here, which is the point of D9:
    any text that is not a refusal or a shrug is simply the wish."""
    assert interpret_lunch_answer(a_lunch_question(), "???").wish == "???"
