# Design — what the team should remember

Companion to `design_durability.md` and `design_chat.md`. Those documents gave every meeting a
durable record and a way to ask for one in your own words. Each team still starts from nothing: it
does not know that "Daan" usually means Daan Jansen, that this group always has soup, or that the
last time someone asked for "somewhere sporty" the chosen place was turned down. This document
proposes a memory that outlives the team that made it.

It builds on two inputs, both kept: the first notes (Appendix A, verbatim) and an analysis of the
field — CoALA, Reflexion, ACE, Letta/MemGPT, Mem0, Zep/Graphiti, LongMemEval, the LangChain and
Anthropic write-ups (Appendix B). This document adds what akgentic and pydantic-ai actually provide,
verified against the installed packages, and what this team needs.

> **The one sentence to keep:** *remember only what will change a future decision — and say when
> it stops being true.*

**Status:** proposal, revised 2026-11-02 now that there is a login (`design_auth.md`). Nothing is
built. §4.2 says exactly where memory is stored; §9 lists the questions still open, §10 the spike
that comes first.

---

## 1. Starting points

From the notes and the analysis, five ideas carry the design:

1. **The aim is better decisions, not a richer prompt.** Enriching the prompt is the mechanism; the
   test of every memory is *which future behaviour changes because of it*. If there is no answer,
   it is not stored.
2. **Two independent axes.** *What* is remembered — working, semantic (facts), episodic
   (experiences with their outcome), procedural (ways of working). And *when* it is selected — the
   notes' always / by context / by question, extended with **before an intended action** and
   **on a new finding**. The fourth matters most here: a hint for a lookup has to be there *before*
   the lookup, not with its results.
3. **Writing deserves as much design as reading.** Signal → capture what was actually said →
   interpret → bound (for whom, until when) → merge → evaluate → retire. And **a lesson the agent
   inferred has a different status from a correction a person confirmed.**
4. **Relevance is "may and can it apply" before "how similar is it".** Scope, validity, task and
   step, trustworthiness — then usefulness. A stale correction can look very similar to the
   question and still be wrong.
5. **Managing memory means being able to explain it.** Where did this come from, what kind is it,
   what did it replace, why was it chosen for this task, was it actually used — and can a person
   correct, disable or delete it.

---

## 2. Ten cases from this team

The analysis ends with: *work out ten real corrections before choosing a storage form.* Here they
are, from the agents this project actually has. Each says what goes wrong today and what should
change.

| # | What goes wrong today | What should change | Kind | Scope | Selected | Signal / evidence | Stops being true |
|---|---|---|---|---|---|---|---|
| 1 | "Daan" is asked about every time — or, if the address book had one Daan, silently right | `@Intake` proposes Daan Jansen for this organiser, and asks only when unsure | semantic (alias) | organiser | before `look_up_people` | the person's own answer to "which Daan?" | when that person leaves the address book |
| 2 | "my team" means nothing | "my team" expands to Sanne, Femke, Daan | semantic (group) | organiser | at conversation start | an explicit statement | when the person says so |
| 3 | Lunch is ordered without knowing that Sanne is vegetarian | the wish passed to `@Catering` says so | semantic (preference) | person | before `plan_meeting` | Sanne's own statement, or the organiser's | on request — personal data, deletable |
| 4 | "somewhere quiet for focus" is re-judged each time | Library is proposed first for this group's focus sessions | semantic (place preference) | organiser | before `FindLocationAssignment` | an explicit "always the Library for focus" | when the location changes |
| 5 | "somewhere sporty" became *Meeting in Nature*, which the person turned down | next time the facility manager says plainly that no location has sports facilities | episodic → procedural | all | before `FindLocationAssignment` | the rejected slot and the cancel, in the trace | when a location with sports facilities appears |
| 6 | Stand-ups are requested at the 60-minute default | 30 minutes is proposed for this group's stand-ups | semantic (preference) | organiser | before `plan_meeting` | an explicit correction | when the person says so |
| 7 | "Like last week's design review" means nothing | the earlier meeting's people, place and length are offered — **a later step, see M5** | episodic | organiser | on a new finding | the earlier meeting's own record | never — it happened |
| 8 | The *meadow* room was too noisy for a workshop | the facility manager avoids it for workshops | episodic → semantic | all | before `FindLocationAssignment` | a person's remark after the meeting | when the room is renovated, or after review |
| 9 | The menu has only one warm option, so "something warm" is always soup | **nothing to remember** — the menu is authoritative, `@Catering` reads it every time | — | — | — | — | — |
| 10 | Someone typed a name nobody knows, once | **nothing to remember** — a one-off is not a lesson | — | — | — | — | — |

What the table shows, before any storage is chosen:

- **Most of it is facts and preferences** (1, 2, 3, 4, 6), stated by a person, and true until that
  person says otherwise. They need a scope (person or organiser) and a way to be deleted, and
  little else.
- **Episodes already exist — and are not needed yet.** Case 7 is a meeting this system booked; its
  record is a coordinator's state (`design_durability.md` R2). Episodic memory here would be an
  *index* over records we keep anyway, not a second copy of them. It serves this one case, which
  nobody has asked for, so it is a later step (M5) — kept in the design, not in the plan.
- **Lessons are few and need review** (5, 8). They are inferred from outcomes, and one rejection
  does not justify a rule: they start as *proposed*, and a person promotes them.
- **Two of ten should not be memory at all** (9, 10). Nine is a source that is already correct and
  already consulted — remembering it would duplicate it and let the copy go stale. Ten is noise.
  Memory must not become a pile of repairs for things fixed better at the source.

---

## 3. What the framework offers — verified

Read from the installed packages (`akgentic-tool` 1.12.0, `pydantic-ai-slim` 2.61.0) and the
`pydantic-ai-harness` wheel, not from documentation alone:

| Offering | What it is | Survives the team? | Fit |
|---|---|---|---|
| `KnowledgeGraphTool` (akgentic) | entities and typed relations, keyword/vector search, summarised into every agent's context each turn | **No** — `knowledge_graph` is a *team-scoped* collection: every search and removal carries the team id | working memory within one meeting; useless across meetings, because here **a team is a meeting** |
| `PlanningTool` (akgentic) | a shared task board as per-turn context | No | working memory; the coordinator's state already is ours |
| `SkillTool` (akgentic) | a menu of procedures in the system prompt, bodies loaded on demand | yes — authored in the card | procedural memory that a person writes; not learned |
| `WorkspaceTool` (akgentic) | a file tree per workspace, with optional RAG and a **git journal** | **Yes**, by choice of scope: `workspace_id="memory"` gives `<principal>/_id/memory`, reached by *every* team of that principal; `workspace_metadata_keys` gives a tree per metadata value; `workspace_sharable` shares across principals | the store: durable across teams, inspectable, editable by a person; the journal makes "every accepted mutation one commit, authored by the agent that made it" |
| `LLM_CONTEXT` channel / `ContextUpdater` (akgentic) | a tool card's `get_context_states()` delivered into each turn as a delta | — | the akgentic way to inject an *always* block, bounded and event-sourced |
| `Memory` (`pydantic-ai-harness`) | a Markdown notebook: `MEMORY.md` injected each run, other notes read/searched on demand, written by the model (`write_memory`), namespaced, CAS writes, write metadata; file / SQLite / Postgres stores | yes, with SQLite/Postgres | a good notebook for a conversational agent; see §5 for why it is not the core here |
| `ConversationSearch`, `Skills` (harness) | recall over persisted history; on-demand procedures | — | overlap with event sourcing and `SkillTool` |

Two facts shape everything after this:

- **Anything team-scoped is working memory only.** One team arranges one meeting and is gone. The
  only akgentic store that outlives it is a workspace tree with a non-team scope.
- **`pydantic-ai-harness` pins `pydantic-ai-slim` exactly** — 0.61.0 needs 2.61.0, 0.63.0 needs
  2.63.0. Our pydantic-ai version is chosen by akgentic's own ranges; adopting the harness ties
  every akgentic upgrade to a harness release of the same minor. `Memory` exists in 0.61.0, so it
  is *available* today.

---

## 4. The proposal

### 4.1 Two trees: mine, and ours

The login changes the shape of the store, and makes it simpler. A workspace with a `workspace_id`
is resolved under the **owner of the team** — the logged-in person, since `design_auth.md` — so
"per organiser" needs no field, no team metadata and no `organisers/<id>` folder: it is simply the
owner's own tree. What is true whoever is asking — Sanne is vegetarian, the meadow room is noisy —
must not be per organiser, or every organiser would have to learn it again. Hence two trees.

**M1 — memory lives in two journaled akgentic workspace trees, both with `git_journal=True`:**

- **`memory` — mine.** Per principal (the default). What *this* organiser said about how they work:
  aliases, groups, defaults, place preferences (cases 1, 2, 4, 6) — and, later, their episodes
  (M5). Nobody else's team can reach it.
- **`memory-shared` — ours.** `workspace_sharable=True`. Facts about people and places, and the
  agents' lessons (cases 3, 5, 8). Every team reaches it.

```
memory/                        — one per person, under their own principal
├── organiser.md               aliases, groups, defaults, place preferences (1, 2, 4, 6)
└── episodes/                  reserved for the later step (M5) — not created now

memory-shared/                 — one for everybody
├── people/<email>.md          what a person prefers, said by them or about them (3)
├── places/<location_id>.md    facts about a location or a room, with validity (8)
└── lessons/<agent>.md         procedural lessons, proposed or confirmed (5)
```

Both outlive every meeting; both are plain files a person can read and fix; and each tree's journal
is the provenance the analysis asks for — who changed what, when, and what it was before — without
a table of our own.

### 4.2 Where it is stored, concretely

Memory is **files on the server's disk**, in the same place akgentic keeps every workspace. Nothing
goes to a database or an outside service. The path is
`<WORKSPACES_ROOT>/<scope>/_id/<workspace_id>`, where `<scope>` is the team owner's email for a
personal tree and `_shared` for a shared one (`resolve_workspace_path`, verified in the auth spike):

| Running as | `WORKSPACES_ROOT` | Jettro's own memory | Shared memory |
|---|---|---|---|
| compose (`make up`) | `/data/workspaces`, on the `server-data` volume | `/data/workspaces/jettro@rag4p.org/_id/memory/` | `/data/workspaces/_shared/_id/memory-shared/` |
| host (`make run-server`) | `data/workspaces` in the repo, git-ignored | `data/workspaces/jettro@rag4p.org/_id/memory/` | `data/workspaces/_shared/_id/memory-shared/` |

Beside each tree sits its **journal**, a git repository named after it — `memory.git`,
`memory-shared.git` — and, once search is switched on, an `.index` directory for the RAG index.
They are siblings, not children, so the tree an agent sees holds only the items.

Three ways to look at it:

- **the console** — its workspace tab shows a team's workspaces, through the framework's
  `/workspace/{team_id}/tree` and `/file` routes (with `workspace_id=memory` or `memory-shared`);
- **the Memory page** (M9) — ours, the same routes, through one of your own teams;
- **the disk** — `docker compose exec server ls /data/workspaces/...`, and `git log` in the
  journal to see every change with its author.

Two consequences worth stating:

- **Backups and resets.** It lives on `server-data` with the event store, so `make reset` wipes
  memory too. Memory and meetings have different lifetimes; a reset that keeps memory would be a
  separate target (§8).
- **Sharing needs permission.** A shared tree is only created if the server allows it:
  `AKGENTIC_WORKSPACE_SHARED_KINDS=id` in the server's environment. A card asking for a shared tree
  without it fails loudly at team creation — never silently falls back to a personal tree.

### 4.3 One item format: a lesson bound to its situation

**M2 — every item says when it applies, why, and how we know**, in front matter a person can read
and a test can check — the ACE-style item from the analysis:

```markdown
---
kind: preference            # fact | preference | episode | lesson
status: confirmed           # confirmed | proposed | retired
scope: organiser            # organiser (the owner of this tree) | person:<email> | all
situation: focus sessions
reason: "always the Library for focus" — said in conversation
exception: workshops need a bigger room
evidence: team 46c39651… message 7f2e…   # the run and message that taught it
review_when: the Library is renovated or closes
supersedes: null
---
Propose the Library first for this group's focus sessions.
```

The body is the advice; the front matter is what lets code decide whether it *may* apply. The tree
already says whose it is, so `scope` only has to tell `person:<email>` from `all` in the shared
tree; in a personal tree it is always `organiser`. Every item also records **who said it**
(`said_by: <email>`), because in the shared tree the writer and the subject can differ: Sanne saying
she is vegetarian is not the same evidence as her organiser saying so.

### 4.4 Selection: by code, at the moment of action

The analysis's most useful point for this team: **a hint for an action must arrive before the
action.** Most of our actions are typed handlers, so selection can be done in code, by the action
being taken, without relying on a model to remember to look something up.

| Agent | Moment | What is selected, by what | How it arrives |
|---|---|---|---|
| `@Intake` | conversation start | `memory/organiser.md` of the person it talks to (`self.user_id`): aliases, groups, defaults — confirmed only, bounded | an *always* block on the `LLM_CONTEXT` channel |
| `@Intake` | a name or a group | `recall(...)` over the organiser's tree and `people/` — episodes too, once M5 is taken up | a tool, because the trigger is in the words |
| `@Intake` | before `plan_meeting` | lunch preferences of the settled participants | folded into the `lunch_wish` it passes on — so `@Catering` needs no change (§9 Q2) |
| `@FacilityManager` | `FindLocationAssignment` | `places/` and `lessons/facility_manager.md` in the shared tree, confirmed, matched on the wish; and the organiser's place preferences, passed down by `@Intake` in the wish, so the facility manager never reads a personal tree | appended to the assignment's rendering by the handler, before `act()` |
| `@Catering`, `@Scheduler` | — | nothing in v1 | — |
| `@Coordinator` | — | **nothing — it stays deterministic (D1)** | — |

**M3 — selection is by scope and status first, similarity second.** An item is a candidate only if
its scope matches, it is `confirmed`, and its `review_when` has not been met; among candidates,
plain matching on `situation` is enough at this size (a handful of files). RAG over the tree
(`workspace_rag_search`) is available when volume justifies it, not before.

### 4.5 Writing: two paths now, a third later

**M4 — what a person said is written at once, as confirmed.** `@Intake` gets `remember(kind,
scope, situation, text)`. It may only store what the person said in this conversation, with their
words as the evidence and their email as `said_by`; the tool refuses booking ids, secrets and
anything without a scope. `scope: organiser` goes to their own tree, `person:` and `all` to the
shared one. Correcting the same item again *supersedes* it — the journal keeps the old one.

**M5 — episodes are a later step, and when they come, code writes them, not a model.**

*What an episode is.* A remembered event with its outcome — not a rule ("propose the Library") or
a fact ("Sanne is vegetarian"), but "this happened": *on 15 July Sanne and Daan had a design
review at Meeting in Nature, 09:00–10:00, with soup, and it went ahead.* The other kinds of memory
are distilled from experience; an episode is the experience itself, kept so it can be gone back to.

*What it would be for.* Case 7: "the same as last week's design review". The meeting's record
exists — its coordinator's state, shown on the Meetings screen — but an agent cannot reach it: it
cannot call the server's routes, and nothing in a team lists *other* teams. An episode would be
the agent-readable trail to that record.

*Why not now.* It serves one case of ten, and nobody has asked for it. It would be a second copy
of records we already keep, which can drift from them — the problem `design_durability.md` set out
to remove. It would quietly accumulate who met whom, and when. And it needs the most new machinery
of anything here: an actor that writes without making the coordinator less deterministic.

*When it is taken up,* two shapes are on the table, and the first is preferred because it copies
nothing:

- **read the records** — give `@Intake` a read-only way to find earlier meetings in the
  coordinators' own snapshots, by people and title;
- **an index written by code** — when a meeting is confirmed or cancelled, one line in `episodes/`
  (title, people, place, day, status, team id), written by a small deterministic actor, never by a
  model, because it needs no judgement.

Until then, the one thing an episode would add to the rest of this design — evidence for a lesson —
is already covered: an item's `evidence` names the team and message that taught it, which points
at the real record directly.

**M6 — what an agent inferred is written as proposed, and is never applied until a person promotes
it.** After a turned-down location or a cancellation with a reason, `@FacilityManager` may write a
proposed lesson. A proposed item is visible and reviewable, never injected. *One rejection does not
justify a rule* is enforced by status, not by prompt wording.

**M7 — consolidation is later, and it is a separate job.** Merging duplicates, generalising
lessons and retiring stale items is the "memory keeper" agent from the notes. It is phase 3: until
there is enough memory to consolidate, it would be a solution looking for a problem.

### 4.6 Trust, privacy and the guarantees we already have

- **M8 — memory is data, never authority.** It arrives labelled with its kind and status, below the
  agent's own instructions, and it can never approve a slot, choose a time or name a recipient.
  The gates (I4), `TalkOnlyToHuman` (I7) and the one-service rule (D1) are untouched: memory is
  not a service, and no specialist gains a second MCP server.
- **Personal data is treated as such.** A person's preferences live in their own file, which can
  be shown, corrected and deleted as a whole. Nothing secret is stored, and no booking id — the
  meeting's record is the coordinator's state, not memory.
- **M11 — who may see and change what follows the login.** Your own tree is yours: only your teams
  reach it, so only you see it. In the shared tree, `people/<email>.md` is **about** a person, and
  that person may always see, correct and delete it — whoever wrote it. Places and lessons are
  everybody's to read; promoting a proposed lesson (M6) or deleting a place fact is for an admin
  (`ADMIN_EMAILS`). The Memory page enforces this; the agents never delete.
- **The demo login is not a privacy boundary.** Anyone can log in as anyone (`design_auth.md` A3),
  so per-person memory shows the *mechanism*, not protection. That is acceptable for invented
  people; it is the first thing to change before real names go in.
- **Teams made before the login** belong to `anonymous`, and would have their own `anonymous` tree.
  Memory only starts with teams made after the login.

### 4.7 Seeing why

**M9 — every application is an event in the trace.** When memory is selected, the agent emits a
`MemoryApplied(items, reason)` event, so the Trace screen answers "why did it propose the
Library?". The journal answers "who wrote this and what did it say before". A **Memory** page
lists, for the logged-in person, *my memory* (their own tree) and *about me* (their file in
`people/`), plus places and lessons; it links each item to the run that wrote it and lets a person
edit, retire or delete what M11 allows, and an admin promote.

---

## 5. Why not the harness `Memory`, or the knowledge graph

| | Workspace tree + our tool (proposed) | `pydantic-ai-harness` `Memory` | `KnowledgeGraphTool` |
|---|---|---|---|
| Outlives a meeting | yes (`_id` scope) | yes (SQLite/Postgres) | **no** — team-scoped |
| Per person, from the login | yes — resolved under the team owner | only if we pass a namespace ourselves | no |
| Who writes | code, or a narrow typed tool | the model, freely (`write_memory`) | the model, via graph updates |
| Confirmed vs proposed | in the item, enforced by code | not modelled | not modelled |
| Selection before an action, by code | yes — the handler chooses | the notebook is injected each run; notes on the model's initiative | summary each turn; search on the model's initiative |
| Provenance | the git journal, per commit | optional write metadata | state events |
| A person can read and fix it | files, in the console | files or rows, with a UI of our own | graph tools |
| Dependency cost | none new | an exact pydantic-ai pin, 0.x API | an extra (`[vector_search]`) |

The harness notebook is good at what it does, and the right tool for an agent that should take
its own notes freely. This team's memory is mostly *stated* facts and *proposed* lessons whose
status matters, applied at typed moments — which is easier to keep honest in code we own. **M10 —
the harness stays an option for `@Intake`'s scratch notes (Q4), not the store of record.**

---

## 6. How we will know it works

The analysis borrows LongMemEval's split — retrieval, combining over sessions, time, knowledge
updates, abstaining without evidence — and adds two this team needs: **applying a correction** and
**not applying a rule too widely**. The ten cases become scenarios:

| Scenario | Passes when |
|---|---|
| applied when it should be | case 1: a second conversation proposes Daan Jansen without asking |
| not applied out of scope | case 4's Library preference does not reach a workshop, or another organiser — logged in as Daan, Jettro's Library preference is never proposed |
| shared where it should be | Sanne's vegetarian lunch, said once in Jettro's conversation, reaches Daan's lunch for Sanne |
| superseded | after "actually, the Loft for focus", the Library is not proposed again |
| proposed is not applied | case 5's lesson, still proposed, changes nothing |
| retired is not applied | after `review_when` is met, the item is skipped |
| abstains | with no memory, behaviour is exactly today's |

These run against the scripted model first (as `test_intake.py` does) and then live; they are the
first cases of the evals the README roadmap lists.

---

## 7. Decisions proposed

| # | Decision | Rationale |
|---|---|---|
| M1 | **Two journaled workspace trees: `memory` per person, `memory-shared` for everybody** | The only akgentic store that outlives a team; per person comes free from the login; facts about people and places must not be learned again per organiser |
| M2 | **Every item states kind, status, scope, situation, reason, exception, evidence and when to review it** | So code can decide whether it *may* apply before anything decides whether it *helps* |
| M3 | **Select by scope, status and validity first; similarity second; RAG only when volume needs it** | Relevance is not textual likeness, and a handful of files needs no index |
| M4 | **What a person said is written at once, as confirmed, by a narrow `remember` tool** | Direct corrections should stop the same mistake at once; a narrow tool keeps ids and secrets out |
| M5 | **Episodes are a later step; when they come, they read the meetings' records or are indexed by code — never written by a model** | One case of ten, not yet asked for; a copy can drift, and it accumulates personal data. Kept in the design so the thought is not lost |
| M6 | **What an agent inferred is proposed, and never applied until a person promotes it** | An inferred lesson has a different status from a confirmed correction |
| M7 | **Consolidation — the memory keeper — is phase 3** | Until there is memory to consolidate, it has nothing to do |
| M8 | **Memory is data, never authority; it cannot pass a gate** | The gates and the one-service rule are what make this team safe |
| M9 | **Every application is a `MemoryApplied` event; a Memory page shows, edits, retires and promotes** | Managing memory means explaining it |
| M10 | **`pydantic-ai-harness` `Memory` stays an option for scratch notes, not the store of record** | Status and code-driven selection are the point here; the harness pins pydantic-ai exactly |
| M11 | **Your tree is yours; a file about a person is theirs to see and delete; admins promote and prune the shared tree** | The login gives every item an owner or a subject; the demo login shows the mechanism, not protection |

---

## 8. What it costs, honestly

- **A second kind of durable data.** Meetings live in event-store snapshots; memory lives in
  workspace trees. Both sit on the `server-data` volume today, so `make reset` takes both — a reset
  that keeps memory is a separate target if it is wanted. Two kinds of data, two lifetimes —
  accepted, because they have different owners (the team vs. the person).
- **Our own tool card.** Reading and writing items, the always block and the events are code we
  write and test; the harness would have given us a notebook for free.
- **Personal data, visibly.** The moment `people/` exists, deleting a person's preferences is a
  feature the Memory page must have, not a nice-to-have.

---

## 9. Questions open

**Q1 — who is the organiser?** *Answered by the login (2026-11-02).* The team's owner — the person
logged in — is the organiser: `@Intake` reads it as `self.user_id`, and the `memory` tree resolves
under it by itself. The team-metadata workaround this question recommended is withdrawn.

**Q2 — where do lunch preferences apply?** `OrderLunchAssignment` carries a headcount, not the
participants, so `@Catering` cannot look anyone up. Folding preferences into `lunch_wish` at
`@Intake` needs no message change but helps only the chat team; passing the participants down
would help the form team too, at the cost of changing three messages. *Recommendation:* fold at
`@Intake` first.

**Q3 — when is search worth it?** Plain matching on front matter is enough for tens of items.
`workspace_rag_search` exists for when it is not.

**Q4 — a scratch notebook for `@Intake`?** The harness `Memory` would let it keep free-form notes
across conversations. Worth it only if the confirmed items prove too rigid for conversation.

**Q5 — retention.** How long a proposed lesson nobody promoted, an episode (once M5 is taken up), or a preference
nobody used is kept.

---

## 10. Implementation order

0. **Spike**, against the installed packages:
   1. reading and writing a workspace tree from a tool card of ours, not only through
      `WorkspaceTool`'s own callables — and whether those writes are journaled and attributed;
   2. an always block through `get_context_states()` on the `LLM_CONTEXT` channel, and how it
      survives a restore;
   3. what the console shows of the tree;
   4. a personal and a shared tree on one agent, with `AKGENTIC_WORKSPACE_SHARED_KINDS=id` —
      that both resolve as §4.2 says, for two different owners, and that the shared one refuses
      to bind without the permission;
   5. two teams of different owners writing the same file in the shared tree at once — whether
      the workspace's own locks serialise them, or the second write must re-read and retry.
1. **Phase 1 — confirmed facts and preferences** (cases 1–4, 6): the item format, the store, the
   `remember` / `recall` tools and the always block on `@Intake`, `MemoryApplied`, the scenarios of
   §6 against the scripted model.
2. **Phase 2 — before the action** (cases 4, 8): the facility manager's handler selects places
   and confirmed lessons before choosing.
3. **Phase 3 — proposed lessons and review** (case 5): proposed writes, the Memory page with
   promote and retire, and then the memory keeper.
4. Live runs, the docs, the changelog.

**Later, when "like last time" is actually wanted — episodes (case 7, M5).** First a spike: can a
read-only lookup over the coordinators' snapshots serve `@Intake` without copying anything; only
if not, the index in `episodes/` and the small deterministic actor that writes it.

---

## 11. Changelog

- 2026-10-28: Initial design, from the first notes (Appendix A) and an analysis of the field
  (Appendix B), checked against the installed packages. Found that akgentic's knowledge graph is
  team-scoped — useless across meetings here, where a team is a meeting — while a workspace tree
  with a `workspace_id` outlives teams and is journaled per commit. Found that `pydantic-ai-harness`
  ships a `Memory` notebook (in 0.61.0, matching our pin) but pins pydantic-ai exactly. Worked
  through ten cases from this team: most are stated facts and preferences, episodes already exist
  as records, lessons are few and need review, and two of ten should not be memory at all.
  Proposed one journaled tree, items bound to their situation, selection by code at the moment of
  action, three write paths with three statuses, and a trace event for every application.
- 2026-10-29: **Episodes moved to a later step** (M5, case 7). They stay in the design — what they
  are, what they would be for, and the two shapes they could take, reading the records preferred
  over indexing them — but not in the plan: they serve one case nobody has asked for, would copy
  records we already keep, and accumulate who met whom. The spike item and phase that served them
  moved to a closing "later" note in §10.
- 2026-11-02: **Revised for the login** (`design_auth.md`). One tree became two (M1): `memory` per
  person, resolved under the team owner by the framework, and `memory-shared` for people, places
  and lessons. `organisers/<id>` became the owner's own `organiser.md`; items record `said_by`.
  New §4.2 says where memory is stored on disk, beside its git journal, and how to look at it. M11
  sets who may see and change what. Q1 answered by the login; two spike items added for the shared
  tree.

---

## Appendix A — the first notes, verbatim

> # Waarom Geheugen
>
> En van de situatie is bijvoorbeeld correcties, stel voor een bepaald document wordt iets
> overgenomen dat niet klopt. Kan ook zijn dat voor een specifiek onderwerp standaard het verkeerde
> document wordt gevonden. Een tip voor de query kan dan helpen.
>
> Het doel van geheuden is het verrijken van de prompt naar een LLM. Je zou kunnen zeggen dat je dit
> zelf in de systeem prompt wel moet kunnen doen. Maar dan moet je alles van te voren weten. Met
> geheugen kun je een dynamischer gevoel maken.
>
> Het aanpassen van het geheugen kan ook met een agent gebeuren die gespeciliseerd is in het zo goed
> mogelijk toepassen van geheugen. Maar je zult het moeten beheren, dus je moet er inzicht in hebben.
>
> Zou geheugen meer het format van regels moeten hebben. Als dit gebeurd, doe dan dat, voeg dan dit
> toe, zoek dan op zus.
>
> ## Toepassen
>
> Ik moet nog nadenken over wat je in memory opslaat en wanneer je het gebruikt. Zo kun je
> doorzoekbaar maken, maar je kunt het ook zo doen dat het altijd wordt toegepast.
>
> Het is ook nog wel interessant wanneer je het geheugen op haalt. Doe je dit als uitbreiding op de
> system prompt? Doe je dit na elk bericht van een Human, kan het ook door andere agents aangevraagd
> worden?
>
> ### Altijd
>
> Hier kun je regels/opmerkingen opslaan die altijd worden toegepast, het is slim om hier te helpen
> om de regels duidelijk te maken, maar ook om het document beperkt te houden om effectief te
> blijven.
>
> Wel zouden we regels nog kunnen filteren, bijvoorbeeld door gebruik te maken van tags. Je moet wel
> oppassen dat het niet te ingewikkeld wordt.
>
> ### Context
>
> Je kunt het alleen in specifiek situaties toepaseen, denk bijvoorbeeld aan klantspecifiek, of zelfs
> gebruikers specifiek. Kan ook afhangen van de vraag, maar die maakt het al iets makkelijker. Je zou
> een vraagh kunnen categoriseren en per categorie iets toevoegen
>
> ### Op basis van de opdracht/vraag
>
> Hier moet je iets meer doen, je moet namelijk gaan zoeken. Dan moet je heel duidelijk zijn in waar
> je op gaat zoeken. Waar ga je op matchen om te bepalen of een geheugen relevant is.

## Appendix B — the analysis it builds on

The analysis that followed the notes, in summary; its sources are listed for reading in the order
it recommends.

- **Purpose:** memory keeps information from earlier interactions so that an agent makes better
  decisions next time — a different answer, query, source, follow-up question or way of working.
  Ask of every memory which future behaviour it changes.
- **What vs when:** the notes' always / context / by-question is *when*; *what* is working,
  semantic, episodic or procedural. Selection gains two moments: before an intended action, and on
  a new finding.
- **A correction is three possible problems** — a wrong source, a wrong lookup, a wrong
  interpretation — each with its own fix, and memory should not become a pile of repairs for
  structural faults. A useful item names situation, lesson, reason, exception, evidence and when to
  review it.
- **Relevance before similarity:** scope, validity in time, fit to task and step, trust, then
  usefulness.
- **The write lifecycle:** signal, capture, interpret, bound, merge, evaluate, retire; inferred
  lessons are not confirmed corrections; immediate corrections vs background consolidation; keep
  access to the original evidence.
- **Management is explanation:** origin, kind, what it replaced, why it was selected, whether it
  was applied, and the means to correct, disable or delete. Retrieved memory does not carry the
  authority of system instructions.
- **Evaluation:** measure behaviour — the original mistake made less often, the correction not
  applied where it does not belong.

Recommended reading: LangChain — Memory overview; CoALA (§4); Reflexion; ACE — Agentic Context
Engineering (§2–3); Anthropic — Effective context engineering for AI agents. Further: MemGPT and
Letta (memory and consolidation); Mem0; Zep — key concepts (facts with validity over time);
Generative Agents; LongMemEval; Redis — long-term conversational memory; and the Pydantic AI
harness documentation on Memory (the Notebook model).
