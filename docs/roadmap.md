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

- **Guardrails.** A check before an agent books or orders - *may this lunch for twenty be ordered
  on Sanne's behalf?* The hook is known: a capability on the agent, like `TalkOnlyToHuman`, can
  look at a tool call before it runs and refuse it. Possibly with a decision model for the rules.
- **Evaluations.** Tests check the code; nothing yet measures the models' choices. The first
  cases are already written down: the three live conversations in `design_chat.md` §14, and the
  Campus memory - was it followed, and does the reason say so?

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
- Participants opening the team behind a meeting someone else arranged
  (`design_auth.md` A13).

## Not planned

- **Changing a meeting.** Cancel it and plan a new one ([durability](durability.md)).
- **A *My agenda* page.** The meeting service's own web page shows a person's agenda already.
- **A real identity provider.** OIDC would replace only the login page; the session and
  everything after it stay (`design_auth.md` A8).
