"""Turning a human's answer into a typed decision.

This lives apart from any client on purpose (design_gui.md G6). The terminal
and the server ask the same two questions and must read the answers the same
way; a second interpretation living in a browser is a second thing to get
wrong, and it would be the one nobody tests.

Everything here is pure: a question and a string in, a decision out. No input,
no printing, no actors.
"""

from __future__ import annotations

from meeting_agents.messages import (
    LunchApprovalDecision,
    LunchApprovalRequest,
    SlotApprovalDecision,
    SlotApprovalRequest,
)

#: Answers that decline the proposed slots. Silence is among them: nothing is
#: booked at that point, so the safe reading of an empty answer is "no".
SLOT_REFUSALS = {"n", "no", "none", ""}

#: Answers that mean "no lunch". Anything else is taken as a description of
#: one, because the point of the gate is that a person may say what they like.
LUNCH_REFUSALS = {"n", "no", "none", "nothing", "skip"}

#: Answers that mean "yes, but you choose". An empty wish is a real answer
#: here - composing the lunch is @Catering's judgement, with a menu we never
#: show. Note that silence means the opposite of what it means at the slot
#: gate, and deliberately so: by now lunch has been asked for already, and the
#: only open question is what kind.
LUNCH_DEFERRALS = {"", "y", "yes", "please", "anything", "surprise me", "you choose"}


class UnreadableAnswer(ValueError):
    """The answer did not match the question.

    Raised rather than guessed. A terminal catches this and asks again; a
    server turns it into a 4xx. Neither should pick a time slot on a person's
    behalf because they typed "banana".
    """


def interpret_slot_answer(request: SlotApprovalRequest, answer: str) -> SlotApprovalDecision:
    """Read an answer to the slot gate as a choice among *this* question's slots.

    The structure is in the question, not the answer: the candidates travel
    with it, so the answer only has to be an index. That is why a browser can
    render radio buttons and still send a string.
    """
    folded = answer.strip().lower()
    if folded in SLOT_REFUSALS:
        return SlotApprovalDecision(plan_id=request.plan_id, approved=False)
    if folded.isdigit() and 1 <= int(folded) <= len(request.candidates):
        return SlotApprovalDecision(
            plan_id=request.plan_id,
            approved=True,
            slot=request.candidates[int(folded) - 1],
        )
    msg = f"Answer 1-{len(request.candidates)} to pick a slot, or n for none of them."
    raise UnreadableAnswer(msg)


def interpret_lunch_answer(request: LunchApprovalRequest, answer: str) -> LunchApprovalDecision:
    """Read an answer to the lunch gate (D9).

    Only the two answers that are *not* descriptions are interpreted: a
    refusal and a shrug. Everything else is passed through untouched, because
    making sense of "something vegetarian" is the job of the agent holding the
    menu - not of whichever client happened to collect the words.
    """
    wish = answer.strip()
    folded = wish.lower()
    if folded in LUNCH_REFUSALS:
        return LunchApprovalDecision(plan_id=request.plan_id, wants_lunch=False)
    if folded in LUNCH_DEFERRALS:
        return LunchApprovalDecision(plan_id=request.plan_id, wants_lunch=True)
    return LunchApprovalDecision(plan_id=request.plan_id, wants_lunch=True, wish=wish)
