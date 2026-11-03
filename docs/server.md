# The server

## What it is

The team does not run in your browser. It runs in a **team server**, and the browser is a window
onto it. The server creates a team when you start a meeting, delivers the messages you send it,
keeps every message the team sends, streams them to whoever is watching, and holds a question
open until someone answers it.

The server is akgentic's own - the open-source *community* tier of `akgentic-infra` - configured,
not written. The sample adds four small things to it: a health check over the three services,
a login, the Memory page's route, and two fixes to how messages are stored.

Two browser apps look at it:

| | Shows | At |
|---|---|---|
| **The planner** | the *meeting*: the form, the conversation, the two questions, a readable trace, your meetings, your memory | <http://localhost:8300> |
| **The akgentic console** | the *team*: its agents and how they are arranged, what each model was given, what a run cost | <http://localhost:8400> |

> **The one sentence to keep:** *the server owns execution; the browser observes it and sends
> requests.*

## How it works

### A meeting, from the browser's side

1. **Start a team.** The planner asks the server for a new team from the catalog -
   `meeting-planner` for the form, `meeting-planner-chat` for a conversation. One team is one
   meeting.
2. **Watch it.** The planner opens one socket to the team and receives every event as it
   happens: each message, who sent it to whom, and the framework's own events underneath.
3. **Send the request.** The form becomes a typed `PlanMeetingRequest`, posted as a message from
   `@Human` to `@Coordinator`. A conversation posts plain text to `@Intake` instead.
4. **Answer a question.** When the coordinator asks, the question arrives on the socket. The
   planner shows it as a card; your answer goes back as text, with the id of the question it
   answers. The server finds the question, and `@Human` - you, inside the team - turns the text
   into the typed decision the coordinator accepts, using the same code as the terminal.
5. **Read it back later.** Every event is in the server's store. The *Meetings* tab lists your
   teams; the *Trace* tab shows any of them again; a stopped team can be revived.

### What the planner has

| Tab | What it is for |
|---|---|
| **Platform** | whether the three services are up, asked every ten seconds |
| **Plan a meeting** | the form: who, which day, how long, where, and whether you attend |
| **Talk to the planner** | the conversation with `@Intake`; the questions appear inline as cards |
| **Meetings** | every meeting you arranged, its ids - meeting, room booking, lunch order - and what it waits for; cancel or resume |
| **Trace** | one meeting's messages as rows that read like a story; a switch shows the framework's events too |
| **Memory** | what is remembered for you, about you and about places, with its history |

Which question is open is read from the trace, not from what the browser remembers it typed: a
question with no answer after it is open. So a reload, a second tab or a team that was revived
all show the same thing.

### What the sample adds to the server

- **`/platform/health`** asks the three services' own `/health` and reports all three at once -
  *up*, *degraded* (it answered, badly) or *unreachable* (it did not answer), because a 503 and a
  silence have different causes. The server's own readiness says nothing about whether nomnom is
  down - and that failure would otherwise arrive several turns later, dressed as a tool error.
- **A login** - see [who is asking](who-is-asking.md).
- **`/me/memory`** - see [memory](memory.md).
- **Two fixes to the event store**, described below.

Everything else - teams, messages, the socket, questions and answers, the store, reviving a team -
is the framework's. The routes the planner uses:

| Route | What it does | Whose |
|---|---|---|
| `POST /teams` | create a team from the catalog, with the meeting it is asked to arrange | framework |
| `POST /teams/{id}/message/from/@Human/to/@Coordinator` | send a typed message: the request, or a cancel | framework |
| `POST /teams/{id}/human-input` | answer a question, as text, with the question's id | framework |
| `WS /ws/{id}`, `GET /teams/{id}/events` | the team's events, live or stored | framework |
| `GET /teams`, `GET /teams/{id}/agent-states` | your teams, and each coordinator's record | framework |
| `POST /teams/{id}/restore` | revive a stopped team | framework |
| `GET /platform/health` | the three services at once | ours |
| `/auth/...` | the login | ours |
| `GET /me/memory` | the Memory tab | ours |
| `PUT`, `DELETE /me/memory/items/{id}` | edit or delete an item you may change | ours |
| `POST`, `DELETE /me/memory/suggestions/{key}` | remember a suggestion, or *Not now* | ours |
| `POST`, `DELETE /me/memory/proposals/{id}` | accept a memory keeper's proposal, or *Not now* | ours |

### The console

The console is the framework's own front end, run beside the planner and pointed at the same
server. It is built from upstream's repository and configured by a mounted file, never copied
into this one. Log in with an API key from `.env`, and you see the team rather than the meeting:
the hierarchy as a graph, each agent's system prompt and exactly what its model was given, and
what the run cost. Each team carries the meeting it was asked to arrange as typed metadata, so the
console can name the runs in its list and filter them by title, day and place.

## Why it is built this way

**The server owns execution.** If the browser held the team, closing the tab would end the
meeting. With the server holding it, a question can wait for an hour, a second tab sees the same
state, and the terminal and the browser drive the very same team. The coordinator never blocks on
you - a question is a message out, an answer a message in - which is what makes this possible at
all.

**Configure the framework; do not rebuild it.** The community tier already runs teams, stores
their events, streams them and correlates answers with questions. The sample adds only what is
specific to it, and composes the server the way the framework documents, so an upgrade does not
silently drift from a copied composition.

**Answers are text, read on the server.** The framework's human path is text plus the id of the
question it answers. The coordinator only accepts typed decisions. Reading the text into a
decision on the server, next to the question, makes *the team is waiting for a person* a fact the
server knows - so any client, now or later, sees an open question. The other way, the browser
posting typed decisions itself, would have made each client reconstruct that, and own the shape
of a domain message. (`design_gui.md` G1, G6.)

**Two clients, each for its own question.** *What happened to my meeting?* and *what did the
model see?* are different questions with different audiences. The planner answers the first and
is the demo; the console answers the second and is the framework's. Neither has to be both.
(G15.)

### A lesson from building it

The first run over HTTP completed the whole saga - and the question about the time never showed
up in the browser. The store writes YAML with a safe dumper, which does not know a clock time
like `10:00`, so every message carrying a time was silently dropped from the store. Later the
same happened to every message carrying a plan's status, because the safe dumper does not
recognise a `str` enum as a string. Both are fixed by teaching the dumper those two types, at
startup, without reshaping the domain.

The part worth remembering: **the agents never noticed.** A message the store cannot write is
still delivered, so the team runs perfectly while its history quietly loses exactly the messages
a screen is waiting for. Only building the screen that reads the history found it.
(`design_gui.md` §8.2, §8.4.)

## What it does not do

- **Scale out.** One server, a store of files on one volume. The community tier is for one
  machine.
- **Edit a meeting from the browser.** Cancel it and plan a new one.
- **Show the shared memory in the console.** The framework serves only your own tree; the Memory
  tab has its own route for the rest.

## Where in the code

| File | What is there |
|---|---|
| `server/src/meeting_server/app.py` | the server's composition: the framework, plus what is added |
| `server/src/meeting_server/platform.py` | `/platform/health` |
| `server/src/meeting_server/yaml_types.py` | the two fixes to the event store |
| `agents/src/meeting_agents/human.py` | `@Human`: turns your text into a typed decision |
| `gui/src/api/client.ts` | every call the planner makes to the server |
| `gui/src/TeamContext.tsx`, `gui/src/hooks/useTeamStream.ts` | the one socket, and the team being watched |
| `gui/src/pages/` | the planner's screens |
| `console/` | how the console is built and configured |

The design: [`design_gui.md`](design/design_gui.md).

---

*Last checked against the code: 2026-11-03, `5e9a494`.*
