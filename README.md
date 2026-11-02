# Meeting Planner

A Python rewrite of the original Java/Spring Boot "meeting-planner-embabel" project, split into
independent, containerized microservices. See [`design.md`](./design.md) for the full analysis of
the original project and the decisions behind this rewrite.

## What this is

Three independent FastAPI services, each with its own SQLite database, REST API, and a small
server-rendered (Jinja2 + HTMX) UI. Each service also runs a second process exposing an
**MCP server** (via [FastMCP](https://gofastmcp.com)) with a narrower, agent-oriented tool set —
see `design.md` section 3 for the design and rationale.

| Service            | Purpose                                      | REST+UI port | MCP port |
|--------------------|-----------------------------------------------|:---:|:---:|
| `meeting-service`   | People, agendas, and meeting scheduling       | `8001` | `8101` |
| `location-service`  | Locations, rooms, and room bookings           | `8002` | `8102` |
| `nomnom-service`    | Food/drinks catalogue and ordering            | `8003` | `8103` |

**Current phase scope** (see `design.md` and [`design_akgents.md`](./design_akgents.md) for the
roadmap): plain REST APIs, Pydantic/SQLModel domain models, agent-facing MCP servers that wrap
each service's own REST API, and an **agent team** built on the in-house "Akgents" framework that
plans a meeting end to end from the command line. There is **no** authentication/OAuth on the
services' REST APIs (the MCP endpoints use a lightweight per-service API key instead, see `design.md`
section 3.3); the team server has a demo login, described below. Each service is self-contained and does not share a common library; a small amount of logic
(e.g. the day-availability algorithm) is duplicated between `meeting-service` and
`location-service` by design.

## The agent team

`agents/` holds a team of [Akgents](https://github.com/b12consulting/akgentic-framework) actors,
defined in catalog YAML under `agents/catalog/`:

- `@Coordinator` — deterministic; drives the booking saga and is the only agent the human talks to.
  Its state is the meeting's only record — which meeting, room booking and lunch order belong
  together — snapshotted by the framework and restored with the team (`design_durability.md`).
- `@Scheduler` — finds slots both people are free, and books the meeting.
- `@FacilityManager` — books the room, and delegates lunch to `@Catering`.
- `@Catering` — orders the food.

**Each specialist can reach exactly one MCP server** — its own service's, and nothing else. That
isolation is asserted by tests, not by review (`agents/tests/test_catalog.py`). Specialists never
talk to each other directly; they exchange typed messages through the coordinator, except for the
one hop from `@FacilityManager` to `@Catering`, which is why the coordinator never learns that
lunch exists.

To run it, start the stack, put an `OPENAI_API_KEY` in `.env` (never commit it), and ask:

```bash
make up
make plan-meeting ARGS='--title "Design review" \
  --with sanne@rag4p.org daan@rag4p.org --day 2034-06-20 --at yuma'
```

The team proposes candidate time slots and waits for you to approve one. It then asks what you
feel like for lunch — answer in your own words (*"something vegetarian, no bread"*) and `@Catering`
matches it against the menu, or answer `no` to skip it. Nothing is booked until both questions are
answered, and the confirmation tells you what lunch actually arrived.

To keep a scripted run from stopping at that question, settle it on the command line:

```bash
make plan-meeting ARGS='... --lunch "a hot soup"'   # or --no-lunch
```

The place can be described instead of named — `--place "somewhere quiet"` in place of `--at yuma`.
`@FacilityManager`, the only agent that sees the locations and their descriptions, chooses one
before the slot search, and the slot question names the place and why, so approving the time
approves the place.

## The team you talk to

A second team, `meeting-planner-chat`, arranges a meeting from a conversation. It is the same team
with one agent in front: `@Intake`, an LLM agent that holds the conversation, looks people up by
name through `@Scheduler`, and makes **one** call to the team — the same typed
`PlanMeetingRequest` the form sends. The coordinator is unchanged in code; it is configured to
treat `@Intake` as its human, and `@Intake` relays its questions and results. There is no way to
approve a time in the conversation: the slot question is answered on its card, as on the form.
The specialists are the form team's own catalog entries, by reference. See `design_chat.md`.

### It remembers

`@Intake` remembers what you tell it that will still be true next time (`design_memory.md`):
who "my team" is, how long your stand-ups are, that Sanne is vegetarian. The next conversation
knows it without asking.

- **Yours, or everybody's.** How *you* arrange meetings lives in your own tree, under your login;
  facts about a person live in a shared tree, so Daan's lunch for Sanne knows she is vegetarian
  even though Jettro said it.
- **Files on the server's disk**, under the workspaces root — `/data/workspaces` on the
  `server-data` volume in compose:
  `<you>/_id/memory/organiser.md` and `_shared/_id/memory-shared/people/<email>.md`, each beside a
  git journal (`memory.git`) recording every change and which agent made it. `make reset` wipes
  them with everything else.
- **Only what a person said**, as confirmed; never a secret or an id, and about someone else only
  after looking them up. Saying it again replaces it; the journal keeps the old version.
- **Visible:** every time memory reaches the model, a `MemoryApplied` row in the Trace says what and
  why. The **Memory** tab shows what is remembered for you and about you, who said it, and what
  each item replaced, read from the journal. The console shows your own tree.

It also runs as a container, reaching the MCP servers over the compose network instead of
`localhost`:

```bash
make build                                     # includes the agents image
make plan-meeting-docker ARGS='--title "Design review" ...'
```

It is not a server: one run plans one meeting and exits, so it sits behind a compose profile and
`make up` leaves it alone.

## The team as a service

The same team also runs behind HTTP, for clients that are not a terminal. `make up` starts it on
<http://localhost:8200>; `make run-server` runs it on the host instead. It is the community tier of
`akgentic-infra` with a route and a login of our own spliced in:

| route | what it answers |
|---|---|
| `GET /platform/health` | all three services at once, probed concurrently — `up`, `degraded` (it answered, badly) or `unreachable` (it did not answer) |
| `GET /auth/users`, `POST /auth/login/person` | the people who may log in, and logging in as one of them |
| `POST /auth/login/apikey`, `GET /auth/me`, `GET /auth/logout` | the session, in the shape the akgentic console expects |

Everything else is the framework's: `POST /teams` creates a team from the catalog,
`POST /teams/{id}/message/from/@Human/to/@Coordinator` starts a plan with a typed
`PlanMeetingRequest` — or cancels one with a `CancelPlanRequest`, which is why cancelling
needs no endpoint of its own — `GET /teams/{id}/events` (or `WS /ws/{id}`) is the trace,
`POST /teams/{id}/human-input` answers a gate with plain text, and `GET /teams` plus
`GET /teams/{id}/agent-states` are the list of meetings: one team arranges one meeting, so there
is no plan store of our own to read.

### Who is asking

The framework already decides who may see which team: the owner, or an admin — anyone else gets a
404, as if the team did not exist. Its community tier just makes everybody `anonymous`. With
`AUTH=demo` (the default in compose) the server tells it who is asking (`design_auth.md`):

- You **log in as any person the meeting service knows**, by picking them. There is no password —
  this demonstrates users, not security. Your meetings, their traces and cancelling are then yours
  alone; `ADMIN_EMAILS` see everybody's.
- The session is an HttpOnly cookie, because a browser cannot put a header on a WebSocket. The GUI
  and the console share it, so **open both on `localhost`**, the host the server is on —
  `127.0.0.1` is a different site and gets no cookie.
- The console logs in with an API key: `API_KEYS` in `.env`, as `key=email` pairs.
- `AUTH_SECRET` signs the cookie; left empty, everybody is logged out at each server restart.
  `AUTH=off` brings back the anonymous server.

Both human gates work over HTTP: the answer is read against the question it refers to by
`ChannelHuman.process_human_input`, using the same `answers.py` the terminal uses. A browser can
render radio buttons for the slots and still send `"2"`.

## The browser client

`gui/` is a React single-page app — the demo platform the command line was not. `make up` serves
it from nginx on <http://localhost:8300>; `make gui-dev` runs it from Vite on
<http://localhost:5173> against the same server. Both origins are already in the server's
`CORS_ORIGINS`.

A login page first — pick who you are — then five screens, with your name and *Log out* in the
app bar:

| screen | what it does |
|---|---|
| **Platform** | the three services, polled every ten seconds. `up` / `degraded` / `unreachable` are kept apart: a 503 and a silence have different causes |
| **Plan a meeting** | the form, then the two gates as they arrive — the slots as radio buttons (the candidates travel with the question), lunch as free text, because `@Catering` holds the menu and is the only agent that should read the words — then the booked meeting |
| **Talk to the planner** | a conversation with `@Intake`: names and a description of the place are enough. The slot question appears inline as a card and is only ever answered there; typing a choice into the conversation is understood and authorises nothing. Then the booked meeting |
| **Meetings** | one row per team run, read from each coordinator's snapshot: the meeting, booking and order ids that nothing else links together, and what it is waiting for. A meeting can be **cancelled** here — the cancel goes to the team that made it, revived if it has stopped, and releases the lunch order, the room and the meeting. A meeting waiting at a gate offers **Resume**, whether or not its team is still running. There is no edit: to change a meeting you cancel it and plan a new one |
| **Trace** | every message, live, with a *framework events* toggle. Off, it is twenty rows that read like a story. On, it is the actor system starting up, receiving and processing — the "show me what happens at the framework level" view. Each row carries a one-line summary of what the message actually said; clicking it opens the whole payload, as readable fields or as the raw envelope. A run that has finished can be re-read from the server, so a trace outlives the socket that carried it |

TypeScript, MUI, TanStack Query, React Router, and about forty lines of WebSocket. The API base is
baked in at build time (`VITE_API_BASE`), because Vite inlines it and the browser runs on the host.

One socket serves all five screens: the server replays from cursor zero on connect, so a second
subscriber would be a second full history.

## The framework's own console

`gui/` shows the *meeting*. The Akgentic console shows the *team*, and it is worth having both: the
transcript with per-agent thinking bubbles, the roster, the agent hierarchy as a graph, each
member's LLM context and system prompt, the workspaces, and what the run spent.

    make console          # http://localhost:8400

It is upstream's [`akgentic-frontend`](https://github.com/b12consulting/akgentic-frontend), run
unmodified. There is no checkout in this repository: Docker builds it from the upstream git URL at
a pinned commit, and the only file we own is `console/config.json`, mounted over the image. See
`console/README.md`. It logs in with one of the `API_KEYS` (see *Who is asking*).

A team run carries typed metadata — the meeting it was asked to arrange — declared on the team
card as `metadata_type` and sent with `POST /teams`. That is what makes a list of runs readable:
the console shows it as chips, names each run in its rail, and builds a filter form from the fields
marked indexed. It describes the *request*, which is known at creation and never changes; the
outcome lives in the plan.

This works at all because our server *is* `akgentic-infra` — `create_app` with two modules added —
so the console's protocol is already served. Nothing was written to support it.

## Project layout

```
meeting-planner/
├── design.md                 # Analysis of the old project + rewrite decisions
├── design_akgents.md          # Design of the agent team (Akgents)
├── design_gui.md              # Design of the team server + browser client
├── design_cancel.md           # Design of cancelling a meeting (built)
├── design_durability.md       # The team is the meeting: a durable coordinator, no plan store (built)
├── design_chat.md             # Talking to the team in free text: @Intake (built)
├── pyproject.toml             # uv workspace root (shared dev tooling config)
├── docker-compose.yml         # Runs all three services together
├── Makefile                   # Shortcuts for common dev tasks (see `make help`)
├── agents/                    # The Akgents team + CLI runner
│   ├── Dockerfile
│   ├── catalog/               # Team, agent, tool, model and prompt YAML
│   ├── src/meeting_agents/    # Coordinator, specialists, messages, plan, CLI
│   └── tests/
├── server/                    # The same team, served over HTTP (akgentic-infra)
│   ├── Dockerfile
│   ├── src/meeting_server/    # app, catalog, platform health, yaml types
│   └── tests/
├── gui/                       # React SPA (Vite + MUI), served by nginx
│   ├── Dockerfile
│   ├── nginx.conf
│   └── src/                   # api client, useTeamStream, TeamContext, pages
└── services/
    ├── meeting-service/
    │   ├── pyproject.toml
    │   ├── Dockerfile
    │   ├── src/meeting_service/   # models, schemas, api, ui, db, seed, main
    │   └── tests/
    ├── location-service/           # same layout
    └── nomnom-service/             # same layout
```

Each service follows the same internal structure:
- `models.py` — SQLModel table definitions and core domain logic (pure functions, unit-tested).
- `schemas.py` — Pydantic request/response DTOs for the API.
- `db.py` — SQLite engine/session setup.
- `seed.py` — demo/seed data, inserted on startup if the DB is empty.
- `api.py` — REST endpoints (`/api/...`).
- `ui.py` — Jinja2 + HTMX server-rendered pages.
- `main.py` — FastAPI app assembly + startup lifespan (creates tables, seeds data).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python 3.12 is pinned via `requires-python`; uv will fetch it if needed)
- [Docker](https://www.docker.com/) + Docker Compose, for running the containerized stack

## Quick start

```bash
# Install all workspace packages into the shared .venv
make sync

# Run quality checks (lint + typecheck + tests)
make check

# Run one service locally with live reload
make run-meeting     # http://localhost:8001
make run-location    # http://localhost:8002
make run-nomnom      # http://localhost:8003

# Run that service's MCP server locally too (separate process, same REST API)
make run-meeting-mcp     # http://localhost:8101/mcp
make run-location-mcp    # http://localhost:8102/mcp
make run-nomnom-mcp      # http://localhost:8103/mcp

# Or run the whole stack in Docker (each container runs both processes)
make build
make up
make logs
make down

# The framework's console: http://localhost:8400 (teams, hierarchy, costs)
# The browser client: http://localhost:8300 once the stack is up,
# or run it from Vite against the same server
make gui-install
make gui-dev         # http://localhost:5173
```

Each service exposes:
- A browsable UI at `/`
- An OpenAPI/Swagger UI at `/docs`
- JSON REST endpoints under `/api`
- An MCP endpoint at `/mcp` on its MCP port, authenticated with a per-service API key
  (`Authorization: Bearer <key>`, see `.env.example` and `design.md` section 3.3)

## Common tasks (Makefile)

Run `make help` for the full list. Highlights:

| Command            | What it does                                              |
|---------------------|------------------------------------------------------------|
| `make sync`         | `uv sync --all-packages` — install/update the shared venv  |
| `make lint`         | `ruff check` across all services                            |
| `make format`       | `ruff format` + `ruff check --fix` across all services      |
| `make typecheck`    | `mypy` across all services                                   |
| `make test`         | `pytest` across all services                                 |
| `make check`        | lint + typecheck + test (what CI should run)                 |
| `make run-<name>`   | run a single service locally with `uvicorn --reload`         |
| `make plan-meeting` | ask the agent team to plan a meeting (needs `make up`)       |
| `make plan-meeting-docker` | the same, in the agents container                     |
| `make run-server`   | run the team server on the host (needs `make up`)            |
| `make gui-install`  | install the SPA's node dependencies                          |
| `make gui-dev`      | run the SPA from Vite on <http://localhost:5173>             |
| `make gui-build`    | type-check and build the SPA into `gui/dist`                 |
| `make gui-lint`     | lint the SPA                                                 |
| `make build`        | `docker compose build`                                       |
| `make up` / `down`  | start/stop the full stack (containers only; volumes kept)    |
| `make clean`        | stop the stack **and delete** the SQLite data volumes         |
| `make reset`        | wipe **all** data: volumes, stray local `*.db`, a host run's event store |

## Development notes

- This is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/): the root
  `pyproject.toml` has `package = false` and lists `services/*` as members. All services share one
  `.venv` at the repo root. `uv sync --all-packages` installs everything; `uv sync --package <name>`
  installs only one service (and will remove its siblings from the venv — prefer `--all-packages`
  for day-to-day dev, and `--package` only when you specifically need an isolated environment).
- Demo data is seeded on first start only (`<service>_service/seed.py`), and seeding is skipped as
  soon as a table has rows. So after changing a seed, run `make reset` to drop the data — and
  `make build` as well, because the seed is baked into the image.
- Each service owns its own SQLite file; there is no shared database. In Docker, each service's DB
  lives on its own named volume (see `docker-compose.yml`).
- Tooling config (ruff, mypy, pytest) lives centrally in the root `pyproject.toml` and applies to
  all services.
- Tests use `pytest` with `--import-mode=importlib` (required because every service has its own
  `tests/test_models.py`, which would otherwise collide as the same module name when run together).
- Each service's MCP server (`<service>_service/mcp_server.py`) is an `httpx` client of that same
  service's own REST API — it never touches the database directly, so any new REST endpoint is
  automatically available to wrap as an MCP tool. Its tests point that client at the FastAPI app
  in-process (`httpx.ASGITransport`) and call tools via FastMCP's in-memory `Client`, so no real
  network server is needed. In Docker, `entrypoint.sh` starts both the REST+UI and MCP `uvicorn`
  processes in the same container; see `design.md` section 3 for the full design.
- The agent team needs an `OPENAI_API_KEY` in `.env` (see `.env.example`); **never commit real
  keys**. Run it through `make plan-meeting`, which passes `.env` to `uv` and points the team at
  the MCP servers on `localhost:810x` — shell variables win over `uv run --env-file`, so the
  committed defaults (which name the compose services) are overridden without editing `.env`.

## Roadmap

Each step so far has a design document, written before it was built: `design.md` (the services
and their MCP servers), `design_akgents.md` (the agent team), `design_gui.md` (the team as a
service, the browser and the console), `design_cancel.md` (cancelling), `design_durability.md`
(the team is the meeting), `design_chat.md` (the team you talk to), `design_auth.md` (who is
asking — the login, and the meetings that are yours) and `design_memory.md` (what the team
remembers, phase 1).

Still to come, each with a design first:

- **The rest of `design_auth.md`** — a *My agenda* page, and the organiser known to `@Intake`.
- **Memory, phases 2 and 3** — the facility manager using place facts before it chooses, proposed
  lessons a person promotes, and a Memory page to see, correct and delete items
  (`design_memory.md` §10).
- **Guardrails** — the hook is known (`BaseAgent.extra_capabilities()`, where `TalkOnlyToHuman`
  already lives); a guard on the specialists' `book_*` calls would be the next one.
- **Evals** for the LLM agents — the three live conversations in `design_chat.md` §14 are the
  first cases.
- Open questions from `design_chat.md` §11: changing a request after it is sent, the model for
  `@Intake`, and how much of the relay to narrate.
- Not planned: a change-meeting feature (cancel and plan again). A real identity provider (OIDC)
  would replace only the login page (`design_auth.md` A8).
