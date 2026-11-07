# Design: how agents talk - messages and types

> **Status:** built 2026-11-07 - all five (Q1), after *How it is built* (Q2): slides 26-30.
> `sequence.js` draws M4 from the order `coordinator.py` sends in. *Why akgentic* (Q3) is still to come.
> The plan's part 5 (*underneath: agents as actors*, [`plan.md`](plan.md)) without the framework:
> what any team of agents needs, shown with the sample's own classes. A slide that introduces
> akgentic - *why use it* - comes later, after these.

## The idea

The room has seen the team as boxes (the patterns, *how it is built*). These slides answer the
question the boxes raise: **what goes along the lines?** Not a chat, and not free text: typed
messages, and a model that answers in a type too. All of it is plain Python and Pydantic; akgentic
is only where it runs.

## Proposed slides

| # | Slide | Content | From the code |
|---|---|---|---|
| M1 | **How do agents talk?** | two ways side by side: a *shared conversation* - everyone reads everything, in text (group chat) - and *messages* - addressed to one agent, with a fixed shape. The sample uses messages. Takeaway: *agents talk in messages, not in a chat* | the patterns slide's group chat, turned down on *the crew* slide |
| M2 | **A message is a type** | two real classes as code: `BookMeetingAssignment` (plan_id, title, participant_emails, day, slot) and its answer `MeetingBooked` (plan_id, meeting_id). The contract between two agents is a schema: validated when it is made, a renamed field breaks a test, not a demo | `messages.py` |
| M3 | **The model answers in a type, too** | the specialist's shape in one handler: assignment in → `attempt(message, BookedMeeting)` → a typed message out; and `BookedMeeting` with `succeeded`, `meeting_id` (*"Never invent one"*) and `reason`. Free text never crosses from one agent to the next; a failure is a field, not a sentence | `specialists.py`, `outputs.py` |
| M4 | **One meeting, in messages** | a sequence diagram that builds up: `PlanMeetingRequest` → `FindLocationAssignment` / `LocationFound` → `FindSlotsAssignment` / `SlotsFound` → `SlotApprovalRequest` to you … your `SlotApprovalDecision` → `BookMeetingAssignment` / `MeetingBooked` → … → `PlanCompleted`. Every message carries the `plan_id` | the coordinator's `receiveMsg_*` handlers |
| M5 | **What messages buy you** | four things, one line each: *a trace for free* (every message is an event), *waiting costs nothing* (your answer may come a day later - nothing is blocked), *durable* (keep the messages and a stopped team can be revived), *testable* (send an agent a message, check what it sends back). Leads into *why akgentic* | `docs/durability.md`, the trace, the tests |

## Where in the deck

Proposed: **right after *How it is built* (now 25)** - the boxes first, then what goes between
them - and before the repository and the first live demo, where the trace shows these very
messages.

## Questions

| Id | Question | Options |
|---|---|---|
| Q1 | Which of M1-M5? | all five; or M2-M4 (the types and the flow), with M1 and M5 in the speaker notes |
| Q2 | Where? | after *How it is built* (proposed); or after the team patterns, before *How it is built* |
| Q3 | *Why akgentic* | later, as asked - a slide after M5 would be its natural place |
