# Design — the documentation

> **Status:** agreed, 2026-11-03; questions answered (§8). Steps 1 to 3 of §6 are done - the move,
> the index, the overview and the memory page - and step 4 has begun: the services and the team pages.

> **The one sentence to keep:** *the designs say what we decided and why, at the time; the docs
> say what is there now, and why it is that way.* Everything below follows from it.

## 1. What is wrong now

- **The only way in is the history.** Eight design documents, about 4,200 lines, each written
  before its step was built and amended afterwards by changelogs, "what building it taught us" and
  "checked against the code" sections. To learn how memory works today you read `design_memory.md`
  from the first notes through phase 2 and work out which parts still hold. `design_cancel.md`
  opens by saying it is partly superseded by `design_durability.md`.
- **Nothing describes the whole.** Each design is a step. How the services, the team, the server,
  the browser, the login and memory fit together is only in the README, spread over 366 lines that
  are also the quick start.
- **The why is there, but buried.** The reasons - why a deterministic coordinator, why the team is
  the meeting, why memory is chosen by code - are the most useful part for someone learning from
  the sample, and they sit in decision tables between dropped alternatives.
- **The designs sit in the repository root**, next to the Makefile. `docs/` has the demo script and
  your notes.
- **The code cites the designs** - about 218 references, by file name and decision id
  (`design_memory.md M18`, `design_cancel.md §8.3`, `G25`). Whatever moves must keep those true.

## 2. Who reads it

| Reader | Wants | Starts at |
|---|---|---|
| **Someone learning from the sample** - akgentic, agents with tools, memory | what each idea is, why it was done this way, what it costs | the overview, then one topic |
| **A developer changing it** | how the pieces fit, where in the code, which decision a line refers to | the overview, the topic, the design |
| **A presenter** | what to show, in what order | `demo.md` |
| **You, writing about it** | the lessons, with the evidence | the lessons page, your notes |

## 3. The proposal

```
README.md                  what it is, quick start, layout, a link to docs/  (shorter)
docs/
  README.md                the index: where to start, per reader
  overview.md              the sample in one page: the story, the pieces, one diagram
  services.md              three services, their MCP servers, one service per agent
  team.md                  the agents, the deterministic coordinator, the saga, the two gates
  server.md                the team as a service: akgentic-infra, the browser, the console, the trace
  durability.md            the team is the meeting: restore, cancel, resume
  conversation.md          @Intake: a team you talk to, the relay, what the model may say
  who-is-asking.md         the login, ownership, the organiser
  memory.md                the four kinds, chosen by code, the journal, the Memory page, the limits
  lessons.md               what building it taught us, across all steps
  roadmap.md               what is next, and what is not planned
  demo.md                  (exists) the demo script
  memory_blog.md           (exists) your notes - not touched
  design/
    design.md ... design_memory.md, design_docs.md   moved here, file names unchanged
```

## 4. Decisions proposed

**W1 — two kinds of document.** A *topic page* describes what is there now and why; it is kept
current, and has no changelog. A *design* records what was proposed, decided and dropped, at the
time; after its step is built it is history, and changes only by a status header (W3). A topic
page links to the design for the long reasoning instead of repeating it, so the two cannot drift
apart on the same question.

**W2 — the designs move to `docs/design/`, with their file names.** `git mv`, nothing renamed. The
code cites them by name (`design_memory.md M18`), so every one of those references stays true and
none needs editing; only links with a path - the README's, and the designs' links to each other -
are fixed. Renaming them to `docs/design/memory.md` reads nicer and would break about 218
references for it.

**W3 — every design opens with the same status header.** Built, partly built or superseded; the
date; *the current picture is in `docs/<topic>.md`*; and which sections were superseded and by
what. Today each design words its status its own way, in a different place - a `## Status`
heading, a bold line, a quote block - and `design_cancel.md` points at `design_durability.md`
only from a note above its status. The body is not rewritten.

**W4 — no decision index** (Q4). The code cites decision ids from eight prefixes, and the
status header (W3) of each design says which ids it holds; a separate table would need upkeep for
little gain.

**W5 — every topic page answers the same five questions,** in this order, written for someone
learning from the sample (Q3):
1. *What it is* - one paragraph a newcomer can follow, with no framework names yet.
2. *How it works* - the flow in words and a diagram where it helps; class and message names
   appear as the reader needs them, code only where the idea is in the code (a handler that
   selects memory before the model runs).
3. *Why this way* - the reasons, and the alternatives turned down - the heart of each page, since
   the choices are what carries over to another project. Decision ids in passing, for whoever
   wants the design.
4. *What it does not do* - the limits, on purpose and not yet.
5. *Where in the code* - the files, as links, last and short: a starting point for the reader who
   wants to look, not a map for a developer.

**W6 — checked against the code, and dated.** Like the designs: each page is written from the
code as it is, not from the designs, and ends with *Last checked against the code: <date>,
`<commit>`*. Where a design and the code disagree, the page follows the code and the disagreement
goes in the design's status header.

**W7 — a few diagrams, as Mermaid.** It renders on GitHub and lives in the text: the pieces and
who talks to whom (overview), the booking saga with its two gates (team), and how a memory item
travels from a sentence to a prompt (memory). No images to keep in step.

**W8 — `lessons.md` collects what building taught us.** Six designs have one or more "what
building it taught us" sections, and the live runs found more (the lost update between two `remember` calls,
the Campus memory that lost to a description). One page, by theme rather than by date - the
framework, models and prompts, memory, testing - each lesson with its evidence and a link. It is
the page most worth reading for someone learning from the sample, and the raw material for your
blog; your notes stay yours.

**W9 — the README gets shorter, not emptier.** What it is in a paragraph, the quick start, the
project layout, the Makefile table, and a link to `docs/README.md`. The long sections - the team,
the conversation, memory, the login - move to their topic pages. The roadmap moves to
`roadmap.md`, updated: the *My agenda* page is dropped (the meeting service's own UI does it),
memory phase 2 and login step 5 are done.

**W10 — plain Markdown, no site generator.** It reads on GitHub and in an editor. MkDocs could be
added later over the same files; nothing here prevents it (Q1).

## 5. Considered and not chosen

- **Rewriting the designs into current documents.** It loses what they are good for: the
  reasoning at the time, the alternatives, what was measured and dropped. It is also the most work.
- **Merging the explanations into the designs** (a "current state" section in each). That is what
  happened with the "checked against the code" sections, and it is why they are hard to read now.
- **One long architecture document.** Easier to write, harder to link to, and the code wants to
  point at one topic.

## 6. Order of work

Each step is one commit, and you review each page before the next.

1. **The move** (W2, W3): `git mv` the eight designs, fix the path links, write the status
   headers. Mechanical; checked by a link check over all Markdown. Each header gets its *Now*
   line - where the current picture is - with the topic page that holds it.
2. **The index and the overview**: `docs/README.md`, `overview.md` with its diagram. Fixes the
   shape every other page follows.
3. **`memory.md`** first of the topics: it is the freshest, the demo leans on it, and it has the
   most "why" to explain (chosen by code, never authority, the journal).
4. **The other topics**, in the order the sample was built: services, team, server, durability,
   conversation, who-is-asking.
5. **`lessons.md`**.
6. **The README and the roadmap** (W9), last, when there is somewhere for its sections to go.

## 7. Risks

- **Two places say the same thing.** W1 keeps it small: designs freeze, topic pages link rather
  than repeat. What remains is the price of having both.
- **The topic pages go stale.** The *last checked* line (W6) makes it visible; when behaviour
  changes, the topic page changes in the same commit - as `demo.md` does now.
- **The move breaks a link I did not find.** The link check in step 1 covers Markdown; references
  in code are by name and do not move.

## 8. Questions answered (2026-11-03)

- **Q1** — Plain Markdown on GitHub is enough; no site (W10).
- **Q2** — `memory_blog.md` stays where it is, for now.
- **Q3** — The reader learning from the sample comes first (W5): concepts and reasons before code.
- **Q4** — No decision index (W4).

## 9. Changelog

- 2026-11-03: Proposal, from an inventory of the eight designs, the README, `docs/` and the
  references to the designs in the code.
- 2026-11-03: Questions answered (§8). W4 became *no decision index*; W5 is written for the
  reader learning from the sample.
- 2026-11-03: **Step 1 done.** The nine designs are in `docs/design/` under their own names, and
  each opens with the same status header; no link broke.
- 2026-11-03: **Step 2 done.** `docs/README.md`, the index, and `overview.md`, with the pieces as
  a diagram, one meeting from start to finish, and the seven ideas that carry over.
- 2026-11-03: **Step 3 done.** `memory.md`, the first topic page, with the Campus run as its
  lesson; the memory design's header has its *Now* line.
- 2026-11-03: **Step 4, the services page.** `services.md`; `design.md`'s header has its *Now* line.
- 2026-11-03: **Step 4, the team page.** `team.md`, with the saga as a sequence diagram;
  `design_akgents.md`'s header has its *Now* line.
