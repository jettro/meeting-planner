# Moving a meeting to another day — design

> **Status:** draft, 2026-11-27, for review. Nothing is built. The work stays on the branch
> `claude/reschedule-meeting` until it has been tried, so the talk's demo on `main` cannot break.
>
> **Revisits:** `design_cancel.md`, which decided *"There is no update. If something about a
> meeting is wrong, you cancel it and plan a new one."* This design keeps the spirit of that
> decision: nothing is updated in place. A move books the meeting again, on the new day, and only
> then releases the old bookings - the same saga, run twice, in the team that owns the meeting.
>
> *A design records what was decided and why, at the time; it is not kept current.*

## Why

The demo books a meeting and cancels one. What people do most with a meeting is neither: they
move it. *"Can we do Thursday instead?"* is the request everyone recognises, and it is the one
that shows a team at work best:

- the **record** matters: the team must know what it booked to release it (question 3);
- the **human approves again**: the new time is a question, not a guess;
- the **wishes carry over**: the place, *somewhere quiet*, and *vegetarian, no bread* are not
  asked again;
- and it can **fail halfway** in a new way: the new room is taken, and the old meeting must
  survive that untouched.

## What a move is

| | Stays | Changes |
|---|---|---|
| Who | title, participants, organiser | - |
| When | duration | the **day**; the **time**, chosen again at the slot gate |
| Where | the place (`location_id`, its name and why it was chosen), the place wish | the **room**, booked again at the same place |
| Lunch | whether there is lunch, and the wish in words | the **order**, placed again for the new day |

The services have no update operations (`book_*` and `cancel_*` only), and a new day needs a new
agenda entry, a new room booking and a new delivery date anyway. So a move is: **book the new one,
then release the old one.**

## Decisions

**M1 - The move happens in the team that owns the meeting.** *The team is the meeting*
(`design_durability.md`): the coordinator's state is the only record of what was booked, so it is
the only place that can release the old bookings and book new ones without copying anything. A
move is a typed message to that team, exactly like a cancel (R4) - revived first if it has
stopped.

Two alternatives were considered and set aside:

- *A new conversation loads an existing meeting.* It needs a way to read one team's record from
  another and a server path to find it, and it creates a second writer for the same bookings -
  the problem `design_cancel.md` §8.2 had to solve before durability removed it.
- *Cancel, then plan a new meeting.* It breaks before it makes (M3), loses the link between the
  two, and someone has to copy the wishes into the new request by hand or by model. It is what
  the demo can already do; it is not a better story.

**M2 - What carries over is copied by code, not restated by a model.** The coordinator builds the
new booking from its own record: same plan, new day, booking fields cleared. The model in the
conversation only supplies the day. A wish can not be lost or rephrased on the way.

**M3 - Make before break.** The new meeting, room and lunch are booked first; the old ones are
released only when all three are in place. If any new step fails, what was newly booked is
released and the old meeting is left exactly as it was, then reported: *"The meeting stays on
Tuesday: no room at the Library on Thursday."* At no point does the person have no meeting.

**M4 - One question: the time.** The slot gate opens again, with the place's name and reason, so
the person approves the new time and sees where it is. There is no lunch question: the wish is
kept (M2). Declining every slot ends the move, not the meeting - nothing was booked, nothing is
released (M10).

**M5 - Same plan, same id.** The meeting keeps its `plan_id`; every message of the move carries
it, as all messages do. The old booking is finished, so nothing else is in flight for that plan
and there is nothing to confuse a late answer with. A move id would add a second key to every
message for no case that needs it.

**M6 - The vocabulary.** Three new messages; everything else is reused.

```
MovePlanRequest(plan_id, day)                    @Human/@Intake -> @Coordinator
PlanMoved(plan, previous, failures)              @Coordinator   -> @Human/@Intake
MoveFailed(plan, reason, released, failures)     @Coordinator   -> @Human/@Intake
```

Reused unchanged: `FindSlotsAssignment` / `SlotsFound`, `SlotApprovalRequest` /
`SlotApprovalDecision`, `BookMeetingAssignment` / `MeetingBooked`, `BookFacilitiesAssignment` /
`FacilitiesBooked`, `CancelAssignment` / `Cancelled`, `AssignmentFailed`. The specialists do not
change at all, and neither do the booking rules: the new assignments carry the newly approved
day and slot, which is what the rules check against.

- `PlanMoved.plan` is the meeting as it now is; `previous` is the booking it replaced, ids
  included, and `failures` lists any old booking that could not be released.
- `MoveFailed.plan` is the meeting as it still is; `released` says whether new bookings had to be
  undone, and `failures` any that could not be.

**M7 - The state.** `CoordinatorState` gains:

```python
#: The new booking while a move runs: the plan with the new day and no ids yet.
moving: MeetingPlan | None = None
#: What the release queue is for when it empties: "cancel", "move" or "move_failed".
releasing_for: str = "cancel"
```

While `moving` is set, the specialists' answers fill in `moving`, not `plan`. When the new
lunch (or room, without lunch) is booked: `plan` becomes the new booking, the old one is queued
for release with `releasing_for="move"`, and the queue's end sends `PlanMoved` instead of
marking the meeting cancelled. On a failure: the new partial bookings are queued with
`releasing_for="move_failed"`, `moving` is cleared, and the queue's end sends `MoveFailed`.
State first, then send (R8), as everywhere.

`MeetingPlan` gains one field, so the record says the meeting moved:

```python
#: Earlier bookings this meeting replaced, oldest first: day, time and ids.
moved_from: list[PreviousBooking] = []
```

**M8 - Same day, another time: allowed, with one limit.** Make before break means the old meeting
still holds its time while the new one is found, so the new time can not overlap the old one.
That is the honest consequence of M3 and is stated, not worked around.

**M9 - The place does not change.** It was approved with the first time. If it has no room on the
new day, the move fails and the meeting stays (M3). Choosing a new place from the wish is
possible later (open question Q2).

**M10 - Which meetings can move.** Only a booked one (`CONFIRMED`) that is not being cancelled or
moved already. Anything else is answered with `MoveFailed`, nothing done, and a reason in words:
*not booked yet*, *cancelled*, *already being moved*. A move to the day it is already on is
allowed (another time, M8).

**M11 - Cancelling during a move** releases both: the new partial bookings and the old meeting.
It uses the existing late-booking rule (R5) for anything that lands after the cancel.

**M12 - In the conversation.** `@Intake` gets a sixth tool, `move_meeting(day)`, for the meeting
this conversation arranged. It sends `MovePlanRequest` and nothing else; the time is asked on the
person's screen, as always. "Just move it to Thursday at ten" is understood and authorises
nothing, exactly like the first booking (I4). The prompt's line *"a different day, people or place
means a new conversation"* becomes: *a different day: move_meeting; different people or place: a
new conversation.* `PlanMoved` and `MoveFailed` are relayed and explained like the other
outcomes.

**M13 - In the planner.**

- The meetings list offers **Move…** beside **Cancel meeting**: a day picker, then the plan screen
  with the slot question. A meeting made in a conversation offers **Continue the conversation**,
  which reopens it - the conversation is where that meeting is moved.
- **A fix the move needs:** the plan and chat screens take the *first* outcome as final and stop
  looking for questions after it (`TeamContext.outcome`). After a move there is a second
  question and a second outcome. The rule becomes: the outcome is the latest one, and a question
  is open if it came after it and is unanswered. `PlanMoved` counts as booked.
- While a move runs, the list shows *moving to Thursday* from `state.moving`.

**M14 - @Guard.** "Can we move it to Thursday?" is about arranging the meeting, which the prompt
already covers ("Thursday" is given as an example). Four cases are added to the evaluation set to
hold that: a move, a move with a time, a move with a reason, and "move my dentist appointment",
which is something else.

**M15 - Memory, unchanged.** A move changes no fact about a person or a place. Facts about the
place are shown again to the facility manager when it books the new room.

## What would be built

1. `messages.py`: the three messages, `PreviousBooking`; both teams' `message_types`.
2. `coordinator.py`: `receiveMsg_MovePlanRequest`, the `moving` branch in the four specialist
   handlers and `SlotApprovalDecision`, the release queue's three endings.
3. `intake.py` and `intake_prompt.yaml`: `move_meeting`, the two relays, the prompt line.
4. The GUI: the outcome rule (M13), **Move…**, **Continue the conversation**, the chip.
5. `guard_eval`: four cases.
6. Tests, without the stack, like `test_cancel.py`: a move end to end; the slot declined; no room
   on the new day (the old meeting untouched, the new meeting released); lunch failing on the new
   day; a cancel during a move; a move refused for each M10 reason; a restored team mid-move. One
   run with the real specialists and a stub model, as for cancel, to prove the hops.
7. `docs/team.md`, `docs/demo.md` (an act for the move), and this document's status.

Rough size: a day of work, most of it the coordinator and its tests. The specialists, the
services, the MCP servers and the booking rules do not change.

## For the talk

If it works, demo 2 gets one more line - *"Can we move it to Thursday?"* - and question 3 gets its
best example: the record is what makes a move possible, and make-before-break is what a failure
halfway looks like when it is designed for. Nothing in the deck changes until it has been tried.

## Open questions

- **Q1 - A time in the request?** "Move it to Thursday at ten" could narrow the slot question to
  that time when it is free. *Recommendation:* the day only, for now; the slot question already
  lists the times, and the person picks one on screen - the approval stays visible.
- **Q2 - A full place on the new day.** Fail and keep the meeting (M9), or ask the facility
  manager to choose again from the wish, and show the new place at the slot gate?
  *Recommendation:* fail first; choosing again is a later step.
- **Q3 - The planner's Move button.** Needed for meetings made with the form; the demo's move
  would happen in the conversation. *Recommendation:* build it - it is small next to the outcome
  fix the screens need anyway.
- **Q4 - `moved_from` on the plan.** Keep the history on the record (recommended), or only in the
  trace?
- **To verify:** a stopped *conversation* team is revived by a new message, as a stopped form team
  is by an answer (R4). Measured for cancel; to be measured for the chat team before relying on
  it in the demo.
