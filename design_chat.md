# Design — a team you talk to

Companion to `design_akgents.md`, `design_gui.md` and `design_durability.md`. Those documents built
a team you *fill in*: a typed `PlanMeetingRequest`, a deterministic `@Coordinator`, two gates, and
a team that is its meeting. This one adds a way to arrange a meeting **in your own words**, by
putting one new agent in front of that team: `@Intake`, an LLM agent that holds the conversation,
turns it into the request the coordinator already understands, and passes the coordinator's
questions and answers back and forth.

> **The one sentence to keep:** *the model listens; the coordinator decides; the human approves.*

**Status:** proposal. Nothing is built yet. §13 answers how places and people are found from
the person's own words; §11 lists what is still open, §12 the spike and the order of work.

---

## 1. What it is, and what it is not

A **second team**, in its own catalog namespace (`meeting-planner-chat`), whose hierarchy is the
first team's with one agent added at the top:

```
entry_point: @Human              ChannelHuman (unchanged)
└── @Intake                      BaseAgent (LLM) — new; no MCP
    └── @Coordinator             Coordinator (unchanged code; human_name: "@Intake")
        ├── @Scheduler           unchanged
        └── @FacilityManager     unchanged
            └── @Catering        unchanged
```

The goal is an **easier way to create a meeting**, not an LLM that orchestrates. So the saga stays
exactly where it is: deterministic (D1), durable (`design_durability.md` R1), one meeting per team
(R2). `@Intake` makes **one** call to the team, a typed `PlanMeetingRequest`, and from then on its
job is to relay and to explain.

What changes:
- `meeting_agents/intake.py`: the new agent, its tools and one capability (§4, §7).
- A catalog namespace with a team card, an intake entry and prompt, and a coordinator entry that
  differs from the form team's in one config value (§9).
- A **Talk to the planner** page in the browser (§8).

What does not change: `human.py`, the services, their MCP servers, and everything in the saga
that books or releases. The coordinator's difference in *this* team is configuration: it
addresses its human as `@Intake` (`CoordinatorConfig.human_name`, which exists for exactly this,
§4.2 rule 3).

What changes for both teams is §13: so that a person can describe the place and name the people
rather than know ids and email addresses, `@FacilityManager` and `@Scheduler` each gain one
read-only, typed lookup, and the coordinator gains one step in front of the slot search. It is
additive — a request with an id and email addresses runs exactly as today — and it is built first,
on the form team.

---

## 2. Why an intake agent, and not an LLM coordinator

An earlier version of this document made the coordinator itself an LLM agent with typed tools
(Appendix A). It was dropped when the goal was stated plainly: *an easier way to create meetings
using free text.* The intake agent meets that goal with far less at stake:

| | LLM coordinator (dropped) | Intake agent |
|---|---|---|
| Who sequences the bookings | the model, through six guarded tools | the deterministic coordinator, as today |
| New code with booking consequences | tool preconditions, a shared cancel driver | none — the intake only sends a request or a cancel |
| Coordinator changes | a new class | one YAML value, plus the location step both teams share (§13) |
| Model calls per meeting | conversation + ~4 during the saga | conversation + ~1 per relayed message (§6) |
| What can go wrong if the model misbehaves | a step skipped, a plan stranded at `SCHEDULED` | a wrong request — which the human still has to approve at the slot gate |

The intake agent *is* the "small intake LLM step" that `design_akgents.md` §7.1 anticipated, and
§4.2 rule 5 kept the door open for it: free text arrives as an extra message type in front of the
typed one, not as a change to it.

---

## 3. The conversation, walked through

```
@Human      -> @Intake        AgentMessage            "Design review with Sanne and Daan on 11 July, somewhere in nature, something warm for lunch"
@Intake     -> @Scheduler     FindPeopleAssignment    (tool: look_up_people — §13.2)
@Scheduler  -> @Intake        PeopleFound             one match each
@Intake     -> @Human         AgentMessage            "A design review for Sanne and Daan on 11 July, an hour, somewhere in nature. I'll find a time."
@Intake     -> @Coordinator   PlanMeetingRequest      (tool: plan_meeting, with a location wish)
@Coordinator-> @FacilityManager FindLocationAssignment  (§13.1)
@FacilityManager -> @Coordinator LocationFound        Meeting in Nature — "outdoor activities"
@Coordinator-> @Scheduler     FindSlotsAssignment
@Scheduler  -> @Coordinator   SlotsFound
@Coordinator-> @Intake        SlotApprovalRequest     (human_name is @Intake)
@Intake     -> @Human         SlotApprovalRequest     a fresh copy, addressed to @Human (§5)
@Intake     -> @Human         AgentMessage            "Three times work for both — pick one."
@Human      -> @Intake        SlotApprovalDecision    the gate, answered in the page by answers.py
@Intake     -> @Coordinator   SlotApprovalDecision    forwarded unchanged
   … the form team's saga, untouched: meeting → room → lunch …
@Coordinator-> @Intake        PlanCompleted
@Intake     -> @Human         PlanCompleted           a fresh copy, for the page's booked card
@Intake     -> @Human         AgentMessage            "Booked: 09:00–10:00 in room-a, two soups."
```

From `FindSlotsAssignment` down, this is the form team's trace line for line, and the slot
question now names the place it chose. The lunch wish travelled
inside `PlanMeetingRequest.lunch_wish`, so there was no lunch gate. Had the person not mentioned
lunch, `@Intake` would have sent `lunch_wish=None` and the coordinator's own lunch gate (D9) would
have come through the same relay.

---

## 4. `@Intake`

`IntakeAgent(BaseAgent, Akgent[IntakeConfig, IntakeState])`, re-parameterised for card coercion
(step-5 lesson). It is a `BaseAgent`, so free text from the human takes the framework's native
path — `receiveMsg_AgentMessage` → `act(message, StructuredOutput)` → a reply to `@Human` — and
its conversation is snapshotted and restored with the team (`init_llm_context`, restore phase 2e).

**Three tools**, on a `ToolCard` subclass `IntakeTools` named in its catalog entry:

| Tool | Arguments | Sends | Refused when |
|---|---|---|---|
| `look_up_people` | the names the person used | `FindPeopleAssignment` to `@Scheduler` (§13.2) | — |
| `plan_meeting` | title, participant emails (settled by a lookup), day, **a location wish or a location id**, duration (60), with lunch, lunch wish | `PlanMeetingRequest` to `@Coordinator` | a meeting has already been requested in this conversation; an email address no lookup settled |
| `cancel_meeting` | — | `CancelPlanRequest` to `@Coordinator` | nothing has been requested yet, or it is already cancelled |

`plan_meeting` builds a real `PlanMeetingRequest`, so the form's validation applies unchanged; a
validation error goes back to the model as a `ModelRetry` that quotes it, so it can correct itself
or ask the human. A refused tool is a readable result, not a crash (§7.4 lesson 4).

There is deliberately **no approval tool.** The model cannot say yes to a time slot on anyone's
behalf: the slot gate is a typed question answered by the human in the page (§5). *"The second one
please"* typed into the chat is understood by the model and authorises nothing; the prompt tells it
to point at the question on screen.

**What it remembers.** One fact beyond the conversation: the `plan_id` of the meeting it
requested, learned from the first message the coordinator sends back. `cancel_meeting` needs it.
It must survive a restore, so it belongs in state — `IntakeState(AgentState)` with
`plan_id: str = ""` — and not in an instance attribute. The step-5 lesson says replacing
`AgentState` loses the backstory; that was a *fresh* instance. Carrying the backstory across is
believed safe and is spike item 2 (§12).

---

## 5. The relay

`@Intake` has a typed handler for every message the coordinator sends its human:
`SlotApprovalRequest`, `LunchApprovalRequest`, `PlanCompleted`, `PlanFailed`, `PlanCancelled`.
Each one does the same two things, in code, with no model involved:

1. **Send `@Human` a fresh copy**: a new message with the same fields, a **new id** and
   `recipient=@Human`.
2. **Tell the model what happened** (§6), so the conversation can say it in words.

The fresh copy is not tidiness; the server requires it. `POST /teams/{id}/human-input` finds the
question by its inner id — the *first* `SentMessage` carrying it — and then routes the answer by
`message.recipient.name`, which must be a `UserProxy` (`TeamService._find_message`,
`TeamRuntime.process_human_input`). The coordinator's question is addressed to `@Intake`. Forward
that same object and the answer is refused; send a fresh copy to `@Human` and it lands on
`ChannelHuman`, which reads it with `answers.py` exactly as today.

The answer then finds its own way back. `ChannelHuman` sends a decision to `message.sender` — the
copy's sender, `@Intake` — and `@Intake` forwards it to `@Coordinator` unchanged. The decision
carries the `plan_id`, and the coordinator correlates on nothing else, so no mapping between the
two copies of the question is kept anywhere.

A **cancel from the Meetings screen** needs nothing new: it goes from `@Human` straight to
`@Coordinator` (the route names both), and the `PlanCancelled` comes back through the relay like
any other outcome.

---

## 6. Telling the model

After relaying, `@Intake` re-enters its own conversation through
`super().receiveMsg_AgentMessage` with an `AgentMessage(type="notification")` whose content is a
short rendering — *"Update: the coordinator asked the person to choose between 09:00–10:00,
10:00–11:00 and 11:00–12:00. The question is on their screen."* The framework's reply protocol for
a notification says *no reply is expected*, so the model may answer briefly or not at all.

This costs one model call per relayed message — about four in a meeting. It buys two things that
matter in a conversation: the model can answer *"which times were there again?"*, and the outcome
is said in words (*"Booked: 09:00–10:00 in room-a, two soups"*) next to the card that shows it.
Because the update is a real turn, it is in the LLM context the framework persists and restores,
so a resumed conversation still knows what was asked (spike item 3 confirms that).

---

## 7. Guarding what the model can say

Tools bound what the model can *do*. `StructuredOutput` lets it address anyone on the roster, and a
free-text message to `@Coordinator` would be dropped (it has no `AgentMessage` handler), one to a
specialist would reach that specialist's model and its write tools, and one to `@Catering` would
break D2.

So `IntakeAgent.extra_capabilities()` returns `TalkOnlyToHuman`, a pydantic-ai capability that
refuses any recipient other than `@Human` with a `ModelRetry`: *"You write only to @Human; reach
the team through your tools."* It is the project's first guardrail, on the seam found in the
review (`BaseAgent.extra_capabilities()`, after `TriageAuditCapability`).

D2 holds, and more cleanly than in the dropped design: the lunch wish reaches `@Catering` exactly as
it does from the form — as `PlanMeetingRequest.lunch_wish`, which the coordinator passes on as
data and never renders. `@Intake` hears the word "lunch" from the person, but never sees a menu,
never addresses `@Catering`, and the coordinator still never mentions lunch to anyone.

---

## 8. The prompt

A catalog entry, rendered by `Prompt.render()` — so a format string, with **no literal braces**
(§7.4 lesson 1), and a test renders it. A first draft:

```text
You help the person you are talking to, @Human, arrange one meeting. You write
only to @Human. The team that books it is reached only through your tools, and
what it does comes back to you as a message that starts with "Update:".

To request the meeting you need:
- a title
- who takes part. Names are fine: look them up with look_up_people. If a name
  matches more than one person, or nobody, ask which person they mean. Never
  guess an email address.
- the day, as YYYY-MM-DD
- what kind of place, in their own words - "somewhere quiet", "a natural
  environment". The team chooses the location that fits, and the person sees
  the choice before anything is booked. Only if they name a location id, pass
  that instead.
- how long it lasts, in minutes - 60 if nobody says
- whether they want lunch, and if so what kind, in their own words; if lunch
  never came up, leave it undecided and the team will ask
Ask for what is missing, a few things at a time. Before calling plan_meeting,
say in one sentence what you are about to request, so a mistake can be caught
while it is free.

Then call plan_meeting once. The team finds times both people are free and asks
the person to choose one in a question that appears on their screen. You cannot
choose a time for them and you cannot approve one: if they tell you their
choice, point them at the question.

This conversation arranges one meeting. Once it has been requested, a different
day, people or place means a new conversation - say so plainly. To call the
meeting off, use cancel_meeting; it releases everything that was booked.

Rules:
- Never say anything is booked until an update says so. Never invent an id.
- Times are local clock times, HH:MM, with no timezone.
- If a tool refuses, read why, and tell the person in plain words.
- If an update says something failed, say what failed and what is still booked,
  and offer cancel_meeting.
- Pass what the person says about lunch on unchanged. You do not choose food
  and you do not know the menu.
```

---

## 9. The page and the catalog

**Talk to the planner** (`/chat`), beside *Plan a meeting*:

- **Transcript:** the `AgentMessage`s between `@Human` and `@Intake`, as bubbles; the gate
  questions as inline cards (`GatePrompt` reused); the outcome as the same booked/failed/cancelled
  card the plan page shows.
- **The input box always talks to `@Intake`**:
  `POST /teams/{id}/message/from/@Human/to/@Intake` with `{content}`. Gates are answered on their
  card, through `/human-input`, as today. Keeping the two apart is what keeps "the human approves"
  structural: nothing typed in the conversation can answer a gate.
- **A question belongs to the human only if it is addressed to `@Human`.** The trace of a chat run
  holds each question twice — the coordinator's copy to `@Intake` and the relay's copy to
  `@Human` — and only the second is ever answered. `TeamContext` therefore reads open gates and
  outcomes from messages whose recipient is `@Human`. In the form team every question already is,
  so this is one filter added and nothing changed there.
- **New conversation** starts a new team, as *Plan another* does. One `TeamProvider`, one socket
  (G8), now also knowing which namespace it started.
- **Meetings** lists chat runs too (filter on both namespaces). *Resume* opens `/chat` for a chat
  run and `/plan` for a form run, chosen by `catalog_namespace`; as today it restores the team
  first. *Cancel* works unchanged (§5).

**The catalog**, `agents/catalog/meeting-planner-chat/`: `team/team.yaml` (the hierarchy above;
`message_types` starting with `akgentic.agent.messages.AgentMessage`, so free text is the default
for any client — the console included), `agent/intake.yaml`, `prompt/intake_prompt.yaml`,
`tool/intake_tools.yaml`, and `agent/coordinator.yaml` with `human_name: "@Intake"`. The three
specialists: cross-namespace refs if `load_team` resolves them (it pre-loads one namespace — spike
item 4), otherwise copies plus a test asserting each equals the form team's apart from
`namespace`. No `metadata_type`: nothing about the meeting is known when a conversation starts
(G18), and the Meetings screen reads the title from the coordinator's state anyway.

The console on :8400 works with this team for free — its input sends `AgentMessage`s, which is what
`@Intake` takes — so it is the first live client, before our page exists.

---

## 10. Decisions proposed

| # | Decision | Rationale |
|---|---|---|
| I1 | **A second team: `@Intake` (LLM) in front of the unchanged deterministic coordinator** | The goal is easier input, not LLM orchestration. D1, R1 and R2 stay exactly as they are |
| I2 | **The coordinator is configured, not changed: `human_name: "@Intake"`** | The swap point §4.2 rule 3 kept for this. Every question and outcome reaches the intake without a line of coordinator code |
| I3 | **`@Intake` makes one call to the team, a typed `PlanMeetingRequest`; and one more to cancel** | The model parses; the code decides. Its tools have no booking consequence the human has not yet to approve |
| I4 | **No approval tool; gates are answered on their card, never in the conversation** | The human approves, structurally. Understanding "the second one" is not authorising it |
| I5 | **The relay is code: a fresh copy to `@Human`, a new id, the answer forwarded unchanged** | Required by how `/human-input` finds and routes a question (§5), and it keeps the model out of the path a decision takes |
| I6 | **Each relayed message is also a notification turn for the model** | So the conversation can explain what is on screen and say the outcome in words; durable because it is a real turn |
| I7 | **`TalkOnlyToHuman`: the intake addresses no one but `@Human`** | Free text to the coordinator is dropped, to a specialist reaches its write tools, to `@Catering` breaks D2 |
| I8 | **One conversation, one meeting** | `design_durability.md` R2. A different day after the request means a new conversation; the prompt says so, and confirms the request before sending it while a mistake is still free |
| I9 | **The page reads only messages addressed to `@Human` as gates and outcomes** | A chat trace holds each question twice; only the relay's copy is the human's |
| I10 | **A place is described, and `@FacilityManager` chooses it — as a saga step before the slots, shown on the slot question** | The judgement stays with the agent that holds the locations (as D9 did for the menu), and approving the slot approves the place (§13.1) |
| I11 | **People are named, and `@Scheduler` looks them up — as a typed lookup `@Intake` makes before requesting anything** | A name cannot be matched loosely; an ambiguous one is a question for the person, which is conversation (§13.2) |
| I12 | **Both lookups are typed assignments, never the free-text door** | The pattern every assignment follows, with a typed answer and a way to say *no*; free text would reach a model holding `book_*` with nothing to frame it |

---

## 11. Questions open

**Q1 — how are people and locations found?** **Answered in §13**: the person describes the place
and `@FacilityManager` chooses it (I10); the person names the people and `@Scheduler` looks them
up (I11); both as typed assignments (I12). The options it replaces — ids and emails typed by hand,
a free-text question to a specialist, a directory panel in the page — are kept here only as the
fallbacks if a live run shows a lookup misbehaving.

**Q2 — "make it Thursday" after the request.** I8 answers it with a new conversation. A gentler
alternative is a *New conversation from this one* button that seeds the new intake with a summary of
the old request. Worth it after the first live use, not before.

**Q3 — which model for `@Intake`?** `gpt-6-luna`, like the specialists, with the same 240s timeout
(§7.6); move up a tier only if live runs show it requesting things the person did not say.

**Q4 — narrate every relay, or only the outcome?** I6 narrates all of them (~4 calls). The cheaper
option narrates only the outcome and lets the cards speak for the gates, at the cost of a model
that does not know what times were offered.

---

## 12. Implementation order

0. **Spike, written down as it goes**, against the installed packages:
   1. a fresh `SlotApprovalRequest` sent by `@Intake` to `@Human` is answered through
      `/human-input`, the decision reaches `@Intake` as `message.sender`, and forwarded it books the
      meeting;
   2. `IntakeState(AgentState)` keeps the backstory (the system prompt is still there) and
      survives a stop and restore with its `plan_id`;
   3. a notification turn synthesised through `super().receiveMsg_AgentMessage` is in the LLM
      context after a restore;
   4. whether `load_team` resolves cross-namespace refs;
   5. which capability hook `TalkOnlyToHuman` belongs on;
   6. that neither lookup (§13) ever makes a specialist book anything, across a handful of live
      runs with deliberately vague wishes and names.
1. **The location wish, on the form team first (§13.1).** The messages and validator, the
   coordinator step, `@FacilityManager`'s handler and prompt, the recorded fields, the location
   on the slot question, and a *describe the place* field on the form. Saga tests with a stub
   facility manager — chosen, nothing fits, a request with an id unchanged — and one live run.
2. **The people lookup (§13.2)**: `@Scheduler`'s handler and prompt, with tests for one match,
   several and none.
3. `intake.py`: `IntakeAgent`, `IntakeState`, `IntakeTools`, `TalkOnlyToHuman`, the relay handlers.
   Unit tests for the tools' refusals and for the relay (fresh id, recipient, forwarded decision)
   with no model at all.
4. The `meeting-planner-chat` catalog and prompt; catalog tests — the card loads, the prompt
   renders, `@Intake` has no MCP, the coordinator differs only in `human_name`, the specialists
   match the form team's.
5. A saga test in the style of `test_saga.py`: stub specialists, the real coordinator, `@Intake`
   with `act()` replaced by a script that calls `plan_meeting` — then both gates through the relay,
   `PlanCompleted` relayed; and a restore in the middle, as `server/tests/test_restore.py` does.
6. **A live run through the console on :8400**, before any GUI.
7. The page, the recipient filter in `TeamContext`, Meetings over both namespaces, Resume by
   namespace. `make gui-build` is the check.
8. A live run in the browser: a conversation to a booked meeting; one parked at the slot gate,
   stopped, resumed, finished; one cancelled from Meetings.
9. README, the status lines, the changelog.

---

## 13. The place and the people, in the person's own words (the answer to Q1)

A person does not think in location ids, and the first version of this idea, in an earlier
project, never asked for one: it asked *what kind of place* — an office, something sporty,
somewhere in nature. The locations already carry exactly that kind of description
(`list_locations` → *Meeting in Nature*: "Combine meetings with outdoor activities";
*GreenSpace*: "Eco-friendly meeting rooms surrounded by plants"; *Library*: "Quiet spaces for
focused meetings"; …).

The answer to Q1 follows the rule D9 already set for lunch: **the judgement stays with the agent
that holds the information.** `@Catering` is the only agent that sees the menu, so it turns
"something vegetarian" into items. `@FacilityManager` is the only agent that sees the locations, so
it turns "a natural environment" into a location. `@Scheduler` is the only agent that sees the
address book, so it turns "Sanne and Daan" into email addresses. Nothing is copied out of the
agent that owns it, and no agent gains a second MCP server.

Both lookups are **typed assignments** — the pattern every other assignment follows (message in,
`act(message, OutputType)`, typed answer out, `succeeded` and `reason` so a failure can be said)
— not the free-text door of the old option (b), which would hand the request to a model holding
`book_*` with nothing to frame it.

### 13.1 The place: a step in the saga, before the slots

`PlanMeetingRequest` takes **either** a `location_id` **or** a `location_wish` — the person's
words — and its validator refuses both or neither. When the wish is what arrived, the coordinator's
saga gains one step in front of the slot search:

```
@Coordinator     -> @FacilityManager  FindLocationAssignment(plan_id, wish, headcount)
@FacilityManager -> @Coordinator      LocationFound(plan_id, location_id, name, reason)
@Coordinator     -> @Scheduler        FindSlotsAssignment …            (as today)
```

Three choices, each for a reason:

- **In the saga, not in the intake.** The coordinator already owns the order of the steps; this is
  one more, and the form team gets it too — a *describe the place* field next to the location
  picker. It can be built and tested on the form team before `@Intake` exists (§12 step 1).
- **Before the slots, not after.** The slot question then names the place and why it was chosen —
  *"Design review at Meeting in Nature (outdoor activities — closest to 'a natural environment')
  on 11 July"* — so approving the slot approves the place. Choosing after the slot would fit
  room availability better, but then nobody would ever approve the location, and the human
  decides is the rule. `SlotApprovalRequest` gains optional `location_name` and `location_reason`,
  empty for a request that named an id, so the form team's question is unchanged when no wish
  was given.
- **"Nothing fits" is an answer.** An honest *no* from the facility manager (`succeeded=False`, a
  reason) fails the plan before anything is booked, like a refused slot. A loose match is allowed
  but must say why, and the reason is on the slot question, where rejecting costs nothing.

`@FacilityManager` gains one handler, `receiveMsg_FindLocationAssignment`, answering with a typed
`ChosenLocation(succeeded, location_id, name, reason)`, and a paragraph of prompt: match the wish
against the descriptions, use `facility_list_rooms` to skip a location that cannot seat
`headcount`, copy the id exactly as listed, book nothing. Whether a room is free *at the chosen
time* is still checked when the room is booked, as it is today for a location named by id.

`MeetingPlan` records `location_wish`, `location_name` and `location_reason` beside
`location_id`, for the same reason it records `lunch_wish`: the record should say what was asked
for, not only what was chosen. The Meetings screen shows them.

### 13.2 The people: a lookup the intake makes, in the conversation

People are different in one way that matters: a wrong guess is a meeting in a stranger's
agenda. A description can be matched loosely; a name cannot. So the people lookup is not a saga
step but a **question `@Intake` asks before it requests anything**, because the follow-up —
*"there are two Daans — de Vries or Jansen?"* — is conversation, which is the intake's job.

`@Intake` gets a third tool, `look_up_people(names)`, which sends a typed
`FindPeopleAssignment(names)` to `@Scheduler`. The scheduler gains one handler answering
`PeopleFound(matches)` — for every name asked, every person in `list_people` it could be, with
their email — and replies to its sender, which is `@Intake`, as every scheduler handler already
replies to its sender. The intake then decides in code what the model sees: one candidate per name
is settled; none or several becomes a question for the person. Only settled email addresses ever
reach `plan_meeting`.

This is the one place `@Intake` addresses a specialist, and it does so through a tool and a typed
assignment, never through `StructuredOutput` — so `TalkOnlyToHuman` (I7) is untouched. The
scheduler's model still has `meeting_book_meeting` in reach, as it does for every slot search; the
assignment's framing (*"look these names up with list_people; book nothing"*) and the typed answer
are what keep it to a lookup, exactly as they do for `FindSlotsAssignment`.

### 13.3 What this changes, honestly

The intake design promised that the specialists and the coordinator stay as they are. This answer
to Q1 breaks that promise, deliberately and additively:

| Where | What is added | What is not changed |
|---|---|---|
| `messages.py` | `FindLocationAssignment`, `LocationFound`, `FindPeopleAssignment`, `PeopleFound`; `PlanMeetingRequest.location_wish`; optional location fields on `SlotApprovalRequest` | every existing message, field and default |
| `coordinator.py` | one step before the slot search, taken only when a wish arrived | everything after it — the saga, R1–R8 |
| `specialists.py`, `outputs.py` | one read-only handler and one output type each on `@FacilityManager` and `@Scheduler` | every booking and release handler |
| prompts | a paragraph each for the two specialists | the rest |
| `plan.py` | three recorded fields beside `location_id` | the derived status, `compensations()` |

Nothing that books or releases changes, and a request that names a `location_id` and email
addresses runs exactly as today — which is what makes it safe to build first, on the form team.

---

## Appendix A: the dropped design — an LLM coordinator

The first version of this document made the coordinator itself a `BaseAgent` that read free text
and sequenced the saga through six typed tools (`propose_meeting`, `ask_to_approve_slot`,
`book_meeting`, `book_facilities`, `cancel_plan`, `current_plan`), each guarded by a precondition
read from the plan's derived status, with the slot gate kept typed and a capability limiting whom
the model could address.

It was a sound design for a different goal — showing an LLM coordinate specialists — and it is
dropped because that is not the goal. What it found is kept: the specialists' contract (replies to
the sender, except `@FacilityManager` addressing `@Coordinator` by name), the reason a free-text
message to a specialist is dangerous (it reaches the specialist's model and its write tools), and
the guardrail seam. What made it heavy was that the model held the order of irreversible steps;
the intake design leaves that with the code that already holds it.

---

## Changelog

- 2026-10-28: Initial design — an LLM coordinator with typed tools (now Appendix A).
- 2026-10-28: **Rewritten around an intake agent**, after the goal was stated as *an easier way to
  create meetings in free text*, and on top of `design_durability.md` (the team is the meeting).
  `@Intake` holds the conversation and makes one typed call; the deterministic, durable
  coordinator is unchanged and configured to treat `@Intake` as its human. Reading the server's
  human-input path showed the relay cannot forward a question as-is — the answer is routed by the
  question's recipient, which must be a `UserProxy` — so the relay sends the human a fresh copy
  (I5), and the page treats only messages addressed to `@Human` as the human's (I9).
- 2026-10-28: **Q1 answered (§13, I10–I12).** The person describes the place — "a natural
  environment" — and `@FacilityManager`, the only agent that sees the locations and their
  descriptions, chooses one as a saga step before the slot search, so the slot question names the
  place and approving it approves both. The person names the people, and `@Scheduler` looks them
  up for `@Intake`, which asks the person when a name is ambiguous. Both are typed assignments, the
  same rule D9 set for lunch: the judgement stays with the agent that holds the information. This
  adds one read-only handler to each of two specialists and one step to the coordinator — nothing
  that books or releases — and it is built first, on the form team.
