# The services

## What it is

Underneath the agents are three ordinary web services, the kind any company already has:

| Service | What it knows | Web page and API | For agents |
|---|---|---|---|
| **meeting service** | people, their agendas, the meetings | <http://localhost:8001> | port 8101 |
| **location service** | places, their rooms, room bookings | <http://localhost:8002> | port 8102 |
| **nomnom service** | a lunch menu, and orders | <http://localhost:8003> | port 8103 |

Each has its own database, a REST API, and a small web page where a person can look things up
and book by hand. None of them knows that agents exist.

Each also runs a second, smaller door meant for agents: an **MCP server**. MCP - the Model Context
Protocol - is a standard way to offer *tools* to a model: a name, a description, typed parameters
and a result. The meeting service's MCP server, for instance, offers `list_people`,
`find_common_slots`, `book_meeting` and `cancel_meeting`.

## How it works

**An MCP server is a client of its own service.** Every tool is a few lines that call the
service's REST API and reshape the answer. It never touches the database and holds no rules of
its own: whether a room is free, or a meeting overlaps, is decided by the REST API, for every
caller alike - the web page, a script, or an agent.

**The tools are fewer than the API.** An agent gets what it needs to decide and act, and no
more:

| Service | Its tools for agents |
|---|---|
| meeting | `list_people`, `get_person_availability`, `find_common_slots`, `check_meeting_feasibility`, `book_meeting`, `cancel_meeting` |
| location | `list_locations`, `list_rooms`, `get_room_availability`, `book_room`, `cancel_room_booking` |
| nomnom | `get_menu`, `search_product`, `place_order`, `get_order_status`, `cancel_order` |

There is no tool to list every order, summarise sales, or read someone's agenda in full: free
slots, yes; the titles of other people's meetings, no. Every tool that books or cancels answers
with a clear result - it worked, with the id to refer to it later; or it did not, and why - so the
agent can relay it or try something else.

**Each agent is given exactly one of the three.** `@Scheduler` gets the meeting service's tools,
`@FacilityManager` the location service's, `@Catering` the menu. This is set in the team's
configuration (`agents/catalog/meeting-planner/agent/*.yaml`), where each agent lists the one MCP
server it may use, and a test fails if an agent gets two or two agents share one.

**A key per service.** An MCP server only answers requests that carry its service's key. The
keys are in the team's configuration as placeholders, filled from `.env` when a team is built,
and another test fails if a real value is ever written into the configuration.

## Why it is built this way

**An agent is held to its job by what it can reach, not by what it is told.** A prompt that says
*only book rooms* is a request; a model that has only the location service's tools *cannot* book a
meeting or order food, however a conversation goes. Splitting the tools by service turns the
team's division of labour into a boundary, and a test keeps it there. It also keeps each prompt
short: an agent reads the descriptions of five or six tools, not sixteen. (`design_akgents.md`
§2.)

**One set of rules, whoever calls.** Because the MCP server calls the REST API, an agent and a
person at the web page cannot get different answers to *is this room free?* There is one place
to fix a rule, and one place to test it.

**Narrow tools are safer and easier for a model.** Fewer tools means fewer wrong choices; tools
that return only what is needed leak less - a model planning a meeting has no use for the
titles of someone's other meetings. A result that says *why* it failed lets the model recover
instead of guessing.

**The services stay ordinary on purpose.** They could be any company's existing systems. The
sample shows agents added in front of services that were not built for them - and the services
learn nothing about agents, so they can be replaced by real ones.

### A lesson from a live run

The booking tools first declared their times as *time* values. The models answered with full
timestamps - `10:00:00+00:00` - though a meeting room has no time zone. The tools now take plain
`HH:MM` text, ignore an offset if one arrives and say so in their answer, and refuse anything that
is not a clock time, because a guessed hour is how a meeting ends up in the wrong slot. What a
tool's *schema* says is part of the prompt, and models read it literally.

## What it does not do

- **Authentication on the REST APIs.** The web pages and REST APIs are open; only the MCP servers
  ask for a key. The login that decides whose meetings you see lives in the team server
  ([who is asking](who-is-asking.md)), not here.
- **Share code between services.** Each is self-contained. A little logic - working out free time
  in a day - exists twice, in the meeting and the location service, by choice: they are meant to
  stand alone.
- **Know about each other.** A meeting does not know its room, a room booking does not know its
  lunch. Which belong together is kept by the team ([overview](overview.md)).

## Where in the code

| Folder | What is there |
|---|---|
| `services/<name>/src/<name>/api.py` | the REST API |
| `services/<name>/src/<name>/mcp_server.py` | the MCP server: the tools for agents |
| `services/<name>/src/<name>/models.py` | the data and the rules, such as free time in a day |
| `services/<name>/src/<name>/seed.py` | the demo people, places and menu |
| `agents/catalog/meeting-planner/tool/*_mcp.yaml` | how the team connects to each MCP server |
| `agents/tests/test_catalog.py` | the tests that keep one service per agent, and secrets out |

The design: [`design.md`](design/design.md) §3 for the MCP servers, and the first part of
[`design_akgents.md`](design/design_akgents.md) for how the team uses them.

---

*Last checked against the code: 2026-11-03, `51db19f`.*
