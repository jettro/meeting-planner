# Meeting Planner — Design Document

## Status
Draft — analysis phase. This document tracks the migration of the old Java/Embabel
"meeting-planner-embabel" project into a new Python-based multi-package / multi-container project.

Source project analyzed: `/Users/jettrocoenradie/Development/personal/agent4j/meeting-planner-embabel`

---

## 1. Analysis of the Existing Java Project

### 1.1 High-level architecture
A Maven multi-module Spring Boot application (Java 21) built around the **Embabel** AI agent
framework and **Spring AI**. It demonstrates an AI-driven meeting planner that coordinates several
sub-agents (meeting scheduling, room booking, food ordering) behind a chat interface, secured end
to end with OAuth2/OIDC.

Modules (Maven):

| Module | Type | Port | Purpose |
|---|---|---|---|
| `common` | library | – | Shared domain model: `Agenda` (availability/booking algorithm used by both people and rooms) |
| `agent` | library | – | Embabel agents: `MeetingAgent`, `LocationAgent`, `FoodAndDrinksAgent` + domain models/tools |
| `web-app` | Spring Boot app | 8080 | Main UI (Thymeleaf/Bootstrap), chat endpoint, OAuth2 client, orchestrates agent invocations |
| `auth-server` | Spring Boot app | 9000/9001 | Standalone OAuth2/OIDC Authorization Server (JWT issuer, demo users, 3 OAuth clients) |
| `mcp-location` | Spring AI MCP Server (SSE) | 8081 | Exposes location/room tools over MCP, secured as OAuth2 resource server |
| `mcp-nomnom` | Embabel MCP server | – | Food/drinks ordering: menu, orders, reporting, its own `HandleOrderAgent` |

### 1.2 Core domain concepts
- **`Agenda`** (common): generic day/time-slot availability tracker. Used both for a `Person`'s
  calendar and for a meeting `Room`'s calendar. Methods: `checkAvailability`, `bookMeeting`,
  `availabilityForDay` (9:00–17:00 business window), `getMeetings`.
- **`Person`** / **`Participants`**: wraps an `Agenda`; exposes AI tools to check availability,
  book for all participants, and list free slots for a day.
- **`Meeting`** / **`MeetingRequest`** / **`MeetingResponse`**: meeting entity + input/output DTOs.
  `MeetingService` is in-memory persistence (no DB).
- **`Location`** / **`Room`**: 11 pre-seeded demo locations (Luminis, TechHub, CityView, Like Home,
  Meet Nature, GreenSpace, Harbor, Library, Loft, Villa, Campus), each with 3 rooms of varying
  capacity, each room has its own `Agenda`. Seeded with sample bookings for demo purposes.
- **Food ordering domain** (`mcp-nomnom`): `Product`/`Category` catalog (`ProductStore`,
  `MenuService`), `Order`/`OrderItem`/`OrderStatus`, `OrderService` with rich filtering and sales
  reporting (by date range, location, product, category, revenue).

### 1.3 Agent / AI layer (Embabel + Spring AI)
- **`MeetingAgent`** (`@Agent`): `findParticipants` → `bookMeeting` (`@AchievesGoal`). Uses an LLM
  with `withToolObject(participants)` to reason over availability and book a slot, or respond "No
  common availability found". Implements `StuckHandler`.
- **`LocationAgent`**: `findLocation` → `findRoomAtLocation` → `bookRoom` (`@AchievesGoal`), using
  `toolGroups = {"location"}` — tool calls are routed to the remote `mcp-location` MCP server.
- **`FoodAndDrinksAgent`** (in `agent` module, calls out to `mcp-nomnom` via `toolGroups =
  {"food_and_drinks"}`) — simplified, single-action version.
- **`HandleOrderAgent`** (in `mcp-nomnom`, more elaborate): `receiveOrder` → `confirmOrder` (uses
  `WaitFor.formSubmission` — human-in-the-loop confirmation) → `storeOrder` → `processOrder`
  (`@AchievesGoal`, exported remotely as MCP tool `acceptOrder`).
- **`ChatAgent`** / **`ChatTools`** (web-app): a Spring AI `ChatClient` with chat memory and a
  `@Tool`-annotated bridge (`ChatTools`) that triggers `AgentInvocation`s for `MeetingAgent`,
  `LocationAgent` (via `BookingResult`/`RoomRequest`), and `FoodAndDrinksAgent` — i.e. one
  conversational entry point orchestrating three independent agents/goals.
- Multiple LLM "roles" configured (`FAST`, `BALANCED`, `BEST`) mapped to OpenAI GPT-4 mini variants.

### 1.4 MCP servers
- **`mcp-location`**: Spring AI MCP server over SSE transport exposing 3 tools (`all-locations`,
  `check-room-availability`, `book-room`), secured with OAuth2 JWT validation, plus a small web UI
  for docs/testing and a request-logging filter.
- **`mcp-nomnom`**: Embabel-based MCP server for food ordering; also has its own REST controllers
  (`OrderController`, `ProductController`) and a documentation controller.

### 1.5 Security / Auth (explicitly out of scope per user)
- Full custom OAuth2 Authorization Server (`auth-server`) issuing JWTs (RS256), 3 registered OAuth
  clients (`meeting-planner-web` – auth code, `meeting-planner-sse` – client credentials,
  `meeting-planner-public` – PKCE), demo users (`user`, `admin`, `planner`) with roles, consent
  screen, admin/session management controllers.
- `web-app` is an OAuth2 client; `mcp-location` (and presumably `mcp-nomnom`) act as OAuth2
  resource servers validating JWTs.
- **User decision: the new project will not include this OAuth2 machinery.**

### 1.6 Web layer
- Thymeleaf + Bootstrap 5 UI: home, create-meeting, meetings list, persons list/agenda, locations
  (with weekly/monthly calendar views, booking stats), NomNom food ordering UI, a chat UI.
- Controllers: `HomeController`, `LocationController`, `NomNomController`, `ChatController`,
  `LogoutController`.

### 1.7 Persistence
- Everything is **in-memory** (no database) — `MeetingService`, `PersonFinder`,
  `LocationService` (seeded in constructor), `OrderService` (`ConcurrentHashMap`), `ProductStore`.
  Data is lost on restart; fine for a demo, not for production.

### 1.8 Tech stack summary
Java 21, Spring Boot 3.5.x, Spring AI 1.1.1, Embabel Agent Framework 0.3.3, Spring Authorization
Server, Thymeleaf, Bootstrap 5.3.8, Maven multi-module build, JUnit 5 + Mockito.

### 1.9 Notable things to decide on for the Python rewrite
- Embabel is Java/Kotlin-only — the Python equivalent will need a different agent-orchestration
  approach (e.g. LangGraph, OpenAI Agents SDK / Agno, plain function-calling, CrewAI, custom
  orchestrator) and a different MCP server library (official `mcp` Python SDK / FastMCP).
  **→ needs a decision (see open questions).**
- No OAuth2/Authorization Server equivalent will be built — needs a decision on whether *any*
  lightweight auth is wanted for inter-service calls, or none at all for a local/dev setup.
- In-memory persistence may or may not be kept; needs a decision per the new project's goals
  (demo vs. something closer to real use).
- A `.env` file with a **live OpenAI API key** exists in the old project — this must **not** be
  copied verbatim into any committed file; a fresh `.env.example` will be created instead.

---

## 2. New Project Direction (to be filled in via discussion)

### 2.1 Confirmed decisions

**Scope (phase 1 — this effort)**
- Build **three independent services**, each a separate Python package / Docker container:
  1. `meeting-service` — people, agendas, availability, meeting booking (replaces `common`
     Agenda model + `agent`'s meeting domain + `MeetingService`/`PersonFinder`).
  2. `location-service` — locations, rooms, room availability & booking, seeded demo data
     (replaces `mcp-location`).
  3. `nomnom-service` — product catalog, orders, reporting (replaces `mcp-nomnom`'s
     non-agentic parts: `MenuService`, `ProductStore`, `OrderService`, controllers).
- **No OAuth2 / auth-server.** No inter-service auth for now — plain REST/HTTP (JSON) between
  services where needed.
- **No MCP, no agents, no LLM orchestration in this phase.** The "Akgents" framework
  (an existing in-house framework built on Pydantic AI, already published as PyPI packages) will
  be layered on top **later**, as a **separate package** in this same monorepo, once the three
  core services exist and expose stable APIs. The chat orchestrator and cross-agent flows from
  the Java project are explicitly deferred, not dropped.
- Each service ships **both** a JSON API (FastAPI) **and** a basic server-rendered UI
  (Jinja2 + HTMX) in the same app — no separate SPA for now.
- Domain models are **Pydantic-based** throughout (per requirement that agenda/location/nomnom
  components "must be created through Pydantic"). Persistence uses **SQLModel** (Pydantic +
  SQLAlchemy) over **SQLite**, one DB file per service.
- Demo/seed data is kept (sample locations/rooms, sample products, a few sample bookings) so each
  service is immediately explorable after startup, mirroring the old project's UX.
- No shared/common Python package between services for now — each service owns its own copy of
  any model it needs (e.g. its own `Agenda`-equivalent availability logic). Revisit later if
  duplication becomes painful.

**Repo & tooling**
- **Monorepo**, single git repo, single `docker-compose.yml` to run all services together.
- `uv` workspace for dependency management, Python **3.12**.
- **FastAPI** for the API/UI layer (Jinja2 templates + HTMX for interactivity, no separate build
  step/frontend toolchain).
- **pytest** for tests, **ruff** for lint/format, **mypy** for type checking. No pre-commit hooks
  for now.
- Service names: `meeting-service`, `location-service`, `nomnom-service` (also used as package
  and container names).

### 2.2 Open questions
None blocking — proceeding to scaffold. Will revisit when the Akgents/agent layer is added:
how services are exposed as MCP tools, LLM provider/config, and whether a shared `common`
package becomes worthwhile at that point.

### 2.3 Component/package breakdown

```
meeting-planner/
├── design.md
├── pyproject.toml              # uv workspace root
├── docker-compose.yml          # runs all 3 services together
├── services/
│   ├── meeting-service/
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   ├── src/meeting_service/
│   │   │   ├── main.py         # FastAPI app factory, mounts API + UI routers
│   │   │   ├── models.py       # Pydantic/SQLModel: Person, Agenda logic, Meeting
│   │   │   ├── db.py           # SQLModel engine/session (SQLite)
│   │   │   ├── seed.py         # demo data
│   │   │   ├── api.py          # JSON REST endpoints
│   │   │   ├── ui.py           # Jinja2 + HTMX routes
│   │   │   └── templates/
│   │   └── tests/
│   ├── location-service/       # same layout: locations, rooms, bookings
│   └── nomnom-service/         # same layout: products, categories, orders, reports
└── (later) packages/agent-layer/   # Akgents-based orchestration, MCP, chat — phase 2
```

### 2.4 Tech choices (finalized for phase 1)
- Web/API framework: **FastAPI**
- Data/validation: **Pydantic v2**
- Persistence: **SQLModel over SQLite** (one file per service, e.g. `meeting.db`)
- UI: **Jinja2 templates + HTMX**, Bootstrap for styling (kept from the old project's look & feel)
- Packaging/deps: **uv** (workspace), Python **3.12**
- Testing/quality: **pytest**, **ruff**, **mypy**
- Containerization: one **Dockerfile** per service + root **docker-compose.yml**
- Agent/orchestration framework (phase 2, not now): **Akgents** (in-house, Pydantic AI based)

---

## 3. MCP Layer Design (Phase 1.5 — agent-facing tools)

### 3.1 Goals & principles
This phase adds an **MCP (Model Context Protocol) server per service**, built with **FastMCP**.
The MCP surface is a deliberately **narrow, agent-oriented API** — it is *not* a 1:1 mirror of the
REST API:
- Expose only what an agent needs to **reason and act** (menus, availability, rooms/locations,
  booking actions), never administrative/reporting views (e.g. no "list all orders",
  no "orders summary", no raw DB dumps).
- Read tools return just enough detail to decide what to do next (e.g. free slots, not full
  agenda contents with other people's meeting titles).
- Write tools (booking/ordering/cancelling) always return a **structured, actionable result**:
  success + a stable reference id, or failure + a clear human-readable reason the agent can relay
  or act on (retry with different params, pick another slot, etc.).
- Each service's MCP server is implemented **inside that service's own package** (no shared MCP
  library/package), consistent with the "no shared common package" decision from phase 1.
- **The MCP server never implements business logic itself — it is an HTTP client of its own
  service's REST API** (details in §3.2). It reshapes/filters REST responses into the narrower
  tool contracts above; it does not touch the database or duplicate domain logic.

### 3.2 Deployment & transport
- Each service runs its MCP server as a **separate process within the same container**, on its
  own port, next to the existing REST+UI `uvicorn` process:

  | Service            | REST+UI port | MCP port |
  |---------------------|:---:|:---:|
  | `meeting-service`   | 8001 | **8101** |
  | `location-service`  | 8002 | **8102** |
  | `nomnom-service`    | 8003 | **8103** |

- Transport: **streamable HTTP** (`mcp.http_app()` served via its own `uvicorn` instance) — works
  over the network between containers/agents, supports multiple concurrent agent clients, and
  fits the existing Docker Compose setup. (Not stdio — that only works for a local single-client
  process, which doesn't fit a multi-container architecture.)
- Each Dockerfile/entrypoint will need to start **two processes** (REST+UI app, MCP app). Simplest
  approach: a small `entrypoint.sh` (or a process manager like `honcho`/`supervisord`, TBD at
  implementation time) that starts both `uvicorn` processes; `docker-compose.yml` exposes both
  ports per service.
- **The MCP server is a client of its own service's REST API, not a reimplementation of it.**
  Each `@mcp.tool()` function is a thin wrapper that makes an HTTP call (via `httpx`) to the
  service's own REST endpoints (`http://localhost:<rest-port>/api/...`) and translates the
  response into the agent-facing tool shape from §3.4. The REST API stays the **single source of
  truth for business logic** (availability checks, overlap detection, order totals, etc.); MCP
  never talks to the database or duplicates that logic directly. This keeps one code path for
  all callers (UI, REST clients, agents) and means any new REST endpoint is automatically
  available to wrap as an MCP tool later.

### 3.3 Auth
- Lightweight **per-service API key**, implemented with FastMCP's built-in
  `StaticTokenVerifier` (`fastmcp.server.auth.providers.jwt.StaticTokenVerifier`) — a standard
  MCP client sends it as a normal `Authorization: Bearer <key>` header, so no custom header or
  hand-rolled middleware is needed. One env var per service: `MEETING_MCP_API_KEY`,
  `LOCATION_MCP_API_KEY`, `NOMNOM_MCP_API_KEY`. No OAuth2 (consistent with the phase 1 decision)
  — this is just enough to stop the MCP endpoints being fully open on the network.
- Keys are dev-only defaults in `docker-compose.yml`/`.env.example`, to be rotated for any
  real deployment.
- This API key only protects the **MCP endpoint**; the REST API the MCP server calls internally
  stays unauthenticated on `localhost` within the container (consistent with "no inter-service
  auth" from phase 1) — the MCP key is the boundary agents actually cross.

### 3.4 Per-service tool catalogs

#### `meeting-service` MCP (port 8101)
| Tool | Input | Output |
|---|---|---|
| `list_people` | — | `[{email, name}]` — lets an agent resolve names to the emails other tools need. |
| `get_person_availability` | `email, day` | `{email, name, free_slots: [{start, end}]}` — only free gaps, **not** other meetings' titles/content. |
| `check_meeting_feasibility` | `participant_emails, day, start, end` | `{feasible: bool, unavailable_people: [email]}` |
| `book_meeting` | `participant_emails, day, start, end, title` | Success: `{success: true, meeting_id, day, start, end, participant_emails}`. Failure: `{success: false, reason}` (e.g. `"<name> is not available 10:00-11:00"`). |
| `cancel_meeting` | `meeting_id` | `{success: bool, message}` — requires the exact id returned by `book_meeting`, no lookup-by-description. |

#### `location-service` MCP (port 8102)
| Tool | Input | Output |
|---|---|---|
| `list_locations` | — | `[{location_id, name, description}]` |
| `list_rooms` | `location_id` | `[{room_code, capacity}]` |
| `get_room_availability` | `location_id, day, start, duration_minutes, number_of_people` | `{available: bool, room_code: str \| null, day, start, duration_minutes}` — wraps the existing `POST /api/rooms/check-availability`, which picks the smallest suitable room by capacity; it does not expose a free-slot list for a specific `room_code`. If nothing fits, the agent simply sees `available: false` for that location/time/headcount combination. |
| `book_room` | `location_id, room_code, day, start, end, title` | Success: `{success: true, booking_id, location_id, room_code, day, start, end}`. Failure: `{success: false, reason}`. |
| `cancel_room_booking` | `booking_id` | `{success: bool, message}` |

#### `nomnom-service` MCP (port 8103)
| Tool | Input | Output |
|---|---|---|
| `get_menu` | `category` (optional) | `[{item_id, name, description, price, category}]` — the full agent-facing menu. |
| `search_product` | `query` | `{item_id, name, price, description} \| null` — fuzzy name match, for free-text requests ("a coffee"). |
| `place_order` | `location, delivery_date, items: [{item_id, quantity}], note` | Success: `{success: true, order_id, total_amount, status}`. Failure: `{success: false, reason}` (e.g. unknown item id). |
| `get_order_status` | `order_id` | `{order_id, status, delivery_date, total_amount, items: [{name, quantity}]}` — enough to understand/act on the order's state, not a full admin record. |
| `cancel_order` | `order_id` | `{success: bool, message}` — requires the exact `order_id` from `place_order`. |

All failure responses use the **reason-only** level of detail (a clear human-readable explanation,
not a list of suggested alternative slots/rooms/items — the agent/orchestrator is expected to
decide what to try next, e.g. by calling the relevant availability/search tool again). This can be
revisited later if the agent layer needs richer "try this instead" hints.

### 3.5 Required model/API changes to support this phase
Since MCP tools call the REST API (not the DB/models directly, see §3.2), every gap below must be
closed as a **new REST endpoint first**; the MCP tool is then just a thin wrapper around it.
- `meeting-service`: needs a new `DELETE /api/meetings/{meeting_id}` endpoint. `AgendaItem`
  currently has no back-reference to the `Meeting` it belongs to, so this endpoint can't yet
  clean up the per-person agenda entries it created — requires adding a `meeting_id` foreign key
  to `AgendaItem` (set when `POST /api/meetings/book` creates them) so the delete endpoint can
  remove the `Meeting` row **and** every associated `AgendaItem`.
- `location-service`: needs a new `DELETE /api/rooms/bookings/{booking_id}` endpoint.
  `RoomBooking.id` already works directly as the `booking_id` — no model change needed.
- `nomnom-service`: needs a new `PATCH`/`DELETE /api/orders/{order_id}/cancel` endpoint that sets
  `status = OrderStatus.CANCELLED` — no model change needed (`Order.order_id` already works as
  the external reference).
- None of the three services currently expose any of these endpoints — they're new REST surface,
  not just new MCP surface, and should get their own tests like the existing endpoints.

### 3.6 Package layout (per service, once implemented)
```
services/<name>-service/
├── pyproject.toml           # add `fastmcp` + `httpx` dependencies
├── Dockerfile               # updated to start both uvicorn processes
├── entrypoint.sh            # starts REST+UI app and MCP app together
└── src/<name>_service/
    ├── ... (existing api.py, ui.py, models.py, db.py, seed.py, main.py)
    └── mcp_server.py        # FastMCP instance + @mcp.tool() definitions for this service
```

### 3.7 Explicitly deferred / out of scope for this MCP phase
- No agent/orchestration code yet (Akgents layer) — this phase only stands up the MCP *servers*;
  nothing calls them as a client yet.
- No cross-service MCP tool (e.g. "plan an entire meeting with room + food in one call") — each
  MCP server only exposes its own service's tools for now.
- No "suggest alternatives" logic in booking failures (see 3.4) — revisit once an agent is driving
  these tools and real usage shows it's needed.

---

## 4. Changelog
- 2026-10-21: Initial analysis of the Java source project completed.
- 2026-10-21: MCP layer design added (section 3) — FastMCP-based, one server per service, API-key
  auth, streamable HTTP transport, agent-facing tool catalogs for meeting/location/nomnom
  services, and the model changes (`AgendaItem.meeting_id`) needed to support cancellation.
- 2026-10-21: Clarified that each MCP server calls its own service's REST API over HTTP (never
  the DB/business logic directly) — new REST endpoints (meeting cancel, room-booking cancel,
  order cancel) are required to back the corresponding MCP tools.
- 2026-10-21: Implemented the REST API prerequisites from §3.5: `DELETE /api/meetings/{id}`
  (meeting-service, with `AgendaItem.meeting_id` FK added so agenda items are cleaned up),
  `DELETE /api/rooms/bookings/{id}` (location-service, with `booking_id`/`id` now returned from
  booking/list responses so the id is actually available to cancel), and
  `POST /api/orders/{id}/cancel` (nomnom-service, idempotent — returns `success=false` rather than
  erroring on a second cancel). Added API-level tests (`tests/test_api.py` + isolated-DB
  `conftest.py`) per service. Verified end-to-end against the Docker Compose stack. The actual
  FastMCP servers are not yet implemented — next phase.
- 2026-10-21: Implemented the FastMCP servers for all three services (`mcp_server.py` per
  service), each an `httpx` client of its own REST API as designed in §3.1/§3.2. Auth uses
  FastMCP's built-in `StaticTokenVerifier` (standard `Authorization: Bearer <key>` header) rather
  than a hand-rolled header check — §3.3 updated accordingly. `location-service`'s
  `get_room_availability` tool was aligned to the REST API's actual capability (capacity/time
  check across rooms, not a per-room free-slot list) — §3.4 updated. Added `entrypoint.sh` per
  service to run both the REST+UI and MCP `uvicorn` processes in one container, updated each
  `Dockerfile` to expose both ports and run the new entrypoint, and updated `docker-compose.yml`
  with the MCP ports and `*_MCP_API_KEY` env vars (dev defaults via new `.env.example`). Added
  MCP tool tests per service using FastMCP's in-memory `Client` against an in-process
  `httpx.ASGITransport`-backed REST client (no real network server needed). Verified end-to-end
  with a real `fastmcp.Client` against the built Docker Compose stack (auth rejection, tool
  listing, and tool calls all confirmed working for all three services).
