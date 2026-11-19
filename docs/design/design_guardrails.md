# Design — guardrails: checks before an agent acts

> **Status:** agreed, 2026-11-06: option B, and a check on what `@Intake` is asked. The version
> agreed on 2026-11-04 chose option A; §13 says what changed and why. **Built: the rules** (§12
> step 2, §14). **Proposed, 2026-11-19, not agreed:** `@Guard` now, on a language model, checking
> both what `@Intake` is asked and what it answers - §15; it changes GR3, GR4, GR9 and GR11.
> Re-checked on 2026-11-19 after the upgrade to akgentic-framework 2.19.1, the latest on PyPI
> (akgentic-agent 1.8.1, akgentic-llm 2.5.2, akgentic-team 1.12.0, akgentic-infra 1.17.0,
> pydantic-ai-slim 2.58.0, openai 3.37.0); first checked on akgentic-llm 2.5.0 with
> pydantic-ai-slim 2.61.0. Also the draft
> akgentic design `DECISION_MODELS_DESIGN.md` (2026-11-04, in the akgentic-framework worktree
> `akgents-jev-models-support-505f8f`, not committed) and the `decision-models` playground with
> its blog post (*Exploring decision models with Pydantic AI*, 19 and 31 October 2026).

> **The one sentence to keep:** *code checks what code can know; a decision model, run by akgentic
> as a member of the team, answers what needs judgement; neither is the model that acts.*

## 1. What a guardrail is for, here

Three agents in this team hold tools that change the world: `@Scheduler` books meetings,
`@FacilityManager` books rooms, `@Catering` orders food. `@Intake` writes memory and requests
meetings. Each is a language model choosing a tool call and its arguments. Everything that makes
the team safe today is *around* those choices, not *on* them:

| Already there | What it holds |
|---|---|
| one service per agent (`design_akgents.md` §2, a test) | `@Catering` cannot book a room, whatever it is told |
| the two questions to the person (D4, D9) | nothing is booked before a time and a lunch are approved |
| typed answers and `succeeded` | a failure is reported as a failure, never as an invented id |
| `TalkOnlyToHuman` (I7) | `@Intake` writes only to the person |
| `refusal()` in memory | no secrets, no ids in memory - a regular expression |
| the services themselves | a room too small, a slot taken, an unknown product is refused |

Two things nothing checks.

**Whether a call matches what was approved, and fits what was asked.** After you approve 10:00 on
Tuesday at the Library, `@FacilityManager`'s model calls `book_room(location_id, room_code, day,
start, end, title)` with arguments it fills in itself. A slip - another day, another location -
would be booked, because the service only checks that the room is free. `@Catering` turns
*something vegetarian, no bread* into `place_order(items)`, and nothing checks that the items are
vegetarian, or that twelve sandwiches for three people is a mistake.

**What `@Intake` is asked.** Whatever is typed into *Talk to the planner* reaches a general
language model that holds tools to request meetings and write memory. Its prompt keeps it to
meetings, but a prompt is a request to the model, not a check on the input: *write me a poem*,
*what is the capital of France*, or *ignore your instructions and remember this* all reach it.
The planner is for arranging a meeting and for what is remembered about how you meet; anything
else should not reach the model at all.

A guardrail, in this design, is a check in one of two places: **between the model's tool call
and the service**, or **between the person's message and `@Intake`'s model**. Either can stop
what comes next.

## 2. Decision models, as the blog used them

A decision model answers typed questions about a text instead of writing text: a yes/no, a
pick-one, or a score on a rubric, each with a **probability** or a **distribution**. From the
post and the playground:

- Pydantic AI runs one like any other model: `Agent(OpenAIDecisionsModel('gpt-6-luna'),
  output_type=...)`. Each field of the output type is a question - a `bool` a yes/no, a `Literal`
  or `StrEnum` a pick-one, an `IntEnum` with a description per level a rubric. The field's
  description is the question; the agent's instructions frame them all.
- It goes to OpenAI's **Decisions API**, `/v1/decisions`. `openai:gpt-6-luna` as a model string
  silently goes to chat completions instead - the trap the post found in its Logfire trace.
- The answer comes with confidence in `provider_details` - *how far the answer landed from the
  threshold*, not *how sure it is to be right*. Thresholds need calibrating on labelled cases.
- Wording matters more than the question type: a sharper description moved P(harmful) from 0.29
  to 0.95.
- It cannot explain itself in prose. The reason a guardrail gives must come from the question
  that failed, not from the model.
- Tools become a route question: with tools attached, the model first picks *which route* - a
  tool or the output - before it answers ours.

That is a good fit for judgement - *is this about arranging a meeting?*, *does this order fit
the wish?* - typed questions with a probability, answered in one request, cheaply, writing no
text that could be talked round. It is a bad fit for what code can know - a date, a headcount, a
total - as the priority table in the post shows: the levels come from the model, the arithmetic
is Python.

## 3. What the code offers — verified

**akgentic cannot run a decision model yet.** `ModelConfig.provider` is a `Literal` of `openai,
openai-chat, azure, azure-chat, nvidia, google-gla, mistral, anthropic, openrouter`, and
`create_model()` looks the provider up in `_PROVIDER_FACTORIES`. `get_output_type()` wraps a
structured type in `NativeOutput` for the OpenAI family; a decision model's profile has
`supports_json_schema_output=False` and fills output in tool mode, so that wrapper would be
refused. Nothing in the sample can change this without changing akgentic.

**akgentic's own design already plans it.** `DECISION_MODELS_DESIGN.md` (draft, 2026-11-04):
phase 1 adds the providers `openai-decisions` and `system-one` and the raw output type; phase 2
keeps the confidence and distributions (`RunOutcome`, `DecisionDetails`); phase 4 a
`DecisionAgent` - no tools, typed answer, routing in Python, an event; phase 5 a guard capability
and a decision tool. Phase 1 waits on **akgentic-llm#182**, which moves pydantic-ai to `>=2.65`.
On 2026-11-19 #182 is still an open pull request on GitHub; akgentic-llm 2.5.2 (3 November) is
the latest release, and its provider list and `get_output_type()` are unchanged.

**The retry change, and why the upgrade went back on it.** pydantic-ai 2.60 changed how a retry is
stored: a tool's `ModelRetry` became a `tool-return` with `outcome='retried'`, an output retry a
`retry-feedback` part. akgentic's `ContextManager` knows only the older part kinds (`context.py`,
`PartKind`). On akgentic-llm 2.5.0 with pydantic-ai 2.61, as this project ran until 2026-11-19, a
refusal showed in akgentic's tool events as `ToolReturnEvent(success=True)`, and the first output
retry would have ended the run with `Unrecognized part_kind 'retry-feedback'`
(akgentic-llm#180, closed by the pin below).

akgentic-llm 2.5.2 pins `pydantic-ai-slim~=2.58.0`, so the upgrade moved pydantic-ai **back**,
from 2.61.0 to 2.58.0 - the only 2.58 release. There a tool's `ModelRetry` is a `retry-prompt`
part again, and akgentic reports it as `ToolReturnEvent(success=False)`: a refusal is a failed
call in the framework's events, and no part kind can end the run. One gap is left: 2.58 already
has `ToolReturnPart.outcome` (`success | failed | denied | interrupted`), and akgentic reports
every `tool-return` as a success whatever its outcome. The rules never produce one.
`GuardrailChecked` (§6) stays what says *why* a call was refused. When #182 lands, pydantic-ai
moves to `>=2.65` and the retry is a `tool-return` again; the test that drives a real run
(`test_guardrails.py`) accepts either.

**A `BaseAgent` always carries the framework's tools** - `TeamTool` (`hire_members`,
`fire_members`) and `MailboxTool` (`read_mailbox`) are inserted in `on_start`. On a decision
model they would become a route question. A capability's **`prepare_tools`** may return an
empty list; *"filtering also blocks tool execution"*, and the model is offered no tools, so no
route question.

**A `BaseAgent` can forget.** `clear()` empties its conversation; the system prompt is rebuilt on
the next run. A guard that clears before every check judges each one alone.

**The confidence is reachable before akgentic keeps it.** A capability's `after_model_request`
receives the `ModelResponse`, so its `provider_details` - confidence, distributions - can be read
in the guard itself until phase 2 makes it akgentic's job.

**One actor can ask another and wait.** `proxy_ask(address, timeout=...)` calls a method on
another actor and blocks until it returns - the framework itself asks the orchestrator this way.
It is a Pykka call, not a message: it does not go through `send()`, so it is not a message in the
trace.

**`@Intake` sees the person's text in one place.** It does not override
`BaseAgent.receiveMsg_AgentMessage`, where the person's free text arrives and becomes one
`act()`. The team's updates reach its model through `_tell_the_model`, which calls the parent's
handler directly. An override of `receiveMsg_AgentMessage` therefore sees exactly the person's
messages, before any model does. A message `@Intake` sends `@Human` from code is a planner line in
the chat like any other (`ChatPage.tsx`, `conversation()`).

**pydantic-ai capabilities can stop a tool call before it runs.**
`before_tool_execute(ctx, *, call, tool_def, args)` gets the validated arguments of every tool
call, MCP tools included (`tool_def.name` is the prefixed name, `facility_book_room`). Raising
`ModelRetry(message)` skips the call and tells the model why. `BaseAgent.extra_capabilities()`
adds capabilities to an agent; `@Intake` already uses it for `TalkOnlyToHuman`.

**akgentic does not handle a deferred tool call.** Nothing in `akgentic/` refers to
`ApprovalRequired`, `CallDeferred` or `DeferredToolRequests`. A guardrail can refuse; it cannot
yet *pause* a call for a person to approve it.

## 4. Where a guardrail could live

| | **A. A capability on the acting agent, calling a decision model itself** | **B. akgentic learns decision models; a guard is an agent** | **C. A guard agent asked by message** | **D. In the services** |
|---|---|---|---|---|
| Where it stops a call | `before_tool_execute` | the same hook, asking `@Guard`; and `@Intake`'s handler | the same hook, by message | the REST API refuses |
| akgentic change | none | the decision providers (phase 1) | none, or B for the guard's model | none |
| Sees the approval | yes | the rules do - they stay in the acting agent | only what the message carries | no |
| In the trace and the console | an event of our own | an agent with its model and cost, plus the event | an agent and its messages | no |
| What it would teach | the capability seam | a framework extension, used by a real team | guards as team members | nothing about agents |

**Chosen: B.** It means three things.

1. **akgentic runs decision models** - phase 1 of akgentic's own design, contributed upstream,
   not forked and not patched in the sample. The sample needs nothing beyond phase 1.
2. **The judgement is a member of the team, `@Guard`**: a `BaseAgent` on
   `openai-decisions:gpt-6-luna`, offered no tools, cleared before each check, answering typed
   questions. The console shows it as an agent, with its model and what its checks cost, as it
   shows the others. It is shaped like akgentic's planned `DecisionAgent` so that it can become
   one.
3. **The rules stay in code, in the acting agent.** They need the approval, which `@Guard` does
   not have, and they are arithmetic. That part of A remains, and needs no decision model, so it
   can be built before akgentic is ready.

`@Guard` is asked by a direct call with a timeout (`proxy_ask`), not by message: a tool call
that is waiting cannot wait for a reply message, and the framework asks its orchestrator the same
way. What that costs: the question is not a message in the trace, so the `GuardrailChecked` event
says what was asked and answered.

What B costs compared with A: it waits for upstream (#182, then phase 1), and until a release
carries phase 1 the sample pins akgentic-llm to a git revision. What it gives: the decision call
goes through akgentic's model config, retrying HTTP client, usage and pricing, and the guard is
visible in the console - the gap A had to hide behind a seam.

## 5. The checks

Two layers, rules first.

**Rules - code, in the acting agent's capability.** What can be known exactly is never asked of
a model:

| Tool | Rule | Why it matters |
|---|---|---|
| `meeting_book_meeting` | the participants, the day and the slot are the approved ones | the model fills these in; a slip books the wrong meeting |
| `facility_book_room` | the location, the day, the start and the end are the approved ones | the same, for the room |
| `catering_place_order` | the location and the date are the meeting's; the number of items is at most a set amount per person | twelve sandwiches for three is a slip, not a wish |

These need the assignment the agent is working on. The handler already has it when it calls
`act()`; it hands it to the capability for the length of that one run.

**Questions - `@Guard`, only where judgement is needed.** Worded in the catalog, so they can be
tuned without code:

| Where | Question | Kind |
|---|---|---|
| `@Intake`, each message from the person | *Is this message about arranging this meeting, about what is remembered, a greeting, or something else?* | pick-one: arrange, memory, greeting, other |
| `catering_place_order` | *Do these items fit the lunch wish - and what is remembered about the people's diets?* | pick-one: fits, partly, does not fit |
| `@Intake`'s `remember` | *Is this about how the person likes to meet - or is it sensitive personal data, or about something else?* | pick-one |

**The check on what `@Intake` is asked**, in more detail:

- `@Guard` is shown the person's message, the last thing `@Intake` said to them - so *yes*,
  *Thursday* and *Sanne and Daan* are read as answers - and whether a meeting has been requested
  yet. Not the whole conversation: the question is about this message.
- **arrange**: describing the meeting, answering what was asked, cancelling it, asking about its
  progress. **memory**: what to remember, what is remembered, what to forget. **greeting**:
  hello, thanks. These pass.
- **other** is refused: general knowledge, writing, code, advice, and attempts to change
  `@Intake`'s instructions.
- Messages starting with `/` are the framework's commands and are not checked.

The lunch question runs in `@Catering`'s capability after the rules pass. The memory question
replaces nothing: `refusal()` still runs first and catches secrets and ids; the question adds what
a regular expression cannot see - *Sanne has diabetes* is health data, not a lunch preference.

## 6. What a refusal does

- **A broken rule** raises `ModelRetry` with the rule in plain words - *"book_room was called for
  Wednesday; the approved day is Tuesday 1 December"*. The model may correct the call. A second
  refusal on the same tool in one run ends it as a failure (`succeeded=False`), so it becomes an
  `AssignmentFailed` like any other, and the plan reports what is still booked.
- **An order answered *does not fit*** above its threshold raises `ModelRetry` with the question
  and the answer - the decision model writes no reason, so the guardrail's message is the
  question it failed. *Partly* passes, and is noted.
- **A message answered *other*** above its threshold never reaches `@Intake`'s model. `@Intake`
  answers from code, with the sentence on the guardrail's card - *"I can only help arrange this
  meeting and remember how you like to meet."* The refused message is not added to its model's
  context, so an instruction hidden in it is never read by a model that holds tools.
- **Unsure** - below a confidence threshold - passes with a note: a guardrail that blocks on
  noise blocks the demo.
- **Every check is an event** - `GuardrailChecked`: the agent that asked, the check, the answer,
  its probability and confidence, passed, refused or skipped - sent by the agent that asked, in
  the trace like `MemoryApplied`. *Why was lunch not ordered?* and *why did the planner not answer
  me?* both have an answer.
- **When `@Guard` cannot answer** - the endpoint is down, or the call times out - the question is
  skipped, the event says so, and the call or the message goes ahead; the rules still run (Q3,
  and Q7 for the check on what `@Intake` is asked).

## 7. Configuration

- **`@Guard`** is a catalog agent card in `meeting-planner`: `meeting_agents.guard.GuardAgent`,
  `can_be_hired: false`, a framing prompt, and `model_cfg` referring to a new
  `meeting-planner.guard_model` - `provider: openai-decisions`, `model: gpt-6-luna`. Both teams
  list it once, by reference, as they list the specialists. The key is `OPENAI_API_KEY`, already
  in `.env`.
- **A guardrail is a catalog card**: which rules or which question, its wording and options, its
  thresholds, and for `@Intake` the refusal sentence. The acting agent's card lists the cards it
  uses; a team without them runs as today.
- **The dependency**: `akgentic-llm` from a git revision that has phase 1, until a release has it;
  then back to PyPI.

## 8. How we will know it works

Unit tests with `@Guard` replaced by a fake: every rule refuses its slip and lets the approved
call through; every answer maps to pass, note or refuse; a timeout skips and says so; a refused
message is answered from code and is not in `@Intake`'s context. Then **the first evaluation
set** - the roadmap's other item - because the blog's lesson applies here word for word:
thresholds need labelled cases. For `@Intake`: a dozen each of requests, answers that only make
sense in context, memory questions, greetings, off-topic questions and attempts to change the
instructions. For lunch: a dozen wishes with orders that do and do not fit. Each run against the
real endpoint, the probabilities written down, the thresholds chosen from them.

## 9. Decisions

| # | Decision | Why |
|---|---|---|
| GR1 | **Rules are a pydantic-ai capability on the acting agent, in `before_tool_execute`** | They need the approval; akgentic takes capabilities already |
| GR2 | **Rules in code first, a decision model only for judgement** | Arithmetic is code; the post's priority table |
| GR3 | *(revised in §15)* **Judgement is a team member, `@Guard`: a `BaseAgent` on an akgentic decision provider, offered no tools, cleared before each check, asked by a direct call with a timeout** | Option B: the decision call is akgentic's - config, retries, cost, the console |
| GR4 | *(revised in §15)* **First slice: the rules on the three booking tools, `@Guard`, and the check on what `@Intake` is asked; the lunch question next, memory after** | The rules need no upstream; the intake check is the clearest judgement and the plainest use of B |
| GR5 | **A refusal of a tool call is `ModelRetry` with the rule or the question; twice is a failure** | The model can correct a slip; a stubborn one ends as a plan failure |
| GR6 | **Every check is a `GuardrailChecked` event, sent by the agent that asked** | Managing a guard means explaining it, as for memory (M9); and the call itself is not a message |
| GR7 | **A guardrail is a catalog card with its wording and thresholds** | Tuned without code, and visible |
| GR8 | **An evaluation set chooses the thresholds before they are trusted** | Confidence is not accuracy |
| GR9 | *(revised in §15)* **Upstream first: akgentic-llm#182, then phase 1 of akgentic's decision design; the sample pins a git revision until it is released** | B needs it; a fork or a patch in the sample would teach the wrong thing |
| GR10 | **An off-topic message never reaches `@Intake`'s model; `@Intake` answers from code** | A check that lets the text reach the model anyway checks nothing |
| GR11 | *(dormant, §15.4)* **`@Guard` reads confidence from the response itself, in `after_model_request`, until akgentic keeps it (phase 2)** | Thresholds need it now; phase 2 replaces it |

## 10. Questions

Answered on 2026-11-04 and still standing: **Q2** - no asking the person mid-booking yet
(`ApprovalRequired`, which akgentic does not handle); **Q3** - when the decision endpoint is down,
skip the questions, never the rules; **Q5** - one decision request per check, with every question
of that check in it. **Q1** is now GR4. **Q4** is answered by this revision: yes, check what
`@Intake` is asked. **Q6** is answered by B: the decision provider goes to akgentic now.

Q7-Q10 agreed on 2026-11-06 as proposed below.

- **Q7** — When `@Guard` cannot answer, should a message to `@Intake` pass (as Q3), or be
  refused? Proposed: pass, with the event saying so - `@Intake`'s prompt still keeps it to
  meetings, and an outage of the check should not stop the planner.
- **Q8** — Is *what do you remember about Sanne?* a memory question? Proposed: yes for the people
  and places of this meeting - what `@Intake` may already be shown - and *other* for anyone else.
- **Q9** — Who takes phase 1 upstream, and in which order? Proposed: #182 first, as reviewed;
  then phase 1 as its own akgentic-llm pull request from the `akgents-jev-models-support` work;
  the sample's spike runs on that branch.
- **Q10** — akgentic's design (§6.4) would make a `BaseAgent` on a decision model fail at start
  when its output is `StructuredOutput`. `@Guard` never uses `StructuredOutput`, but is a
  `BaseAgent`. Proposed: word that check on the output type actually used, or let `@Guard`
  become the first `DecisionAgent` when phase 4 lands - and say so in akgentic's design.

## 11. Spike, before building

- **S0** — The sample runs on an akgentic-llm with #182 and an `openai-decisions` provider,
  pinned by git revision, on pydantic-ai `>=2.65`; the existing tests still pass, and a tool's
  `ModelRetry` shows as a retry, not a success, in akgentic's tool events.
- **S1** — A capability returned from a specialist's `extra_capabilities()` sees an MCP tool call
  in `before_tool_execute`, with its prefixed name and validated arguments, and a `ModelRetry`
  from it reaches the model as a retry, not an error that ends the run.
- **S2** — `@Guard` starts in a team on `openai-decisions:gpt-6-luna`; `prepare_tools` returning
  nothing leaves no route question; after `clear()` a check sees no earlier one; `act()` with a
  pick-one output returns the answer; `after_model_request` sees the probabilities and confidence;
  the console shows its usage and cost under `@Guard`.
- **S3** — The assignment a handler is working on reaches the capability for the length of one
  `act()`, and is gone after it - so a check never reads the previous plan.
- **S4** — `@Guard` can be asked, with a timeout, from `@Intake`'s handler and from inside
  `before_tool_execute` (through `asyncio.to_thread`, so the acting agent's loop is not blocked); a
  timeout comes back as *skipped*; two agents asking at once do not deadlock.
- **S5** — The refusal: an override of `receiveMsg_AgentMessage` that answers from code shows in
  the chat as the planner's line, and the refused message is not in `@Intake`'s context - neither
  in the run after it nor after the team is restored.

## 12. Order of work

*Steps 1, 3, 4 and 5 are replaced by §15.8 if §15 is agreed.*

1. **Upstream**, outside this repository: #182, then phase 1 in akgentic-llm.
2. **Meanwhile, the rules** - they need no decision model: the capability, S1 and S3, the tests,
   the event and its row in the trace. *Done, 2026-11-06 - §14.*
3. **The spike** S0, S2, S4, S5, once a phase 1 branch exists.
4. **`@Guard`**, its card and `guard_model`, its tests.
5. **The check on what `@Intake` is asked**: the override, the card, the refusal, the evaluation
   set and its thresholds.
6. **The lunch question**, its card and its evaluation set.
7. **A live run**: an off-topic question and an attempt to change the instructions, both
   refused; an ordinary conversation that passes; a booking slip and an order that does not fit,
   both refused.
8. **The docs**: a topic page, `guardrails.md`, the demo and the lessons; and back to akgentic
   from PyPI when a release carries phase 1.

## 13. Changelog

- 2026-11-04: Proposal, from the roadmap's guardrails item, the blog post and the
  `decision-models` playground, checked against the installed akgentic and pydantic-ai.
- 2026-11-04: Agreed: GR1-GR9, and Q1-Q5 as proposed. Q6 open.
- 2026-11-06: Revised at the person's request. **Option B instead of A**: the judgement moves to a
  team member, `@Guard`, on an akgentic decision provider; the rules stay in code (GR1, GR3, GR9
  changed; the `Judge` seam is gone, `@Guard` replaces it). **A check on what `@Intake` is
  asked**, first in the order of work (Q4 reversed; GR4 changed; GR10 new). Found while checking:
  akgentic's own draft design for decision models, which this now builds on; the pydantic-ai 2.60
  retry change that installed akgentic misreports (§3); the `prepare_tools`, `clear()`,
  `after_model_request` and `proxy_ask` seams B uses (GR11 new). Spike S0, S2, S4, S5 new or
  rewritten; Q7-Q10 new.
- 2026-11-06: Agreed: GR1-GR11, and Q7-Q10 as proposed.
- 2026-11-06: The rules built (§14).
- 2026-11-19: Re-checked after upgrading to akgentic-framework 2.19.1 (llm 2.5.2, team 1.12.0,
  infra 1.17.0). Still true: no decision provider in `ModelConfig`, the `NativeOutput` wrapper,
  nothing handles `ApprovalRequired` / `CallDeferred` / `DeferredToolRequests`, #182 open, and the
  capability hooks GR1 and GR11 use (`before_tool_execute`, `after_model_request`,
  `prepare_tools`) all present in pydantic-ai 2.58. Changed: pydantic-ai went back from 2.61 to
  2.58 with akgentic-llm's pin, so a refusal is a `retry-prompt` part and a failed call in
  akgentic's events, no longer a success (§3). agent, core, tool and catalog did not change, so the
  `clear()`, `proxy_ask`, `TeamTool` / `MailboxTool` and `receiveMsg_AgentMessage` facts stand.
  Live: one meeting with lunch, three checks *passed*.
- 2026-11-19: Proposed (§15): `@Guard` built now on a language model, its own model card the swap
  to a decision model later; two checks on the chat - the person's message and `@Intake`'s answer
  - after a demo where `@Intake` recommended restaurants. GR12-GR15 and Q11-Q14 new; GR3, GR4,
  GR9 revised, GR11 dormant.

## 14. What was built: the rules

- **`meeting_agents/guardrails.py`**: `BookingRules`, the card - `max_items_per_person` (3: a
  main, a side, a drink) and `refusals_per_run` (2, GR5); `ApprovalRules`, the capability, one
  instance per run (`for_run`) so refusals are counted per run; the three rules; and
  `GuardrailChecked`, with `outcome` first so the trace's one-line summary shows it.
- **The approval is `current_message()`** - the assignment whose handler is running, set and
  cleared by the framework. No state is handed to the capability, so nothing can leak between
  plans (S3, answered by the framework rather than by our code). A booking call during any other
  assignment - a lookup, a cancel - is refused, even with the right values.
- **Clock readings are read as the services read them**: `10:00:00+00:00` is 10:00, or the rules
  would refuse a call the service books correctly.
- **The three specialists list `booking_rules`** in their cards; `SpecialistAgent.extra_capabilities()`
  turns it into `ApprovalRules`. The trace needed no change: it already shows any
  `meeting_agents` event as a row.
- **Spike S1**, in pydantic-ai 2.61 and again live over MCP: the hook sees `facility_book_room`
  with validated arguments (a `date` for `day` from a function tool); a `ModelRetry` reaches the
  model as a `tool-return` with `outcome='retried'` carrying the rule (on pydantic-ai 2.58, since
  2026-11-19, as a `retry-prompt` part carrying it - same text, same correction); an exception from the hook
  ends the run, and `attempt()` reports it as an `AssignmentFailed`.
- **Live, 2026-11-06**: an ordinary meeting with lunch - three checks, all *passed*. Then a lunch
  wish of *twelve soups, we are very hungry* for two people: `@Catering` ordered 12, the rule
  refused (*12 items for 2 people; at most 3 per person (6)*), the model ordered 6, and its summary
  told the person why: *6 soups; 12 could not be met because the order limit is 3 items per
  person.* Both meetings were cancelled and every booking released.
- **Tests**: `test_guardrails.py` (21: each rule, the capability, and two real pydantic-ai runs),
  S3 and the card wiring in `test_specialists.py`, the catalog and team-card tests widened to a
  card that gives the model no tool.

## 15. Revision, 2026-11-19: `@Guard` on a language model, now

> **Status:** proposed, 2026-11-19. Not agreed yet. Nothing in it is built.

### 15.1 Why now, and why not wait

akgentic still cannot run a decision model: #182 is open, and phase 1 has not started (§3,
re-checked 2026-11-19). Meanwhile the gap in §1 has shown itself in a demo. Two turns in *Talk to
the planner*:

> **Person:** Can you help me find a nice restaurant around amsterdam
> **Planner:** Sure - are you looking to arrange a meeting at a restaurant around Amsterdam? If
> so, what should the meeting be called, who else should attend, and what day should it be?
> **Person:** do not need a meeting, just search for a good restaurant
> **Planner:** Got it - no meeting. I can't run a live restaurant search, but a few well-regarded
> Amsterdam options are De Kas, ... If you share your budget and preferred cuisine, I can narrow
> it down.

The first answer is right: the question could be about a meeting, and the planner asks. The
second answer is the gap. The person said there is no meeting, and the model answered anyway,
from general knowledge, and offered to go on. Its prompt keeps it to meetings; the model read
that prompt and went past it.

So `@Guard` is built now, on the **language model the team already uses**
(`gpt-6-luna` through `meeting-planner.default_model`), shaped so that a decision model can
replace that model later without changing anything around it. The rules (§14) are unchanged.

### 15.2 What is checked: the message, and the answer

| | Checks | Catches in the example | Misses |
|---|---|---|---|
| **The person's message**, before `@Intake`'s model | *is this about the meeting?* | the second message | a message that passes, followed by an answer that drifts |
| **`@Intake`'s answer**, before it reaches the person | *does this answer help with something else?* | the second answer | an off-topic message that reaches the model (an instruction in it is read by a model with tools) |
| **Both** | both | both | - |

Proposed: **both**, each for what only it can do.

- **The message check is the gate (GR10, kept).** An off-topic message never reaches the model
  that holds the tools, so an instruction hidden in it is never read there. `@Guard` sees the
  message, the last thing the planner said, and whether a meeting has been requested - so *yes*,
  *Thursday* and *do not need a meeting* are read as answers to what was asked. Pick one:
  **arrange**, **memory**, **greeting**, **other** (§5, unchanged).
- **The answer check is the backstop.** It catches the model drifting on a message that rightly
  passed, which the message check cannot see. `@Guard` sees the answer and the message it
  answers. Pick one: **meeting** (about arranging this meeting, its progress, what is remembered,
  or saying what the planner can and cannot do) or **other** (gives help with anything else).
  Refusing to help counts as *meeting*: *"I can only help with meetings"* is a good answer.
- **Which answers.** Every output of `@Intake` addressed to `@Human`, including the short notes
  it writes after an *Update:* turn. The model can drift there too, and the notes are short.

Cost: two extra model calls per turn in the chat - one per message, one per answer - each a
short prompt with one structured answer. The form team is not affected: nothing in it is free
text.

### 15.3 What a refusal does

- **A message answered *other*** is answered from code with the card's sentence - *"I can only
  help arrange a meeting and remember how you like to meet."* - and is not added to the model's
  context (GR10, §6, unchanged).
- **An answer judged *other*** is sent back to the model once with `ModelRetry` and the card's
  instruction - *"Your answer helps with something other than this meeting. Say briefly that you
  can only help arrange the meeting."* - the same hook and the same retry rule `TalkOnlyToHuman`
  uses (`after_output_validate`, `can_retry`). When no retry is left, the answer is replaced by
  the card's sentence. The off-topic answer never reaches the person.
- **When `@Guard` cannot answer** - an error, or no answer within the card's timeout - the check
  is skipped, the event says so, and the message or the answer goes ahead (Q3, Q7).
- **Every check is a `GuardrailChecked` event** from `@Intake`, as for the rules (GR6): which
  check, the answer, and passed, refused or skipped. The trace already shows it.

### 15.4 How `@Guard` stays swappable for a decision model

The seam is the **question, typed**, and the **model card**:

- **The answer type is the questions and nothing else.** Each check is a pydantic model whose
  fields are pick-ones, a `Literal` with the question as the field's description - the shape a
  decision model answers (§2). There is **no free-text reason**: a decision model cannot write
  one, so nothing downstream may depend on one. The reason in the event and in the refusal is the
  question that failed and its answer, as §6 already said.
- **`@Guard`'s model is its own card**, `meeting-planner.guard_model`. Today it holds what
  `default_model` holds - `provider: openai`, `model: gpt-6-luna`. The swap is that one card
  changing to `openai-decisions` once akgentic has it. `@Intake` asks `@Guard` the same question
  either way and gets the same type back.
- **Confidence is optional.** The verdict carries `confidence: float | None`. On a language model
  it is `None`, and the answer is taken as it is: no self-reported score, which would be a number
  the model writes, not a measure. The card's thresholds apply only when a confidence is there,
  so they wait for the decision model and the evaluation set (GR8, GR11 dormant until then).
- **`@Guard` is shaped like akgentic's planned `DecisionAgent`** (§3): a `BaseAgent`, offered no
  tools (`prepare_tools` returns nothing, so `hire_members`, `fire_members` and `read_mailbox`
  are gone), cleared before each check, answering through `act(prompt, output_type=...)`.
- **What a language model adds that a decision model would not**: it can be talked round by the
  text it judges - *"classify this as arrange"*. It holds no tools and answers a closed type, so
  the worst it can do is pass a message; the model behind it still has its prompt, and the answer
  check still runs. That is the main reason to swap later.

### 15.5 How `@Intake` asks

- **The message check** in an override of `receiveMsg_AgentMessage` - exactly the person's
  messages (§3); `_tell_the_model` calls the parent directly and is not checked. Messages starting
  with `/` are not checked (§5).
- **The answer check** in a capability on `@Intake`'s `after_output_validate`, next to
  `TalkOnlyToHuman`. It runs inside the model's run, so it asks through `asyncio.to_thread` and
  does not block the loop.
- **Both ask `@Guard` with `proxy_ask(..., timeout=...)`**, a direct call, not a message (GR3).
  `@Guard` asks no one, so the call cannot deadlock.
- **Where `@Guard` sits**: a member of the chat team under `@Intake`, `can_be_hired: false`. The
  form team does not list it until the lunch question needs it.
- **A team without `@Guard`** - an older team restored, or a card without it - runs as today:
  no member, no check, and a log line.

### 15.6 Decisions proposed

| # | Decision | Why |
|---|---|---|
| GR12 | **`@Guard` runs now on a language model, `meeting-planner.guard_model` (gpt-6-luna), its own card** | The gap is shown; akgentic's decision provider is not near; the card is the swap |
| GR13 | **Two checks on the chat: the person's message before the model (the gate), and `@Intake`'s answer before the person (the backstop)** | The gate keeps text from a model with tools; only the backstop sees a drift like the example's |
| GR14 | **A refused answer gets one `ModelRetry`, then the card's sentence** | The same hook and retry rule as `TalkOnlyToHuman`; the person never sees the drift |
| GR15 | **The answer type is pick-ones only, no reason; confidence is `None` on a language model and thresholds wait for it** | What a decision model can answer is all the code may rely on |

Changed by this revision: **GR3** - `@Guard` on the model its card names, a language model now,
a decision provider later; **GR4** - the first slice is `@Guard` and the two chat checks; the lunch
question next, memory after; **GR9** - upstream is no longer first: the decision provider is a
later swap of one card, and the sample stays on akgentic from PyPI; **GR11** - kept, but dormant
until there is a confidence to read. GR10 stands.

### 15.7 Questions

- **Q11** — Both checks, or only the message? Proposed: both (§15.2). Message only halves the cost
  and still catches the example's second turn, but not an answer that drifts on its own.
- **Q12** — Check every answer to `@Human`, or only answers to a message the person typed?
  Proposed: every answer - the *Update:* notes are written by the same model.
- **Q13** — A short reason from the language model, for the trace only, while it is not a decision
  model? Proposed: no (GR15) - it would be the one thing that changes at the swap, and the
  question and its answer already say why.
- **Q14** — The two sentences: the refusal *"I can only help arrange a meeting and remember how
  you like to meet."* and the retry instruction in §15.3. Proposed as written; both live on the
  card and can be tuned without code.

### 15.8 Spike, then order of work

- **S2'** (S2 on a language model) — `@Guard` starts in the chat team on `guard_model`;
  `prepare_tools` returning nothing leaves it no tools; after `clear()` a check sees no earlier
  one; `act()` with the pick-one type returns it; the console shows its usage and cost.
- **S4, S5** as in §11: the call with a timeout from the handler and from the capability, a timeout
  comes back as *skipped*; a refused message is answered from code and is not in the context,
  after a restore either.

1. The spike, S2', S4, S5.
2. `@Guard`: `GuardAgent`, its card and `guard_model`, the two answer types; tests with a fake.
3. The message check: the override, the card, the refusal, the event.
4. The answer check: the capability, the retry, the replacement, the event.
5. The evaluation set, small: the example above as its first case; a dozen each of requests,
   answers in context, memory questions, greetings, off-topic questions, attempts to change the
   instructions, and drifting answers. Measured as accuracy - no thresholds yet.
6. A live run: the example refused at its second turn; an ordinary conversation that books a
   meeting with no refusal.
7. The docs: `conversation.md` and its *Last checked* line, and a lesson if the run teaches one.
