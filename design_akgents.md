# Design — Akgents Agent Layer

Companion to [`design.md`](./design.md). That document covers the three Python microservices
(REST + UI + MCP). **This** document covers the next phase: an **Akgents multi-agent team** that
drives those services through their MCP endpoints on behalf of a human.

## Status

**Design agreed; implementation started.** §7 records the decisions, §7.2 the implementation
order — step 1 (`find_common_slots`) is done. Also agreed: v1's human entry point is a typed
`PlanMeetingRequest`, not free text.

---

## 1. What Akgents is (notes to remember)

[Akgents / akgentic](https://github.com/b12consulting/akgentic-framework) is a Python 3.12+
multi-agent framework built on the **actor model** ([Pykka](https://pykka.readthedocs.io/)).

The rules that actually shape a design:

- An **actor owns its state** and communicates only by messages. It never shares mutable data.
- **One actor processes one message at a time.** This makes an actor the natural single owner of
  mutable data — no locks needed inside a handler.
- An actor **never blocks its thread to wait**. It records "what I am waiting for" in its state,
  returns, and continues when the reply message arrives. This is the same mechanism used for
  waiting on an LLM *and* for waiting on a human.
- The **Orchestrator is itself an Akgent**, created explicitly. Agents must be created *through*
  the hierarchy (orchestrator → coordinator → members), because that propagates the orchestrator
  address, team id and parent. Creating an agent directly on the `ActorSystem` leaves it without
  telemetry, team lookup or state snapshots.

### 1.1 Anatomy of an Akgent

Four things make an agent:

1. **Config** — facts fixed for the agent's lifetime (identity). `BaseConfig` / `AgentConfig`.
2. **State** — everything that changes while handling messages. `BaseState` / `AgentState`.
3. **Messages** — Pydantic models derived from `Message`.
4. **Handlers** — methods named `receiveMsg_<MessageType>`.

> **Rule of thumb:** *config is identity, state is progress.* An invariant (e.g. a meeting id that
> the whole team works on) belongs in config, not repeated in every state snapshot.

Both config and state are **serialised** into the event/telemetry stream →
**never put secrets in either**. Live objects (repositories, clients, actor addresses) cannot go
in config/state either; they are set on the instance via a setter after creation.

`on_start()` runs in the actor's own thread: create concrete state, init live instance fields,
attach the state observer. **Do not look up team members in `on_start`** — children are not on the
roster yet. Use lazy lookup (`cached_property` + `get_team_member(name)`).

### 1.2 Package map

| Package | Responsibility | Depends on |
|---|---|---|
| `akgentic-core` | Actors, typed messages, orchestrator, `AgentCard` | — |
| `akgentic-llm` | Multi-provider LLM, ReAct loop, capabilities, budgets | — |
| `akgentic-tool` | `ToolCard` abstractions, **MCP**, workspace, planning | core |
| `akgentic-team` | Team lifecycle, `TeamCard`, event sourcing, persistence | core |
| `akgentic-agent` | `BaseAgent` = actor + LLM + tools; typed message routing | core, llm, tool |
| `akgentic-catalog` | **YAML/config registry** for teams, agents, tools, prompts | core, llm, tool, team |
| `akgentic-infra` | FastAPI + WebSocket server, "teams as a service" | all |
| `akgentic-frontend` | Angular web UI | — |

Install as `akgentic-framework[...]` (meta-distribution pinning a tested set) or à la carte.

### 1.3 Deterministic actor vs LLM agent — the most important choice

`akgentic-agent`'s `BaseAgent` composes actor + LLM + tools. But the framework's own guidance
(and the blog series) is explicit:

> **Only the work that requires judgement should reach a model.**

In the reference case-handling team, routing and fact-storage stay **deterministic** (`Akgent`
subclasses); only judgement calls (assess urgency, draft a plan) are `BaseAgent` (LLM) subclasses.

Related rules worth repeating, because they bear directly on *our* booking/cancelling domain:

- **"A message is an assignment; a tool is freedom."** A message is a decision the team already
  made. A tool is a capability the model may choose to use.
- **Giving a model a mutation tool is not an authorization policy.** In the blog's own experiment,
  a prompt asking to update *one* case updated *two*. The fix is structural, not prompt wording:
  narrow the tool surface, validate a proposed command, require human approval, or enforce the
  invariant in deterministic code.
- **"The model proposes; the human decides; the handler writes."**

---

## 2. MCP integration (the critical requirement)

**Hard requirement: each agent may only reach its own service's MCP server.**

### 2.1 How tools bind to an agent — verified

`AgentConfig.tools` is a plain **per-agent** list:

```python
tools: list[ToolCard] = Field(default_factory=list, ...)
```

Each `AgentCard` carries its own `config`, and `AgentCard.get_config_copy()` returns a **deep copy**
per spawned agent. There is **no team-level shared tool registry** that would leak one agent's
tools to another. Verified in the framework's own shipped catalog data, where `manager.yaml` and
`expert.yaml` deliberately carry *different* tool lists.

**Conclusion: strict per-agent MCP isolation is directly supported.** We give each specialist a
single `MCPTool` pointing at its own service, and nothing merges them.

> **Caveat to be honest about:** `BaseAgent` *auto-adds* `TeamTool` and `MailboxTool`. So an agent
> has its own MCP server **plus** the framework's own team/mailbox tooling (which is what lets it
> message colleagues). "Only its own MCP server" is true of *domain* capability, not of the
> framework's built-in collaboration surface.

### 2.2 `MCPTool` and its connection config — verified field lists

`akgentic.tool.mcp.MCPTool` subclasses `ToolCard` and has exactly one field: `connection`.
It contributes **only** via `get_toolsets()` (never `get_tools()`), because MCP tool schemas live
on the server and are discovered at runtime.

`MCPHTTPConnectionConfig`:

| Field | Type | Default | Notes |
|---|---|---|---|
| `url` | `str` | required | MCP endpoint URL |
| `transport` | `"streamable-http" \| "sse"` | `"streamable-http"` | **never inferred from the URL** |
| `bearer_token` | `str \| None` | `None` | sent as `Authorization` header |
| `timeout` | `float` | `10.0` | init timeout |
| `read_timeout` | `float` | `300.0` | transport read timeout |
| `tool_prefix` | `str \| None` | `None` | prefixes every tool name from this server |

`MCPStdioConnectionConfig` also exists (`stdio_command`, `stdio_args`, `stdio_env`, `stdio_cwd`,
`stdio_token_env_var`, …) for local subprocess servers — **not what we need**, ours are HTTP.

### 2.3 How well this matches what we already built — very well

| What we built (design.md §3) | What `MCPTool` expects | Verdict |
|---|---|---|
| Streamable HTTP transport | `transport="streamable-http"` (the default) | ✅ exact match |
| `Authorization: Bearer <key>` via `StaticTokenVerifier` | `bearer_token` field | ✅ exact match |
| Deliberately **narrow**, agent-shaped tool catalogs | *(see constraint below)* | ✅ fortunate |
| One MCP server per service, own port | one `MCPTool` card per agent | ✅ exact match |

**Constraint found:** `MCPTool` has **no tool allowlist/denylist**. An agent sees *every* tool the
server exposes. Grepped the source for `allow`/`deny`/`filter`/`include_tools`/`exclude` — zero
hits. This would have been a problem if our MCP servers mirrored the full REST API — but we
deliberately designed them as narrow, agent-facing surfaces (no "list all orders", no admin
views). **The phase-1 MCP design decision pays off exactly here.** It also means the MCP server
*is* the security boundary: whatever we expose there, the agent can call.

`tool_prefix` is still worth using (e.g. `meeting`, `facility`, `catering`) for unambiguous
telemetry and to avoid any future name collision across servers.

**Verified against the installed packages** (`akgentic-framework` 2.18.1 → `akgentic-tool` 1.12.0),
not just the source on GitHub:

- `MCPTool.model_fields` is exactly `['connection']`; `MCPHTTPConnectionConfig` carries exactly the
  fields and defaults in the table above.
- `AgentConfig.tools` is `list[ToolCard]` and two configs genuinely get **separate** lists —
  appending a tool to one leaves the other empty. Isolation is real, not assumed.
- `ToolFactory(tool_cards=[MCPTool(...)]).get_toolsets()` yields a
  `PrefixedToolset(MCPToolset)` which, against our running meeting-service container, discovered
  all six tools (`book_meeting`, `cancel_meeting`, `check_meeting_feasibility`,
  `find_common_slots`, `get_person_availability`, `list_people`) with `prefix="meeting"` applied.
- **`bearer_token` authenticates against our `StaticTokenVerifier`**: the dev key connected, a
  wrong key was rejected with `MCPError`. This was the riskiest assumption in the design and it
  holds.

`AgentCard` and `TeamCard` field lists also match §3.2 exactly.

### 2.4 Secrets

`MCPTool` itself has **no `${VAR}` interpolation**. The catalog has one
(`akgentic.catalog.env.resolve_env_vars`, pattern `${VAR}`, raises `OSError` if unset), but it is a
**runtime utility applied by the consumer**, not by the catalog on write — the catalog stores
`${VAR}` literally. Needs confirming at implementation time that the create-team path we use
actually calls it. Fallback is trivial: resolve env vars in our own bootstrap before building the
team.

This matters because config is serialised into telemetry — the API key must not be baked into a
committed YAML file.

---

## 3. Defining the team in YAML (the catalog)

`akgentic-catalog` is *"the validated configuration boundary in front of the runtime"* — not a new
runtime. `catalog.load_team(namespace)` returns the same `TeamCard` a Python constructor would.

### 3.1 The `Entry` envelope

Everything (team, agent, tool, prompt, model, meta) is one shape:

- **catalog envelope** — `id`, `kind`, `namespace`, `user_id`, `description`
- **model selector** — `model_type`, a dotted Pydantic class path
- **model data** — `payload`, validated against that class

`kind` is a closed set: `team | agent | tool | prompt | model | meta`.
`model_type` is an allowlisted import (`akgentic.*` always; our own classes need an explicit
`set_allowed_prefixes([...])` call once at process start).

**Unknown keys are hard errors** (a `skils` typo is refused). But **omitted** keys silently take
their defaults — e.g. forgetting `tools` quietly yields an agent with no tools. Treat every field
as a checklist item.

### 3.2 `TeamCard` / `AgentCard`

```python
class TeamCardMember(SerializableBaseModel):
    card: AgentCard
    headcount: int = 1
    members: list[TeamCardMember] = []      # subordinates — the hierarchy IS this nesting

class TeamCard(SerializableBaseModel):
    name: str | None
    description: str | None
    entry_point: TeamCardMember             # the team's external interface; headcount MUST be 1
    members: list[TeamCardMember] = []      # top-level members, excluding entry_point
    message_types: list[type] = []          # first is the default
    metadata_type: type[SerializableBaseModel] | None
    agent_profiles: list[AgentCard] = []    # hireable at runtime, NOT spawned at startup
    welcome_message: str | None
```

```python
class AgentCard(SerializableBaseModel):
    agent_class: str | type                 # dotted path, e.g. "akgentic.agent.BaseAgent"
    skills: list[str] = []                  # used for dynamic discovery / hiring
    description: str                        # required
    config: BaseConfig                      # name, role, prompt, model_cfg, tools live HERE
    can_be_hired: bool = False
    metadata: dict = {}
```

Notes: `role` is a **derived property** from `config.role` (not a field) and must be non-empty —
it is the orchestrator's registry key. `name` is `@`-prefixed by convention (`"@Manager"`).
Nesting in `members` is what determines **who creates whom** at spawn time.

### 3.3 References (`__ref__`)

A payload embeds `{"__ref__": "<entry-id>"}` wherever it wants another entry's content. The whole
vocabulary is three keys — `__ref__`, `__type__`, `__namespace__` — and **any other key next to
`__ref__` is a validation error** (a ref is a pure pointer; you cannot patch alongside it).

- same namespace: `{ __ref__: manager }`
- cross namespace: `{ __ref__: global.id_gpt_6_luna }` (split on first dot), gated on the target
  namespace being `shareable: true`
- a pure *type* tag (no ref): `{ __type__: akgentic.agent.messages.AgentMessage }`
- a specific polymorphic subclass: `{ __model__: "...CliUserProxyConfig", ... }`

Editing a shared entry changes every referrer on next resolve. Delete protection blocks removing a
referenced entry.

### 3.4 Shape of a team YAML (abridged from the framework's own seed data)

```yaml
namespace: agent-team
user_id: anonymous
name: Agent Team V1
description: ...
shareable: false
public: true
entries:
  team:
    kind: team
    model_type: akgentic.team.TeamCard
    payload:
      entry_point:
        card: { __ref__: human_proxy }
      members:
      - card: { __ref__: manager }
        members:
        - card: { __ref__: expert }
        - card: { __ref__: assistant }
      message_types:
      - __type__: akgentic.agent.messages.AgentMessage
  manager:
    kind: agent
    model_type: akgentic.core.AgentCard
    payload:
      description: Helpful manager coordinating team work
      agent_class: akgentic.agent.BaseAgent
      skills: [coordination, delegation]
      config:
        name: '@Manager'
        role: Manager
        prompt:
          template: { __ref__: id_team_template }
          params: { role: manager, instructions: Coordinate the team. }
        model_cfg: { __ref__: global.id_gpt_6_luna }
        tools:
        - __ref__: global.id_web_search
  id_team_template:
    kind: prompt
    model_type: akgentic.catalog.NativeValue
    payload:
      value: "You are a helpful {role}. \n{instructions}"
```

Note the real example makes **`entry_point` the human proxy**, with the manager as a member
beneath it — the human is the team's external interface.

A namespace bundle is one YAML document with a closed root key set
(`namespace, user_id, name, description, properties, shareable, public, entries`); `entries` is a
**mapping keyed by id**. Import is **atomic replace, not merge** — entries absent from the bundle
are deleted. `validate_namespace_yaml()` gives a dry-run report.

> ⚠️ Found a **documentation discrepancy**: `docs/cli-usage-guide.md` shows an older shape with a
> separate top-level `team:` key and `entries` as a *list*. The mapping form above matches the real
> shipped seed data, so we follow that — but verify against the installed version at implementation
> time.

### 3.5 From YAML to running actors

```
YAML  →  Catalog(repository=YamlEntryRepository(root)).load_team(ns)  →  TeamCard
      →  TeamManager(actor_system, event_store).create_team(card, ...)
      →  TeamFactory.build(...)                                       →  TeamRuntime
```

`TeamRuntime` exposes the live `orchestrator_addr`, `entry_addr`, `supervisor_addrs`, `addrs`.
`TeamManager` also gives us lifecycle: `create_team` / `stop_team` / `resume_team` / delete, with
`STOPPED` preserving the card, metadata, event stream and agent snapshots.

### 3.6 How agents address each other

**Not wired in code and not wired in YAML.** It is a **runtime lookup by name**:

- The LLM emits a `StructuredOutput` containing `Request(message, recipient)` objects.
- `resolve_recipient()` then: `@Name` → `get_team_member("@Name")` against the live roster;
  a bare role name → `hire_member(role)`, spawning a new agent from a `can_be_hired` profile.
- A `RecipientCheckCapability` validates recipients *during* the run and raises `ModelRetry` with a
  corrective prompt if the model names someone unreachable, so it can retry before the turn ends.

So YAML only decides **what `@name`s exist** and **which profiles are hireable**.

---

## 4. Team topology (agreed)

```
entry_point: @Human              akgentic.agent.HumanProxy          no MCP
└── @Coordinator                 deterministic Akgent               no MCP
    ├── @PlanRepository          deterministic Akgent               no MCP — owns the MeetingPlan store
    ├── @Scheduler               BaseAgent (LLM)   meeting  MCP :8101  prefix "meeting"
    └── @FacilityManager         BaseAgent (LLM)   location MCP :8102  prefix "facility"
        └── @Catering            BaseAgent (LLM)   nomnom   MCP :8103  prefix "catering"
```

`@Catering` is nested under `@FacilityManager` so that the facility manager owns the whole
"room + lunch" bundle — the coordinator asks once, and the human never learns where lunch comes
from. That nesting also means the facility manager is the actor that *creates* the catering agent,
and gives us a genuine agent-to-agent hop rather than a flat star.

`@PlanRepository` and `@Coordinator` are **deterministic** `Akgent` subclasses — they route and
store, they do not reason. Only the three service specialists call a model.

Tool assignment, which is the isolation guarantee:

| Agent | `config.tools` | Can reach |
|---|---|---|
| `@Human` | — | nothing |
| `@Coordinator` | — | nothing (delegates only) |
| `@PlanRepository` | — | nothing (owns local store via instance field, not config) |
| `@Scheduler` | `[MCPTool(url=…:8101/mcp, bearer=${MEETING_MCP_API_KEY}, tool_prefix="meeting")]` | meeting-service only |
| `@FacilityManager` | `[MCPTool(url=…:8102/mcp, bearer=${LOCATION_MCP_API_KEY}, tool_prefix="facility")]` | location-service only |
| `@Catering` | `[MCPTool(url=…:8103/mcp, bearer=${NOMNOM_MCP_API_KEY}, tool_prefix="catering")]` | nomnom-service only |

### 4.1 Runtime shape

A **fourth container** (`agent-team`) in `docker-compose.yml`, running a CLI runner. It reaches the
MCP servers by compose service name — `http://meeting-service:8101/mcp` etc. — not `localhost`.
Keys come from the same `*_MCP_API_KEY` env vars already wired in `.env.example`, injected into the
catalog YAML as `${MEETING_MCP_API_KEY}` and resolved at team-build time (never committed).

LLM provider: **OpenAI**, model **`gpt-6-luna`** (the small/fast tier, as used for members in the
framework's own sample), via `OPENAI_API_KEY` and overridable with `AGENT_MODEL`. The coordinator
is deterministic (D1) so it needs no model of its own; only the three specialists call one.

### 4.2 Keeping the GUI and free-text doors open

D7 (CLI first) and §7.1 (typed input first) are **sequencing decisions, not architectural ones**.
Neither may foreclose `akgentic-infra` + the Angular frontend, or free-format input, later. The
blog's infra chapter is blunt about where that goes wrong — *"the server owns execution; the
client observes it and sends requests"* — and it documents that the original blocking stdin proxy
had to be **thrown away** for the server. We avoid paying that cost twice. Binding rules:

| Rule | Why it protects the GUI / free text |
|---|---|
| **The CLI runner is a thin client.** It builds the team, sends one message, renders events, exits. No orchestration, no saga logic, no booking rules. | A GUI replaces the runner only. If logic leaks into the runner, it cannot be reused by a server. |
| **`@Coordinator` never blocks on the human.** It records `awaiting_approval` in its state and returns; the answer arrives later as a message. | This is exactly the CLI→HTTP difference. A blocking `input()` inside a handler would deadlock a web request. |
| **The human bridge is a swappable agent class**, named in YAML (`agent_class`), not hard-wired. | Swapping the CLI proxy for `ServerUserProxyAgent` becomes a one-line YAML change. |
| **Questions to the human carry an explicit `recipient`**, and answers correlate on the **inner** message id. | Documented infra gotcha: without it the server cannot route an answer back to the right proxy. |
| **`message_types` is a list; `PlanMeetingRequest` is simply the first.** | Free-text intake is added as a *second* message type plus an intake step — purely additive, no rewrite. |
| **Team lives in catalog YAML, not Python.** | The infra server creates teams by `catalog_namespace`. A Python-constructed team would have to be ported. |
| **Plan store sits behind a repository protocol**, its implementation named by **dotted path in config**, its location by env var. | Lets a server swap the file store for a shared/db one, and lets a resumed agent rebuild it in `on_start` (framework rule: no live objects in config). |
| **No secrets or live objects in config/state.** | Config and state are serialised into telemetry, which the GUI renders. |

---

## 5. The scenario, walked through

> *"The human requests a meeting between Jettro and Daniel. First the Scheduling agent finds a
> suitable moment when both are available. Next a room and lunch are requested… If a meeting is
> cancelled, the room and the lunch must be cancelled as well. But if a room is changed, the lunch
> must be rebooked."*

Happy path, with the agreed single approval gate on the time slot:

1. Human → `@Coordinator`: a typed `PlanMeetingRequest` (participants, day, duration, location).
2. `@Coordinator` → `@PlanRepository`: create plan → `plan_id`.
3. `@Coordinator` → `@Scheduler`: find a slot for these participants.
   `@Scheduler` calls `meeting_find_common_slots` (new — see G1) and proposes one slot.
4. **Approval gate.** `@Coordinator` → `@Human`: "Tuesday 10:00–11:00 — ok?" The coordinator
   records `awaiting_approval` in its state and *returns*; it does not block. On approval it
   continues. **Nothing has been written to any service yet.**
5. `@Coordinator` → `@Scheduler`: book it. `meeting_book_meeting` → `meeting_id` → stored in the
   plan.
6. `@Coordinator` → `@FacilityManager`: room + lunch for *N* people, this slot, this location.
7. `@FacilityManager`: `facility_get_room_availability` → `facility_book_room` → `booking_id`.
8. `@FacilityManager` → `@Catering`: lunch for *N*, this location, this date.
   `@Catering`: `catering_get_menu` / `catering_search_product` → `catering_place_order`
   → `order_id`. Replies upward.
9. `@Coordinator` → `@PlanRepository`: store `booking_id` + `order_id`.
10. `@Coordinator` → Human: confirmed, with all three references.

Note which steps are judgement and which are not. Steps 1, 2, 4, 9, 10 are deterministic routing
and storage. Only 3, 7 and 8 reach a model — and of those, only *choosing a slot among candidates*,
*choosing a room* and *choosing lunch items and quantities* are genuinely judgement.

### 5.1 This is a distributed saga — and that is the hard part

Three independent services, three independent writes, no shared transaction. The requirement
*"if a meeting is cancelled, the room and the lunch must be cancelled as well"* is a textbook
**compensation** requirement.

**(a) The saga is deterministic, not LLM judgement.** Per §1.3, an LLM holding `cancel_*` tools is
not an authorization policy. If the coordinator merely *asks* an LLM to "also cancel the room and
lunch", a bad turn silently leaves a room booked and lunch being delivered for a meeting that no
longer exists. The cancellation fan-out is therefore a **deterministic handler on
`@Coordinator`** that runs the compensations in a fixed order and reports partial failures
explicitly. The specialists still own the MCP calls (isolation is preserved) — but *which* calls
happen, and in what order, is decided in code, not in a prompt.

**(b) `@PlanRepository` remembers the links.** Nothing in our services records that
*meeting 12 ↔ room booking 8 ↔ order abc-123*; each only knows its own id. One actor owns that
store, every read/write goes through it as a message, so it needs no lock and every access is
observable — the blog's `CaseRepositoryAgent` pattern. Business data stays separate from the team
event history, which is the separation the framework recommends.

The **MeetingPlan** aggregate:

| Field | Source |
|---|---|
| `plan_id` | ours |
| `meeting_id` | meeting-service |
| `participants`, `day`, `start`, `end` | meeting-service |
| `location_id`, `room_code`, `booking_id` | location-service |
| `order_id`, `delivery_date` | nomnom-service |
| `status` | **derived, not stored** (blog: *status derived, not stored* — avoids drift) |

**Cancel meeting** → compensate in reverse order: `cancel_order` → `cancel_room_booking` →
`cancel_meeting`. Each is already roughly idempotent (nomnom returns `success:false` on double
cancel; the other two 404). Partial failure must surface to the human, not be swallowed.

**Change location** → rebook lunch. Agreed rule: a nomnom order is tied to a **location**
(e.g. `yuma`), not a room code, so swapping `room-a → room-b` *within* one location leaves the
lunch order valid and must **not** trigger a rebook. Only a change of *location* cancels and
re-places the order.

Both flows are **deferred to iteration 2** (see §7.1) — but the plan store is designed now so that
iteration 1 already records everything they will need.

---

## 6. Gaps in our current REST/MCP surface

Found while walking the scenario. None are blockers, but they shape the work.

- **G1 — no multi-person slot finder.** ✅ **Closed.** `POST /api/meetings/common-slots` +
  `find_common_slots` MCP tool now return every window where all participants are free, with
  `latest_start` so no arithmetic is needed. Previously an agent had to call
  `get_person_availability` per person and intersect the results itself — pure computation that
  §1.3 says to keep out of the model.
- **G2 — no "move/reschedule" operations.** There is no change-room or change-time endpoint;
  "changing a room" means cancel + rebook, leaving a window where nothing is booked. Accepted for
  this project; deferred.
- **G3 — no plan/correlation store.** → closed by `@PlanRepository` (D3).
- **G4 — nomnom `place_order` has no headcount concept.** It takes explicit
  `items: [{item_id, quantity}]`. So "lunch for 4" is the agent's judgement about quantities. That
  is genuinely a judgement call, so it stays with `@Catering`'s LLM — noted, not closed.
- **G5 — location/room capacity vs participant count.** `get_room_availability` takes
  `number_of_people` and picks the smallest suitable room; the coordinator must thread the
  participant count through. Easy, just needs wiring.

---

## 7. Decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | **Deterministic `Akgent` coordinator**, LLM `BaseAgent` specialists | Keeps routing and irreversible writes out of a model's hands (§1.3) |
| D2 | **`@Catering` nested under `@FacilityManager`** | The facility manager owns the room+lunch bundle; the human never sees where lunch comes from |
| D3 | **`@PlanRepository` actor** owns the MeetingPlan store | Single-owner actor needs no lock; keeps business data separate from team event history |
| D4 | **Approve the proposed time slot only** | One gate, before anything is written; room and lunch then proceed automatically |
| D5 | **Only a *location* change rebooks lunch** | A nomnom order is tied to a location, not a room code |
| D6 | **OpenAI**, default model `gpt-6-luna` | Small/fast tier is enough for the three specialists; the coordinator uses no model at all |
| D7 | **CLI runner in a 4th container**, MCP via compose service names | Consistent with the rest of the project; `akgentic-infra` deferred but **not** foreclosed — see §4.2 |
| D8 | **Add `find_common_slots` first**, then the happy path | Turns fallible LLM arithmetic into one deterministic call (G1) |
| D9 | **A second gate: lunch, described in free text** | A person wants a say in lunch, but not a menu — see §7.7 |

### 7.1 Still to settle, and what is deferred

**One open item — how the human's request reaches a deterministic coordinator.** D1 means the
coordinator does not reason, so it cannot parse *"book a meeting between Jettro and Daniel next
Tuesday with lunch"*. **Agreed:** iteration 1's CLI takes a **typed `PlanMeetingRequest`**
(participants, day, duration, location) — the blog's `HandleCaseRequest` pattern, and consistent
with *"a message is an assignment"*. Free-text intake becomes an optional later addition (either a
small intake LLM step or an LLM coordinator), without disturbing the saga design.

**Deferred to iteration 2:** the cancellation and location-change sagas (§5.1). The plan store is
designed for them now; the handlers come later.

**Deferred but explicitly planned** (not "maybe"): `akgentic-infra` as a service + the Angular
frontend, and free-format human input. §4.2 lists the rules that keep both reachable without a
rewrite. Any change that would break one of those rules needs discussing first.

**Deferred indefinitely:** gap G2's dedicated move/reschedule endpoints.

### 3.7 Mechanics confirmed while building the team (step 4)

Each of these was checked against the installed packages, not assumed:

* **Nothing in the framework resolves `${VAR}`.** `resolve_env_vars` says so in
  its own docstring ("called by runtime consumers, not by catalog services") and
  no caller exists anywhere in the installed code. `meeting_agents.bootstrap`
  therefore owns resolution, and does it after hydration so it reaches a value
  wherever it ended up. It raises on a missing variable rather than leaving a
  placeholder to surface later as a connection error to a host named
  `${MEETING_MCP_URL}`.
* **Dispatch is by method name**: `receiveMsg_<MessageType>`, Thespian-style.
  An unhandled type is logged as `Unknown message ...` and dropped — which is
  how the dropped `PlanSnapshot` acknowledgement was first spotted.
* **`list[type]` fields take `{__type__: dotted.path}`** in YAML. A bare string
  fails validation (`Input should be a type`). This is how `message_types` is
  written.
* **A YAML file's name must equal its `id`** — `team.yaml` must declare
  `id: team`. `load_team` then finds it by `kind: team`, not by id.
* **The model-type allowlist governs `Entry.model_type` only, not
  `agent_class`.** `_resolve_agent_class` calls `import_class` with no allowlist
  check, so `meeting_agents.coordinator.Coordinator` loads without
  `set_allowed_prefixes` — our `model_type` stays `akgentic.core.AgentCard`.
* **`AgentCard.config` is coerced to the `ConfigType` of its `agent_class`.**
  This is what lets `CoordinatorConfig` and `PlanRepositoryConfig` be written as
  plain YAML, and it produces the isolation guarantee in its strongest form: the
  deterministic agents have **no `tools` field at all**, so no configuration
  mistake could give either of them an MCP server.
* `TeamRuntime.send_from_to(sender_name, recipient_name, message)` is the
  outside-in entry point, and `TeamFactory.build(card, actor_system, ...)` is a
  static method.

### 7.3 Durability before notification (decided while implementing)

The first version of the coordinator told the human a plan was complete and
asked the repository to store it in the same breath. Those are two mailboxes, so
"completed" could reach the human before the plan was written — and a test
reading the store immediately after the notification caught it.

`PlanCompleted` is now sent only when `@PlanRepository` acknowledges the write.
That makes the claim honest: if the human was told, it is stored.

This introduced a second, subtler problem worth recording. Acknowledgements of
the *earlier* saves are still in flight when the final one is sent, and a plan
id matches all of them, so the first ack to arrive was mistaken for the last.
The fix is to correlate on the snapshot's **derived status** rather than on the
id alone: only a `CONFIRMED` plan can be the final write. Deriving status rather
than storing it, decided back in step 2 for a different reason, is what made
that correlation available.

### 7.4 What the first live run taught us (step 5)

Everything up to this point was verified with stubs. Running the real team
against the real MCP containers and a real model found six things no test had,
and each one is now covered by a test so it cannot come back.

**1. A prompt is a format string.** `Prompt.render()` is
`template.format(**params)`, so a literal `{` in prompt text raises `KeyError`.
`@Catering`'s prompt contained `{item_id, quantity}` as an illustration. It
failed inside `on_start`, where the agent still starts — just without its
backstory. Silent lobotomy. Every prompt in the catalog is now rendered by a
test.

**2. A free window is not a meeting.** `find_common_slots` answers with windows
("everyone is free 09:00–17:00") and the prompt rightly tells the model to relay
them untouched, because arithmetic is where models slip. But nobody then cut the
window down to the meeting's length, so the team proposed a *seven-hour* slot for
a one-hour meeting and would have booked it. Slicing is pure arithmetic, so it
now happens in `meeting_slots()` in Python, capped at three candidates because
this becomes a question for a human.

**3. Models invent timezones.** Declared as `time`, a tool parameter advertises
`format: time` in its schema, and the model repeatedly answered `10:00:00+00:00`.
Nothing in this domain has a timezone — a venue is simply at 09:00 — so the
offset met a naive time in a comparison and produced a 500 with an unhelpful
message. Fixed in three layers:
  - the REST API refuses an offset outright (`WallClock`), because a *system*
    integrator sending `+02:00` may genuinely mean a conversion and must be told
    we do not do that;
  - the agent-facing MCP tools take a plain `HH:MM` **string**, so the schema
    stops inviting an ISO timestamp, and ignore a trailing offset while saying
    so in a `note`, because the model never meant a conversion — it meant the
    clock reading it was given;
  - the prompts say times are local and carry no offset.

**4. A strict boundary can be worse than a tolerant one.** The first attempt
rejected offsets at the MCP boundary too. That turned a typo into a *fatal*
error: a tool-input validation failure ends the agent's turn, whereas a tool
*result* it can read lets it correct itself. Validate at the edge that owns the
data; translate, don't adjudicate, at the edge that faces the agent.

**5. `compensated` was a lie.** `PlanFailed` reported the undo steps a failed
plan *needs* under a field named `compensated`, which reads as "already undone".
A live failure reported `cancel_meeting` for meeting 1 and the meeting was still
there afterwards — correctly, since running compensations is iteration 2, but
nobody reading the message would know. Renamed to `outstanding`.

**6. An approval without a slot was read as a refusal.** A client that got the
field name wrong had its plan silently cancelled and was told it had not been
approved. `SlotApprovalDecision` now rejects that at construction. A GUI (§4.2)
would have hit this.

What worked first time: per-agent MCP isolation, the saga ordering, the approval
gate, durability-before-notification, and the actor hop to `@Catering` — the
coordinator never learns that lunch exists. The verified run booked meeting 2,
room `room-a` (booking 7) and a confirmed lunch order for exactly two people; a
second run correctly avoided the slot the first had taken.

### 7.5 What the first live CLI run taught us

Step 6 put a real terminal in front of the team: `make plan-meeting` built the
card, sent one `PlanMeetingRequest`, printed three candidate slots, read an
answer from stdin and reported a booked meeting, room and lunch. Two things came
out of running it for real rather than against stubs.

**The actor must not hold the client.** `HumanProxy` only handles the framework's
free-text `AgentMessage`; our typed messages would be logged and dropped. Rather
than teach the actor about a terminal, `ChannelHuman` relays them to a
`HumanChannel` — a Protocol, defaulting to a `QueueChannel`. The actor never
blocks and knows nothing about who is listening, and replies go back through
`runtime.send_from_to("@Human", "@Coordinator", …)`. That is the §4.2 rule-3 swap
point: an HTTP handler or websocket implements the same Protocol, and the
blocking `input()` stays in `cli.py` where it belongs.

**A booking nobody can read is half a booking.** The run produced a perfectly
correct room booking referenced as *"Meeting"* — the facility manager was never
told the title, so the model filled the gap with a plausible noun. The MCP tool
had accepted a `title` all along. The lesson is not about prompting: a field the
agent is not given is a field it will invent. `BookFacilitiesAssignment` now
carries the title, and a test pins it. The next run booked *"Architecture
workshop"*, which is what the person reading the room calendar needs.

Also confirmed: shell variables win over `uv run --env-file`, so the Makefile can
point a host run at `localhost:810x` without touching the committed `.env`.

### 7.6 A timeout is a design decision, not an accident

The first run by someone other than me failed, and it failed in the least
useful way imaginable: two hundred lines of traceback ending in
`ModelTimeoutError`. Three things were wrong, and only one of them was the
timeout.

**akgentic's defaults are deliberate, and they are not ours.** A model request
times out after 120s, and the retry policy explicitly *does not* retry a
timeout — it retries 429s and 5xx, which are unambiguous, and fast-fails
everything else. That is a sound default: a timed-out request may still be
executing on the server, so retrying one that books a room could double-book
it. But a reasoning model with nine tools exceeds 120s often enough to matter,
and because a specialist's failure fails the whole plan, one slow call ends
everything. The specialists now allow 240s via
`runtime_cfg.http_client_config.timeout`. We raise the ceiling rather than add
retries, precisely because the framework is right about the risk.

**A timeout budget is a chain, not a number.** The CLI gave up after 300s —
longer than one call at the old 120s, shorter than one call at the new 240s,
and far shorter than the three back-to-back calls between approval and a booked
meeting. Raising one timeout without the other would have converted a provider
failure into a *client* failure. It is now 900s, and a test pins it above three
slow calls, because the next person to tune one of these numbers needs to be
told about the other.

**A traceback is not an error message.** `logger.exception` put the full stack
in front of a person who only needed to know that nothing was booked and they
could try again. The reason already travels to the coordinator as a typed
`AssignmentFailed` and is reported there; the stack is a debug detail and now
appears only under `--verbose`. Verified by forcing a timeout: five readable
lines instead of two hundred.

What this did *not* turn out to be is worth recording too. The obvious suspect
was the approval gate — a human taking minutes to answer while sessions sit
idle. A run with a four-minute pause before answering completed normally, so
the actor, its MCP session and its connection pool all survive an idle human.
The gate is not the fragile part.

### 7.7 A second gate, and the menu that never travels

D4 said *one* gate, on the time slot, because that is the only decision that
has to be made before anything is written. Using the team showed the reasoning
was right about *when* to ask and wrong about *how much*: lunch simply appeared,
and a person who would like a say in their own lunch had none.

So there is a second question now, asked **after** the slot is approved and
**before** anything is booked. The order matters: nobody should be asked about
lunch for a meeting that may never happen.

**The answer is free text, and that is what keeps D2 intact.** The obvious
design — show the menu, let the human pick — would have dragged the NomNom menu
from `@Catering` through `@FacilityManager` to `@Coordinator` and out to the
human, turning the one agent allowed near that MCP server into a courier and
telling the human exactly where lunch comes from. Letting a person say
*"something vegetarian, no bread"* instead means **no menu ever moves**:
`@Catering` reads the wish against the menu it alone holds, and the judgement
stays with the agent that has the information. Isolation survives because we
asked a vaguer question, not because we added a guard.

The wish is a **data field on `BookFacilitiesAssignment`, deliberately absent
from `rendering()`** — same trick as `with_lunch`. The facility manager reads it
in Python and passes it down; the coordinator's prose still never mentions
lunch, and the test that holds that line still passes.

**Three states, not two.** `with_lunch=False` → no lunch, no question;
`with_lunch=True, lunch_wish=None` → ask; `with_lunch=True, lunch_wish="..."` →
settled. The third exists so `--lunch "a hot soup"` and `--no-lunch` never block
a scripted run on a prompt nobody is there to answer. A gate with no
non-interactive path is a gate that breaks automation.

**Declining lunch is not a failure.** Only an unapproved slot fails a plan: a
meeting with no agreed time is not a meeting, while a meeting with no lunch is
just a smaller meeting. The two gates also read silence differently on purpose —
empty means *no* at the slot gate and *you choose* at the lunch gate, because by
then lunch has already been asked for and only the kind is open.

Finally, the wish is **remembered on the plan**, so the D5 relocation saga can
rebook the same kind of lunch at the new location rather than guessing again.
And because the human asked in words, they are answered in words: a short
summary travels back `OrderedLunch` → `LunchOrdered` → `FacilitiesBooked` →
`MeetingPlan.lunch_summary` and is printed in the confirmation.

### 7.2 Implementation order

1. ✅ `find_common_slots` REST endpoint + MCP tool on meeting-service, with tests (closes G1).
2. ✅ New `agents/` workspace package: dependencies, `MeetingPlan` model, plan store.
3. ✅ Catalog YAML: 3 `MCPTool` entries, model config, prompts, the 3 specialist agent entries.
   (The team card and the two deterministic agent entries move to step 4, because their
   `agent_class` dotted paths must exist before the YAML referencing them can be loaded.)
4. ✅ `@Coordinator` + `@PlanRepository` deterministic actors; typed messages; `team/team.yaml`.
5. ✅ `@Scheduler`, `@FacilityManager`, `@Catering` LLM agents — verified live against the
   running MCP containers and `gpt-6-luna` (see §7.4).
6. ✅ CLI runner + approval gate via `HumanProxy` — verified live end to end (see §7.5).
7. ✅ Dockerfile, compose service, Makefile targets, README.
8. ✅ The lunch gate (D9) — a second question, free text, with a non-interactive path (§7.7).

---

## 8. Changelog

- 2026-10-26: Initial Akgents design. Researched `akgentic-core/-llm/-tool/-team/-agent/-catalog`
  plus the full 8-part blog series. Verified that **per-agent MCP isolation is supported**
  (`AgentConfig.tools` is per-agent, deep-copied per spawn, no shared registry) and that `MCPTool`'s
  `streamable-http` + `bearer_token` configuration is an exact match for the MCP servers built in
  phase 3. Recorded the framework constraint that **`MCPTool` has no tool allowlist** — which our
  deliberately-narrow MCP surfaces already compensate for. Proposed a topology
  (`@Human` → `@Coordinator` → `@Scheduler`, `@FacilityManager` → `@Catering`), identified the
  booking flow as a **distributed saga** needing deterministic compensation plus an id-correlation
  store, logged five gaps in the current REST/MCP surface, and raised ten open questions.
- 2026-10-26: Decisions D1–D8 agreed (§7): deterministic coordinator + LLM specialists;
  `@Catering` under `@FacilityManager`; a `@PlanRepository` actor for id correlation; a single
  approval gate on the proposed time slot; only a *location* change rebooks lunch; OpenAI;
  CLI runner in a 4th container; `find_common_slots` added first. Cancellation/compensation sagas
  and `akgentic-infra` deferred. One item left open: confirming a typed `PlanMeetingRequest` as
  the v1 human entry point (§7.1).

## 9. Changelog

- 2026-10-26: Step 1 — `find_common_slots` added to meeting-service (closes G1); see `design.md`.
- 2026-10-26: Added §4.2 after a steer that a **GUI and free-format input are wanted in time**.
  CLI-first and typed-input-first are now explicitly recorded as *sequencing*, not architecture,
  with eight binding rules that keep `akgentic-infra` + frontend and free text reachable without a
  rewrite. Note `akgentic-framework[agent,catalog]` leaves `infra` one extra away.
- 2026-10-26: Step 2 — created the `agents/` workspace package (`meeting_agents`) with the
  `MeetingPlan` aggregate, a `PlanStore` protocol with in-memory and atomic-JSON implementations,
  and env-driven `Settings`. Status is **derived** from which ids are present, so it cannot drift;
  `compensations()` and `relocation_compensations()` return the undo steps as ordered plain data,
  keeping the saga out of a model's hands and testable without any actor or LLM. 23 tests.
  Verified the framework assumptions against the installed packages — see §2.3.
- 2026-10-26: Step 3 — the three specialist agents are now defined in **catalog YAML**, not Python:
  one `MCPTool` entry per service, a shared model entry (`gpt-6-luna`), a prompt per agent, and
  three agent entries that each `__ref__` exactly one tool. Secrets and URLs are `${VAR}`
  placeholders resolved from `Settings.as_catalog_env()`, so the catalog is safe to commit.
  **The isolation guarantee is now asserted by tests rather than by review**: `test_catalog.py`
  checks that each agent has exactly one MCP tool, that no two agents share a URL, and that no
  real key is present. Verified live end to end — catalog YAML → `resolve_by_id` → env resolution
  → `ToolFactory` → the three running MCP containers, each agent listing only its own prefixed
  tools (`meeting_*`, `facility_*`, `catering_*`). 15 tests; 79 in the workspace.
  Two findings worth remembering: an unquoted YAML scalar cannot contain `": "`, and
  `Catalog.resolve()` takes an `Entry` object — `resolve_by_id(namespace, id)` is the call that
  returns a hydrated model.
- 2026-10-26: Step 4 — the team now assembles. Added the typed message vocabulary
  (`messages.py`), the deterministic `@Coordinator` and `@PlanRepository`
  (`coordinator.py`, `plan_repository.py`), a `bootstrap.py` that owns `${VAR}`
  resolution, and the YAML for the coordinator, the repository, the human entry
  point and the team card itself. `catalog.load_team("meeting-planner")` now
  returns the full hierarchy: `@Human -> @Coordinator -> {@PlanRepository,
  @Scheduler, @FacilityManager -> @Catering}`.
  The saga is proven end to end **without a model or a network call** — stub
  specialists in a real actor system drive slots, approval, meeting, room and
  lunch (`test_saga.py`). That is the test that keeps D1 honest: if it ever
  needs an LLM, something deterministic has stopped being deterministic.
  Two bugs found and fixed by that test, both recorded in §7.3: notification
  racing persistence, and acknowledgements correlated on plan id alone.
  Mechanics confirmed against the installed packages are in §3.7.
  113 tests in the workspace.
- 2026-10-26: Step 5 — the three LLM specialists are real agents now
  (`specialists.py`, `outputs.py`), each answering in a typed contract that
  carries `succeeded` and `reason` so a failure is sayable and an id is never
  invented. `@FacilityManager` owns the hop to `@Catering`, so the coordinator
  still knows nothing about lunch. Two framework facts cost time and are worth
  remembering: a `BaseAgent` subclass must **re-parameterise**
  (`class X(BaseAgent, Akgent[XConfig, AgentState])`) for its own config type to
  be picked up by card coercion, and `BaseAgent.on_start` *assigns*
  `AgentState(backstory=...)`, so replacing state with a subclass instance
  silently discards the agent's system prompt — use instance attributes for
  in-flight bookkeeping.
  Then the team was run for real, against the three MCP containers and
  `gpt-6-luna`, and found six bugs that stubs could not. They are written up in
  §7.4; the short version is that prompts are format strings, a free window is
  not a meeting, models invent timezones, a strict boundary can be worse than a
  tolerant one, `compensated` was a lie, and an approval without a slot read as
  a refusal. All six are fixed and covered by tests. 143 tests pass; two
  consecutive live runs reached `CONFIRMED` with a real meeting, room and lunch
  order, the second correctly avoiding the slot the first had taken.
- 2026-10-26: Step 6 — the CLI runner and the approval gate. `human.py` adds a
  `HumanChannel` Protocol with a `QueueChannel` default and `ChannelHuman`, a
  `HumanProxy` subclass that relays our typed messages to whoever is listening;
  `cli.py` is a thin client over it that decides nothing about meetings. Replies
  travel back via `runtime.send_from_to`, which works identically for a terminal,
  an HTTP handler or a websocket (§4.2 rule 3), and `make plan-meeting` runs it on
  the host. Verified live twice against the real services and `gpt-6-luna`: three
  candidate slots offered, the chosen one honoured, meeting + room + confirmed
  lunch order persisted. The run also exposed a room booked as "Meeting" — the
  facility manager was never given the title, so the model invented one;
  `BookFacilitiesAssignment` now carries it. See §7.5. 166 tests pass.
- 2026-10-26: Step 7 — the team ships as a container (D7). Unlike the three
  services it is **not a server**: one run plans one meeting and exits, so it
  sits behind a compose `profiles: ["agents"]` (left alone by `make up`), keeps
  `stdin_open`/`tty` for the approval prompt, and takes its arguments straight
  from `docker compose run` via an `ENTRYPOINT`. Inside the network each agent
  still reaches exactly one MCP server, by compose service name. The catalog
  travels in the image; URLs and secrets stay `${VAR}` placeholders in the
  environment, so nothing secret is baked in. `make plan-meeting` (host) and
  `make plan-meeting-docker` (container) are the two ways in, and a missing
  `OPENAI_API_KEY` now fails by name rather than inside a provider call.
  Verified live: a containerised run booked meeting 6, room-a (booking 11,
  correctly titled) and a CONFIRMED lunch order, with the plan record persisted
  on its own volume. 167 tests pass.
- 2026-10-26: A run by someone other than me died on `ModelTimeoutError` with a
  two-hundred-line traceback. Three fixes, written up in §7.6: the specialists
  now allow 240s per model call (akgentic defaults to 120s and deliberately does
  *not* retry a timeout, since a timed-out booking may still have happened —
  so we raise the ceiling rather than retry); the CLI's reply budget went to
  900s, because three slow calls run back to back between approval and a booked
  meeting and a client timeout below that sum invents failures; and the stack
  trace is now a `--verbose` detail rather than the first thing a person sees.
  Also ruled out, by experiment: a human taking four minutes to answer the
  approval prompt breaks nothing. 172 tests pass.
- 2026-10-26: **D9, the lunch gate.** Added a second human question, asked after the slot is
  approved and before anything is booked. It is answered in **free text**, which is what lets the
  NomNom menu stay inside `@Catering` — showing a menu would have made the one agent allowed near
  that server a courier and broken D2. `PlanMeetingRequest.lunch_wish` is tri-state (`None` asks,
  anything else settles), so `--lunch "..."` and `--no-lunch` keep scripted runs from blocking.
  Declining is not a failure. The wish is stored on the plan for the D5 relocation saga, and a
  short summary flows back so the confirmation says what lunch actually arrived. `@Human` needed a
  new handler for the question — an undeclared message type is logged and dropped, which would have
  hung the plan silently. 193 tests; verified live across all four paths (asked, scripted,
  declined, no lunch).
