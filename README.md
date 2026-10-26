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
plans a meeting end to end from the command line. There is **no** authentication/OAuth on the REST
APIs (the MCP endpoints use a lightweight per-service API key instead, see `design.md` section
3.3). Each service is self-contained and does not share a common library; a small amount of logic
(e.g. the day-availability algorithm) is duplicated between `meeting-service` and
`location-service` by design.

## The agent team

`agents/` holds a team of [Akgents](https://github.com/b12consulting/akgentic-framework) actors,
defined in catalog YAML under `agents/catalog/`:

- `@Coordinator` — deterministic; drives the booking saga and is the only agent the human talks to.
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
  --with jettro@rag4j.org daniel@rag4j.org --day 2034-06-20 --at luminis'
```

The team proposes candidate time slots, waits for you to approve one — nothing is booked before
you do — and then books the meeting, the room and the lunch.

## Project layout

```
meeting-planner/
├── design.md                 # Analysis of the old project + rewrite decisions
├── design_akgents.md          # Design of the agent team (Akgents)
├── pyproject.toml             # uv workspace root (shared dev tooling config)
├── docker-compose.yml         # Runs all three services together
├── Makefile                   # Shortcuts for common dev tasks (see `make help`)
├── agents/                    # The Akgents team + CLI runner
│   ├── catalog/               # Team, agent, tool, model and prompt YAML
│   ├── src/meeting_agents/    # Coordinator, specialists, messages, plan store, CLI
│   └── tests/
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
| `make build`        | `docker compose build`                                       |
| `make up` / `down`  | start/stop the full stack (containers only; volumes kept)    |
| `make clean`        | stop the stack **and delete** the SQLite data volumes         |

## Development notes

- This is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/): the root
  `pyproject.toml` has `package = false` and lists `services/*` as members. All services share one
  `.venv` at the repo root. `uv sync --all-packages` installs everything; `uv sync --package <name>`
  installs only one service (and will remove its siblings from the venv — prefer `--all-packages`
  for day-to-day dev, and `--package` only when you specifically need an isolated environment).
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

See `design.md` for the full rewrite plan and `design_akgents.md` for the agent team. Still to
come: running the agent team in its own container, compensating sagas for cancelling or moving a
meeting, a web frontend (`akgentic-infra` + Angular) alongside the CLI, free-format input instead
of typed arguments, and OAuth2/auth-server.
