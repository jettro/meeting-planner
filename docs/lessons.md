# Lessons

What building the sample taught us, gathered from every step. Each lesson says what happened,
what to take from it, and where the full story is. They are grouped by theme rather than by
date, because the same lesson often came back in a different step.

## Models and prompts

**A field the agent is not given is a field it will invent.** The first booking from the
terminal was a correct room booking, titled *"Meeting"*. Nobody had told the facility manager
the meeting's title, so its model filled the gap with a plausible word - though the booking tool
had accepted a title all along. The assignment now carries the title, and a test pins it. This is
not about prompting: whatever an agent needs, give it, or it will be made up.
([`design_akgents.md`](design/design_akgents.md) §7.5.)

**A tool's schema is part of the prompt, and models read it literally.** Declared as a *time*, a
tool parameter told the model to send a time format, and it sent `10:00:00+00:00` - a time zone,
for a meeting room that has none. The tools now take plain `HH:MM` text.
(`design_akgents.md` §7.4; [the services](services.md).)

**Translate at the edge that faces the agent; refuse at the edge that owns the data.** Refusing
the offset at the tool's input made a typo fatal: a failed input check ends the agent's turn,
while a result it can read lets it correct itself. So the tool now ignores an offset and *says
so* in its answer, and only the REST API - where a real system might mean a conversion - refuses
one. (`design_akgents.md` §7.4.)

**How memory is framed decides how much it counts.** A remembered *for a sportive environment,
choose Campus* reached the facility manager and lost to a place whose one-line description
mentioned outdoor activities, because the prompt said to *weigh it with the descriptions*.
Introduced instead as first-hand knowledge that counts when it speaks to the request, it won -
and the agent now says in its reason whether it followed it. A memory written as a fact (*Campus
has sport facilities*) is stronger than one written as an order, because the prompt tells the
model not to take orders from memory. ([Memory](memory.md).)

**A rule that leaves an argument open gets it filled in.** The offer rule said *call remember on
a clear yes*, and the model did - with `about` set to the person's own email rather than
`organiser`. The meal was kept as a fact *about* the person, where their own conversations never
apply it. Naming the argument in the rule fixed it, and a test now holds the wording.
([`design_memory.md`](design/design_memory.md) §10.5.)

**Delivered is not used.** In one run the model knew Sanne was vegetarian and still asked *what
kind of lunch?* without mentioning it. Code can guarantee that memory reaches the model, and the
trace can prove it; whether the model *uses* it is a question only evaluations can answer.
([`design_memory.md`](design/design_memory.md) §10.2.)

**Saying less is often right.** After passing a question to the person, `@Intake`'s model usually
said nothing, because the card on screen already said it. Narrating every step costs a model
call and rarely adds a line. ([`design_chat.md`](design/design_chat.md) §14.)

**A prompt is a format string.** A prompt rendered with Python's `format` turns a literal `{` into
an error, and the error happened while the agent started - so it started anyway, without its
instructions. Every prompt in the catalog is now rendered by a test. (`design_akgents.md` §7.4.)

## Where code ends and the model begins

**Arithmetic is code.** The scheduler was told to report free time exactly as the meeting service
gave it, because models slip on arithmetic. But a free window is not a meeting: nobody cut
*free 09:00-17:00* down to an hour, and the team proposed a seven-hour slot. Cutting it is now
plain Python, as is finding the common free time in the first place. (`design_akgents.md` §7.4,
D8.)

**Settle in code what code can settle.** A name that matches one person is settled by code, not
by the model reading the answer; a request naming someone no lookup settled is refused by code.
The model is left with what needs it: reading a sentence, and asking a good question.
([The conversation](conversation.md).)

**A name that lies is a bug.** A failed plan listed the steps still needed to undo it in a field
called `compensated`, which reads as *already undone* - and the meeting it listed was, correctly,
still there. Renamed to `outstanding`. (`design_akgents.md` §7.4.)

**Refuse a wrong message where it is made.** An approval sent without a time was read downstream
as a refusal, so the plan was cancelled and the person told they had not approved. The decision
now refuses to exist without a time. A wrong field name should be heard about at the point of the
mistake. (`design_akgents.md` §7.4.)

## The framework

**When the framework seems wrong, check our side first.** An experiment found the coordinator
empty after a team was revived, and concluded that our agents *could not* be durable - and a plan
store was built on that. In fact the coordinator's state had no observer, so none of its changes
were ever saved; the specialists attached one, the coordinator did not. The fix was one line. The
experiment had measured our code correctly and read it as a property of the framework.
([Durability](durability.md).)

**A framework default is a decision someone made.** A model call times out after two minutes, and
the framework deliberately does not retry a timeout: a timed-out request may still be running,
and retrying one that books a room could book it twice. So the specialists got a longer timeout,
not retries - because the framework was right about the risk. (`design_akgents.md` §7.6.)

**A timeout budget is a chain.** Raising the model's timeout to four minutes without raising the
client's - five minutes, for three model calls in a row - would have turned a slow provider into
a client failure. A test now keeps the client's limit above three slow calls.
(`design_akgents.md` §7.6.)

**Silent loss is the worst failure.** The event store could not write a clock time, and later a
status enum, so it dropped every message that carried one - while the team ran perfectly,
because a message the store cannot write is still delivered. Only building the screen that reads
the history found it. ([The server](server.md).)

**Use what is there.** The login needed no authorisation code: the framework already checks who
owns a team, and every refusal in the tests is its own. What it lacked was only a way to know who
is asking. ([Who is asking](who-is-asking.md).)

**Reviving a team is not waking its watchers.** A message to a stopped team revives it and the
coordinator acts correctly, but a browser already watching that team was not told. Only the
explicit restore route wakes waiting sockets, so the planner restores first and then watches.
Found in the browser; no test watched a socket. ([`design_durability.md`](design/design_durability.md) §10.)

## Memory

**Two writes in one turn can lose one.** In the first live conversation, *my team* and *my
stand-ups* were both answered *Remembered*, and only the second was in the file. The model had
called the tool twice in parallel; the write gate guards against *other* writers, so to it the
second write was simply newer. One lock per file fixed it, and a test runs eight writes at once.
([`design_memory.md`](design/design_memory.md) §10.2.)

**The login is what made memory personal.** Before there were users, *per organiser* had nobody
to belong to. The smallest step to build gave every item an owner and *me* a meaning.
([Who is asking](who-is-asking.md).)

## Testing and checking

**Live runs find what stubs cannot.** The first run against the real services and a real model
found six things no test had: the prompt that was a format string, the seven-hour slot, the
invented time zones, the fatal strict check, the lying field name, the approval without a time.
Each is now a test, so it cannot come back. (`design_akgents.md` §7.4.)

**A test that decides both ways.** The restore test stops a team at the time question, revives
it and books the meeting. With the observer line it passes; without it, no snapshot is ever
written and it fails. That is what settles a disputed question - not an argument.
(`design_durability.md` §10.)

**Wait for the right thing, not for a while.** A test of a cancel that arrives during a booking
sometimes cancelled before the booking had even landed - a different case, handled correctly,
but not the one under test. It now waits until the coordinator's record shows the booking. Read
the record instead of guessing at timing. (`design_durability.md` §10.)

**A test must do what the real thing does.** A restore test handed a live question to the answer
handler and failed; the server never does that - it reads the question back from its store. The
code was right and the test was not faithful. (`design_chat.md` §14.)

**The build is the check.** The type check on its own passed while the real build found five
errors, because the build reads settings the bare command does not.
([`design_gui.md`](design/design_gui.md) §8.3.)

**A traceback is not an error message.** The first failure someone else saw was two hundred lines
of stack ending in a timeout. What they needed was one line: nothing was booked, try again. The
reason now travels as a typed failure and is reported in words; the stack is for debugging.
(`design_akgents.md` §7.6.)

---

*Gathered from the designs' lessons sections and the live runs, 2026-11-03.*
