# From solo agents to AI teams - talk plan (draft 2)

DevPulse meetup No. 7, Thu 3 December 2026, Zwolle. Slot 19:00, next talk 20:00:
**about 45 minutes of talk and demo, 10 minutes of questions.** Audience: developers after dinner,
mixed experience with agents. Free meetup, so: a story first, code second.

> **Status:** draft 2, now reconciled with both decks (in `talk/source/`, not committed). The
> decks themselves are not changed.

## What the abstract promises

The talk has to deliver these, so each must have a clear moment:

| Promise | Where in the talk |
|---|---|
| how agents communicate, share state and coordinate with people | parts 3 and 5 |
| collaboration patterns, before the engineering | part 3 |
| how do you define responsibilities? | part 3 |
| which state belongs to each agent? | part 3, part 5 |
| how do you involve people? | part 3, demo 1 |
| akgents, the Actor Model, *why we chose it* | part 5 |
| a live demo: arrange a meeting, find a room, lunch | parts 4 and 6 |
| when a team is worth the extra complexity | part 8 |

## What the two decks bring

### *Bring a crew to do your job* (Keynote, March 2025, 49 slides)

The order, recovered from the file:

| Slides | Section | Keep? |
|---|---|---|
| 1-2 | title, disclaimer (images are Midjourney), about me | keep, update |
| 3-8 | *the dullest activity of the day: planning a meeting*; the other solutions; *Let AI help us*; what it needs to do (availability, room, coffee and lunch, confirmation); balloon images and the unconvinced man | **keep - this is the opening** |
| 9 | *Being a good agent*: remember, listen, talk, take action | maybe, as one line |
| 10-17 | LLM basics: static knowledge (*Jettro from The Owl House*), system prompt, context, memory, a tool; *LLM recap: that is still not fun* | drop - replaced by the new deck's six slides; keep the Owl House answer as a joke |
| 18-27 | the augmented LLM, a ReAct prompt written by hand, notebooks | drop - frameworks do this now |
| 28-36 | reasoning models, deepseek vs phi4, the allowance question | drop - a different talk |
| 37 | *Your agent becomes overloaded*: one agent, three tools | **keep - the turn to teams** |
| 38 | the crew: Personal Assistant, Schedule Manager, Facility Manager, Food Manager | **keep - see below** |
| 39-42 | multi-agent architectures: parallel, two diagram-only variants (probably supervisor and hierarchy), group chat | **keep - the patterns** |
| 43 | microservice architecture | **keep - the software analogy** |
| 44 | *Akgents - Actor Model meets Agents*: Hewitt, Bishop, Steiger 1973; an actor keeps state, acts, sends messages, spawns others | **keep** |
| 45 | the actor diagram: Human Proxy, Facility Manager, meeting and lunch request and response | keep, redraw with today's names |
| 46-47 | the demo (*Hier Akgent demo laten zien*); *Now I am having fun* | the demo becomes the real sample |
| 48 | where to go from here: CrewAI, AutoGen, Bedrock, OpenAI Assistant, smolagents | drop or refresh - dated |

### *From solo agents to AI teams - playful* (pptx, 6 slides)

One diagram that builds up the anatomy of an agent, each slide with a playful title and a single
takeaway line:

1. *So... what's my job?* - a goal and a finish line.
2. *I have a plan. Probably.* - the LLM, prompting, the execution loop: *the model proposes, the
   software runs the loop.*
3. *Less talking. More doing.* - tools, MCP: *tools turn proposed actions into actual work.*
4. *Wait, what were we doing?* - context: state, conversation, memory, knowledge base.
5. *Who gave it the delete button?* - boundaries: business rules, guardrails, human approval:
   *the runtime enforces the boundaries.*
6. *Now everybody has opinions.* - you, messages and routing, agents A/B/C with their own state,
   tools and checks: *independent agents, shared objective.*

This replaces slides 10-36 of the old deck: the same ground in six slides, at the level a 2026
audience needs. It also gives the talk its vocabulary - **goal, loop, tools, context,
boundaries** - which part 3 can reuse for the team.

### The story the two decks already tell together

**The crew on slide 38 of the old deck is the meeting planner's team.** In March 2025 it was a
drawing: Personal Assistant, Schedule Manager, Facility Manager, Food Manager. Today it runs:
`@Intake`, `@Scheduler`, `@FacilityManager`, `@Catering` - plus one the drawing did not have, a
coordinator that is plain code. That is the spine of the talk:

> *Last year I drew a crew. This year it works - and the interesting part is everything the
> drawing did not show.*

And the old deck's running gag carries it: the unconvinced man under the balloons (*he does not
look convinced yet*) is convinced at the end (*now I am having fun*).

## The one sentence

*A team works for the same reason a good software design works: clear responsibilities, narrow
interfaces, state with an owner - and a human who decides.*

And the line from the sample to keep coming back to:
**the model listens, the coordinator decides, the human approves.**

## The story, in eight parts

| # | Part | Min | Slides from |
|---|---|---|---|
| 1 | The dullest job of the day | 3 | old 1-8 |
| 2 | One agent, built up - and overloaded | 6 | new 1-5, old 37 |
| 3 | Bring a crew: patterns and four questions | 10 | new 6, old 38-43, new slides |
| 4 | Demo 1: the crew at work | 8 | live |
| 5 | Underneath: agents as actors | 7 | old 44-45, new slides |
| 6 | Demo 2: the team you talk to | 5 | live |
| 7 | Beyond the demo | 4 | new slides |
| 8 | When is a team worth it? | 2 | new, old 47 |

### 1. The dullest job of the day (3 min) - old deck 1-8

*What is the dullest activity of a working day?* Planning a meeting. The usual solutions (call
everybody, send an email, ask your PA if you are so lucky), then *let AI help us*, and what it
needs to do: availability, a room, lunch, a confirmation. The man under the balloons is not
convinced.

Optional laugh: the old slide where a plain LLM *knows* Jettro - from *The Owl House*.

### 2. One agent, built up - and overloaded (6 min) - new deck 1-5, old 37

The six-slide build of the new deck, using the meeting as the running example:
goal → loop → tools → context → boundaries. On *Who gave it the delete button?*, tell one real
failure from building the sample (`docs/lessons.md`): a room booked titled *"Meeting"*, or the
seven-hour slot. Then old slide 37: one agent with the scheduling, facility and lunch tools -
*your agent becomes overloaded*: one prompt, every tool, every risk.

### 3. Bring a crew (10 min) - new 6, old 38-43, new slides

- **New slide 6** (*now everybody has opinions*) opens it.
- **Old 43, microservices:** we split software for the same reasons - responsibility, narrow
  interfaces, independent change. Agents are no different.
- **Old 39-42, the patterns:** parallel, supervisor, hierarchy, group chat. Name which the sample
  uses (supervisor with a hierarchy under it, and a front door) and which it turned down (group
  chat, a model as router - harder to trust, test and explain).
- **Old 38, the crew** - with the reveal that it now exists.

Then the four questions, the anatomy from part 2 applied to a team (one growing diagram):

| Question | Answer in the sample | Anatomy word |
|---|---|---|
| **Who does what?** | one agent, one service; **code where the answer is known, a model where judgement is needed** - the coordinator is plain code | goal, tools |
| **How do they talk?** | typed messages, not chat; a model's answer is a type too | loop |
| **Who keeps what?** | each agent its own state; the coordinator's record *is* the meeting; memory lives outside the team | context |
| **Where is the human?** | `@Human` is a team member; a question is a message out, an answer a message in; nothing booked before you said yes | boundaries |

The surprise for most of the room: *not every team member needs a model.*

### 4. Demo 1: the crew at work (8 min)

`docs/demo.md` act 1, shortened:
1. Plan a meeting in the form - Sanne and Daan, *somewhere quiet*.
2. First gate: the time, with the place and **why**. Nothing booked yet.
3. Second gate: lunch in your own words - *something vegetarian, no bread*.
4. The confirmation, then the **trace**: twenty rows that read like a story - part 3, visible.
   Flip on *Framework events* as the bridge to part 5.
5. Sanne's agenda in the meeting service: it really happened.

### 5. Underneath: agents as actors (7 min) - old 44-45

The *why akgents*, kept to what explains the concepts - not a framework tour.

- **Old 44, Hewitt 1973:** an actor keeps its own state, acts, sends messages, creates other
  actors. Map it on part 3: responsibility = actor, communication = message, state = the actor's
  own. A fifty-year-old idea that fits agents remarkably well.
- **Old 45, redrawn** with today's names: `@Human`, `@Coordinator`, `@FacilityManager`,
  `@Catering`, and the real message types.
- **Why it fits**, one example each:
  - *waiting for a human costs nothing* - no thread is blocked on the gate; the answer can come a
    day later;
  - *durable* - every message is kept, so a stopped team is revived, and a cancel goes to the team
    that made the meeting;
  - *observable* - typed messages give the trace and the console for free;
  - *a team is configuration* - team, agents, prompts and tools are YAML.
- **Code, briefly** (two or three snippets, large font): a message type; the specialist's shape -
  *assignment in, a model with a type to answer in, a typed message out*; the coordinator's
  handler for the time decision.
- One honest slide: what the framework decided for us - no retry on a timeout, because a retry
  could book a room twice.

### 6. Demo 2: the team you talk to (5 min)

`docs/demo.md` act 4, then one memory beat:
1. *A design review with Sanne and Daan on Tuesday, somewhere in nature, no lunch.* `@Intake` -
   the old deck's *Personal Assistant* - looks the names up, never guesses an email, and sends the
   same typed request the form sends.
2. Type *the second one* in the chat: understood, and **authorises nothing**.
3. One memory moment (act 5.3): *Sanne is vegetarian*, remembered once, applied when Daan books
   with her; the trace shows `MemoryApplied`. Memory is evidence, never an order.

If time runs short, skip step 3. If there is time left, the akgentic console (act 3): exactly
what a model saw.

### 7. Beyond the demo (4 min)

The bio promises *what happens beyond the demo* and *experiments that didn't go to plan*. Three
or four from `docs/lessons.md`:
- *A field the agent is not given is a field it will invent* - the booking titled "Meeting".
- *Delivered is not used* - code can prove memory reached the model, not that it was used.
- *Silent loss is the worst failure* - the event store dropped messages while the team ran fine.
- *Live runs find what stubs cannot* - six bugs in the first real run, each now a test.

### 8. When is a team worth it? (2 min)

A short checklist:
- the work crosses **systems with different owners or risks** (agendas, rooms, money);
- some steps are **irreversible** and need code or a human in charge;
- parts need **different context**, and you want each prompt small;
- you want to **test and trace** each part on its own.

And when not: one system, reversible actions, a context that fits - stay solo.
Close with the balloons: *now I am having fun* - and the repository link.

## Decisions

Proposed in draft 2, answered on 2026-11-06.

| Id | Decision | Decided |
|---|---|---|
| T1 | Live demo or recorded | **live**, with a video of the demo as a backup |
| T2 | How much akgents code | **little**. The console is already in the deck; perhaps the team's YAML definition, not yet decided. No Python unless it explains something better than words |
| T3 | Memory in the talk | **yes, one slide** - and not much more |
| T4 | Guardrails | **a slide, and something in the demo.** The decision models are left out of the demo and shown on the slide |
| T5 | The old deck's LLM basics and ReAct (10-36) | **dropped**; the playful deck's six slides replace them (now slides 3-8) |
| T6 | *Where to go from here* (old 48) | **dropped** |
| T7 | Spine of the story | *last year I drew a crew, this year it works* - **kept for now, not the punch line** |
| T8 | Format | **HTML**, in `talk/slides`; a PDF export is needed at some point |
| T9 | The repository | **promoted on a slide, with a QR code or a short link** - perhaps just before the demo |

## Demo risks

- Model latency on venue wifi: tether a phone, keep the stack running before 19:00, and plan one
  meeting beforehand so the trace and the agenda can be shown even if a new run is slow.
- Use `localhost`, not `127.0.0.1`, and a login that is not in `ADMIN_EMAILS` (`demo.md` §0).
- `make reset` the afternoon before; pick a weekday a week or so after 3 December.

## Answered questions

1. **Length:** aim for 45 minutes, with room for questions and some breathing space. The part
   timings above add up to 45; they are a ceiling, not a target.
2. **Audience:** mixed stacks, so no focus on Python. Code only where it helps.
3. **Old slides 40-41:** probably the design patterns for agent layouts and architectures that
   already exist - to be brought into part 3.
4. **Format:** HTML, with a PDF export (T8).

## Still open

1. Which part of the demo shows a guardrail (T4), and what goes on the guardrails slide.
2. Whether the team's YAML gets a slide (T2).
3. The repository's short link or QR code (T9), and where the slide goes.
