# Cancelling a meeting — design

Status: **proposed**. Nothing here is built yet.

This document replaces two earlier drafts, both of which designed a way to
*change* a plan: the first by mutating it inside the team that made it, the
second by making a revision that supersedes it. Both are dropped.

**There is no update.** If something about a meeting is wrong, you cancel it
and plan a new one. The system releases everything it booked, and what happens
next is the human's business.

This is a demo, and the thing it demonstrates is a saga that can undo itself.
A revision was a more interesting feature and a much larger one — inherit
tables, a plan-supersedes chain, a state-driven saga, a diffed compensation
list — all of it scaffolding around the one piece that was actually missing.
Cancel *is* that piece, alone.

---

## 1. What cancelling does

**All three bookings go.** The lunch order, the room, and the meeting itself.
There is nothing to choose and nothing to ask — cancel means cancel.

In reverse booking order, because that is the order the services expect:

| Held | Released by | Where |
|---|---|---|
| `order_id` | `cancel_order` | nomnom-service |
| `booking_id` | `cancel_room_booking` | location-service |
| `meeting_id` | `cancel_meeting` | meeting-service |

That list is already computed, correctly, by `MeetingPlan.compensations()`,
which returns all three for a finished plan. The only time it returns fewer is
a plan that never got that far: a plan cancelled before lunch was ordered has
no `order_id` to release. The three `cancel_*` MCP tools exist and take the ids
the plan is holding.

So the work is not *what* to cancel. It is wiring up the running of it.

`relocation_compensations()` goes. It was written for a change of location,
nothing calls it outside its own tests, and with no update feature it can
never be reached.

## 2. The vocabulary

```
CancelPlanRequest(plan_id)                     @Human       -> @Coordinator
CancelAssignment(plan_id, step, reference)     @Coordinator -> one specialist
Cancelled(plan_id, step, succeeded, reason)    specialist   -> @Coordinator
PlanCancelled(plan)                            @Coordinator -> @Human
```

Four messages. `CancelAssignment` carries a `CompensationStep`, which names the
tool and therefore names the service, so routing is a lookup from step to the
one agent that reaches it. **The one-service rule (D1) is untouched**:
`@Scheduler` cancels meetings, `@FacilityManager` cancels room bookings,
`@Catering` cancels orders, each on the service it already talks to.

`Cancelled` carries `succeeded` and `reason` for the same reason every other
specialist result does: a specialist that could not cancel something needs a
truthful way to say so. Inventing success here is worse than elsewhere — it
would leave a real booking behind a plan that claims to have released it.

## 3. No gate

The confirmation lives in the browser, not in the team.

The SPA already holds the plan, so it can say in words what is about to be
released — "the lunch order, the room at yuma and the meeting in three
agendas" — from the plan's own fields, before it sends anything. Routing that
through `@Human` would add a request/decision pair and a piece of coordinator
state to re-ask a question the client can already answer.

The slot gate and the lunch gate are different: they need an answer the client
does not have, and the answer changes what gets booked. A confirmation changes
nothing. It only decides whether the message is sent at all.

## 4. Running them

The coordinator drives the list **one at a time**, in `compensations()` order,
sending the next `CancelAssignment` when the previous `Cancelled` arrives.

Serial, not parallel, for two reasons: the order is the one the services
expect — release the dependent thing before the thing it depends on — and a
partial failure is describable. "Released the lunch, failed on the room, never
reached the meeting" is a sentence. Three concurrent failures are not.

`CoordinatorState` gains the remaining queue per plan, alongside `candidates`
and `awaiting_lunch`:

```python
cancelling: dict[str, list[Compensation]]
```

**A failed step does not stop the run.** One stale reference — a booking
somebody already released by hand — must not strand the other two. The failure
is reported at the end and the next step goes out.

## 5. What the plan ends up saying

The plan keeps its ids. It is a record of what was booked, and erasing them
would lose that. `cancelled: bool` already exists and is already what makes
`status` read `CANCELLED`, so **no new field is needed on the plan**.

A step that failed is reported in `PlanCancelled` and is in the trace, which
for a demo is where you would look anyway. Mirroring it onto the plan is a
second place to keep in step for no new behaviour.

## 6. The browser

- A **Cancel meeting** button on the plan dialog, for any plan that is not
  already cancelled.
- A **confirmation** listing what will be released, in words, not ids (§3).
- The plan stays in the Plans list afterwards, with a `CANCELLED` chip. This is
  a demo of a saga undoing itself; hiding the result would hide the point.
- Nothing else changes. There is no Revise button, no History section, no
  team-lifecycle call. To plan a different meeting, the human uses **Plan
  another**, which is what that button already does.

## 7. Order of work

1. `CancelPlanRequest` / `CancelAssignment` / `Cancelled` / `PlanCancelled` in
   `messages.py` and in the team card's `message_types`; a `CancelOut`
   structured output beside the other specialist results.
2. One `receiveMsg_CancelAssignment` per specialist — three small handlers,
   each calling the one `cancel_*` tool it owns.
3. The coordinator: the queue, the serial driver, `cancelled = True`,
   `PlanCancelled`. Delete `relocation_compensations()` and its tests.
4. The server endpoint and `client.ts`.
5. The button, the confirmation, the chip.

Steps 1–3 are testable without the stack, as the saga tests already are.

## 8. Open questions

1. **Cancelling a plan that is mid-flight**, before it has finished booking.
   The compensation list is correct at the moment it is read, but a booking in
   progress could land after it. Simplest answer for a demo: refuse to cancel a
   plan that is not at rest, and say why.
2. **`PlanFailed` already reports `outstanding`** compensations without running
   them. Once the runner exists, should a failure run them automatically, or
   keep reporting and let the human press Cancel? Reporting is the more honest
   demo — it shows the mess, then shows it being cleaned up.

---

## Appendix A: what the dropped designs measured

Both earlier drafts needed to know whether a finished team could be brought
back to life. The answers were measured against the running stack, and two of
them are facts about the framework that will matter again.

- **A stopped team can be restored.** `POST /teams/{id}/restore` returned 200
  for a team stopped the previous day.
- **Restoring re-runs nothing.** `TeamRestorer` replays the log through
  `Orchestrator.restore_message`, which appends to the orchestrator's history
  and notifies subscribers but **never routes a message to an agent**. A
  restored 142-event team was still at 142 events.
- **A restored team works.** A `LoadPlan` sent to a restored team's
  `@PlanRepository` was received, processed, and answered with a
  `PlanSnapshot`, appending events 143–148. MCP connections and all.
- **`@Coordinator` comes back empty.** Agent state snapshots are written from
  `StateChangedMessage`, which is only emitted by an agent whose state has an
  observer attached — and exactly one place in the framework attaches one:
  `BaseAgent.__init__` (`agent/agent.py:277`), the LLM agent. Our deterministic
  agents never do. Measured: a finished team's state directory holds three
  files, the three specialists, and nothing else.

**The last one is the one to remember.** Our deterministic agents are not
durable, by construction. Anything that must survive a restart belongs in the
plan store.

It also decides something for *this* design: cancelling an old plan happens in
a **new team**, which loads the plan from the repository. Not in the team that
made it. The coordinator there would have no memory of it anyway, and the plan
store is the thing that does.
