# Roadmap

Each step was designed before it was built; the designs are in [`design/`](design/). This page
says what is done, what is next, and what is not planned.

## Done

| Step | What it gave the sample | Read |
|---|---|---|
| The services | three services, each with an MCP server for agents | [the services](services.md) |
| The team | four agents, a plain-code coordinator, two questions to you | [the team](team.md) |
| The server and the browsers | the team as a service, the planner, the console, the trace | [the server](server.md) |
| Cancelling | a saga that undoes itself: order, room, meeting | [durability](durability.md) |
| Durability | the team is the meeting: revive, resume, cancel | [durability](durability.md) |
| The conversation | `@Intake`, a team you talk to | [the conversation](conversation.md) |
| Who is asking | the login, what is yours, the organiser who attends | [who is asking](who-is-asking.md) |
| Memory, phases 1 and 2 | yours, about people, about places; the Memory tab with history | [memory](memory.md) |
| Memory, phase 3a | edit and delete on the Memory tab, and what you said about others | [memory](memory.md) |
| Memory, phase 3b | suggestions: a team for a group, a meal for a kind of meeting, kept only on your yes | [memory](memory.md) |
| Memory, phase 3c | the memory keeper: proposes merges, retirements and rewordings of Mine; you accept or refuse | [memory](memory.md) |
| The documentation | these pages | [`design_docs.md`](design/design_docs.md) |

## Next

Each with a design first.

- **Guardrails** - designed in [`design_guardrails.md`](design/design_guardrails.md). A check
  between an agent's tool call and the service: rules in code that the call matches what was
  approved, and a decision model (`gpt-6-luna` on OpenAI's Decisions API) for judgement - *does
  this order fit the lunch wish?*
- **Evaluations.** Tests check the code; nothing yet measures the models' choices. The first
  cases are already written down: the three live conversations in `design_chat.md` §14, and the
  Campus memory - was it followed, and does the reason say so?

### Smaller, for the planner

- **The trace beside the conversation.** *Talk to the planner* shows the conversation, and the
  trace of the same team is a click away on *Trace*. Showing it beside the chat - a panel next to
  the messages, the same rows the Trace tab draws from the one socket the page already holds -
  would let you watch the team work while you talk to it.
- **Addresses you can reload and bookmark.** The planner keeps its place in memory, not in the
  address bar (`MemoryRouter`, `design_gui.md` G9), so a reload starts at *Platform* and a page
  cannot be bookmarked. G9 was chosen before a stopped team could be revived; now that a team is
  the meeting and comes back on request (`design_durability.md`), a URL per tab - and per
  meeting, as `/trace/<team>` already is - can work. nginx already serves `index.html` for every
  path. It needs a design note that withdraws G9.

## Open questions

- Should a failed plan release what it already booked by itself, or only report it?
  (`design_cancel.md` §8.3)
- *Make it Thursday* after the request: a new conversation now; a *new conversation from this one*
  button later? Which model for `@Intake`, and how much of the relay to narrate?
  (`design_chat.md` §11, Q2-Q4)
- Where should lunch preferences apply, when is search worth it, and how long is a memory kept?
  (`design_memory.md` §9, Q2, Q3, Q5)
- Should the memory keeper tidy the shared lists too - what is said about people and places - and
  whose yes would accept a change there? (`design_memory.md` §10.6, Q14)
- Should a request carry a preferred time, so *design reviews in the morning* can be remembered
  and the scheduler offers those slots first? (`design_memory.md` §10.7, Q17)
- Participants opening the team behind a meeting someone else arranged
  (`design_auth.md` A13).

## Not planned

- **Changing a meeting.** Cancel it and plan a new one ([durability](durability.md)).
- **A *My agenda* page.** The meeting service's own web page shows a person's agenda already.
- **A real identity provider.** OIDC would replace only the login page; the session and
  everything after it stay (`design_auth.md` A8).
