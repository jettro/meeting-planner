# Meeting Planner

A Python rewrite of the original Java/Spring Boot "meeting-planner-embabel" project, split into
independent, containerized microservices. See [`design.md`](./design.md) for the full analysis of
the original project and the decisions behind this rewrite.

## What this is

Three independent FastAPI services, each with its own SQLite database, REST API, and a small
server-rendered (Jinja2 + HTMX) UI:

| Service            | Purpose                                      | Port   |
|--------------------|-----------------------------------------------|--------|
| `meeting-service`   | People, agendas, and meeting scheduling       | `8001` |
| `location-service`  | Locations, rooms, and room bookings           | `8002` |
| `nomnom-service`    | Food/drinks catalogue and ordering            | `8003` |

**Current phase scope** (see `design.md` for the roadmap): plain REST APIs and Pydantic/SQLModel
domain models only. There is **no** authentication/OAuth, no agentic/LLM layer, and no MCP server in
this phase — those are deliberately deferred to a later phase. Each service is self-contained and
does not share a common library; a small amount of logic (e.g. the day-availability algorithm) is
duplicated between `meeting-service` and `location-service` by design.

## Project layout

```
meeting-planner/
├── design.md                 # Analysis of the old project + rewrite decisions
├── pyproject.toml             # uv workspace root (shared dev tooling config)
├── docker-compose.yml         # Runs all three services together
├── Makefile                   # Shortcuts for common dev tasks (see `make help`)
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

# Or run the whole stack in Docker
make build
make up
make logs
make down
```

Each service exposes:
- A browsable UI at `/`
- An OpenAPI/Swagger UI at `/docs`
- JSON REST endpoints under `/api`

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
- No `.env`/secrets are required in this phase. If/when a later phase introduces LLM calls, add a
  fresh `.env.example` — never commit real API keys.

## Roadmap

See `design.md` for the full rewrite plan. Deferred to a later phase: an agent/orchestration layer
(built on the in-house "Akgents" framework), MCP servers, a chat interface, and OAuth2/auth-server.
