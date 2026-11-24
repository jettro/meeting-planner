# Design: a thread for the second half - five questions, a failure, and the bill

> **Status:** built 2026-11-24, after a review of the whole deck. The review found the second half
> read as a tour of features (messages, configuration, memory, guardrails, security) with nothing
> tying them back to *what changes when it is a team*. Asked for by the human: the thread, the
> missing failure slide and a measured cost. Slides that changed a lot went to the extras; small
> changes were made in place.

## The thread

The comic ends with *what if I built a team for this?*. Slide 27 answers: then it has to answer
five questions that one agent never had to.

| # | Question | One agent | A team | Slides |
|---|---|---|---|---|
| 1 | Who does what? | one prompt does it all | each agent its part - in configuration | akgentic, a team is configuration, the cards |
| 2 | How do they talk? | one conversation | typed messages, addressed to one agent | the five message slides |
| 3 | What if a step fails? | the model has to remember | the one in charge holds the record | **new**: what if a step fails halfway? |
| 4 | What do they remember? | its own conversation | who sees what - decided in code | the four memory slides |
| 5 | Who may do what? | one set of rights | rights at every hop | the guardrails and the security slides |

- **Every slide of a section carries its question** in the top-left corner (`data-q` on the
  section, drawn by CSS), so the room knows where it is.
- **The configuration moved** from after the messages to right after akgentic: *teams as
  configuration* leads straight into *a team is configuration*, and question 1 is one block.
- **The close is the five questions**: *start with one agent; build a team when the work, the
  context or the risk pulls apart - and then answer* the five. The old checklist (*when is a team
  worth it?*) moved to the extras.
- Not labelled, on purpose: the repository, the demos, and *talk to the planner* - they are the
  sample at work, not an answer to one question.

## Question 3: what if a step fails halfway?

Built from `coordinator.py`, `plan.py` and `design_cancel.md`:

- `@Coordinator` holds the record - the meeting, booking and order ids - in its state, snapshotted
  on every change.
- A failure is `PlanFailed` with `outstanding`: the undo steps for what was booked
  (`MeetingPlan.compensations()`), reported, **not run** - on purpose (`_fail`): you see the mess,
  then clean it up.
- Cancel runs them one at a time, in reverse booking order: `cancel_order` ->
  `cancel_room_booking` -> `cancel_meeting`, each by the agent that owns that service.

The slide's example is a room that fails after the meeting is booked: `outstanding` is then
`cancel_meeting`, and Cancel releases it - all as the code does it.

**Found while checking the example - not on the slide.** When *lunch* fails after the room is
booked, `@FacilityManager` names the room only in the failure's text
(`receiveMsg_AssignmentFailed`, "room ..., booking ... still booked"). The coordinator never got
`FacilitiesBooked`, so the booking id is not on the plan and not in `outstanding` - and Cancel
would leave that room booked. The code says so itself: running that compensation is "iteration
2". A candidate for the sample's roadmap, and a good line for questions: *the record must hold an
id the moment it is booked*.

## What a meeting costs - measured 2026-11-24

The sample's request (*a design review with Sanne and Daan on Tuesday, somewhere quiet, and
lunch*), gpt-6-luna, three runs of each, against the local services. The team's numbers are
akgentic's `LlmUsageEvent`s - the ones the console shows - collected by an `EventSubscriber`; the
single agent's are pydantic-ai's `result.usage`. Approvals were answered by the script.

| | Model calls | Input tokens | Output | Cost (USD) | Time |
|---|---|---|---|---|---|
| One agent (step 5) | 5 | 10.9-12.1k | 0.9-1.2k | 0.0015-0.0018 (uncached) | 16-33 s |
| The team, from the form | 13-15 | 31.2-35.5k | 1.3-1.5k | 0.0015-0.0021 | about 33 s of model time |
| The chat team, with @Guard | 25-30 | 64.3-79.7k | 2.3-2.5k | 0.0029 | 43 s; 292 s with a timed-out retry |

- **@Guard** in the chat team: 3 calls, 2.3k tokens - a small part of it.
- **Cost is close for all three** because the team's repeated prompts are cached (its events
  carry the cached price); the single agent's figure is priced without cache. Tokens are the fair
  comparison: 1x, 3x, 6x.
- **Two chat runs counted, not three**: the third found no slot - the earlier test runs had filled
  1 December for Sanne and Daan. It is left out.
- **Cleaned up afterwards**: the test runs' 14 meetings (29-42), 14 room bookings (34-47) and 14
  lunch orders were cancelled through the services' APIs. Older bookings were left alone.

The slide (*What did that meeting cost?*) sits after demo 2: bars to scale for input tokens, 1x /
3x / 6x, the cost per meeting, @Guard's share, and the papers' 3-15x.
