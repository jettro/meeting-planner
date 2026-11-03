# Meeting Planner

A meeting planner run by a small team of AI agents, built as a sample to learn from. You say who
should meet, on which day and roughly where - in a form or in your own words - and the team finds
a time, chooses a place, books a room, puts the meeting in everyone's agenda and orders lunch,
asking you before anything is booked. It is built on
[akgentic](https://github.com/b12consulting/akgentic-framework), and started as a Python rewrite
of the Java project "meeting-planner-embabel".

**Start with the [documentation](docs/README.md)**: an [overview](docs/overview.md) of the whole
sample in one page, a page per topic on how it works and why, the [lessons](docs/lessons.md) from
building it, and the [demo script](docs/demo.md).

## What runs

| | What it is | Where |
|---|---|---|
| **meeting service** | people, agendas, meetings - REST API and web page | <http://localhost:8001>, MCP on 8101 |
| **location service** | places, rooms, room bookings | <http://localhost:8002>, MCP on 8102 |
| **nomnom service** | the lunch menu and orders | <http://localhost:8003>, MCP on 8103 |
| **team server** | runs the agent teams (akgentic-infra, community tier) | <http://localhost:8200> |
| **planner** | the browser app: plan, talk, meetings, trace, memory | <http://localhost:8300> |
| **console** | akgentic's own front end: the team, prompts, costs | <http://localhost:8400> |

Open them all on `localhost`, not `127.0.0.1`: that is a different site and gets no login cookie.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python 3.12 is pinned via `requires-python`; uv fetches it if
  needed)
- [Docker](https://www.docker.com/) and Docker Compose
- An OpenAI API key, for the agents

## Quick start

Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY` - **never commit real keys**. For the
login, also set `AUTH_SECRET`, and `ADMIN_EMAILS` and `API_KEYS` if you want them (see
[who is asking](docs/who-is-asking.md); `API_KEYS` are `key=email` pairs, for the console).

```bash
make build
make up
```

Then open the planner at <http://localhost:8300>, log in as anyone, and plan a meeting. The
[demo script](docs/demo.md) walks through everything it can do.

`make reset` wipes all data - meetings, traces and memory; the seed puts the people, places and
menu back on the next `make up`.

### From the terminal

The same team runs from the command line, against the stack:

```bash
make plan-meeting ARGS='--title "Design review" \
  --with sanne@rag4p.org daan@rag4p.org --day 2034-06-20 --at yuma'
```

It proposes times and asks you to pick one, then asks about lunch - answer in your own words, or
`no`. Describe the place instead of naming it with `--place "somewhere quiet"`, and settle lunch
up front with `--lunch "a hot soup"` or `--no-lunch`.

`make plan-meeting-docker ARGS='...'` does the same inside the agents container. It is not a
server - one run plans one meeting - so it sits behind a compose profile and `make up` leaves it
alone.

### Parts on the host

```bash
make sync            # install all workspace packages into the shared .venv
make check           # lint + typecheck + tests

make run-meeting     # one service, with live reload: http://localhost:8001
make run-meeting-mcp # its MCP server: http://localhost:8101/mcp
make run-server      # the team server on the host (needs make up)
make gui-install
make gui-dev         # the planner from Vite: http://localhost:5173
```

`run-location`, `run-nomnom` and their `-mcp` targets work the same way.

Each service has a web page at `/`, its OpenAPI page at `/docs`, its REST API under `/api`, and
its MCP server at `/mcp` on its MCP port, which asks for a per-service key
(`Authorization: Bearer <key>`; see `.env.example`).

## Project layout

```
meeting-planner/
├── docs/                      # The documentation: overview, topics, lessons, demo, roadmap
│   └── design/                # The design of each step, written before it was built
├── services/                  # The three services, each self-contained
│   ├── meeting-service/       #   src/meeting_service/: models, schemas, api, ui, db, seed,
│   ├── location-service/      #   main, mcp_server - the same layout in all three
│   └── nomnom-service/
├── agents/                    # The agent team
│   ├── catalog/               #   the two teams, their agents, prompts and tools, as YAML
│   └── src/meeting_agents/    #   coordinator, specialists, @Intake, messages, memory, CLI
├── server/                    # The team server: akgentic-infra plus login, health, memory page
├── gui/                       # The planner: React, Vite, MUI, served by nginx
├── console/                   # How the akgentic console is built and configured
├── docker-compose.yml
├── Makefile                   # make help lists every task
└── pyproject.toml             # uv workspace root, shared tooling config
```

## Common tasks

Run `make help` for the full list.

| Command | What it does |
|---|---|
| `make sync` | install or update the shared venv (`uv sync --all-packages`) |
| `make lint` / `format` / `typecheck` / `test` | ruff, ruff format, mypy, pytest - across everything |
| `make check` | lint + typecheck + test, what CI should run |
| `make run-<name>` | run one service locally with `uvicorn --reload` |
| `make plan-meeting` | plan a meeting from the terminal (needs `make up`) |
| `make plan-meeting-docker` | the same, in the agents container |
| `make run-server` | run the team server on the host (needs `make up`) |
| `make gui-install` / `gui-dev` / `gui-build` / `gui-lint` | the planner: install, run from Vite, build, lint |
| `make console` | open the akgentic console |
| `make build` | `docker compose build` |
| `make up` / `down` / `logs` / `ps` | start, stop, follow and list the stack (volumes kept) |
| `make clean` | stop the stack **and delete** the data volumes |
| `make reset` | wipe **all** data: volumes, stray local `*.db`, a host run's event store |

## Development notes

- This is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/): the root
  `pyproject.toml` has `package = false` and lists the packages as members, and they share one
  `.venv` at the repository root. Prefer `uv sync --all-packages`; `uv sync --package <name>`
  installs one package and removes its siblings from the venv.
- Run the tests from the repository root (`make test`): the agent and server tests find the
  catalog from there.
- Tests use `pytest --import-mode=importlib`, because every service has its own
  `tests/test_models.py`, which would otherwise collide.
- Demo data is seeded on first start only, and skipped as soon as a table has rows. After
  changing a seed, run `make reset` - and `make build`, because the seed is baked into the image.
- Each service owns its own SQLite file, on its own named volume in Docker; there is no shared
  database and no shared library between services.
- An MCP server's tests point its `httpx` client at the service's FastAPI app in-process and call
  the tools through FastMCP's in-memory client, so no network server is needed. In Docker,
  `entrypoint.sh` starts both the REST and the MCP process in one container.
- `make plan-meeting` passes `.env` to `uv` and points the team at the MCP servers on
  `localhost:810x`. Shell variables win over `uv run --env-file`, so the committed defaults, which
  name the compose services, are overridden without editing `.env`.
- The planner's API base is baked in at build time (`VITE_API_BASE`), because Vite inlines it and
  the browser runs on the host.

## Roadmap

What is done, what is next and what is not planned: [docs/roadmap.md](docs/roadmap.md).
