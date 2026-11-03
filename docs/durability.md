# Durability

## What it is

A meeting takes time to arrange. The team asks you about the time and then waits - for a minute,
or until tomorrow - and in between the server may restart, or the team may be stopped. When your
answer finally comes, the team has to know what it was waiting for. Weeks later, when you cancel,
it has to know what it booked.

The sample's answer is one idea: **the team is the meeting.** One team arranges one meeting, and
the coordinator's state - which meeting, which room booking, which lunch order, and what it is
waiting for - is the only record of it. There is no separate database of plans. A stopped team is
brought back from what the server kept, and everything that concerns the meeting, cancelling
included, goes to that team.

> **The one sentence to keep:** *one meeting, one owner, one record.*

## How it works

### What is kept

The server keeps two things for every team:

- **every message**, which is what the trace shows; and
- **the latest state of every agent**, saved whenever the state changes - a *snapshot*.

For the coordinator, the state is the meeting's record: the request, the times on offer, the slot
you approved, the ids the services gave back, what it is waiting for, and why it failed if it did.

### Bringing a team back

A stopped team is revived when something is delivered to it, or when the planner asks for it. The
framework starts the agents again and gives each the state it last saved. It does **not** replay
old messages through the agents: the coordinator does not ask you again or book anything twice.
It simply wakes up knowing where it was.

So a meeting parked at the time question can be answered tomorrow: the answer revives the team,
the coordinator sees which question is open, and the saga carries on.

### Resume and cancel

The *Meetings* tab lists your teams with each coordinator's state, and offers what fits:

- **Resume** for a meeting that is waiting for you. It revives the team and shows the open
  question again.
- **Cancel** for any meeting not cancelled yet - waiting, booked or failed. The cancel goes to
  the team that made the meeting - revived first if it had stopped - because only its
  coordinator knows what was booked.

Cancelling releases what was booked, newest first: the lunch order, then the room, then the
meeting. Each release goes the way the booking went - the order through `@FacilityManager` to
`@Catering`, the room through `@FacilityManager`, the meeting through `@Scheduler`. A release that
fails does not stop the others; it becomes one line in the report of how the cancel went. Cancelling
twice reports the first cancel again, instead of trying to release ids that are already gone.

If a booking is still under way when you cancel, its answer is released the moment it arrives.

### State first, then send

Every coordinator handler records what changed in its state before it sends the message that
reports it. Whoever reads the stream - the planner, the trace - therefore sees *booked* only after
the snapshot that says so has been saved.

## Why it is built this way

**One record cannot disagree with itself.** An earlier version kept plans in a store of their
own, with an agent that owned it, beside the teams that did the booking. Every operation then had
two places to keep in step - and cancelling needed a *new* team that loaded the plan and stopped
the old one first. Making the coordinator's state the record removed the store, the agent, the
second team and the stop: the ids that belong together are kept by the team that booked them.
([`design_durability.md`](design/design_durability.md) R2, R3, R4.)

**Snapshots, not replay.** Replaying old messages through the agents would re-run their
handlers, and handlers book rooms. Restoring the last state brings an agent back to where it was without
doing anything again.

**The question waits as a fact, not as a thread.** Because the coordinator never blocks on you, a
question is just state plus a message in the store. Nothing has to stay running for it to be
answerable later. (See [the team](team.md).)

**Resume is offered by what the coordinator waits for**, not by whether the team happens to be
running. A stopped team waiting for you is resumable; a finished or failed one is not, though it
can still be cancelled. (R6.)

**There is no update.** Changing a meeting was designed twice, and dropped twice: it needed a
chain of revisions and a saga that compared them - all scaffolding around the one piece that was
missing, undoing. Cancel *is* that piece. To change a meeting, cancel it and plan a new one.
([`design_cancel.md`](design/design_cancel.md).)

### A lesson from building it

For a while, the conclusion was that the coordinator *could not* be durable. An experiment had
stopped a team, revived it, and found the coordinator empty; most of the plan store was built on
that finding. It was wrong. The framework saves an agent's state only if the state has an
*observer* attached, and replacing a state keeps the observer of the old one - never creates one.
The specialists attach one when they start; the coordinator started from a fresh state with none,
so none of its changes were ever saved. The fix was one line in `on_start`:

```python
self.state = CoordinatorState()
self.state.observer(self)
```

The experiment had measured our code correctly, but read it as a property of the framework.
A test that stops a team at the time question, revives it and books the meeting now decides it
both ways: with the line, it passes; without it, no snapshot is ever written.

## What it does not do

- **Survive a crash mid-call.** If the server dies while a specialist is waiting for its model or
  a service, that reply is lost; the record still says what was booked before. Out of scope on
  purpose. (R9.)
- **Release a failed plan by itself.** A failure lists what is still booked; releasing it is a
  cancel (`design_cancel.md` §8.3, still open).
- **Change a meeting**, as above.

## Where in the code

| File | What is there |
|---|---|
| `agents/src/meeting_agents/coordinator.py` | `on_start` and its observer line; the cancel and the late-reply handlers |
| `agents/src/meeting_agents/plan.py` | the record, and `compensations()`: what to release, newest first |
| `agents/src/meeting_agents/specialists.py` | `release`: one cancellation, answered whatever happens |
| `gui/src/pages/MeetingsPage.tsx` | the Meetings tab: Resume and Cancel |
| `server/tests/test_restore.py` | stop, revive, answer, book |

The designs: [`design_durability.md`](design/design_durability.md) and, for the release itself,
[`design_cancel.md`](design/design_cancel.md).

---

*Last checked against the code: 2026-11-03, `cedef30`.*
