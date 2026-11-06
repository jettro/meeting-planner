# Documentation

Start with the [overview](overview.md): what the sample is, its pieces, one meeting from start to
finish, and the ideas behind it - in one page.

## Where to go next

| If you want to | Read |
|---|---|
| understand what the sample shows, and why it is built this way | the [overview](overview.md), then a topic below |
| learn from what went wrong while building it | the [lessons](lessons.md) |
| see it working, or present it | the [demo script](demo.md) |
| run it | the [README](../README.md), *Quick start* |
| know what is next | the [roadmap](roadmap.md) |
| know why a decision was made, or what was turned down | its design, in [`design/`](design/) |

## Topics

Each topic page says what something is, how it works, why it is built this way, what it does not
do, and where to find it in the code. They describe what is there now.

| Topic | What it covers | |
|---|---|---|
| [Memory](memory.md) | four kinds of memory, chosen by code, the journal, the Memory page, the limits | |
| [The services](services.md) | three services, their MCP servers, one service per agent | |
| [The team](team.md) | the agents, the plain-code coordinator, the booking saga, the two questions | |
| [The server](server.md) | the team as a service, the planner, the console, the trace | |
| [Durability](durability.md) | the team is the meeting: revive, cancel, resume | |
| [The conversation](conversation.md) | `@Intake`, a team you talk to, what the model may say | |
| [Who is asking](who-is-asking.md) | the login, what is yours, the organiser | |
| [Lessons](lessons.md) | what building it taught us, across all steps | |

## The designs

Every step was designed before it was built, and the design kept: what was proposed, what was
decided and why, what was measured and dropped. They are history - each opens with its status
and what replaced parts of it - and they are where the decision ids in the code (`D1`, `M18`)
come from.

| Design | Step |
|---|---|
| [`design.md`](design/design.md) | the old Java project, the three services and their MCP servers |
| [`design_akgents.md`](design/design_akgents.md) | the agent team (D) |
| [`design_gui.md`](design/design_gui.md) | the team server, the planner and the console (G) |
| [`design_cancel.md`](design/design_cancel.md) | cancelling a meeting |
| [`design_durability.md`](design/design_durability.md) | the team is the meeting (R) |
| [`design_chat.md`](design/design_chat.md) | a team you talk to: `@Intake` (I) |
| [`design_auth.md`](design/design_auth.md) | who is asking: the login (A) |
| [`design_memory.md`](design/design_memory.md) | what the team remembers (M) |
| [`design_docs.md`](design/design_docs.md) | this documentation (W) |
| [`design_guardrails.md`](design/design_guardrails.md) | guardrails: checks before an agent acts (GR) - agreed, not built: a `@Guard` agent, and a check on what `@Intake` is asked |
