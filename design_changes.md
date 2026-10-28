# Revising a meeting — design

Status: **proposed**. Nothing here is built yet.

An earlier draft of this document designed a *mutation*: load a plan, change it
in place, undo what the change invalidated, all inside the team that made it.
It was argued down, correctly, in favour of the model below. The findings that
drove the first draft are kept in Appendix A, because they are the reason this
one can be confident about what it is *not* doing.

---

## 1. The model

**A revision is a new plan that supersedes the old one.** The human asks to
move Thursday's meeting to Friday; the system makes a *new* plan, books what
Friday needs, releases what Thursday held, and marks the old plan superseded.
The old plan survives as a record of what was booked.

A revision runs in a **new team**, like any other plan. One team, one plan, one
event log — the property the Trace screen is built on stays true.

### Why this and not a mutation

1. **The saga keeps one shape.** Mutating in place means reschedule re-enters
   the saga at "find slots", change-room at "book room", change-lunch at "order
   lunch" — five partial resumptions, hand-written. A revision instead asks one
   question, "what does this plan still lack?", which is the same question a
   brand-new plan asks. §4.
2. **A plan is written as a snapshot**, so changing one in place overwrites
   what it used to say. In a system whose point is a legible record, losing
   "what did we have before Friday?" is a real loss.
3. **No team lifecycle problem.** No restoring a stopped team, no team that was
   deleted from the console, no two browsers changing one team at once.

### What it does *not* avoid

The old bookings still have to be released. **The compensation runner is still
the one genuinely missing piece**, and building it is still most of the work.
This decision changes *when* compensations run and *how they are computed* — not
whether they are needed.

## 2. What a revision inherits

Decided: **a revision carries over what it does not change**, and only the
difference is cancelled. Changing the sandwich order should not cancel and
rebook the room.

| Revision | Meeting | Room booking | Lunch order |
|---|---|---|---|
| Cancel | release | release | release |
| Change lunch | keep | keep | release |
| Change room, same location | keep | release | keep |
| Change location | keep | release | release |
| Reschedule | release | release | release |
| Change participants | release | keep | release |

The reasoning behind each cell, since none of it is obvious:

- **The meeting survives a room change** because a meeting lives in the meeting
  service — people's agendas — and a room lives in the location service. Moving
  rooms does not change anyone's calendar.
- **Lunch survives a room change but not a location change**, because an order
  is tied to a location, not a room code. This is the rule
  `relocation_compensations()` already encodes; §3 shows it falling out for
  free.
- **A reschedule releases everything**, because all three bookings are for a
  time.
- **Changing participants** keeps the room (it was big enough and we are not
  modelling capacity) but rebooks the meeting, whose attendee list changed, and
  the lunch, whose headcount changed.

## 3. The compensation list is a diff

This is the part that makes the model pay for itself.

The coordinator builds the new plan by **carrying over the references the
revision keeps and leaving the rest empty**. What must then be cancelled is
exactly what the old plan holds that the new one does not:

```python
def compensations_against(self, previous: MeetingPlan) -> list[Compensation]:
    """What `previous` holds that this plan does not inherit."""
```

One method replaces two. `relocation_compensations()` can go: a same-location
room change carries `order_id` across, so the diff yields nothing for lunch; a
genuine move cannot carry it, so the diff yields the cancel. Identical answers,
without a second method that has to be kept in step with the first.

`compensations()` stays, for an outright cancel — a plan that inherits nothing.

Two things fall out that are worth stating:

- **The diff cannot disagree with the plan.** Under a mutation design, "what to
  undo" was computed from the *kind of change*; here it is computed from the two
  plans themselves. A revision that forgets to drop a reference cannot ask for
  a cancellation of something it is still using.
- **A revision that changes nothing is a no-op**, for free. Every reference
  carries over, the diff is empty, nothing is cancelled and nothing is booked.

## 4. The saga becomes state-driven

Honesty about the main claim in §1: carrying references over means the new plan
starts part-booked, so the saga cannot simply start at the beginning. A
change-room revision arrives with its meeting and its lunch already in hand and
needs only a room.

But this is **one rule, not five**:

> Do the first thing this plan lacks.

The order is the one the plan's own `status` ladder already describes — slots,
approval, meeting, room, lunch. A blank plan lacks all of it and starts at
slots, which is today's behaviour; a change-room plan lacks only a room.

So the work is to replace the coordinator's hard-wired chain (`SlotsFound` →
book meeting → `MeetingBooked` → book facilities → …) with a `next_step(plan)`
consulted after each step completes. That is a refactor of the coordinator, and
it is worth doing regardless: the ladder is currently encoded twice, once in
`status` and once in the order of the handlers.

One subtlety: `next_step` is **the first missing reference**, not the highest
one reached. A change-room plan has a meeting and a lunch but no room; a status
ladder read top-down would call it `SCHEDULED` and then try to order a lunch it
already has. Write the gap-finder explicitly rather than reusing `status`.

## 5. Ordering: cancel first

Decided: **release the old references, then book the replacements.**

The exposure is a window in which the meeting is not booked anywhere. It is
accepted because:

- It matches what the human just said. They asked to move the meeting; the old
  slot being free is the point, not a side effect.
- Booking first can deadlock against ourselves. A reschedule that keeps the same
  room competes with our own outstanding booking for it.
- "Cancel first" releases only **the difference**, not everything. A lunch
  change never touches the room, so the window only ever covers what is
  genuinely being replaced.

If a replacement booking then fails, the result is a plan in the same
half-finished state the existing failure path already handles, and the old plan
is already superseded. §10 carries the open question of whether that is good
enough.

## 6. Data model

On `MeetingPlan`:

```python
supersedes: str | None = None      # the plan this one revises
superseded_by: str | None = None   # set on the old plan when the new one lands
```

`superseded_by` is what makes the Plans screen cheap: **a plan is current when
`superseded_by` is None.** Without it the screen would have to walk the chain.

`PlanStatus` gains `SUPERSEDED`, taking precedence over `CANCELLED` in the
computed ladder — a superseded plan had references cancelled, but "replaced by a
newer version" is the more useful thing to say about it.

Note for whoever adds it: a new enum member is safe **only because** the event
store now has an `Enum` multi-representer. Adding one before that fix would have
silently dropped every message carrying a plan (`design_gui.md` §8.4).

`team_ids` stays as it is. One plan is still one team, so it is normally one
entry — it simply no longer has to carry the weight of linking a plan's several
runs, because a plan no longer has several.

## 7. Vocabulary and flow

```
RevisePlanRequest(plan_id, revision)   @Human       -> @Coordinator
ReviseApprovalRequest(plan_id, ...)    @Coordinator -> @Human
ReviseApprovalDecision(plan_id, ok)    @Human       -> @Coordinator
CancelAssignment(plan_id, step, ref)   @Coordinator -> the owning specialist
Cancelled(plan_id, step, ref)          specialist   -> @Coordinator
```

`revision` is a tagged union of the six kinds, so the coordinator dispatches on
the kind in one place rather than across six handlers. There is no
`PlanChanged`: a revision ends in `PlanCompleted` carrying the new plan, like
any other plan, which is the whole point.

`CancelAssignment` carries a `CompensationStep`, so routing is a lookup from
step to the specialist that owns that service. **The one-service rule (D1) is
untouched** — `@Scheduler` cancels meetings, `@FacilityManager` cancels room
bookings, `@Catering` cancels orders, each on the service it already reaches.

The flow, for a change of location:

```
@Human           RevisePlanRequest(plan, ChangeLocation("yuma-north"))
@Coordinator     LoadPlan(plan_id)                    -> @PlanRepository
@PlanRepository  PlanSnapshot(previous)               -> @Coordinator
@Coordinator     drafts the new plan: meeting carried over, room and lunch empty
@Coordinator     ReviseApprovalRequest(the diff)      -> @Human
@Human           ReviseApprovalDecision(approved)     -> @Coordinator
@Coordinator     CancelAssignment(CANCEL_ORDER)       -> @Catering
@Coordinator     CancelAssignment(CANCEL_ROOM_BOOKING)-> @FacilityManager
@Coordinator     SavePlan(previous, superseded_by=new)-> @PlanRepository
@Coordinator     next_step(new) == book facilities    -> the ordinary saga
@Coordinator     PlanCompleted(new)                   -> @Human
```

Compensations run **one at a time, in `compensations()` order** — reverse
booking order, which is the order the services expect, and which makes a partial
failure describable.

The gates still apply where the revision invalidates their answer: a reschedule
re-opens the slot gate, a lunch change re-opens the lunch gate, a room change
opens neither. The approval in the middle is separate from both — it confirms
what will be *released*, which is the thing the human has not yet been shown.

## 8. The browser

The Plans screen shows **current plans only** — `superseded_by is None` — with
earlier versions reachable from the plan dialog. A list that accumulated a dead
row per revision would get less useful the more the system was used.

A revised plan's dialog therefore gains a **History** section beside Runs: the
chain of plans it replaces, each a link to that plan and to its own trace. The
trace of "what happened to this meeting over time" is the traces of the chain,
in order — and each one is still a single clean run.

Also needed: a **Revise** button offering the kinds valid for that plan's status
(a cancelled plan offers none; a plan without lunch does not offer "change
lunch"), and a **confirmation** listing what will be released in words rather
than ids — "the lunch order and the room booking at yuma".

The client needs no team-lifecycle calls at all. It creates a team, as it does
now.

## 9. Order of work

1. **The compensation runner**, via plain cancel. Pure release, no rebooking, so
   it builds the missing piece alone: `CancelAssignment` / `Cancelled`, the
   three specialist handlers, and the serial driver.
2. **`next_step(plan)`** in the coordinator, replacing the hard-wired chain.
   Behaviour-neutral for a fresh plan, and provable by the existing tests.
3. **`compensations_against`**, `supersedes` / `superseded_by`, `SUPERSEDED`.
4. **Change lunch** — the smallest real revision: one cancel, one rebook, one
   gate.
5. **Change room, change location, reschedule** — the same machinery with
   different inherit rules.
6. **Change participants** — last, because it is the only one whose inherit
   rules depend on the data rather than on the kind.

## 10. Open questions

1. **A compensation that fails** — a booking someone else already cancelled.
   Stop, or carry on and report? We favour carry-on, so one stale reference
   cannot strand the other two, with the failures recorded on the plan.
2. **A replacement booking that fails after the old one was released.** The
   meeting is now booked nowhere and the old plan is superseded. Options: leave
   it failed and visible, or re-book the original. Re-booking is not reliable —
   the slot may be gone — so "failed and visible" is probably honest, but it
   should be a decision rather than a default.
3. **Does `with_lunch: false` mean "never" or "not yet"?** "Add lunch" to a plan
   that has none is a revision the table in §2 does not describe.
4. **Two revisions of one plan at once.** Both would read the same `previous`
   and both would try to cancel the same references. `superseded_by` makes this
   detectable — the second revision finds it already set — so it can be refused
   rather than ignored.

---

## Appendix A: why not mutate in place, in detail

The first draft reused the team that made the plan. Four things had to be true,
and all four were measured against the running stack. They are recorded because
they are expensive to re-derive, and because two of them are facts about the
framework that will matter elsewhere.

- **A stopped team can be restored.** `POST /teams/{id}/restore` returned 200
  for a team stopped the previous day.
- **Restoring re-runs nothing.** `TeamRestorer` replays the log through
  `Orchestrator.restore_message`, which appends to the orchestrator's history
  and notifies subscribers but **never routes a message to an agent**. A
  restored 142-event team was still at 142 events. Had this been otherwise,
  opening an old plan would have booked a second room.
- **A restored team works.** A `LoadPlan` sent to a restored team's
  `@PlanRepository` was received, processed, and answered with a `PlanSnapshot`,
  appending events 143–148. MCP connections and all.
- **`@Coordinator` comes back empty.** Agent state snapshots are written from
  `StateChangedMessage`, which is only emitted by an agent whose state has an
  observer attached — and exactly one place in the framework attaches one:
  `BaseAgent.__init__` (`agent/agent.py:277`), the LLM agent. Our deterministic
  agents never do. Measured: a finished team's state directory holds three
  files, the three specialists, and nothing else.

**The last point is the one to remember.** Our deterministic agents are not
durable, by construction. Anything that must survive a restart belongs in the
plan store — which is what `CoordinatorState`'s docstring already says when it
calls itself the working copy.

It also means this design never depended on the restore behaviour at all: a
revision loads the plan from the store, which is what a cold start would do.
