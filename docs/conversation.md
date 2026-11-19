# The conversation

## What it is

Instead of filling in the form you can just say what you want: *a design review with Sanne and
Daan on Tuesday, somewhere in nature, no lunch.* One more agent, **`@Intake`**, holds that
conversation. It works out who you mean, asks when something is unclear, and then sends the team
exactly the request the form would have sent. After that it keeps you company: it passes the
team's questions to you, and tells you in words what happened.

Behind it is the same team, unchanged. The coordinator still decides every step, and the two
questions are still answered on their cards - never in the chat.

> **The one sentence to keep:** *the model listens; the coordinator decides; the human approves.*

## How it works

### Where it sits

```mermaid
flowchart TB
    human["@Human - you"]
    intake["@Intake - the conversation"]
    guard["@Guard - is this about the meeting?"]
    coordinator["@Coordinator"]
    scheduler["@Scheduler"]
    facility["@FacilityManager"]
    human <--> intake
    intake -. ask .-> guard
    intake <--> coordinator
    intake -. look up people .-> scheduler
    intake -. look up a place .-> facility
    coordinator --> scheduler
    coordinator --> facility
```

`@Intake` stands between you and the coordinator. The coordinator is configured to treat it as
its human, so every question and outcome goes to `@Intake` first. It can ask `@Scheduler` and
`@FacilityManager` one kind of thing each - *who is this?* and *which place is this?* - and that is
all it can ask anyone. It also asks `@Guard`, before and after its model, whether the
conversation is still about the meeting.

### Its tools

The model gets five tools, and nothing else:

| Tool | What it does |
|---|---|
| `look_up_people` | asks `@Scheduler` who *Sanne* and *Daan* are |
| `look_up_place` | asks `@FacilityManager` which place *the meadow room* is |
| `plan_meeting` | sends the typed request to the coordinator - once |
| `cancel_meeting` | calls the meeting off |
| `remember` | keeps something you said for next time ([memory](memory.md)) |

There is no tool to book, and no tool to approve.

### From words to a request

1. **Names become people.** `@Intake` looks every participant up. One match settles the name, in
   code; several matches or none come back to the model as a question to put to you - *who do you
   mean?* A name is never guessed into an email.
2. **You count.** You are logged in, so `@Intake` knows who it is talking to. You are not looked
   up, and you attend unless you say otherwise.
3. **A place is described, not chosen.** *Somewhere in nature* goes into the request as words.
   Choosing is the facility manager's job, because it is the only agent that sees the places.
4. **The request goes out, once.** Code checks it first: every participant must be someone a
   lookup settled, and a conversation that already requested its meeting is refused a second
   one. `@Intake` says in one sentence what it asked for.

### The relay

When the coordinator asks about the time, `@Intake` passes the question on to you as a fresh
message - a new copy addressed to `@Human`. That is what lets the planner show it as a card and
the server route your answer: it finds a question by its id, and answers it to whoever asked. Your
answer comes back to `@Intake` and goes to the coordinator unchanged. This is code; the model
does not touch it.

The model does hear about it. Every relayed message is also an *update* for the model, so it can
explain what is on your screen, and at the end say what was booked.

### What the model may say, and to whom

The model may write only to you. A rule on its output - `TalkOnlyToHuman` - refuses any other
recipient. Free text to the coordinator would be ignored, and free text to a specialist would
reach that specialist's model and its booking tools.

Typing *the second one* or *just book the ten o'clock* in the chat is understood, and authorises
nothing. In a live run the model answered: *"I can't choose or approve a time for you. Please
select 10:00-11:00 in the question on your screen."*

### What it will talk about

The planner arranges meetings and remembers how you like to meet. Nothing else. A prompt can
ask a model for that, but cannot make it stick: in a demo, *do not need a meeting, just search
for a good restaurant* got three Amsterdam restaurants back. So the conversation is checked twice
by **`@Guard`**, a team member whose only job is answering typed questions about it:

- **Your message, before `@Intake`'s model reads it.** `@Guard` sees the message, what the
  planner said last and whether a meeting has been requested, and picks one: *arrange*, *memory*,
  *greeting* or *other*. *Thursday* after *which day?* is *arrange*; *a nice restaurant around
  Amsterdam* could be a place to meet, so it is *arrange* too, and the planner asks. *Other* is
  answered from code - *"I can only help arrange a meeting and remember how you like to meet."* -
  and never reaches the model with the tools, so an instruction hidden in it is never read there.
- **The planner's answer, before you read it.** `@Guard` sees the answer and your message, and
  picks *meeting* or *other*. Saying what the planner cannot do is *meeting*. An answer that
  helps with something else is sent back to the model once; if it drifts again, you get the same
  sentence instead.

If `@Guard` cannot answer within 30 seconds, the check is skipped and the conversation goes on;
the trace says so. Every check is a `GuardrailChecked` row in the trace: *message check* or
*answer check*, what `@Guard` answered, and passed, refused or skipped.

`@Guard` runs on the same language model as the rest of the team, through its own model card,
`guard_model`. It answers only with the pick-one - no reason in its own words - so that card can
later name a decision model and nothing else changes. Its wording and the two sentences live on
cards, and `make guard-eval` runs 39 labelled messages and answers against the real model.

## Why it is built this way

**Easier input, not a model in charge.** The goal was a nicer way to ask for a meeting. A model
that ran the saga would have been more flexible - and harder to trust, test and explain, for no
gain in what you can ask for. So the model is put where language is: in front of the team, turning
words into the typed request the coordinator already understood. The team behind it did not
change. ([`design_chat.md`](design/design_chat.md) I1, Appendix A.)

**The human approves, by construction.** Approving is not something the model is asked not to
do; it is something it has no tool for. The questions are answered on their cards, and the
conversation is only ever words. (I4.)

**Code settles what code can.** A lookup with one match is settled by code, not by the model
reading the answer. A request with an unsettled email is refused by code. The model is left
with what needs it: reading your sentence, and asking a good question when something is unclear.
(I3, I11.)

**Ask the agent that knows.** `@Intake` cannot see the places or the people. It asks the two
specialists that can, with typed questions and typed answers - a list of matches, or *nobody by
that name*. Free text to a specialist would reach its booking tools. (I10, I12.)

**Check what reaches the model, not only what it says.** A refusal written by the model after
reading an off-topic message has already let that text into a model that holds tools. So the
first check sits in front of the model and answers from code; the second catches what slips past
the first. ([`design_guardrails.md`](design/design_guardrails.md) §15, GR10, GR13.)

**One conversation, one meeting**, as one team is one meeting. A different meeting is a new
conversation. (I8.)

### A lesson from building it

The relay had to make a *copy* of each question. The coordinator's question is addressed to
`@Intake`, and the server answers a question to whoever it was addressed to - which must be a
person's proxy, not an agent. Forwarding the original would have put a question on your screen
that could not be answered. So `@Intake` sends a fresh one, addressed to `@Human`, and pairs the
answer up with the original itself. A test answers both: the copy books the meeting, the original
is refused.

A second one, from the live runs: after relaying a question the model usually said nothing,
because the card on the screen already spoke for itself. Narrating every step costs a model
call and rarely adds a line.

A third, from the guard: its first version refused *can you help me find a nice restaurant
around Amsterdam*. Strictly that is not a meeting, but the planner's own answer - *do you want a
meeting there?* - was the better one. One line in `@Guard`'s prompt (a place could be where to
meet) fixed it, and the evaluation set has kept it since.

## What it does not do

- **Change the request afterwards.** *Make it Thursday* after the request means a new
  conversation (Q2 in the design).
- **Approve or book anything**, as above.
- **Guess a person.** An unknown or ambiguous name is a question to you.
- **Help with anything but the meeting** - restaurants, facts, writing, code - or take new
  instructions from the chat.

## Where in the code

| File | What is there |
|---|---|
| `agents/src/meeting_agents/intake.py` | `@Intake`: its tools, the checks, the relay, `TalkOnlyToHuman` |
| `agents/src/meeting_agents/guard.py` | `@Guard`, its two questions, `ChatGuard` and the answer check |
| `agents/catalog/meeting-planner-chat/` | the chat team, which reuses the form team's agents |
| `agents/catalog/meeting-planner/agent/guard.yaml`, `model/guard_model.yaml`, `prompt/guard_prompt.yaml` | `@Guard`'s card, model and prompt |
| `agents/catalog/meeting-planner-chat/tool/chat_guard.yaml` | what is checked, the timeout and the two sentences |
| `agents/evals/guard_cases.yaml`, `meeting_agents/guard_eval.py` | the evaluation set, `make guard-eval` |
| `agents/catalog/meeting-planner-chat/prompt/intake_prompt.yaml` | `@Intake`'s prompt |
| `gui/src/pages/ChatPage.tsx` | the *Talk to the planner* tab |
| `agents/tests/test_intake.py` | the relay, the refusals, and what the model is told |
| `agents/tests/test_guard.py` | both checks, a guard that does not answer, and `@Guard` itself |

The design: [`design_chat.md`](design/design_chat.md); the guard:
[`design_guardrails.md`](design/design_guardrails.md) §15-§16.

---

*Last checked against the code: 2026-11-19, the chat guard.*
