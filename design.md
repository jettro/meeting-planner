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

## 3. Changelog
- 2026-10-21: Initial analysis of the Java source project completed.
