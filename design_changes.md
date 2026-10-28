# Changing a plan — design

Status: **proposed**. Nothing here is built yet. This document exists to be
argued with before any of it is.

Everything in it rests on findings from the running system, recorded in §2 so a
later reader can tell what was measured from what was assumed.

---

## 1. What we have, and what is missing

A plan can be *made*. It cannot be *changed*. The pieces that a change needs
are unevenly complete:

| Piece | State |
|---|---|
| The three cancel operations on the services | **Done.** `cancel_meeting`, `cancel_room_booking`, `cancel_order` exist as MCP tools, each on the service that owns the thing |
| Working out what to undo | **Done.** `MeetingPlan.compensations()` and `relocation_compensations()` |
| Anything that *runs* a compensation | **Missing.** `compensations()` is only ever reported, in `PlanFailed.outstanding` |
| A message that asks for a change | **Missing** |
| A coordinator that handles one | **Missing** |
| A specialist that can cancel | **Missing.** Every specialist handler is a *booking* handler |
| Reaching an existing plan from a new conversation | **Done.** `LoadPlan` → `PlanSnapshot` |

So the undo logic was written and never wired up. That is the shape of the
work: mostly wiring, one genuinely new decision (§4).

## 2. What the framework actually does — measured, not assumed

The user's instinct was that a change should reuse the same team. Four things
had to be true for that to be possible, and all four were tested against the
running stack rather than reasoned about.

**A stopped team can be brought back.** `POST /teams/{id}/restore` answered
`200` for a team stopped the previous day, and the team came back `running`.

**Restoring does not re-run anything.** This was the one that could have been
disqualifying: a replay that re-dispatched the saga would book a second room
every time anyone looked at an old plan. It does not. `TeamRestorer` replays
the log through `Orchestrator.restore_message`, which appends to the
orchestrator's history and notifies subscribers — it never routes a message to
an agent. Measured: a restored 142-event team was still at 142 events.

**A restored team routes new messages.** A `LoadPlan` sent to the restored
team's `@PlanRepository` was received, processed, and answered with a
`PlanSnapshot` back to `@Coordinator`, appending events 143–148. The team was
fully alive, MCP connections and all.

**But `@Coordinator` comes back empty.** Agent state snapshots are written from
`StateChangedMessage`, and that message is only ever emitted by an agent whose
state has an *observer* attached. Exactly one place in the framework attaches
one: `BaseAgent.__init__` (`agent/agent.py:277`), the LLM agent. Our
deterministic agents — `@Coordinator`, `@PlanRepository`, `@Human` — never
attach one, so their state is never snapshotted and never restored. Measured: a
finished team's state directory holds three files, `@Scheduler`,
`@FacilityManager` and `@Catering`, and nothing else.

That last finding is the interesting one, and it is **not** a problem. See §3.

## 3. Decision: the same team, and the plan store is the memory

**The same team.** A change to a plan is handled by the team that made it:
restore it, send it the change, stop it again. The alternative — a fresh team
per change — was the earlier assumption, and the measurements above remove its
only real justification.

It also gives a better trace. One plan's history stays one team's event log, in
order, with the change appended after the booking that it changes. Two teams
would mean two logs and a reader stitching them together.

**The plan store is the memory, not the agent.** `@Coordinator` comes back
with an empty `plans` dict, and we are going to leave it that way.

The tempting fix is one line — attach an observer in `on_start` and the
coordinator's state starts being snapshotted. We should not, for three reasons:

1. **It is already the design.** `CoordinatorState`'s own docstring says "the
   durable copy belongs to `@PlanRepository`; this is the working copy". A
   change request that begins by loading the plan is that sentence being true,
   rather than being a comment above a cache.
2. **Two durable copies disagree eventually.** A snapshot of the coordinator's
   working copy and `plans.json` would be written at different moments by
   different code, and the day they differ, nothing detects it.
3. **It would snapshot on every state change.** The coordinator calls
   `init_state` several times per plan; each one would become a write.

So a change begins the way a cold start would: `LoadPlan`, then work from the
`PlanSnapshot`. This has a property worth naming — **it does not depend on the
restore having restored anything**. If the framework's snapshot behaviour
changes, or a plan is changed by something that is not the original team at
all, the flow is identical.

**Consequence for `team_ids`.** It stays, and it stays a list. Reusing the team
means the list usually has one entry, and `@PlanRepository` already refuses to
add a duplicate. It is not wasted: a plan whose original team was deleted must
be changed by some other team, and then there are two.

## 4. The approval model

Agreed with the user: **one confirmation showing exactly what will be
cancelled, then execute.** Not the full gate sequence again, and not silent.

The reasoning is that a change is destructive in a way the original booking was
not. Making a plan only adds; changing one cancels a real room booking and a
real lunch order, and `cancel_order` is not reversible by re-ordering — it
produces a new `order_id`. So the human has to see the damage first. But they
have *already* chosen the change, so asking them to re-approve a slot and a
lunch is asking a question they have answered.

The confirmation is rendered from `compensations()` — which is why that method
already returning `Compensation` objects with a step and a reference is useful
rather than incidental.

**The gates come back only when the change re-opens them.** Rescheduling has to
propose new slots, so the slot gate applies to the new slot. Changing lunch has
to ask what kind. The rule: a change re-asks a question only when the change
invalidates its previous answer.

## 5. The five changes

In the order they should be built, which is also the order of increasing
difficulty.

| # | Change | Undo | Redo | Gate |
|---|---|---|---|---|
| 1 | **Cancel** | everything | nothing | confirmation only |
| 2 | **Change lunch** | the order | order again | confirmation, then the lunch gate |
| 3 | **Change room** (same location) | the room booking | book another room | confirmation only — `relocation_compensations` already knows lunch survives |
| 4 | **Change location** | the booking *and* the order | book and order at the new place | confirmation, then the lunch gate |
| 5 | **Reschedule** | all three | find slots, approve, rebook | confirmation, then the slot gate, then lunch |
| 6 | **Change participants** | depends | see below | confirmation |

**Cancel first, on purpose.** It is the only one that is pure undo, so it
builds the compensation runner — the part that is genuinely missing — with
nothing else mixed in. Everything after it is "compensate, then do a thing we
already know how to do".

**Participants is the awkward one** and should be last. Adding someone can
invalidate the slot (they may be busy) and the lunch (one more portion);
removing someone changes only the headcount. It is really a conditional
reschedule, which is why it wants #5 to exist first.

## 6. The vocabulary to add

Six message types, following the existing naming. `message_types` in the team
card is a list precisely so this is an addition rather than an edit.

```
ChangePlanRequest(plan_id, change)   @Human       -> @Coordinator
ChangeApprovalRequest(plan_id, ...)  @Coordinator -> @Human
ChangeApprovalDecision(plan_id, ...) @Human       -> @Coordinator
CancelAssignment(plan_id, step, reference)
                                     @Coordinator -> the specialist that owns it
Cancelled(plan_id, step, reference)  specialist   -> @Coordinator
PlanChanged(plan_id, plan)           @Coordinator -> @Human
```

`change` is a tagged union of the five kinds, so one request type covers all of
them and the coordinator dispatches on the kind. The alternative — five request
types — spreads one decision across five handlers.

`CancelAssignment` carries a `CompensationStep`, which means the coordinator
can turn `compensations()` straight into a list of assignments and the routing
is a lookup from step to owning specialist. **The one-service rule (D1) is
untouched**: each specialist cancels only on the service it already reaches.
`@Scheduler` cancels meetings, `@FacilityManager` cancels room bookings,
`@Catering` cancels orders.

## 7. The flow, for cancel

```
@Human        ChangePlanRequest(plan_id, Cancel)      -> @Coordinator
@Coordinator  LoadPlan(plan_id)                       -> @PlanRepository
@PlanRepository  PlanSnapshot(plan)                   -> @Coordinator
@Coordinator  ChangeApprovalRequest(compensations)    -> @Human
@Human        ChangeApprovalDecision(approved=true)   -> @Coordinator
@Coordinator  CancelAssignment(CANCEL_ORDER, ...)     -> @Catering
@Catering     Cancelled(...)                          -> @Coordinator
@Coordinator  CancelAssignment(CANCEL_ROOM_BOOKING)   -> @FacilityManager
@FacilityManager  Cancelled(...)                      -> @Coordinator
@Coordinator  CancelAssignment(CANCEL_MEETING, ...)   -> @Scheduler
@Scheduler    Cancelled(...)                          -> @Coordinator
@Coordinator  SavePlan(plan, cancelled=True)          -> @PlanRepository
@Coordinator  PlanChanged(plan)                       -> @Human
```

**One at a time, in `compensations()` order**, not in parallel. The order is
reverse booking order and it is the order the services expect; running them
concurrently would also make a partial failure much harder to describe.

**A compensation that fails must not be silent.** A cancel can legitimately
fail — a booking already cancelled by someone else. The plan should record what
was undone and what was not, which is what `PlanFailed.outstanding` was shaped
for. This needs a decision when we build it, and §9 carries it as an open
question rather than a guess.

## 8. What the browser needs

Small, because the Plans screen already lists plans and opens one.

- A **Change** button on the plan dialog, offering the kinds valid for that
  plan's status — a cancelled plan offers nothing, a plan without lunch does
  not offer "change lunch".
- A **confirmation step** listing what will be cancelled, in words rather than
  as ids: "the lunch order, the room booking at yuma, and the meeting".
- Reuse of the **existing gate components** for the gates a change re-opens.
  `GatePrompt` is already driven by the question that arrives, so a reschedule's
  slot gate should need no new component.
- The SPA must **restore the team before sending**, and stop it afterwards.
  That is two API calls the client does not make today.

A change produces a second burst of events on the same team, so the Trace
screen needs nothing: `/trace/<teamId>` already replays a stored run, and the
change is in the same log.

## 9. Open questions

1. **A compensation that fails.** Stop and report, or carry on and report? We
   favour carry-on-and-report, so one stale booking cannot strand the other two,
   with the failures on the plan. Not decided.
2. **Who restores the team** — the browser, with two extra calls, or the server,
   hiding it behind an endpoint that takes a plan id? The second is nicer for
   every future client and is a small module next to `PlansModule`.
3. **A plan whose team is gone.** Deleting a team is possible from the console.
   Then a change needs a *new* team, which is the case `team_ids` exists for —
   but it is extra code, and it may be honest to simply refuse at first.
4. **Concurrent changes.** Two browsers changing one plan. Today nothing stops
   it. Probably out of scope, but it should be refused rather than ignored.
5. **Does `with_lunch: false` mean "never" or "not yet"?** Change #2 on a plan
   that has no lunch is really "add lunch", which the vocabulary above does not
   distinguish.
