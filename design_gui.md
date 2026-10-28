# Design — the team as a service, and a browser to watch it

Companion to `design_akgents.md`. That document ends with a team that plans a meeting from a
terminal. This one moves runtime ownership into a **service** (`akgentic-infra`, community tier)
and puts a **React single-page app** in front of it.

> **The one sentence to keep:** *the server owns execution; the client observes it and sends
> requests.* Everything below follows from it.

**Status:** proposal. Nothing is built yet. §8 lists the decisions still open.

---

## 1. Why now, and what it is for

The CLI proved the team works. It is a poor demo: one meeting per process, output scrolls past,
and the interesting part — what the agents actually said to each other — is invisible unless you
pass `--verbose` and read a wall of logs.

The goal of this iteration is **not** "the same thing with buttons". It is to make the system
**observable**:

1. **Is the platform healthy?** Are the three services up, and can the agents reach their MCP
   servers?
2. **What is happening right now?** A live trace of every message, as it is sent.
3. **What is happening at the framework level?** Model calls, token usage, state changes,
   tool invocations — the layer the CLI hides entirely.

Planning a meeting is the thing that generates all of the above. It is the vehicle, not the point.

---

## 2. We are cashing in §4.2

`design_akgents.md` §4.2 listed eight rules whose only purpose was to make *this* iteration cheap.
Here is the bill:

| §4.2 rule | What it buys us now |
|---|---|
| The CLI runner is a thin client | The SPA replaces `cli.py` and nothing else. No saga logic to move. |
| `@Coordinator` never blocks on the human | Handlers already return immediately and correlate on `plan_id`. No deadlock to fix. |
| The human bridge is a swappable `agent_class` in YAML | `human.yaml` gets a new dotted path. One line. |
| Questions carry an explicit `recipient` | `_ask_about_lunch` and the slot gate already set it. The server can route answers back. |
| `message_types` is a list | Free-text intake stays additive; not needed for this iteration. |
| The team lives in catalog YAML | The infra server creates teams by `catalog_namespace`. Nothing to port. |
| Plan store behind a protocol, named by config | The server can keep its own store path without touching the agents. |
| No secrets or live objects in config/state | Config and state are serialised into telemetry **and rendered in the browser**. This rule stops being a principle and becomes a visible property. |

The one rule we did **not** anticipate is in §4.

---

## 3. What `akgentic-infra` gives us, verified

`akgentic-framework[infra]` resolves to **`akgentic-infra` 1.16.0** (the blog chapter used 1.10.0).
Confirmed by installing it in a throwaway project and reading the package, not by trusting the post.

**Community tier = one process.** Server and actors together; YAML event store, local files,
in-memory stream. No Redis, no Mongo, no Kubernetes. That is what we want, and what the user asked
for.

**Composition** — the explicit path, because we add our own routes:

```python
settings = CommunitySettings(
    catalog_path=..., event_store_path=..., workspaces_root=...,
    catalog_model_type_prefixes=["meeting_agents."],   # see the trap below
    cors_origins=[...],                                # see §6
)
services = wire_community(settings)
app = create_infra_app(services, settings, modules=[*server_modules(services, settings), ...])
```

**Routes we get for free** (verified against the installed package):

| Route | What it does for us |
|---|---|
| `POST /teams` | Create a team from `catalog_namespace`, with typed metadata |
| `GET /teams`, `GET /teams/{id}` | List and inspect running teams |
| `POST /teams/{id}/message` | Send a typed message (`__model__` envelope) |
| **`POST /teams/{id}/message/from/{sender}/to/{recipient}`** | Exactly our `send_from_to("@Human", "@Coordinator", …)` — a direct match |
| `POST /teams/{id}/human-input` | The correlated question/answer path |
| `GET /teams/{id}/events` | Durable history |
| `GET /teams/{id}/agent-states` | Agent snapshots |
| `POST /teams/{id}/stop`, `/restore` | Lifecycle |
| `WS /ws/{team_id}` | The live event stream, **with replay** |
| `GET /readiness` | Is the *server* ready — **not** a check of our three services (§5) |
| `GET /admin/catalog/...` | Resolve catalog entries — a ready-made "what is this team made of" view |

**There is no `ServerUserProxyAgent` in the package.** The blog defines one in application code, and
so must we (§4).

**Trap, recorded before it bites:** `catalog_model_type_prefixes` must include `"meeting_agents."`,
or the server refuses to load a catalog that names our types. The application factory **reapplies
this from its settings**, so setting it anywhere else gets overwritten at startup.

---

## 4. The hard part: our questions are typed, the human-input path is text

This is the one place where our design and the blog's diverge, and it deserves to be decided rather
than discovered.

The framework's human path is **free text plus a correlation id**:

```
POST /teams/{id}/human-input   { "content": "yes", "message_id": <inner question id> }
→ TeamService finds the original question
→ proxy.process_human_input(content, question)
```

Our coordinator does not accept text. It accepts `SlotApprovalDecision` and
`LunchApprovalDecision` — typed, validated, with a validator that rejects a refusal carrying a
wish. That strictness is deliberate and has already caught real mistakes.

There are two honest ways to bridge this, and they are genuinely different:

### Option A — a `ServerUserProxy` that parses (the blog's shape)

`process_human_input(content, message)` looks at the *question* it is answering and builds the
typed decision: a `SlotApprovalRequest` turns `"2"` into `SlotApprovalDecision(slot=candidates[1])`;
a `LunchApprovalRequest` turns `"something vegetarian"` into a `LunchApprovalDecision`.

*This is exactly the parsing `cli.py` does today*, moved from the client to the server — which is
the §4.2 rule "the CLI runner is a thin client" paying off literally.

- ✅ Uses the framework's pending-question bookkeeping: a question is persisted, answerable later,
  and visible to a client that connects afterwards.
- ✅ The browser stays dumb: render a question, POST a string.
- ✅ A future Telegram adapter (the package ships one) answers the same way for free.
- ❌ One more place where a string is interpreted. It is the server's job now, but it is still
  string-handling.

### Option B — the browser POSTs the typed decision

`POST /teams/{id}/message/from/@Human/to/@Coordinator` with a `LunchApprovalDecision` envelope.
Correlation rides on `plan_id`, as it already does.

- ✅ No parsing anywhere. Pydantic validates at the edge; a wrong field is a 422.
- ✅ Fewer moving parts; `ChannelHuman` barely changes.
- ❌ Bypasses the framework's question/answer correlation, so "this team is waiting for an answer"
  becomes something we derive from the event stream ourselves.
- ❌ The browser now owns the shape of a domain message. A Telegram client would have to repeat it.

**Decided: A.** The reason is not elegance — it is that A makes "the team is waiting for a person"
a **first-class server-side fact** rather than something each client reconstructs. That is precisely
what an observability-focused iteration needs, and it is also the only option in which a second
client (or a reload) can see a pending question.

### 4.1 Where structured data actually comes from

Choosing A raises a fair worry: *does the coordinator now have to extract structured data out of a
conversation?* **No.** D1 holds — the coordinator still does not reason. Three separate things get
confused here, so they are pulled apart:

**Starting a plan is not a conversation.** `PlanMeetingRequest` is a typed message and stays one.
The browser builds it from a form and posts it with a `__model__` envelope. No text, no parsing, no
model. The team then runs until it reaches a gate — *you start it with a booking, and it talks to
you only when it needs to*. That is already how the saga behaves; nothing changes.

**Answering a gate is where text appears, and today there is nothing to extract.** The proxy is
handed the original question (verified: `handle.process_human_input(content, event.message)`), so it
knows what is being answered:

| Question | What the browser renders | What travels | What the proxy does |
|---|---|---|---|
| `SlotApprovalRequest` | A radio list of the candidate slots | `"2"` or `"n"` | Index into `question.candidates` → `SlotApprovalDecision` |
| `LunchApprovalRequest` | A text field | `"something vegetarian"` | `"no"` → declined; anything else → the wish, verbatim |

The slot answer is a **string a radio button produced**, not prose a person typed — the structure
lives in the *question*, which carries the candidates. The lunch answer is free text *by design*
(D9): the wish is a string field all the way down, and the understanding happens in `@Catering`,
the one agent holding the menu. So for both current gates the conversion is deterministic,
~20 lines, and **already written and tested in `cli.py`**.

**Consequence worth acting on:** that parsing moves into a shared `answers.py` used by *both*
`cli.py` and `ServerUserProxy`. Two clients, one tested interpretation — the literal payoff of
"the CLI runner is a thin client".

**When a gate one day needs real understanding** — *"move it to Tuesday afternoon and make it 90
minutes"* — that is **not** coordinator work either. It is §4.2 rule 5: a second message type plus a
small intake agent that converts text to a typed message. The coordinator keeps receiving types.
That door stays shut for now, and stays unlocked.

---

## 5. Three new things to build, in order of risk

### 5.1 `server/` — the infra application (new workspace package)

A fourth Python package alongside `services/*` and `agents/`. It depends on `meeting-agents`
(for the message types, the agents, and the catalog) and on `akgentic-framework[infra]`.

It contributes two application modules of its own — the distinction the blog is firm about
(*"`/plans` describes my application; `/teams` operates the agent runtime"*):

- **`PlansModule`** — `GET /plans`, `GET /plans/{id}`. Reads the existing `PlanStore`. The SPA needs
  a list of past plans that outlives any one team.
- **`PlatformModule`** — `GET /platform/health`. Fans out to the three services and reports each
  one's status. **This is the "check if the services are up" feature**, and it belongs on the
  server: the browser should not be making nine cross-origin calls to decide if the platform is up.

### 5.2 Health endpoints on the three services

There is no `/health` anywhere in this project today (we worked around it repeatedly while
debugging). Add a real one to each service: it reports the service, its database, and — for the MCP
side — nothing, because the MCP server is a separate process.

Worth doing properly: compose `healthcheck:` blocks can then use it, and `depends_on:
condition: service_healthy` becomes available, which would have prevented at least one confusing
startup race already.

### 5.3 `gui/` — the SPA

See §6 for the stack, and §8.3 for what changed once it existed.

---

## 6. Frontend: recommended stack

The brief: **React**, a **well-known component library**, **minimal custom JavaScript**.

| Concern | Recommendation | Why this one |
|---|---|---|
| Language | **TypeScript** | The whole point of this system is typed messages. An untyped client throws that away at the last hop. |
| Build | **Vite** | The default for React in 2026; dev proxy to the server removes CORS during development. |
| Components | **MUI (Material UI)** | The most widely known React library, batteries included. Its `DataGrid` is the event trace with almost no code — sorting, filtering, virtualised scrolling for a long trace, all configuration rather than JavaScript. Mantine is the close runner-up; shadcn/ui is rejected here because it is *more* custom code, not less. |
| Server state | **TanStack Query** | Polling health, fetching plans, cache invalidation — all declarative. |
| Live events | A small `useTeamStream` hook over the native `WebSocket` | ~40 lines. No library earns its weight here. |
| Routing | **React Router** | Three or four screens. |
| Forms | **React Hook Form** + a small Zod schema | The plan request is the only real form. |

**Deployment:** its own container, nginx serving the built assets — consistent with every other
component in this repo. The server's `cors_origins` setting (confirmed present) makes a separate
origin a configuration line rather than a problem. The alternative is mounting the build as static
files inside the Python server, as the blog does; that is simpler but makes the GUI a Python
deployment concern, which this repo has so far avoided.

### Screens

1. **Platform** — are the services up, which locations and people exist, what is the team made of
   (rendered from `GET /admin/catalog/...`, so the YAML is visible in the browser).
2. **Plan a meeting** — the form; then the two gates (slot, then lunch) as cards in the conversation.
3. **Trace** — the live event stream. Two levels: *conversation* (our typed messages — who asked
   whom what) and *framework* (model calls, tool invocations, state changes, usage), toggled. This
   is the "help me see what happens at the framework level" feature, and it is mostly free: the
   events are already on the socket.
4. **Plans** — history, from `GET /plans`.

### Two client gotchas, recorded now because they are cheap now and expensive later

- **Two different ids.** The outer stream message id is for de-duplication on reconnect; the
  **inner** question id is what correlates an answer. Confusing them produces a client that looks
  like it works and a workflow that never moves.
- **A reconnect replays from cursor zero.** The client must track seen ids, or the trace doubles.

---

## 7. What does *not* change

The three services keep their REST APIs, their MCP servers, their databases and their own UIs. The
agents keep their prompts, their one-MCP-server-each isolation, and the saga. `cli.py` **stays** —
it is a working, tested, non-interactive entry point, and a second client is the best proof that the
server really does own execution.

---

## 8. Decisions

| # | Decision | Note |
|---|---|---|
| G1 | **Human bridge: option A** — the human agent converts the answer against the question | See §4.1 and §8.1: it turned out to be `ChannelHuman` itself, not a second class |
| G2 | **The SPA gets its own nginx container** | Consistent with every other component here; `cors_origins` makes a second origin a config line |
| G3 | **One team per plan**, stopped on completion | One team = one meeting makes the trace readable. The server revives a stopped team to deliver a late answer (verified), so stopping early is safe |
| G4 | **First slice: server + health + trace + the full plan flow** | Both gates in the browser. The plans-history screen comes after |
| G5 | **MUI** | `DataGrid` is the trace with almost no custom JavaScript |
| G6 | **Answer parsing lives in a shared `answers.py`** | Used by both `cli.py` and `ChannelHuman.process_human_input`; neither client owns the interpretation |
| G7 | **The server teaches YAML how to write a `time`** rather than changing the domain | §8.2. The alternative was reshaping `ProposedSlot` to suit a storage backend |
| G8 | **One socket, held by `TeamProvider`** | A reconnect replays from cursor zero, so a second subscriber is a second full history. Pages read the stream; they never open one |
| G9 | **The team being watched lives in memory, not in the URL** | A reload loses the socket anyway, and a shareable link to a team waiting on *this* browser is a trap. `MemoryRouter` says so out loud |
| G10 | **No forms library** | React Hook Form + Zod was planned; five fields and two gates did not earn a dependency. Minimal custom JavaScript cuts both ways |
| G11 | **The API base is a build argument, not a runtime variable** | Vite inlines `import.meta.env`. The browser runs on the host, so the default is the host's port mapping, never a compose service name |
| G12 | **A plan records the team runs that touched it** | `MeetingPlan.team_ids`, stamped by `@PlanRepository` because it is the only writer. One team plans one meeting, so a plan changed later has several runs and its trace is all of them |
| G13 | **One Trace screen, two sources** | `/trace` is the live socket, `/trace/<team>` is a stored run fetched once. A second screen would have duplicated every column and both toggles to show the same thing |
| G14 | **`status` is a `computed_field`** | The browser should not re-derive what the domain already knows. Derived stays derived: it serialises out and is never read in — see §8.4 for what that cost |
| G15 | **Two clients, not one** | Our SPA is about the *meeting* and is the demo. Upstream's console is about the *team* — hierarchy, prompts, token spend — and is the instrument. Merging them would mean building the second badly |
| G16 | **The console is built from upstream's git URL, never vendored** | A checkout makes every upstream fix a merge, and a fork is the one thing we have no use for. The pin is a full commit SHA in compose; a short SHA is refused by the git build context |
| G17 | **The console is configured by a mounted file, not a build argument** | Upstream reads `config.json` over its baked-in defaults before rendering, so the backend changes without a rebuild. Our own SPA cannot do this — Vite inlines `import.meta.env` (G11) — and the difference is upstream's design, not an inconsistency |
| G18 | **A team's metadata is the request, not the outcome** | Everything in `MeetingTeamMetadata` is known when the team is created, so it is written once in the same call and never maintained. The outcome changes constantly and already has a home — `MeetingPlan`, reached from a plan rather than from a run |
| G19 | **`title`, `day` and `location_id` are indexed; `participants` is not** | Filtering is an anchored prefix match. On text that is a useful "starts with"; on a count it matches by digit, so a filter of `1` would return 1, 10 and 12 |

### 8.1 There is no `ServerUserProxy`, and that is the better answer

The design said the GUI swap would be a different `agent_class` named in `human.yaml`
(§4.2 rule 3). Building it found two things.

First, the framework **validates `agent_class` when the catalog loads** and rejects anything that
is not an importable dotted path, so `${HUMAN_AGENT_CLASS}` is not available — the catalog cannot
carry a per-deployment class name. That was tried and reverted.

Second, and more usefully: a separate class was not needed. `ChannelHuman` already extends
`HumanProxy`, which already has `process_human_input(content, message)` — the method the server's
human-input route calls. Overriding it to branch on the question type is ~15 lines, and the two
reply vocabularies now sit side by side in one file:

- a client that can build a typed message sends `send_from_to("@Human", "@Coordinator", decision)`
  and never touches the class — the terminal;
- a client that only has text posts to `/teams/{id}/human-input`, and the override reads it against
  the question with `answers.py` — the browser.

A second class would have duplicated all four `receiveMsg_*` handlers for the sake of one method,
and an unhandled message type is silently dropped, so the duplicate would fail quietly the next
time a message type is added. The swap point in `human.yaml` still exists and is still documented;
it simply is not needed for this.

### 8.2 The event store could not write a slot

The first end-to-end run over HTTP completed the saga perfectly and *never showed the approval
question in the event feed*. The persistence subscriber was logging
`cannot represent an object, datetime.time(10, 0)` and dropping every message carrying a slot.

The community tier persists with `yaml.safe_dump` deliberately — the safe dumper and safe loader
are the same dialect, so a value that cannot be read back fails the write instead of corrupting a
file. The safe dumper knows `date` and `datetime`; it does not know `time`. Our slots are `time`,
because the day lives on the plan.

The fix is `server/src/meeting_server/yaml_types.py`: one representer, installed at startup. The
domain is not reshaped to suit a backend.

The quoting in it is not cosmetic. YAML 1.1 reads a bare `10:00:00` as a **sexagesimal integer**,
36000. Pydantic then reads 36000 as seconds since midnight and produces 10:00 anyway — correct by
accident, and only for the times whose digits happen to parse that way (`09:30:00` has a leading
zero and stays a string). Quoting removes the coin toss. Both facts have tests.

This is the kind of failure the trace screen exists to catch, found by building the trace screen's
data source.

### 8.3 What the SPA taught us

Three things only showed up once a browser was holding the socket.

**MUI 9 is not MUI 5.** `<Typography paragraph>`, `InputLabelProps`, and system props on `Stack`
(`alignItems`) are all gone; `sx` and `slotProps` replace them. Worth knowing before copying any
example older than this year.

**`tsc --noEmit` is not the build.** It passed on all three screens while `npm run build`
(`tsc -b && vite build`) found five type errors, because the project references in `tsconfig` carry
settings the bare invocation does not. `make gui-build` is the only check that counts.

**The trace is the demo.** With the framework toggle off, the grid is twenty rows that read like a
story: `@Human → @Coordinator PlanMeetingRequest`, `@Coordinator → @Scheduler FindSlotsAssignment`,
`@Scheduler → @Coordinator SlotsFound`, both gates, then `MeetingBooked`. With it on, the same run
is ~60 rows including every actor's `StartMessage` and every `ReceivedMessage`. The toggle is the
whole §1 feature and it cost one `useState`.

---


- **Memory.** Per agent/user memory, possibly with shared memory between agents. Needs an
  evaluation of what akgents offers before any design.
- **Guardrails**, possibly via a decision model. No known framework support; the first task is
  finding the hook where a guardrail can intercept — the `BaseAgent.act()` path and the
  `ResultMessage` return are the obvious candidates to investigate.

---

## 10. Changelog

- 2026-10-28: Gave a team run something to say about itself. Every row in the console's team list
  read `meeting-planner`, so the only way to tell two runs apart was the minute they started.
  `MeetingTeamMetadata` (G18) is declared as the card's `metadata_type` and sent by the browser
  with `POST /teams`; the console renders it as chips, names the run in its rail, and builds a
  filter form from whichever fields are marked indexed (G19). No agent, message or handler
  changed — this is metadata *about* a run, not state *inside* one.

- 2026-10-28: Added the **Akgentic console** on 8400 (G15–G17), upstream's Angular client run
  unmodified. It cost one compose service and one `config.json`, because the server is
  `akgentic-infra` itself: the protocol the console speaks was already being served. It gives us
  for free the things our SPA deliberately does not have — the agent hierarchy as a graph, each
  member's system prompt and LLM context, and what a run spent. `console/README.md` records why
  there is no checkout.

- 2026-10-28: Added the **Plans** screen (read-only, G4's deferred half): every plan the team has
  made, with its derived status, its service references — the meeting/booking/order ids that
  nothing else in the system links together — and its **runs**. Clicking a run opens that team's
  stored trace in the Trace tab, which now serves two sources (G13): the live socket at `/trace`
  and a finished run at `/trace/<team>`. The link is new: `MeetingPlan.team_ids`, stamped by
  `@PlanRepository` (G12). Exposing `status` as a `computed_field` (G14) broke event persistence
  in exactly the way §8.2 did — see §8.4. Changing a plan is still not possible; the compensations
  are computed but nothing executes them.

- 2026-10-27: The trace shows message *contents*, not just types. Each row carries a one-line
  summary of the payload and opens a dialog with the whole thing — **Fields** (the payload with
  the plumbing removed) and **Raw** (the envelope as it came off the socket, because the moment
  something looks wrong the pretty version is the first thing to distrust). Three rules make it
  readable: an actor address collapses to its `name` (eleven fields of identity around one name,
  otherwise burying the payload it is attached to); ids, `team_id` and `display_type` are dropped;
  and `timestamp`/`sender`/`recipient` are dropped from the content because they are already the
  grid's own columns. The payoff is largest in the framework view, where a `StartMessage` now
  shows an agent's wiring and prompt and an `EventMessage` shows the commands it was given.

- 2026-10-27: Built the SPA (`gui/`). Vite + React 19 + TypeScript + MUI 9, `@mui/x-data-grid`,
  TanStack Query and React Router; `api/client.ts` (the only place that knows the server's shapes),
  `useTeamStream` (one socket, de-duplicated by event id), `TeamContext` (pending gate and outcome
  derived from the stream), and three screens — Platform, Plan a meeting, Trace. Decisions G8–G11
  (§8); §8.3 records what building it taught us. Containerised behind nginx on 8300 with an SPA
  history fallback, plus `make gui-install/gui-dev/gui-build/gui-lint`. Verified in a real browser
  end to end: form → slot gate as radio buttons → lunch gate as free text ("something warm, no
  meat") → `room-a at yuma`, 2 soups, booked — with the whole conversation visible in the trace.

- 2026-10-27: Built the first slice. `/health` on all three services (503 when the database is
  unreachable) and a compose healthcheck using python rather than curl; `answers.py` extracted
  (G6); the `server/` workspace package with `EnvResolvingCatalog`, `PlatformModule`
  (`/platform/health`, fanned out concurrently), `PlansModule` (read-only), its Dockerfile and
  compose service, and `make run-server`. Two findings changed the design: there is no
  `ServerUserProxy` (§8.1) and the event store could not write a `time` (§8.2, G7). Verified live:
  a plan created over HTTP, both gates answered as text through `/teams/{id}/human-input`, room and
  a vegetarian lunch booked, and the finished plan readable from `/plans`. 238 tests pass.
- 2026-10-27: Decisions G1–G6 agreed (§8). Resolved the typed-vs-text worry in §4.1: starting a
  plan stays a typed message, so the team is started with a booking and only talks to a human at a
  gate; and at the gates there is nothing to extract, because the slot answer is an index the
  question itself defines and the lunch wish is free text by design (D9). The coordinator remains
  deterministic. Verified `handle.process_human_input(content, event.message)` hands the proxy the
  original question, which is what makes a type-aware conversion possible, and that a stopped team
  is revived to receive a late answer.
- 2026-10-27: Initial GUI/infra design. Verified `akgentic-infra` 1.16.0 against the installed
  package rather than the blog: confirmed the community wiring, the full route surface (including
  `POST /teams/{id}/message/from/{sender}/to/{recipient}`, which matches our `send_from_to` exactly),
  `cors_origins` support, and that **no `ServerUserProxyAgent` ships with the package** — it is
  application code. Recorded the `catalog_model_type_prefixes` trap. Identified the one real design
  divergence: our questions are typed while the framework's human-input path is free text (§4),
  with a recommendation. Proposed React + TypeScript + Vite + MUI + TanStack Query.
