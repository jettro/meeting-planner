# Design — guardrails: checks before an agent acts

> **Status:** agreed, 2026-11-04. Nothing is built; the spike (§11) comes first. Checked against
> the installed packages: akgentic-agent 1.8.1, akgentic-llm 2.5.0, pydantic-ai-slim 2.61.0,
> openai 3.37.0, and the `decision-models` playground and its blog post (*Exploring decision
> models with Pydantic AI*, 19 and 31 October 2026).

> **The one sentence to keep:** *code checks what code can know; a decision model answers what
> needs judgement; neither is the model that acts.*

## 1. What a guardrail is for, here

Three agents in this team hold tools that change the world: `@Scheduler` books meetings,
`@FacilityManager` books rooms, `@Catering` orders food. `@Intake` writes memory. Each is a
language model choosing a tool call and its arguments. Everything that makes the team safe
today is *around* those choices, not *on* them:

| Already there | What it holds |
|---|---|
| one service per agent (`design_akgents.md` §2, a test) | `@Catering` cannot book a room, whatever it is told |
| the two questions to the person (D4, D9) | nothing is booked before a time and a lunch are approved |
| typed answers and `succeeded` | a failure is reported as a failure, never as an invented id |
| `TalkOnlyToHuman` (I7) | `@Intake` writes only to the person |
| `refusal()` in memory | no secrets, no ids in memory - a regular expression |
| the services themselves | a room too small, a slot taken, an unknown product is refused |

What nothing checks is **whether a call matches what was approved, and whether it fits what was
asked**. After you approve 10:00 on Tuesday at the Library, `@FacilityManager`'s model calls
`book_room(location_id, room_code, day, start, end, title)` with arguments it fills in itself. A
slip - another day, another location - would be booked, because the service only checks that
the room is free. `@Catering` turns *something vegetarian, no bread* into `place_order(items)`,
and nothing checks that the items are vegetarian, or that twelve sandwiches for three people is
a mistake.

A guardrail, in this design, is a check that runs **between the model's tool call and the
service**, and can stop it.

## 2. Decision models, as the blog used them

A decision model answers typed questions about a text instead of writing text: a yes/no, a pick-one,
or a score on a rubric, each with a **probability** or a **distribution**. From the post and
the playground:

- Pydantic AI runs one like any other model: `Agent(OpenAIDecisionsModel('gpt-6-luna'),
  output_type=...)`. Each field of the output type is a question - a `bool` a yes/no, a `Literal`
  or `StrEnum` a pick-one, an `IntEnum` with a description per level a rubric. The field's
  description is the question; the agent's instructions frame them all.
- It goes to OpenAI's **Decisions API**, `/v1/decisions`. `openai:gpt-6-luna` as a model string
  silently goes to chat completions instead - the trap the post found in its Logfire trace. Jev
  (`typesafe:jev-latest`) and a local `system-one:nimble` speak the same protocol; this design
  uses the OpenAI endpoint, as asked.
- The answer comes with confidence in `provider_details` - *how far the answer landed from the
  threshold*, not *how sure it is to be right*. Thresholds need calibrating on labelled cases.
- Wording matters more than the question type: a sharper description moved P(harmful) from 0.29
  to 0.95.
- It cannot explain itself in prose. The reason a guardrail gives must come from the question
  that failed, not from the model.

That is a good fit for a guardrail's judgement: *does this order fit the wish?* is a typed
question with a probability, answered in one request, cheaply, and it writes no text that could
be talked round. It is a bad fit for what code can know - a date, a headcount, a total - as the
priority table in the post shows: the levels come from the model, the arithmetic is Python.

## 3. What the code offers — verified

**pydantic-ai capabilities can stop a tool call before it runs.**
`AbstractCapability.before_tool_execute(ctx, *, call, tool_def, args)` gets the validated
arguments of every tool call. Raising `ModelRetry(message)` skips the call and tells the model
why, so it can correct itself or give up; raising `ApprovalRequired` or `CallDeferred` defers the
call for someone to decide. MCP tools go through the same hook (`tool_def.name` is the prefixed
name, `facility_book_room`).

**akgentic takes capabilities from an agent.** `BaseAgent.extra_capabilities()` returns
pydantic-ai capabilities, appended after the framework's own (the mailbox, the recipient check).
`@Intake` already uses it for `TalkOnlyToHuman`. A specialist can return a guardrail capability
the same way, with no change to akgentic.

**akgentic cannot run an agent on a decision model.** `ModelConfig.provider` is one of
`openai, openai-chat, azure, azure-chat, nvidia, google-gla, mistral, anthropic, openrouter` - no
`openai-decisions`, no `typesafe`, no `system-one`. And a `BaseAgent` always carries the
framework's tools and its structured-output routing; on a decision model, tools become a route
question (`decision.py`), so even with the provider an akgentic agent would ask *which route*
before it asked our question.

**akgentic does not handle a deferred tool call.** Nothing in `akgentic/` refers to
`ApprovalRequired`, `CallDeferred` or `DeferredToolRequests`. A guardrail can refuse today; it
cannot yet *pause* a call for a person to approve it.

**pydantic-ai has the decision models.** 2.61.0 ships `OpenAIDecisionsModel`,
`TypeSafeModel` (Jev) and `SystemOneModel`, `FallbackModel` with `DecisionHandOff`. The playground
asks for 2.62.0 because of the System One precision fix; the OpenAI route does not need it.
akgentic requires `pydantic-ai-slim>=2.58,<3`, so 2.62 is allowed when we want it.

## 4. Where a guardrail could live

| | **A. A capability on the acting agent, calling a decision model itself** | **B. akgentic learns decision models; a guard is an agent** | **C. A guard agent in the team, asked by message** | **D. In the services** |
|---|---|---|---|---|
| Where it stops a call | `before_tool_execute`, in the agent that made it | the same hook, asking the guard agent | the same hook, asking another actor | the REST API refuses |
| akgentic change | none | `openai-decisions` (and `typesafe`, `system-one`) in `ModelConfig`; a way to run an agent bare, without framework tools | none, or B for the guard's model | none |
| Sees the approval | yes - the handler knows the assignment | yes | only what the message carries | no - a service knows nothing about approvals |
| In the trace and the console | through an event of our own | as an agent, with its cost | as an agent and its messages | no |
| Cost of a check | one decision request | the same, plus a model config per guard | an actor hop inside a tool call | none |
| What it would teach | the capability seam, decision models | a framework extension | guards as team members | nothing about agents |

**Proposed: A now, shaped so that B can replace its inside later.** A needs nothing from akgentic,
sits exactly where the call is made, and knows the approval. Its weakness is that the decision
request bypasses akgentic's model config, usage and cost accounting - which is precisely what B
would add. So the decision call goes behind one small seam (`Judge`: a question in, an answer
with probability and confidence out), built today on a pydantic-ai `Agent` with
`OpenAIDecisionsModel`, and later, when akgentic has a decision provider, on that. B is worth
proposing upstream on its own - the two missing pieces are listed in §3 - but this sample should
not wait for it, or fork it. C adds an actor hop inside a tool call for no gain A lacks; D cannot
know what was approved.

## 5. The checks

Two layers, in this order, both in the same capability:

**Rules - code, always first.** What can be known exactly is never asked of a model:

| Tool | Rule | Why it matters |
|---|---|---|
| `meeting_book_meeting` | the participants, the day and the slot are the approved ones | the model fills these in; a slip books the wrong meeting |
| `facility_book_room` | the location, the day, the start and the end are the approved ones | the same, for the room |
| `catering_place_order` | the location and the date are the meeting's; the number of items is at most a set amount per person | twelve sandwiches for three is a slip, not a wish |

These need the assignment the agent is working on. The handler already has it when it calls
`act()`; it hands it to the capability for the length of that one run.

**Questions - a decision model, only where judgement is needed.** One question per tool, worded
in the catalog so it can be tuned without code:

| Tool | Question | Kind |
|---|---|---|
| `catering_place_order` | *Do these items fit the lunch wish - and what is remembered about the people's diets?* | pick-one: fits, partly, does not fit |
| `@Intake`'s `remember` | *Is this about how the person likes to meet - or is it sensitive personal data, or about something else?* | pick-one |

The second replaces nothing: `refusal()` still runs first and catches secrets and ids; the
question adds what a regular expression cannot see - *Sanne has diabetes* is health data, not a
lunch preference.

## 6. What a refusal does

- **A broken rule** raises `ModelRetry` with the rule in plain words - *"book_room was called for
  Wednesday; the approved day is Tuesday 1 December"*. The model may correct the call. A second
  refusal on the same tool in one run ends it as a failure (`succeeded=False`), so it becomes an
  `AssignmentFailed` like any other, and the plan reports what is still booked.
- **A question answered *does not fit*** above its threshold raises `ModelRetry` with the question
  and the answer - the decision model writes no reason, so the guardrail's message is the
  question it failed. *Partly* passes, and is noted. Below a confidence threshold the answer is
  treated as unsure, and passes with a note: a guardrail that blocks on noise blocks the demo.
- **Every check is an event** - `GuardrailChecked`: agent, tool, which rule or question, the
  answer, probability and confidence, passed or refused - in the trace like `MemoryApplied`, so
  *why was lunch not ordered?* has an answer.
- **When the decision endpoint is down** the question is skipped and the event says so; the rules
  still run. Failing closed would stop every lunch order on an outage of a judgement nobody
  needs to make; Q3.

## 7. Configuration

A guardrail is a catalog entry like a tool card: which rules apply, which questions with their
wording, the decision model (`gpt-6-luna` on the Decisions API) and the thresholds. The agent's
card lists it under `tools`, and the agent returns it from `extra_capabilities()`. The key is
`OPENAI_API_KEY`, already in `.env`. A team without the card runs as today.

## 8. How we will know it works

Unit tests with the decision model replaced: every rule refuses its slip and lets the approved
call through; every question's answer maps to pass, note or refuse; the endpoint failing skips
and says so. Then **the first evaluation set** - the roadmap's other item - because the blog's
lesson applies here word for word: thresholds need labelled cases. A dozen lunch wishes with
orders that do and do not fit, a dozen memory sentences that are and are not sensitive, each run
against the real endpoint, the probabilities written down, the thresholds chosen from them.

## 9. Decisions

| # | Decision | Why |
|---|---|---|
| GR1 | **A guardrail is a pydantic-ai capability on the agent that acts, in `before_tool_execute`** | It sees the call and the approval; akgentic takes capabilities already |
| GR2 | **Rules in code first, a decision model only for judgement** | Arithmetic is code; the post's priority table |
| GR3 | **The decision call goes through one seam, `Judge`, built on `OpenAIDecisionsModel`** | So akgentic support (B) can replace its inside later |
| GR4 | **First slice: the approval rules on all three booking tools, and the lunch question** | The real gap, and the clearest judgement |
| GR5 | **A refusal is `ModelRetry` with the rule or the question; twice is a failure** | The model can correct a slip; a stubborn one ends as a plan failure |
| GR6 | **Every check is a `GuardrailChecked` event in the trace** | Managing a guard means explaining it, as for memory (M9) |
| GR7 | **A guardrail is a catalog card with its wording and thresholds** | Tuned without code, and visible |
| GR8 | **An evaluation set chooses the thresholds before they are trusted** | Confidence is not accuracy |
| GR9 | **Upstream, separately: a decision provider in akgentic, and deferred tool calls** | What B and human approval need; not a blocker here |

## 10. Questions

Q1-Q5 agreed 2026-11-04 as proposed below. Q6 is still open.

- **Q1** — Which first: the lunch question, or the memory question? Proposed: lunch - it guards a
  write to a service, which is what *guardrail* means to most readers; memory second.
- **Q2** — Should a refusal ever ask the person - *the order has twelve sandwiches for three,
  order anyway?* That is `ApprovalRequired`, which akgentic does not handle yet (GR9). Proposed:
  not in this step.
- **Q3** — Fail open or closed when the decision endpoint is down? Proposed: open for questions,
  never for rules.
- **Q4** — Should `@Intake`'s incoming messages be checked too (*is this about arranging a
  meeting?*), as the blog's harmful-request predicate? Proposed: later - `@Intake` holds no
  booking tool, and the gates already stand between it and any booking.
- **Q5** — One decision request per check, or one per tool call with every question in it?
  Proposed: one per tool call; the Decisions API takes up to 200 questions in a request.
- **Q6** — Contribute the decision provider to akgentic now, beside this, or after? A design of
  its own either way.

## 11. Spike, before building

- **S1** — A capability returned from a specialist's `extra_capabilities()` sees an MCP tool call
  in `before_tool_execute`, with its prefixed name and validated arguments, and a `ModelRetry`
  from it reaches the model as a retry, not an error that ends the run.
- **S2** — A pydantic-ai `Agent` on `OpenAIDecisionsModel('gpt-6-luna')` can be awaited from
  inside that hook, in akgentic's run, and returns probability and confidence.
- **S3** — The assignment a handler is working on can reach the capability for the length of one
  `act()`, and is gone after it - so a check never reads the previous plan.

## 12. Order of work

1. The spike. 2. `Judge`, the rules and their tests. 3. The lunch question and its card. 4. The
event and the trace. 5. The evaluation set and the thresholds. 6. A live run: a slip and an
order that does not fit, both refused, and an ordinary meeting that passes. 7. The docs: a topic
page, `guardrails.md`, and the demo.

## 13. Changelog

- 2026-11-04: Proposal, from the roadmap's guardrails item, the blog post and the
  `decision-models` playground, checked against the installed akgentic and pydantic-ai.
- 2026-11-04: Agreed: GR1-GR9, and Q1-Q5 as proposed. Q6 open.
