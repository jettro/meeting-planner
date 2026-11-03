# Design — the team is the meeting

> **Status:** built, 2026-10-28, and verified live.
>
> **Lessons:** §10.
>
> **Now:** [`docs/durability.md`](../durability.md) describes durability as it is.
>
> *A design records what was decided and why, at the time; it is not kept current.*

Companion to `design_cancel.md` and `design_gui.md`. Appendix A of `design_cancel.md` measured
that `@Coordinator` comes back empty when a team is restored, and concluded that *"our
deterministic agents are not durable, by construction"*. Most of the plan machinery was built on
that conclusion: the plan store, the `@PlanRepository` that owns it, the Plans screen that reads
it, cancellation in a *new* team, and G23/G25.

This document corrects the conclusion and follows it through. The construction was ours, not the
framework's, and it is one missing line. Once the coordinator is durable, a meeting does not need
a second home: **one team plans one meeting (G3), so the team is the meeting.** The coordinator's
state becomes the only record, the plan store goes, and the browser lists teams.

> **The one sentence to keep:** *one meeting, one owner, one record.*

---

## 1. What is actually wrong

The framework saves an agent's state when the state tells it something changed. Following the
path through the installed packages:

1. `Akgent.init_state(state)` stores the new state **with the observer of the state it
   replaces**: `self.state = state.observer(self.state._observer)`. Its docstring says it plainly:
   *"an agent whose state has none keeps none."*
2. With an observer attached, every `init_state` sends a `StateChangedMessage` to the
   orchestrator.
3. `PersistenceSubscriber` turns that message into an `AgentStateSnapshot`, keeping the latest
   one per agent. The snapshot keeps the state's **concrete type**.
4. On restore, `TeamRestorer` spawns the agents and then calls `init_state(snapshot.state)` on
   each agent that has a snapshot (phase 2d, `akgentic/team/restorer.py`).

`BaseAgent` attaches an observer in its own `on_start`, which is why the three specialists come
back. `Coordinator.on_start` does `self.init_state(CoordinatorState())`, which carries over the
default state's observer, and that is none. So none of its later state changes is ever saved.
Appendix A measured this code correctly, but it was measuring the code, not the framework.

The pattern that works is the one from the blog series (*"Start building agents with akgents: the
core"*):

```python
def on_start(self) -> None:
    self.state = CoordinatorState()
    self.state.observer(self)
```

Attach once, and `init_state` preserves it from then on. This is **snapshot restore, not event
replay**: the framework does not run old messages through business handlers. A restored
coordinator does not ask the human again and books nothing twice. It wakes up knowing what it was
waiting for.

---

## 2. Why the plan store goes too

With a durable coordinator, every plan has two copies: the coordinator's working copy, which is
in its state and now saved, and the record in the store. Most of the hard parts of the last three
designs exist only to keep those two in step:

- §7.3's acknowledgement dance, including the bug where an earlier save's acknowledgement was
  mistaken for the final one;
- G25, which stops every live run before a cancellation, because `PlanStore.save` is a blind
  replace;
- cancellation in a second team that has to `LoadPlan` first (`design_cancel.md` §4);
- the stale run that a durable coordinator would make dangerous: a revived run holding a plan
  that was cancelled elsewhere.

All of them go when there is one copy. The plan store was introduced for D3: *nothing in our
services records that meeting 12, room booking 8 and order abc-123 belong together.* That is still
true, and the coordinator's state now records it, durably, in the team that made the booking. The
list of plans was a list of teams all along, one row per meeting.

---

## 3. Spike: does the state survive the event store? — verified

The YAML event store has bitten this project before (`design_gui.md` §8.2: it could not write a
`time`). `CoordinatorState` holds a `MeetingPlan` with `time` fields and a `computed_field` status
(G14), `ProposedSlot`s and `Compensation` enums.

A spike (outside the repository) saved such a state as an `AgentStateSnapshot` through the real
`YamlEventStore`, with the server's `install_yaml_representers()`, and loaded it back. The state
included a plan at `SCHEDULED`, a `09:30` slot (the leading-zero case §8.2 warns about), a pending
lunch and a cancellation queue.

```
type: CoordinatorState
equal: True
plan status: PlanStatus.SCHEDULED
slot types: ['time', 'time'] 09:30:00
```

The concrete types come back, the state compares equal, and the derived status is read past on
the way in and derived again.

**Not yet verified:** a real team stopped and restored with the coordinator parked at a gate. That
is §8 step 3, and it is the test that turns this document from a claim into a fact.

---

## 4. Durability before notification, without a repository — verified by reading

§7.3's rule stays: *if the human was told, it is stored.* What changes is who does the storing. It
was `@PlanRepository`, acknowledging with a `PlanSnapshot`; now it is the framework, and nothing
acknowledges. Reading `akgentic/core` shows the rule still holds, as long as the order is right:

1. `init_state` tells the orchestrator `StateChangedMessage`.
2. `send` tells the orchestrator `SentMessage` and *then* tells the recipient.
3. Both are `tell`s from the coordinator's own thread to the orchestrator's one mailbox, so they
   arrive in that order.
4. The orchestrator handles each by calling its subscribers synchronously
   (`receiveMsg_StateChangedMessage` → `_notify_subscribers_message`). The persistence subscriber
   writes the snapshot before the orchestrator moves on to the `SentMessage`.

So anyone who learns of a `PlanCompleted` from the event stream, which is the browser and the
console, learns it after the snapshot is on disk. **R8 makes the order a rule: the coordinator
changes its state before it sends the message that reports the change.** The one observer who
can be faster is `@Human`'s actor, which receives the message directly. In the server it answers
nothing about durability. In the CLI there is no event store at all.

---

## 5. The design

### 5.1 The coordinator owns one meeting

**R1** — `@Coordinator` attaches its state observer in `on_start` (§1).

**R2** — **The coordinator's state is the only record of the meeting**, and it holds exactly one:

```python
class CoordinatorState(BaseState):
    plan: MeetingPlan | None = None          # the meeting; None until a request arrives
    candidates: list[ProposedSlot] = []
    awaiting_lunch: bool = False
    cancelling: list[Compensation] = []      # the queue still to run, head first
    cancel_failures: list[str] = []
```

The dicts keyed by plan id go, and so do `awaiting_durability`, `loading_to_cancel` and
`awaiting_cancel_durability`. A second `PlanMeetingRequest` to a team that already holds a plan
is refused with a `PlanFailed` saying so. One team, one meeting has been the rule since G3; now
the state enforces it.

`MeetingPlan` stays, as the *shape* of that record: the ids, the derived status, the
`compensations()` that drive a cancellation. What goes is the plan as a separate *thing* with its
own store and screen. `plan_id` stays on every message as a correlation id, because the
specialists echo it and changing them is out of scope.

### 5.2 What is removed

**R3 — `@PlanRepository`, the plan store and `/plans` are removed; D3 is withdrawn.**

| Removed | Where |
|---|---|
| `PlanRepository`, `PlanRepositoryState`, its catalog entry, its place in `team.yaml` | `agents/` |
| `PlanStore`, `InMemoryPlanStore`, `JsonPlanStore`, `test_store.py` | `agents/src/meeting_agents/store.py` |
| `SavePlan`, `LoadPlan`, `PlanSnapshot` | `messages.py`, `message_types` |
| `MeetingPlan.team_ids` (G12) | `plan.py`: a meeting has one team now |
| `PlansModule`, `GET /plans`, `test_plans.py` | `server/`, which becomes `akgentic-infra` plus `PlatformModule` |
| `PLAN_STORE_PATH`, the plans volume, the `reset` step for `plans.json` | `.env.example`, compose, `Makefile`, Dockerfiles, settings |
| The Plans screen as it is | `gui/`, replaced by §6 |

The specialists are not touched. They mention `@PlanRepository` in two comments
(`specialists.py`), and those comments are updated.

### 5.3 Cancelling goes to the meeting's own team

**R4 — a `CancelPlanRequest` is sent to the team that made the meeting.** If that team has
stopped, the server revives it on delivery, which every delivery route does (verified for G3).
The restored coordinator already holds the plan, so it starts releasing at once, with no
`LoadPlan`. The release saga itself is unchanged: serial, reverse order, failure-tolerant,
idempotent (`design_cancel.md` §4). The booking and its undoing are now one trace in one run.

`design_cancel.md` once considered exactly this (*"mutating it inside the team that made it"*) and
dropped it for the reason Appendix A gave. That reason is gone.

**R5 — a booking that arrives for a cancelled meeting is released on arrival.** This is the one
case where a team can be busy when the cancel comes: the coordinator has sent
`BookMeetingAssignment` and is waiting for `MeetingBooked`. The actor handles one message at a
time, so the cancel runs first, against a plan that has no `meeting_id` yet. When the late
`MeetingBooked` arrives, the coordinator sees `plan.cancelled`. It does **not** go on to book
facilities: it records the id and sends the matching `CancelAssignment`, reporting it in
`PlanCancelled` like any other release. The same applies to `FacilitiesBooked`. This replaces
G25: there is no second team to stop, because there is no second team.

### 5.4 Resume by what the meeting is waiting for

**R6 — Resume is offered when the coordinator's state says it is waiting for the human.** That
means `candidates` is set and the plan is `AWAITING_APPROVAL`, or `awaiting_lunch` is true. It is
offered whether or not the team is alive: attaching replays the history, the open gate is read
from the trace (G24), and answering revives the team. This supersedes G23 (*"by liveness, never
by its status"*), whose premise was the non-durable coordinator.

A meeting that is waiting for a *specialist* (`APPROVED` with lunch settled, `SCHEDULED`,
`ROOM_BOOKED`) on a **stopped** team cannot be resumed. Restore replays history to the
orchestrator, not to agents, so an in-flight reply that was lost stays lost. Only a crash produces
this state: the framework's idle-stop waits until the in-flight count has been zero for an hour,
and R4 means nothing stops a team deliberately any more. Such a meeting is offered Cancel, and R5
covers the case where the reply turns up after all.

---

## 6. The browser: a list of teams

**R7 — the Plans screen becomes a Meetings screen that lists teams.** Everything it needs is
already served by the framework:

| Need | Source |
|---|---|
| Which runs exist, and which team kind each one is | `GET /teams`: `team_id`, `status`, `created_at`, **`catalog_namespace`**, **`metadata`** |
| What was asked for (title, day, location, headcount) | the team's `metadata` (G18, unchanged) |
| What came of it (status, time, room, lunch, the three ids, what it waits for) | `GET /teams/{id}/agent-states`, the `@Coordinator` snapshot |

The table shows one row per team in our namespaces. Teams whose coordinator never received a
request (no plan in state) are hidden. Rows are fetched with `useQueries`, one `agent-states`
call per team. That is fine for a demo with tens of runs; a server-side join is the remedy if it
ever is not, and it is not proposed now.

The row's dialog keeps what the plan dialog had: the three references, *Cancel meeting* with the
same in-words confirmation (G20), and *Resume* by R6. *Open trace* now means the team's own
trace, which includes its cancellation.

The `useLiveRuns` liveness lookup, the stop-first step in `useCancelPlan` (G25) and the
plan-to-runs mapping all go. `startPlan` and `cancelPlan` in `client.ts` both become "send a typed
message to this team's `@Coordinator`". That is what they always were; only the choice of team
changes.

---

## 7. What it costs, honestly

- **Deleting a team forgets its meeting.** The bookings stay in the three services, with nothing
  left that links them. Our browser has no delete, but the framework serves `DELETE /teams/{id}`
  and the upstream console on :8400 may expose it (to check). Either way, it is worth a line in
  `console/README.md`: *cancel before you delete.*
- **Meetings planned from the CLI are not listed.** `cli.py` builds its team with no event store,
  so its runs leave no record the server can see. They are booked, and the services show them,
  but the Meetings screen does not. Today they are listed only when the CLI and the server both
  run on the host and share `data/plans.json` (the containerised server keeps its own), so this
  is a small loss. The remedy, later, is for the CLI to start its team through the server
  rather than in-process.
- **Existing data is not migrated.** Old plans in `plans.json` and the old cancel-only teams are
  dropped by `make reset`. It is a demo.
- **The record lives in framework persistence.** It is a format we do not own, read through a
  route we do not own. That is a real dependency, and also the point: the framework already
  persists, restores and serves this, and the plan store was us doing it a second time.

---

## 8. Decisions

| # | Decision | Rationale |
|---|---|---|
| R1 | **`@Coordinator` attaches its state observer in `on_start`** | `init_state` preserves an observer and never creates one. This is the pattern from the akgents-core post |
| R2 | **The coordinator's state is the only record, and it holds one meeting** | One team, one meeting (G3). A second copy of the record is what made cancellation and durability hard |
| R3 | **`@PlanRepository`, the plan store and `/plans` are removed; D3 withdrawn** | The ids are still correlated, now in the state of the team that booked them |
| R4 | **Cancel is sent to the meeting's own team, revived if stopped** | Its coordinator holds the plan. No `LoadPlan`, no second team, one trace |
| R5 | **A booking reply for a cancelled meeting is released on arrival** | The only race a single team can have. Replaces G25's stop-first guard |
| R6 | **Resume is offered by what the coordinator waits for, not by liveness** | A stopped team is revived on delivery and now remembers. Supersedes G23 |
| R7 | **The browser lists teams: `GET /teams` plus the coordinator's snapshot** | The framework already serves both. The server loses its plans module |
| R8 | **State first, then send** | It keeps §7.3's honesty without an acknowledgement, because the orchestrator handles one agent's telemetry in order |
| R9 | **Out of scope: in-flight replies after a crash, `@FacilityManager._pending`, listing CLI runs** | Only a crash reaches the first two. The third needs the CLI to go through the server |

**Superseded elsewhere**, to be marked in place: D3 and §5.1 (b), and the mechanism of §7.3 (its
rule stays), in `design_akgents.md`. G12, G22's "with its ids" (still true, now in state), G23 and
G25 in `design_gui.md`. In `design_cancel.md`: §4's "a cancellation runs in a new team", §8.2,
and Appendix A's conclusion.

---

## 9. Implementation order

1. **The round trip as a test**: the spike from §3, beside `test_yaml_types.py`.
2. **R1 alone, store still in place.** Add an actor test: once a plan reaches the slot gate, the
   orchestrator holds a `@Coordinator` snapshot with the candidates. `test_saga.py` and
   `test_cancel.py` pass unchanged.
3. **The restore test, which is the one that decides.** Through `TeamManager` with a real event
   store: run to the slot gate with stub specialists, stop the team, resume it, send the
   `SlotApprovalDecision`, and reach `CONFIRMED`. This is Appendix A's experiment, rerun. **If it
   fails, stop here and revisit this document**, because everything after this step depends on it.
4. **R2, R3, R8:** the single-meeting state, the repository and store removed, state-before-send.
   `test_saga.py` and `test_cancel.py` are rewritten against the coordinator's state instead of the
   store. This is the step where the tests change, so it is reviewed on its own.
5. **R4 and R5:** cancel in the own team, release on late arrival. Tests: cancel a stopped team's
   meeting, then cancel while `MeetingBooked` is in flight.
6. **Server:** `PlansModule` and its settings removed.
7. **R6 and R7:** the Meetings screen. `make gui-build` is the check.
8. **A live run:** book through the browser, stop the team, cancel it from Meetings. Then park one
   at the slot gate, stop it, Resume, answer, and reach a booked meeting.
9. Docs: the supersessions in §8, README (the Plans row, the server's route table), and
   `console/README.md` (cancel before delete).

---

## 10. What building it taught us

**The restore test decided it, both ways.** Step 3 ran a team to the slot gate, stopped it,
resumed it and approved the slot: `CONFIRMED`. With the observer line reverted, the same three
tests fail — no coordinator snapshot is ever written. Appendix A's experiment, rerun, came out the
other way for exactly the reason §1 gives.

**A failed plan needs saying so, in the state.** The first draft of R6 read "waiting for the
human" from the candidates alone, and a refused slot left them there — so a rejected meeting would
have been offered Resume forever. `CoordinatorState.failure` records why a plan ended; a plan with
one is finished (still cancellable, never resumable). The Meetings screen shows it as `FAILED`.

**Reviving a team does not wake its sockets.** A message delivered to a stopped team revives it,
and the restored coordinator acts on it correctly — the live run booked a meeting from a team
stopped at its gate. But a browser socket opened on a *stopped* team waits idle until the team is
restored through `POST /teams/{id}/restore`, the only route that notifies waiting sockets. Revival
by delivery does not. So Resume and Cancel in the browser restore first (`api.restoreTeam`, 409
meaning "already running") and only then watch the stream. Found in the browser, not by any test:
the HTTP-level live run never watched a socket.

**R5 needed a test that waits for the right thing.** The first version of the late-facilities
test cancelled immediately after approval, and the cancel sometimes overtook `MeetingBooked` —
which is the *late meeting* case, handled correctly, but not the case under test. It now waits
until the coordinator's state records the meeting before cancelling. Reading the record instead
of guessing at timing is the same move the server tests make for snapshots.

**Verified live** (host-run server, the three services in Docker, the real specialists on
`gpt-6-luna`):
- a meeting parked at the slot gate, its team stopped, answered over `/human-input`: the team
  revived and booked meeting, room and a soup lunch;
- the same team stopped again and cancelled: revived, order → room → meeting released, nothing
  left in any of the three services;
- in the browser: a second meeting parked overnight-style showed *your turn* on the Meetings
  screen; Resume restored the stopped team and showed the open gate; both gates answered;
  booked; stopped again; cancelled from the Meetings screen — and its trace is the whole story,
  booking and release, in one run.

---

## 11. Changelog

- 2026-10-28: **Built.** R1–R8 as designed, plus `CoordinatorState.failure` and the browser's
  restore-before-watch (§10). `@PlanRepository`, `store.py`, `SavePlan`/`LoadPlan`/`PlanSnapshot`,
  `MeetingPlan.team_ids`, `PlansModule` and `PLAN_STORE_PATH` are gone; the Plans screen is now
  Meetings. New tests: the snapshot round trip and the restore tests in `server/tests`, R5 and
  one-team-one-meeting in `agents/tests`. 265 tests pass; verified live end to end.

- 2026-10-28: Initial design, first as "make the coordinator durable" and then, in the same
  discussion, widened to "the team is the meeting". Traced why `@Coordinator` is not restored:
  `init_state` preserves an observer but never creates one. A spike round-tripped a full
  `CoordinatorState` through the real `YamlEventStore`. Reading the orchestrator showed that
  state-before-send keeps §7.3's honesty without a repository (R8). With one durable record, the
  plan store, `@PlanRepository`, `/plans` and cancel-in-a-new-team are removed (R2–R4). The one
  remaining race, a booking reply arriving after a cancel, is released on arrival (R5). Resume is
  chosen by what the coordinator waits for (R6), and the browser lists teams from routes the
  framework already serves (R7).
