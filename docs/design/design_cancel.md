# Cancelling a meeting — design

> **Status:** built, 2026-10-29, and verified end to end: the meeting, the booking and the order
> were really gone from the three services, and the release has its own trace.
>
> **Superseded:** partly, by `design_durability.md` (2026-10-28). The coordinator is durable and
> its state is the meeting's only record, so a cancellation goes to the team that made the meeting
> rather than to a new one, there is no plan store, and nothing is stopped first. The release saga
> itself (§1, §2, §4's ordering and failure rules) is unchanged.
>
> **Still open:** §8.3: should a failed plan run its outstanding compensations itself, or only
> report them?
>
> *A design records what was decided and why, at the time; it is not kept current.*

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
CancelPlanRequest(plan_id)                     @Human           -> @Coordinator
CancelAssignment(plan_id, step, reference)     @Coordinator     -> @Scheduler or @FacilityManager
CancelAssignment(plan_id, step, reference)     @FacilityManager -> @Catering
Cancelled(plan_id, step, succeeded, reason)    specialist       -> its parent
PlanCancelled(plan, failures)                  @Coordinator     -> @Human
```

Four messages. `CancelAssignment` carries a `CompensationStep`, which names the
tool and therefore names the service, so routing is a lookup from step to the
one agent that reaches it. **The one-service rule (D1) is untouched**:
`@Scheduler` cancels meetings, `@FacilityManager` cancels room bookings,
`@Catering` cancels orders, each on the service it already talks to.

**A cancellation travels the same hierarchy a booking does** (D10). The first
sketch had the coordinator address all three specialists directly, which would
have broken **D2 — lunch is the facility manager's business** — and gone around
the team's own shape, since `@Catering` is a child of `@FacilityManager`. So
the coordinator sends both the order and the room release to
`@FacilityManager`: it releases the room itself, forwards the order to
`@Catering`, and passes the reply back up. The forwarder keeps no state — the
message carries the plan and the step. The coordinator still decides *which*
releases happen and in what order; only the delivery follows the hierarchy.

`Cancelled` carries `succeeded` and `reason` for the same reason every other
specialist result does: a specialist that could not cancel something needs a
truthful way to say so. Inventing success here is worse than elsewhere — it
would leave a real booking behind a plan that claims to have released it.

**A release never answers with `AssignmentFailed`.** Every other assignment may
fail the plan; this one may not. The coordinator is running a list and needs an
answer for every entry or the list stalls, so the shared `release()` helper
catches the exception and turns it into `Cancelled(succeeded=False)`. A release
that could not be done is a line in a report, not a failure of the plan.

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

**`PlanCancelled` waits for the write.** Found by a test that failed for the
right reason: the store still read `cancelled=False` when the report arrived,
because the `SavePlan` and the report were concurrent. The browser refetches
`/plans` the moment it sees that word, so it could be told "cancelled" and then
shown `CONFIRMED`. The report is now sent only once `@PlanRepository` has
acknowledged the write — the same gate completion already used. "Cancelled"
means cancelled *and* stored.

**Cancelling a cancelled plan is harmless.** It short-circuits and reports
immediately, with no steps and no failures. A repeat must not look like three
failures against ids that are already gone.

*(Superseded by `design_durability.md` R4: the cancel now goes to the meeting's own team.)*
**A cancellation runs in a new team** that loads the plan from the repository,
because `@Coordinator` is not durable — see Appendix A.

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
- An unfinished plan whose team is still alive offers **Resume** instead, with
  cancelling demoted to **Stop and cancel** beside it (§8). A finished plan
  never offers Resume, however alive its team looks — a team stays `running`
  for an hour after it has done everything it was asked to.
- There is no Revise button and no History section. To plan a different
  meeting, the human uses **Plan another**, which is what that button already
  does.

## 7. What was built

1. `CancelPlanRequest` / `CancelAssignment` / `Cancelled` / `PlanCancelled` in
   `messages.py` and in the team card's `message_types`; a `ReleasedBooking`
   structured output beside the other specialist results.
2. One `receiveMsg_CancelAssignment` per specialist over a shared `release()`,
   plus the `@FacilityManager` forwarder that D10 calls for.
3. The coordinator: the queue, the serial driver, `cancelled = True`, the
   durability gate, `PlanCancelled`. `relocation_compensations()` and its tests
   deleted.
4. `client.ts` — no server endpoint was needed. A cancellation is a typed
   message to `@Coordinator`, so the framework's own message route carries it,
   exactly as planning does.
5. The button, the confirmation, the chip.

Steps 1–3 are tested without the stack: `test_cancel.py` drives the saga
against stub specialists (order, failure tolerance, durability, idempotence,
unknown plan, nothing-booked), and three tests in `test_specialists.py` run the
**real** agents with only the model replaced, which is what proves the
`@FacilityManager` → `@Catering` hop rather than assuming it.

The stored trace of a real cancellation, which is the shape above:

```
@Human            -> @Coordinator      CancelPlanRequest
@Coordinator      -> @PlanRepository   LoadPlan
@PlanRepository   -> @Coordinator      PlanSnapshot
@Coordinator      -> @FacilityManager  CancelAssignment  cancel_order
@FacilityManager  -> @Catering         CancelAssignment  cancel_order
@Catering         -> @FacilityManager  Cancelled         cancel_order         ok
@FacilityManager  -> @Coordinator      Cancelled         cancel_order         ok
@Coordinator      -> @FacilityManager  CancelAssignment  cancel_room_booking
@FacilityManager  -> @Coordinator      Cancelled         cancel_room_booking  ok
@Coordinator      -> @Scheduler        CancelAssignment  cancel_meeting
@Scheduler        -> @Coordinator      Cancelled         cancel_meeting       ok
@Coordinator      -> @PlanRepository   SavePlan
@PlanRepository   -> @Coordinator      PlanSnapshot
@Coordinator      -> @Human            PlanCancelled
```

Afterwards the meeting, the booking and the order were gone from the three
services, the plan read `CANCELLED` with its ids intact, and it listed **two**
runs — the one that booked it and the one that released it.

## 8. Mid-flight plans, and resuming them

Question 1 below used to be open. It is settled, and the answer came from the
framework rather than from us: **a team idle-stops an hour after its last
message** (`ORCHESTRATOR_TIMEOUT_DELAY`, default 3600, unset here). So an
unfinished plan is already in one of two states, and they want opposite things.

**Its team is still alive.** It is parked at a gate, waiting for an answer it
will still accept. Nothing is wrong, and nothing needs releasing — somebody
closed a tab. This one is **resumed**.

**Its team is stopped.** The coordinator kept its state in memory and is not
durable (Appendix A), so there is no way to finish it, ever. Whatever it
booked before it stopped is stranded. This one is **cancelled**.

That is the whole rule, and neither branch needs to ask whether a plan is "at
rest" — team liveness answers it. A finished plan is unaffected: it is
cancelled, as §1 says.

### 8.1 Resuming costs almost nothing

Everything the plan screen shows is derived from the event stream, and the
server replays a team's whole history on connect. So attaching to a live run
needs only its id: the questions, the answers already given and the outcome
all arrive again and the screen rebuilds itself.

The one change needed was in deciding which gate is open. The browser used to
remember what it had answered, which a resumed run does not know. A decision
carries the question's `id` as its `parent_id`, so an answered question can be
recognised **from the trace** — and then a run resumed in a different tab, or
after a reload, shows the gate that is genuinely still open rather than
re-asking one that was settled.

### 8.2 Cancelling stops the live team first, and that is not politeness

*(Superseded by `design_durability.md` R5: with one team owning the meeting there is no second
writer to stop; a booking that lands after a cancel is released on arrival.)*

`PlanStore.save` is a blind replace — last write wins, no version check — and
a cancellation runs in a *second* team while the first may still hold the plan
in memory. Release the room, and a team that is still going books the lunch
and saves its own copy over the top: the plan reads `CONFIRMED` again, with a
meeting that no longer exists and an order nothing references.

So every run on the plan is stopped before the cancelling team is created.
`POST /teams/{id}/stop` is synchronous, so once it returns the old team cannot
write at all. It answers **409** when the team is already stopped, which is
both the common case and the outcome being asked for, so that is not an error
here — liveness is polled and is allowed to be out of date.

This guard lives in the browser, which is where cancellation is started from
(G21 — a cancellation is a typed message, not an endpoint of ours). That is
proportionate for a demo with one client; a system with several would want it
behind the write instead.

### 8.3 Still open

**`PlanFailed` already reports `outstanding`** compensations without running
them. Should a failure run them automatically, or keep reporting and let the
human press Cancel? Reporting is the more honest demo — it shows the mess,
then shows it being cleaned up.

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

*(Correction, `design_durability.md` §1: the conclusion below was a measurement of our code, not
of the framework. `init_state` keeps an observer but never creates one, and our coordinator never
attached one. With the observer attached, the coordinator is restored like any other agent.)*

**The last one is the one to remember.** Our deterministic agents are not
durable, by construction. Anything that must survive a restart belongs in the
plan store.

It also decides something for *this* design: cancelling an old plan happens in
a **new team**, which loads the plan from the repository. Not in the team that
made it. The coordinator there would have no memory of it anyway, and the plan
store is the thing that does.

A fourth fact, found later and the one §8 turns on:

- **Teams idle-stop on their own.** `IdleStopSubscriber` counts in-flight work
  from the telemetry it already receives and stops the team when the count has
  been zero for `ORCHESTRATOR_TIMEOUT_DELAY` seconds —
  `DEFAULT_IDLE_STOP_DELAY_SECONDS = 3600`, and we do not set the variable.
  Measured: a team created at 14:31 stopped at 15:31 with nobody calling
  anything. So `status` on `GET /teams` means *alive*, not *busy*: a run that
  finished everything still reads `running` for the rest of the hour. It is
  only a useful signal next to a plan that has **not** finished, where alive
  does mean "still has work to do".
