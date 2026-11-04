# Design — what the team should remember

> **Status:** phases 1 and 2 built, 2026-11-02, and verified live: confirmed facts and preferences
> remembered by `@Intake`, per person and shared, and what people said about places, read by the
> facility manager before it chooses. Phase 3 is designed in §10.4 (M21-M31,
> Q6-Q11). 3a - editing and deleting on the Memory page, and *Said by me* - is built
> (2026-11-03) and verified live; 3b, suggestions - a team for a group, a meal for a kind of
> meeting - is built (2026-11-03, §10.5, M32-M37) and verified live; 3c, the memory keeper, is
> built (2026-11-03, §10.6, M38-M44) and verified live. Phase 3 is done.
>
> **Where to look:** §4.2 says where memory is stored; §9 lists the questions still open.
>
> **Lessons:** §10.2, and §10.3 for phase 2.
>
> **Now:** [`docs/memory.md`](../memory.md) describes memory as it is.
>
> *A design records what was decided and why, at the time; it is not kept current.*

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
`<root>/<scope>/_id/<workspace_id>`, where `<scope>` is the team owner's email for a personal tree
and `_shared` for a shared one (`resolve_workspace_path`, verified in the auth spike and again in
§10.1).

**The root has two names, and today they disagree (§10.1 S3).** The agents write under
`AKGENTIC_WORKSPACES_ROOT`, read by `WorkspaceTool` itself, which defaults to `./workspaces`. The
server's routes and team deletion read `WORKSPACES_ROOT` (`CommunitySettings.workspaces_root`). Our
Dockerfile sets only the second, so in the container the agents would write to `/app/workspaces` —
inside the image, off the volume, gone at the next rebuild — while the console looks in
`/data/workspaces` and finds nothing. **M12 — the server sets `AKGENTIC_WORKSPACES_ROOT` to its own
`WORKSPACES_ROOT` at startup**, so there is one root. With that:

| Running as | root | Jettro's own memory | Shared memory |
|---|---|---|---|
| compose (`make up`) | `/data/workspaces`, on the `server-data` volume | `/data/workspaces/jettro@rag4p.org/_id/memory/` | `/data/workspaces/_shared/_id/memory-shared/` |
| host (`make run-server`) | `data/workspaces` in the repo, git-ignored | `data/workspaces/jettro@rag4p.org/_id/memory/` | `data/workspaces/_shared/_id/memory-shared/` |

Beside each tree sits its **journal**, a git repository named after it — `memory.git`,
`memory-shared.git` — and, once search is switched on, an `.index` directory for the RAG index.
They are siblings, not children, so the tree an agent sees holds only the items.

Three ways to look at it — not all of them see both trees (§10.1 S4):

- **the console** — its workspace tab shows a team's workspaces through the framework's
  `/workspace/{team_id}/tree` and `/file` routes. It shows **your own** tree (`workspace_id=memory`),
  and only if the `WorkspaceTool` card sits directly in an agent's `tools` — the server finds
  workspaces by scanning those, not cards nested inside ours. It **never** shows the shared tree:
  the framework refuses every `_shared` path with 403, admins included, until an entitlement policy
  exists (`_team_access.check_workspace_scope`).
- **the Memory page** (M9, §4.8) — ours. One route of our own on the server reads both your own
  tree and `people/<me>.md`, with each item's history from the journal, because no framework route
  serves a shared path or a journal.
- **the disk** — `docker compose exec server ls /data/workspaces/...`, and `git log` in the
  journal to see every change with its author.

Two consequences worth stating:

- **Backups and resets.** It lives on `server-data` with the event store, so `make reset` wipes
  memory too. Memory and meetings have different lifetimes; a reset that keeps memory would be a
  separate target (§8).
- **Sharing needs permission.** A shared tree is only created if the server allows it:
  `AKGENTIC_WORKSPACE_SHARED_KINDS=id` in the server's environment. Without it the card's bind
  raises and never falls back to a personal tree — but the spike found that the raise happens in
  the agent's `on_start`, and **a team still gets built**, with the agent half-wired (§10.1 S5). So
  **M13 — the server settles it at startup**: when the catalog uses `MemoryTool` and the variable
  is unset, the server sets it to `id`; when it is set and does not permit `id`, the server refuses
  to start. Either way the first conversation never finds out.

### 4.3 One item format: a lesson bound to its situation

**M2 — every item says when it applies, why, and how we know**, in front matter a person can read
and a test can check — the ACE-style item from the analysis:

```markdown
---
kind: preference            # fact | preference | episode | lesson
status: confirmed           # confirmed | proposed | retired
scope: organiser:jettro@rag4p.org   # organiser:<email> (whose tree) | person:<email> | all
situation: focus sessions
reason: "always the Library for focus" — said in conversation
exception: workshops need a bigger room
evidence: conversation 46c39651…   # the conversation (team) that taught it
review_when: the Library is renovated or closes
supersedes: null
---
Propose the Library first for this group's focus sessions.
```

The body is the advice; the front matter is what lets code decide whether it *may* apply. The tree
already says whose it is, but a person reading the file - in the console, say - should not have to
know that: in a personal tree `scope` is `organiser:<email>`, naming the owner. In the shared tree
it tells `person:<email>` from `all`. Every item also records **who said it**
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

**The card's shape (§10.1 S1, S4; as built, §10.2).** `MemoryTool` holds the two trees privately
— two `WorkspaceTool`s it binds itself — and does all reading and writing through their gated
callables, because that is where the write gate and the journal are: a write from our code is
committed as `write: organiser.md`, authored `@Intake`. They are private because a `WorkspaceTool`
in an agent's `tools` hands the model every file callable it has. Beside it, `@Intake` declares one
plain `WorkspaceTool(workspace_id="memory", read_only=True)` with every capability off: it gives
the model nothing and exists only so the server — and the console — find the organiser's tree.

**Every write re-reads first (§10.1 S6).** The gate refuses to replace a file the writer has not
read, or that changed since: two organisers adding to `people/sanne@rag4p.org.md` at once, the
second is refused with *"it changed since you read it"*. So `remember` reads the file, applies its
one change to what is there *now*, and writes; on a refusal it does that once more. One file per
subject keeps the window small, and nothing is ever merged textually.

**M4 — what a person said is written at once, as confirmed.** `@Intake` gets `remember(kind,
scope, situation, text)`. It may only store what the person said in this conversation, with their
words as the evidence and their email as `said_by`; the tool refuses booking ids, secrets and
anything without a scope. `scope: organiser:<email>` goes to their own tree, `person:` and `all` to the
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
edit, retire or delete what M11 allows, and an admin promote. §4.8 builds the reading half first.

### 4.8 The Memory page, read-only first

The console shows the current `organiser.md` and nothing else: the framework's workspace routes
list and read files, and no route reads a journal (akgentic-infra 1.16.0: `/workspace/{team_id}/tree`,
`/file` and an upload, nothing more). `git log` in the container is the only view of the history.
For a demo, *where did it learn that?* is the question memory most needs answered, so the first
Memory page answers it, and changes nothing.

**M14 — the first Memory page reads; changing comes with phase 3.** Two lists for the person
logged in:

- **Mine** — the items in their own `organiser.md`: how they like to meet.
- **About me** — the items in `people/<me>.md` in the shared tree, whoever wrote them.

Each item shows its situation, its text, who said it and when, and opens into its **history**:
the earlier versions it replaced, newest first, with the date and the writer of each. Editing,
retiring, deleting and promoting (M9, M11) wait for phase 3, with the rules they need. That leaves
§8's obligation — a person can delete what is said about them — unmet for now; acceptable while
the people are invented and anyone can log in as anyone (A3 in `design_auth.md`), and the first
thing phase 3 adds.

**M15 — one route of our own, `GET /me/memory`, the email from the session.** Like `/me/agenda`
(`design_auth.md` A12), the route never takes an email from the request: it uses the request user
from the auth strategy, and with `AUTH=off` that is `anonymous`. It reads the two files straight
from the workspace root with the agents' own `parse_items`, not through a `WorkspaceTool` — that
needs an actor, and a read needs no gate. It answers:

```json
{
  "email": "jettro@rag4p.org",
  "mine": [{
    "item": {...},
    "recorded": {"item": {...}, "changed": "2026-11-02T13:24:38+01:00", "by": "@Intake", "outside": false},
    "history":  [{"item": {...}, "changed": "2026-11-02T13:24:26+01:00", "by": "@Intake", "outside": false}]
  }],
  "about_me": [{"item": {...}, "recorded": {...}, "history": []}],
  "journal": true
}
```

The route is the server's (`meeting_server/memory_page.py`), next to M12 and M13, because the
server owns the root; the framework's routes would not serve `_shared` anyway (§10.1 S4).

**M16 — history is read from the journal, item by item, along `supersedes`.** The journal commits
files, and its author is the **agent** (`write: organiser.md | @Intake`, §10.1 S1), not the person
— who said it is in the item, as `said_by`. So the route:

1. runs `git log --format=%H %aI %an -- <file>` on the tree's journal (`<tree>.git`, with
   `--work-tree`), newest first, at most 50 commits;
2. reads each version with `git show <sha>:<file>` and parses its items;
3. for every current item, follows `supersedes` back through those versions: each earlier item it
   finds is one history entry, dated by the commit that first held it - when it was said. The
   current item gets the same, as `recorded`.

Following `supersedes` rather than matching on situation keeps the history what the code decided
it was (M4's replacement), not a guess. Git runs with a timeout and a scrubbed environment — no
`GIT_*`, no global config — for the same reasons the journal does. With no journal (no git, or
nothing recorded yet), items are listed without history and `journal: false` says why, so a
missing git is visible, not silent as it was (changelog, 2026-11-02). A hand edit is committed as
`out-of-band` when the tool next writes that tree (§10.1 S1 saw one); the page names such a version
*changed outside the planner*.

**What links where.** An item's `evidence` names its conversation. The page links it to that
conversation's trace only when the conversation is the reader's own — it always is under *Mine*;
under *About me* it usually belongs to whoever wrote it, and `OwnerOrAdminPolicy` would answer 404,
so the page names the writer instead (*said by Jettro, in their conversation*).

**What it needs in the GUI.** A **Memory** entry in the navigation and `pages/MemoryPage.tsx`: the
two lists, each item a row that expands into its history, and a line when `journal` is false. It
uses the session the other pages use, and refreshes when the page opens — memory changes in
conversations, not while you look at it.

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
| M12 | **One workspace root: the server sets `AKGENTIC_WORKSPACES_ROOT` from `WORKSPACES_ROOT`** | Otherwise the agents write off the volume and the console reads an empty directory (§10.1 S3) |
| M13 | **The server settles sharing at startup: unset becomes `id`, a value without `id` stops it** | A refused bind leaves a half-wired agent in a team that was built anyway (§10.1 S5) |
| M14 | **The first Memory page reads — mine, and about me, each item with its history; changing waits for phase 3** | *Where did it learn that?* is the demo's question, and editing needs M11's rules |
| M15 | **One route of our own, `GET /me/memory`, the email from the session, reading the files directly** | The framework serves no journal and no `_shared` path; a read needs no actor and no gate |
| M16 | **History is read from the journal along `supersedes`; who said it comes from the item, not the commit** | The journal's author is the agent; `supersedes` is what the code decided was replaced |
| M17 | **A place is named by `@FacilityManager` through a typed `look_up_place`, and remembered under its location id** | Only the facility manager sees the places; a name someone typed is not found again (§10.3 P1) |
| M18 | **Place facts are selected by code in both facility-manager handlers, on a `remembered` field the coordinator never fills** | A room is chosen at booking, not when the location is found (P2); the coordinator stays deterministic |
| M19 | **The facility manager binds the shared tree only: `MemoryTool(personal=False)`** | An organiser's own memory must not reach the model that holds `book_room` (P5) |
| M20 | **The organiser's place preferences reach the wish through `@Intake`'s prompt** | Code cannot tell which items are about places; the slot gate shows the choice anyway (P3) |
| M21 | **Phase 3 in three parts: a person manages (3a), agents propose (3b), the memory keeper (3c)** | Each relies on the one before; an agent may suggest, a person decides |
| M22 | **Who may see and change each list, decided by the server from the session; 404 otherwise** | M11 made concrete; a button is not a check |
| M23 | **A fourth list, *Said by me*** | What you said about someone else was invisible to you once said |
| M24 | **An edit is a new version that supersedes, with the editor as `said_by`** | The history shows the old words and who changed them |
| M25 | **A delete removes the item from the file, not from the journal** | Deleting is not erasing; erasing waits for real names (Q6) |
| M26 | **The server writes as an agent does - both locks, re-read, atomic write - and commits as the person** | The journal names who changed it; an agent's gate sees the change |
| M27 | **`PUT` and `DELETE /me/memory/items/{id}`, looked up only in files the session may change** | No path from the request; the page redraws from disk |
| M28 | **No *retired* in 3a** | The journal keeps old versions; `retired` is left for the keeper (3c) |
| M29 | **A suggestion is a question; an accepted one is stored as said, confirmed** | Keeps "a person decides" without a *proposed* status |
| M30 | **Offer in the conversation, and on the Memory page from the person's own earlier meetings, read by code** | What is new, and what has piled up; nothing stored until yes |
| M31 | **A remembered meal for a kind of meeting settles the lunch wish, and `@Intake` says so** | Like M20 for places; today's words win |
| M32 | **Suggestions are computed on each page read from the person's own meetings, in process** | S10: the owner filter is the framework's; nothing copied |
| M33 | **Repeating: the same people in 2+ meetings, the same title with a lunch wish 2+ times** | Plain and checkable; two so a demo can show it |
| M34 | **Accepting writes to *Mine* through 3a's path, a team with the name the person gives** | Said by the person; the journal names them |
| M35 | ***Not now* goes to `declined.md` in the person's own tree, which no agent reads** | Q11: an offer refused is not made again |
| M36 | **`@Intake` offers once, after the request, by its prompt** | An offer is a question; the page catches what it misses |
| M37 | **A remembered meal fills the lunch wish, said in `@Intake`'s one sentence** | M31 made concrete, like M20 |
| M38 | **The keeper is a team of its own, `memory-keeper`, started by *Tidy up* on the Memory tab** | One model call a person asks for, traced and costed like any run |
| M39 | **It reads only *Mine*, put in its request by code** | One owner per list it tidies; shared lists wait (Q14) |
| M40 | **Merge, retire or reword - at most five, each checked by code before it is shown** | The model judges; code decides what may be shown |
| M41 | **Proposals live in `proposed.md`, which no agent applies** | A separate file says *not yet* more plainly than a status |
| M42 | **Accepting changes *Mine* through 3a's path, as the person** | The history says the keeper proposed it and who accepted |
| M43 | ***Not now* goes to `declined.md`, and is not proposed again** | As for suggestions (M35) |
| M44 | **The page watches the keeper's state until it is done** | The framework's `agent-states`; nothing new on the server |
| M45 | **The one conversation offer comes after the booking, when code invites it** | The person has seen the place and the lunch; a failure invites nothing |
| M46 | **One of four: a place or a lunch for this kind of meeting, a lunch for these people, a team** | Each can be used next time; a time cannot yet (Q17) |
| M47 | **A remembered lunch for these people fills the wish like one for a kind of meeting** | M37, widened |

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

0. **Spike** — done 2026-11-02, §10.1.
1. **Phase 1 — confirmed facts and preferences** (cases 1–4, 6): one root and the start-up check
   (M12, M13); the item format, the two trees and `MemoryTool`; the `remember` / `recall` tools and
   the always block on `@Intake`; `MemoryApplied`; the scenarios of §6 against the scripted model.
2. **Phase 2 — before the action** (cases 4, 8), as checked in §10.3: `look_up_place` and
   place facts (M17), selection in both facility-manager handlers (M18), the shared-only card
   (M19), the wish (M20), and Places on the Memory page.
3. **The read-only Memory page** (M14–M16): `GET /me/memory` with the history, and the page.
   Before phase 2, because it is what shows phase 1 and 2 at work.
4. **Phase 3 — proposed lessons and review** (case 5): proposed writes; on the Memory page edit,
   delete, promote and retire under M11; and then the memory keeper.
5. Live runs, the docs, the changelog.

**Step 3 built (2026-11-02).** `meeting_server/memory_page.py` and `pages/MemoryPage.tsx`, as
§4.8 describes. Verified live: Jettro said his stand-ups last 60 minutes and corrected it to 30; the
page showed the 30 with the 60 struck through under *History*, both linked to the conversation.
Logged in as Sanne, *About me* showed "vegetarian", said by Jettro, *in their conversation*.

### 10.1 The spike — run 2026-11-02

Throwaway code in the session's scratchpad: a `SpikeMemory` card holding two `WorkspaceTool`s
(`memory`, and `memory-shared` with `workspace_sharable=True`, both journaled) on an `@Intake`
subclass, in a real actor system, for two owners. Items 1, 2, 4 and 5 were run; item 3 was read
from the server's source.

- **S1 — code can write through the gate, and the journal attributes it.** Writing
  `organiser.md` from our card through `workspace_write` worked; overwriting it after a
  `workspace_read` worked. The journal holds `write: organiser.md | @Intake` per change, after one
  `out-of-band` commit of the seeded `.gitignore`.
- **S2 — the always block works, and survives a restore.** A `ContextState` provider on our card
  put *"What you remember about this organiser: Daan means Daan Jansen."* into the agent's context
  update. After `stop_team` and `resume_team` the agent still had `user_id`
  `jettro@rag4p.org`, read the same file, and rendered the same block.
- **S3 — two roots.** `WorkspaceTool` writes under `AKGENTIC_WORKSPACES_ROOT` (default
  `./workspaces`); the server's routes read `CommunitySettings.workspaces_root`. Read from source;
  our Dockerfile sets only `WORKSPACES_ROOT`. → M12.
- **S4 — what the routes show** (read from source, `services/_workspace_paths.py`,
  `routes/_team_access.py`): workspaces are found by scanning each agent's top-level `tools` for
  `WorkspaceTool`, so a card nested in ours would be invisible; a `_shared` path is refused with
  403 for every caller. → the card's shape (§4.5) and the Memory page's own route (§4.2).
- **S5 — a refused shared bind does not stop the team.** Without
  `AKGENTIC_WORKSPACE_SHARED_KINDS`, the bind raised the documented `ValueError` — but in the
  agent's `on_start`, and `TeamFactory.build` returned a team whose agent had its personal tree and
  no shared one. The same held for a plain shared `WorkspaceTool`, so this is the framework's
  behaviour in-process, not our wrapper's. → M13.
- **S6 — two owners, one shared file.** Jettro and Daan both read
  `people/sanne@rag4p.org.md`; Jettro wrote; Daan's write was refused (*"it changed since you read
  it"*), the file kept Jettro's version, and Daan's re-read-and-write then landed. → write rule in
  §4.5.
- **Two owners, two trees** — Daan's team could not see Jettro's `organiser.md`, and both saw the
  shared `people/` file: §4.1 as designed.

Not covered: the console against a real team (S4 is from source), and `depends_on` wiring order for
the card shape in §4.5 — both are the first test of phase 1.

### 10.2 What building phase 1 taught us

Built: `agents/src/meeting_agents/memory.py` (the item format, `MemoryTool`, the always block,
`MemoryApplied`), `remember` on `@Intake` and memory in its lookup update, the catalog entries
`memory` and `memory_tree`, `server/src/meeting_server/memory.py` (M12, M13), and the trace showing
`MemoryApplied` among the messages. Tests: `agents/tests/test_memory.py` (the §6 scenarios and the
item format), `server/tests/test_memory_config.py`, `server/tests/test_memory_server.py`.

- **A model calls `remember` twice in one turn, in parallel — and one was lost.** Found in the
  first live conversation: "my team" and "my stand-ups" both answered *Remembered*, and only the
  second was in the file. The write gate guards against *other* writers; to the gate, the first
  write was this agent's own view, so the second replaced it. Fixed with one lock per memory file
  in the process; a test runs eight `remember` calls at once, and fails without the lock every time.
- **The card shape changed from the spike's proposal.** `depends_on` was not needed: private trees
  keep the file tools from the model, and one declared, capability-less card is enough for the
  console. The shared tree is not declared, so the framework's routes answer 404 for it rather than
  the 403 the spike read in the source — not visible either way.
- **M13 became "settle it" rather than "refuse".** The deployment's own catalog asks for the
  shared tree, so an unset variable is set; only a value that forbids it stops the server.
- **The live check, three conversations** (`AUTH=demo`, the real model):
  1. as Jettro: *"my team means Sanne and Daan, my stand-ups are 30 minutes"* and *"Sanne is
     vegetarian"* — two items in `jettro@rag4p.org/_id/memory/organiser.md`, one in
     `_shared/_id/memory-shared/people/sanne@rag4p.org.md`, said_by Jettro. The model looked Sanne
     up before remembering a fact about her, as the tool requires.
  2. as Jettro, a new conversation: *"Plan a stand-up with my team"* — it proposed a 30-minute
     stand-up with Sanne de Vries and Daan Jansen, and said Sanne is vegetarian. Two
     `MemoryApplied` events: the always block, and the lookup that settled Sanne.
  3. as Daan: *"What do you know about my stand-ups?"* — nothing; but the lookup for Sanne
     brought *vegetarian* along.
  In the GUI's trace the two `MemoryApplied` rows sit between the messages, with their reason.
- **Not yet:** whether the model uses a remembered fact is the model's business — in one browser
  run it asked "what kind of lunch?" without mentioning Sanne's diet, though the fact had reached
  it. Phase 1 guarantees delivery, not use; the §6 scenarios test the former, live evals would
  test the latter.

**Later, when "like last time" is actually wanted — episodes (case 7, M5).** First a spike: can a
read-only lookup over the coordinators' snapshots serve `@Intake` without copying anything; only
if not, the index in `episodes/` and the small deterministic actor that writes it.

### 10.3 Phase 2, checked against the code (2026-11-02)

Read against `messages.py`, `specialists.py`, the two catalogs and the location service's seed
before building. Five findings change the plan of §4.4:

- **P1 — places have stable ids, and only `@FacilityManager` sees them.** Eleven locations, each
  with an id (`library`, `meet-nature`) and rooms with a code inside it (`meet-nature` / `meadow`).
  `@Intake` never sees the list: the facility manager is the only agent with the location MCP
  server (D1), and the wish travels as words (`design_chat.md` §13.1). So `@Intake` cannot name a
  place by id, and a fact filed under the name someone typed - "the meadow" - would not be found
  again.
- **P2 — a room is chosen at booking, not when the location is found.** `FindLocationAssignment`
  picks a location; `BookFacilitiesAssignment` names only the location, and the facility
  manager's model picks the room. Case 8 - *the meadow room is too noisy for a workshop* - matters
  at both moments, so place facts must arrive at both handlers, not only the first one §4.4 names.
- **P3 — the organiser's place preference already reaches the wish, by the model.** "Focus
  sessions go to the Library" is in `@Intake`'s always block, and the prompt asks for a place in
  the person's own words; the model can fold one into the other, but nothing makes it. The form
  team has no `@Intake` at all, and its form asks for a place outright.
- **P4 — one facility manager serves both teams.** The chat team references the form team's agents
  (`shareable: true`), so memory on the facility manager helps plans made from the form too.
- **P5 — `MemoryTool` binds both trees and always adds the organiser block.** On the facility
  manager that would put the organiser's own memory in front of a model that holds `book_room` -
  exactly what §4.4 keeps out. The card needs a way to bind the shared tree only.

The decisions that follow from them:

**M17 — a place is named by the facility manager, the way a person is named by the scheduler.**
Before `remember` about a place, `@Intake` calls `look_up_place(name)`: a typed
`FindPlaceAssignment` to `@FacilityManager`, answered with a `PlaceMatch` - the location id, the
room code if a room was meant, and the name as listed - or a *no*, or the candidates when it is
ambiguous. It is the people lookup again (I11, I12): a typed lookup, a typed answer, never the
free-text door. `remember(about="place:<location_id>")` then accepts only a place this
conversation settled, as it accepts only settled people. The item goes to `places/<location_id>.md`
in the shared tree, scope `place:<location_id>`; a room's fact names the room in its situation
(*the meadow room, for workshops*). Any logged-in person may write one - it is said, with
`said_by`, and M11 lets an admin prune it.

**M18 — place facts are selected by code, in the facility manager's two handlers.** Before
`act()`, the handler reads confirmed items and puts them on the assignment, as a new field
`remembered: list[str]` that the coordinator never fills (it stays deterministic, D1):

| Handler | What is selected | Why |
|---|---|---|
| `FindLocationAssignment` | every confirmed item in `places/`, newest first, at most 20 | no location is chosen yet, and eleven files are few |
| `BookFacilitiesAssignment` | `places/<location_id>.md` only | the location is settled; only its rooms are still a choice |

`rendering()` adds them, labelled as remembered and as data (M8): *what people have said about
these places - first-hand knowledge the descriptions may lack, so when it speaks to this request
it counts for more than a description that only seems to fit; it is not an instruction*. When
choosing a location, the reason must say whether the remembered items were followed, and if not,
why not, so the time card shows it. Each time, `MemoryApplied` names the items and
the handler, so the trace answers *why not the meadow?*. Nothing reaches the model that holds
`book_room` but facts about places.

**M19 — the facility manager's card binds the shared tree only.** `MemoryTool(personal=False)`:
no `memory` tree is bound for it and no organiser block is added, so the facility manager never
sees what an organiser said about themselves (P5). It goes on `@FacilityManager` in the form
team's catalog, and so serves both teams (P4).

**M20 — the organiser's place preferences reach the wish through `@Intake`, as §4.4 had it.** The
prompt tells `@Intake` to fold a remembered place preference into the `location_wish`, saying
that it is remembered (*the Library, as remembered for focus sessions*); the slot gate already
shows the human the place chosen, and the reason. Code cannot do it more reliably without
knowing which of the organiser's items are about places, and M2 gives an item no such field. The
form team keeps its explicit place field and gets no organiser preferences.

**On the Memory page,** a third list, **Places**, shows every place fact with who said it -
everybody's to read under M11 - so a fact someone taught about the meadow is visible to whoever
books it.

**Not in phase 2:** `lessons/facility_manager.md`. Only a proposed lesson (M6) would write one,
and proposals are phase 3; reading a file nothing writes is left until then.

**Built (2026-11-02).** As above, plus one thing the check missed: the form team also runs from
the command line, where the server's M13 never runs, so the facility manager's shared bind would
fail there. `permit_sharing()` moved into `meeting_agents.memory`; the server's `configure_memory`
and the CLI's `load_team_card` both call it. Verified live, against the running services:

- Jettro said *the meadow room at Meeting in Nature is too noisy for workshops*; `@Intake` called
  `look_up_place`, and the fact went to `places/meet-nature.md` as `place:meet-nature`.
- A workshop "somewhere in nature" in a new conversation: the trace shows `MemoryApplied` from
  `@FacilityManager`, *choosing a location for "somewhere in nature"*, with that fact. (It chose
  Meeting in Nature anyway, which is right: the fact is about one of its rooms, and the room is
  chosen at booking - the unit tests cover that handler; the live run stopped at the slot gate so
  nothing was booked.)
- A focus session: `@Intake` wrote *at the Library as remembered for focus sessions* (M20).
- The Memory page lists the fact under **Places**.

Seen on the way, not changed: the headcount counts the participants and not the organiser, and
`@Intake` sometimes announces a request and waits for a "yes" before calling `plan_meeting`.

### 10.4 Phase 3, checked against the code (2026-11-03)

Phase 3 is where a person takes control of what is remembered: they see it, change it and
remove it, and - later - accept or refuse what an agent suggests. The Campus run showed why it
matters: a memory written as an order (*choose Campus*) can today only be fixed by telling the
planner again. Checked against `meeting_server/memory_page.py`, `meeting_agents/memory.py` and
akgentic-tool's workspace journal and write gate, as installed.

**What the code offers.** Everything a write from the server needs is in the framework, and
public:

- `write.gate.lock_file_for(meta_dir, path)` and `locks.hold(...)` - the per-file `flock` the
  agents' own write gate takes, across processes;
- `locks.atomic_write(target, payload)`;
- `journal.GitJournal(root, enabled=, timeout_s=, meta_dir=)` with `commit_out_of_band()` and
  `commit_paths(paths, identity, capability)`, and `models.Identity(name, email_local)` for any
  author - not only an agent;
- `workspace.meta_dir_for(workspace_path)` for the lock and journal directory beside a tree.

The agents' gate checks a file's digest before it replaces it, so a page edit between an agent's
read and its write is refused, and `MemoryTool._write` already reads again and retries once. Teams
run in the server process, so the per-file lock `_lock_for` in `meeting_agents.memory` is shared
with the page as well. The request user carries `roles`, and `admin` is among them for
`ADMIN_EMAILS` (`auth.py`).

**What is missing.** The page only reads. There is no list of what *I* said about other people -
an item in `people/sanne@….md` written by Jettro is shown to Sanne, never to Jettro. Nothing sets
`status: proposed`, and nothing reads it but `applies()`.

**M21 — phase 3 comes in three parts, each built and shown before the next.**

| Part | What it gives | Why in this order |
|---|---|---|
| **3a — a person manages** | edit and delete on the Memory page, under M22 | it is the control every later part relies on, and the obligation M14 left open |
| **3b — suggestions** | the planner offers what you keep repeating - a team for a group, a meal for a kind of meeting - and stores it only on your yes | a suggestion is only safe once a person can manage what it becomes |
| **3c — the memory keeper** | an agent that reads a file and proposes merges and retirements, as 3b proposals | it needs 3b to say anything at all |

The rule across all three is the one from the notes: *an agent may suggest, a person decides.*
Nothing an agent concludes is applied before a person accepted it.

This section designs 3a in full and 3b in outline (M29-M31); 3c is sketched. 3b and 3c get their
own check against the code when 3a is built.

**M22 — who may do what, made concrete (M11).**

| Item | Who sees it | Who may change or delete it |
|---|---|---|
| **Mine** - `organiser.md` in your tree | you | you |
| **About me** - `people/<you>.md` | you, and whoever said it | you |
| **Said by me** - an item in `people/<other>.md` with `said_by` you | you, and the person it is about | you, and the person it is about |
| **Places** - `places/<id>.md` | everybody | whoever said it, and an admin |

The server decides, from the session, for every change; the page shows a button only where the
server would allow it, but the button is not the check. A change to an item the person may not
change answers **404**, as the framework does for a team that is not yours - it does not say that
the item exists.

**M23 — *Said by me* is a fourth list.** What you said about other people is yours to see and
withdraw: today it is invisible to you once said. The route finds it by reading `people/*.md` -
a handful of files - for items with `said_by` you.

**M24 — an edit is a new version, never an overwrite.** The page changes the *situation* or the
*text*. The new item keeps the kind and the scope, and gets `said_by` the person who edited it,
`reason: changed on the Memory page`, `evidence: memory page`, and `supersedes` the item it
replaces - so the history shows the old words, struck through, and who changed them. The same
refusals as `remember` apply: no secrets, no ids, nothing empty.

**M25 — a delete removes the item from the file; the journal keeps it.** The item stops being
applied at once, and the file - what is true now - no longer holds it. The history is not
rewritten: the earlier version is still in the journal, which is what lets a person see what
was there. **Deleting is therefore not erasing.** For invented people in a demo that is right;
before real names go in, erasing an item about a person from the journal too is the first thing
to add (Q6).

**M26 — the server writes as an agent does, with the person as author.** For one change:

1. take the in-process lock for the file (`_lock_for`), then the framework's per-file `flock`
   (`lock_file_for`, `hold`) - the two the agents take;
2. commit anything already changed by hand as `out-of-band`, as the gate does;
3. read the file again, inside the locks; find the item by id; apply the one change;
4. write it with `atomic_write`, and commit that path through `GitJournal` under an `Identity`
   named after the person's email.

The journal then says who changed it - *jettro@rag4p.org*, not `@Intake` and not `out-of-band` -
and the history on the page reads *changed on the Memory page by you*. An agent writing the same
file a moment later is refused once by its gate, reads again, and writes on top (§4.5).

**M27 — two routes, the item by its id.** `PUT /me/memory/items/{id}` with `{situation, text}`,
and `DELETE /me/memory/items/{id}`. The server looks for the id only in the files the session may
change (M22), never in a path the request names. Both answer the new `MyMemory`, so the page
redraws from what is on disk.

**M28 — no *retired* in 3a.** A delete is enough while the journal keeps the old version; a status
that hides an item without removing it adds a state to explain and a filter to every reader.
`retired` stays in the format for 3c, where it means *the keeper suggests this is no longer
true*.

**3b — suggestions that make organising easier.** The aim is plain: fewer things to say every
time. Two kinds of suggestion are wanted first, and both are things a person would otherwise
repeat:

- **a team for a group** - you keep inviting Sanne, Daan and Femke; call them *the design team*,
  and next time *the design team* is enough;
- **a meal for a kind of meeting** - workshops get soup, stand-ups get no lunch; then the lunch
  question is answered before it is asked.

Both already *work* once said: *my design team is Sanne, Daan and Femke* is an organiser fact
today, and a remembered *lunch for workshops: soup* can reach the lunch wish as a place
preference reaches the location wish (M20). What 3b adds is that the planner **offers** them,
and that every offer ends in the person's own yes.

**M29 — a suggestion is a question, and the answer is what the person said.** There is no
*proposed* item for these: an offer the person accepts is something they said, stored as
confirmed with `said_by` them, through the paths that already exist. Refused, nothing is written.
That keeps M6's rule - nothing an agent concludes is applied before a person accepted it -
without a new status to explain.

**M30 — two places to offer, at the moment it is useful.**

| Where | When | How it is found |
|---|---|---|
| **In the conversation** | after the request, at most once per conversation | `@Intake` looked three or more people up and no remembered group names them: *"Shall I remember Sanne, Daan and Femke as a team? What should I call it?"* Or the person gave a lunch wish for a meeting whose kind has none remembered: *"Shall I remember soup for workshops?"* A yes is `remember`; anything else is left. |
| **On the Memory page** | when the page opens | **code**, not a model, reads the person's own earlier meetings - the coordinators' records the Meetings tab already reads - and offers what repeats: the same people in three or more meetings, the same lunch wish for meetings with the same kind of title. Each offer has *Remember this* and *Not now*. |

The conversation catches what is new; the page catches what has piled up. Neither stores a
suggestion: the page computes its offers each time, from the records, so there is nothing to keep
in step. This is M5's preferred shape for episodes - *read the records, copy nothing* - used for
the first thing that needed them.

**M31 — a remembered meal settles the lunch wish, and `@Intake` says so.** As with M20: when a
meal is remembered for this kind of meeting and the person said nothing about lunch, `@Intake`
puts it in the lunch wish and says it in its one sentence - *"with soup, as remembered for
workshops"*. The lunch question is then not asked, which is the point; nothing is booked before
the time is approved, so a wrong meal is corrected by saying so, or by declining the time. The
person's own words today always win.

**What a *kind of meeting* is** is the open part (Q10): the title's main word (*workshop*,
*stand-up*, *focus session*), as the person said it in the situation. Matching it is the model's
job in the conversation and a plain, lower-case word match on the page - no similarity search,
in keeping with M3.

**Sketch: 3c — the memory keeper.** An agent started on request - *Tidy up* on the Memory page,
not on a timer - that reads one file and proposes: two items that say the same thing as one, an
item a later one contradicts, an item past its `review_when`. Because the keeper is a model, its
suggestions are stored as `status: proposed`, shown beside 3b's offers with the same *Remember
this* and *Not now*, and never applied until accepted; the keeper changes nothing itself. It is
the "background consolidation" of the notes, kept small: one file, one run, a person accepts each
change.

**Spike, before building 3a.**

- **S7** — a page write followed by `remember` on the same file: the agent's gate refuses once, it
  reads again, and both changes are in the file.
- **S8** — the journal's author for a page write is the person's email, and `_versions` shows it.
- **S9** — the per-file `flock` from the server and from a team's actor in the same process do not
  deadlock with the in-process lock (`_lock_for` is always taken first).
- **S10** (for 3b) — the server can read the person's own teams and their coordinators' records
  in process, through the framework's team service, without calling its own HTTP routes.

**Order of work for 3a.** (1) the spike; (2) the write path in `memory_page.py` with its tests,
against real journals as the read path's tests are; (3) the two routes and *Said by me*; (4) edit
and delete on the page, with the history line for a page edit; (5) live run, then
`docs/memory.md`, the demo's act 5 and the roadmap.

**3a built (2026-11-03).** As above. The spike ran first and passed: a page edit between two
`remember` calls kept all three changes, the journal read `@Intake`, `jettro@rag4p.org`,
`@Intake` (S7, S8), and six page writes beside six agent writes, in parallel, lost nothing and
stuck nowhere (S9). Built in `meeting_server/memory_page.py` (`_lists` holds M22, `_rewrite` M26,
`change_item` and `delete_item` M24 and M25, the routes M27) and `pages/MemoryPage.tsx` (Edit and
Delete where `can_change`, a confirmation for a delete, *Said by me*, and *changed on the Memory
page by …* for a page edit). `meeting_agents.memory`'s per-file lock became public, `file_lock`,
so the page and the agents take the same one. Tests: `server/tests/test_memory_edit.py`, sixteen,
against real journals and, for S7 and S9, the real `@Intake`. Two things settled while building:

- An edit that would put two items of the same kind on one situation is refused, not merged -
  the history follows one `supersedes` chain, and a merge would hide one of them.
- The page never creates a journal. It commits into one an agent's card made; a tree without one
  is still written, and the page says *no history* as it already did.

Verified live, against a copy of the stack's memory: the stand-ups item edited to 15 minutes
showed the old words in its history and *changed on the Memory page by you*; an id in the text
was refused on the page with its reason; the Campus place fact reworded as a fact; the journals
named `jettro@rag4p.org` for both. Logged in as Bram, *About me* offered Edit and Delete on what
Jettro said about him, and the Campus fact - not his - offered neither.

**Questions for 3a.**

- **Q6** — Should deleting an item about a person also remove it from the journal? Rewriting
  history is real work and breaks every earlier version's link; not rewriting means a deleted
  item can still be read from the repository. Proposed: not in 3a, recorded as the limit it is.
- **Q7** (3b) — What signal proposes a lesson? *Answered by M30:* what repeats - in the
  conversation and in the person's own earlier meetings - and the person's yes is the signal.
- **Q10** (3b) — What is a *kind of meeting*: the title's main word, or something the person
  names? Proposed: the word as the person said it in the situation (*workshops*), matched by the
  model in the conversation and as a plain word on the page.
- **Q11** (3b) — Should *Not now* on the page be remembered, so an offer is not made again?
  Proposed: yes, as one small item per refused offer in the person's own tree, never applied to
  a meeting.
- **Q8** — May the person who said something about someone else still change it after the person
  it is about has? Proposed: yes - both may, and the history shows both (M22).
- **Q9** — May anyone change a place fact, or only whoever said it and an admin? Proposed: only
  those two; anyone else tells the planner, which adds a version of their own.

### 10.5 Phase 3b, checked against the code (2026-11-03)

3b makes the planner offer what a person keeps repeating, and keeps it only on their yes
(M29-M31). Checked against `meeting_server/memory_page.py` and `app.py` as 3a left them, the
framework's `TeamService` and event store, `@Intake`'s prompt and tools, and - for S10 - a copy of
the running stack's event store.

**S10 — passed.** The server can read a person's own meetings in its own process:
`services.event_store.list_teams(user_id=<email>, status=None, metadata=None)` answers the teams
that person owns - the same owner filter the framework applies to `GET /teams` - and
`load_agent_states(team_id)` gives each team's snapshots, among them `@Coordinator`'s, whose
`plan` holds the title, the participants and the lunch wish. Against the stack's copy it found
nine of Jettro's teams, form and chat alike, and in two of them the same four people: Daan, Femke,
Lotte and Bram. Older plans have no `organiser` (it came with step 5), so *the person themselves*
is recognised by email, not by that field.

**M32 — the Memory page computes suggestions from the person's own meetings, in process.** The
module is handed the framework's `services` (it already exists in `create_meeting_app`) and reads
only `list_teams(user_id=<the session's>)`: nobody's meetings but your own, as on the Meetings
tab. Nothing is copied or stored; every `GET /me/memory` works them out again, and adds a fifth
list, `suggestions`.

**M33 — what counts as repeating, in code, with two constants.**

| Suggestion | Repeats when | Not offered when |
|---|---|---|
| **a team** | the same people besides you - two or more - are in at least `GROUP_AT = 2` of your meetings | an item in *Mine* already names all of them, by name or email |
| **a meal** | meetings with the same title, ignoring case, had a lunch wish at least `MEAL_AT = 2` times | an item in *Mine* is already about lunch for that title |

Two, not three, so that a demo can show it after two meetings; the constants say where to change
it. The meal offered is the most recent wish for that title. A *kind of meeting* is its title
(Q10): plain and checkable, and *Design review* twice is the case worth catching - a word match
inside titles is left until a live run shows it is needed.

**M34 — accepting writes to *Mine*, through 3a's write path.** `POST
/me/memory/suggestions/{key}` with what the person settled:

- **a team** needs a name, which only the person can give - *the design team*. It becomes a fact,
  situation *who "the design team" is*, text the people's names and emails;
- **a meal** is a preference, situation *lunch for "Design review"*, text the wish - which the
  person may change before accepting.

Both are written with `said_by` the person, `reason: accepted a suggestion from N earlier
meetings`, `evidence: memory page`, through `_rewrite` - so the journal names the person, and
the item replaces any earlier one about the same situation, as `remember` would.

**M35 — *Not now* is remembered, in the person's own tree, where no agent reads it** (Q11).
`DELETE /me/memory/suggestions/{key}` adds one line to `declined.md` beside `organiser.md`: the
offer's key and what it was. `MemoryTool` reads only `organiser.md`, so a declined offer never
reaches a model. The key is a digest of what was offered - the set of emails, or the title and
the wish - so a *different* meal for the same title is a new offer.

**M36 — in the conversation, `@Intake` offers once, after the request, by its prompt.** Two
rules join the memory paragraph:

- when three or more people were looked up and nothing remembered names them as a group: *"Shall
  I remember Sanne, Daan and Femke as a team? What should I call it?"*;
- when the person gave a lunch wish and nothing is remembered about lunch for this kind of
  meeting: *"Shall I remember 'soup' for workshops?"*

At most one offer per conversation, never before the request, and only `remember` on a clear
yes. This is the model's judgement, not code's, and that is acceptable here: an offer is a
question, and nothing is applied until the person answers it. The page catches what the
conversation missed.

**M37 — a remembered meal reaches the lunch wish by `@Intake`'s prompt** (M31 made concrete). A
third rule beside the location one: if a lunch is remembered for this kind of meeting and the
person said nothing about lunch, put it in the lunch wish and say so - *"with soup, as
remembered for workshops"*. The coordinator then does not ask about lunch; the person's own words
today always win.

**What changes.**

| Where | What |
|---|---|
| `server/src/meeting_server/memory_page.py` | `suggestions(...)` from the event store; `Suggestion` on `MyMemory`; accept and decline routes; `declined.md` |
| `server/src/meeting_server/app.py` | `MemoryPageModule(settings.workspaces_root, services)` |
| `agents/catalog/meeting-planner-chat/prompt/intake_prompt.yaml` | the two offers (M36) and the meal rule (M37) |
| `gui/src/pages/MemoryPage.tsx` | a **Suggestions** list at the top: *Remember this* - with a name field for a team and an editable wish for a meal - and *Not now* |
| tests | suggestions from scripted plans in a real event store; accept writes as the person; decline is remembered and never applied; the prompt renders with the new rules |

**Order of work.** (1) suggestions in code and their tests; (2) accept and decline, and
`declined.md`; (3) the page; (4) the prompt rules, with a scripted-model test that the rules are
in the prompt; (5) a live run - two meetings with the same people, then the page; two meetings
titled alike with soup, then a third conversation with no word about lunch; (6) `docs/memory.md`,
the demo's act 5, the roadmap.

**3b built (2026-11-03).** As above: `suggestions`, `accept_suggestion` and `decline_suggestion`
in `memory_page.py`, the module handed `services.event_store` in `app.py`, the **Suggestions**
list on the page, and the three prompt rules. Tests: `server/tests/test_memory_suggestions.py`,
twelve, with a stand-in for the two store reads S10 checked against the real one; and a prompt
test in `test_chat_team_card.py`.

Verified live, against a copy of the stack's meetings and memory:

- the page offered *Daan and Sanne* - both design reviews - and **not** Daan, Femke, Lotte and
  Bram, whom *who my team is* already names; accepted as *the review crew*;
- two *Workshop* requests with soup, and the page offered *lunch for "Workshop"*; accepted;
- a new conversation, *a workshop with the review crew, … no word about lunch*: `@Intake` answered
  *"with you, Daan Jansen and Sanne de Vries, somewhere quiet, with soup as remembered for
  Workshop"* (M37);
- three people and a lunch wish: one offer after the request, *"Shall I remember sandwiches for
  planning sessions?"* (M36).

**Found live, and fixed:** the yes to that offer was remembered with `about` set to the person's
own email, not `organiser` - so it went to `people/<me>.md`, a fact *about* them, which their
own conversations never apply. The offer rule now says *with about "organiser"*, and the prompt
test pins it; the next run filed *who the retro group is* in *Mine*. Seen, not changed: with a
remembered place fact in front of it, the facility manager now explains why it did *not* follow
an item that had nothing to do with the request (M18's reason rule) - correct, and a little
wordy.

**Questions for 3b.**

- **Q12** — Two meetings, or three, before an offer? Proposed: two, for now, in one constant each.
- **Q13** — Should an offer accepted on the page also be offered no more in the conversation?
  It is, by M36's rule: once *Mine* names the group, nothing is offered.

### 10.6 Phase 3c, checked against the code (2026-11-03)

The memory keeper tidies what has piled up - and, like everything in phase 3, only suggests.
It is the one part of memory where a model *concludes* something from memory itself, so it is
the part where "an agent may suggest, a person decides" matters most. Checked against the
framework's `TeamService` and `POST /teams`, the planner's `client.ts` and Meetings tab, the
specialists' handler shape, `MemoryTool`, and 3a's and 3b's write paths.

**What the code offers.** The planner already starts teams itself: `POST /teams` with a
`catalog_namespace`, then a typed message from `@Human` - that is how the form and the
conversation begin, and the team belongs to whoever is logged in. A third namespace is a third
kind of team, with nothing new on the server to start it. A team's agents are read back through
`GET /teams/{id}/agent-states`, which the Meetings tab already uses for the coordinator. The
Meetings tab lists only the form's and the conversation's namespaces, and suggestions read only
`@Coordinator`, so a keeper run appears in neither. Every specialist already has the shape the
keeper needs: an assignment in, `act(message, output_type)`, and code that acts on the typed
answer.

**M38 — the keeper is a team of its own, `memory-keeper`, started from the Memory tab.**
*Tidy up* on the *Mine* list creates a team in that namespace and sends it a
`KeepMemoryRequest` from `@Human` to `@Keeper` - one agent, one model call, owned by the person,
in the trace and the console like any other run, with what it cost. Not on a timer: a person
asks, and is there to read the answer (M7, the sketch in §10.4).

**M39 — it reads one list: your own, *Mine*.** `@Keeper` holds a `MemoryTool` on the personal
tree only - like the facility manager's card the other way round - so it reads `organiser.md`
and nothing about other people or places. Its handler, in code, puts the items in the request
with their ids, situations, words and dates; the model reads nothing else. Shared lists have
more than one owner, and tidying them waits for rules about whose say counts (Q14).

**M40 — three kinds of proposal, and code checks each one.** The model answers a
`KeeperAdvice`: a list of proposals, at most five, each one of

| Proposal | When | What it names |
|---|---|---|
| **merge** | two or more items say the same thing | the items, and the one item that replaces them |
| **retire** | a later item contradicts it, or it is plainly out of date | the item, and why |
| **reword** | the words are unclear, or say an order where a fact is meant | the item, and the new words |

Each with a reason a person can check. Code then drops what does not hold: an id that is not in
*Mine*, a merge of fewer than two items, new words that `refusal()` refuses, a proposal declined
before (M43). The model judges; code decides what may be shown.

**M41 — proposals are a file of their own, `proposed.md`, never applied.** `@Keeper` writes
them beside `organiser.md`, in the same front-matter form, each run replacing the last run's
proposals. `MemoryTool` reads only `organiser.md` to apply memory, so a proposal reaches no model
until a person accepts it. The `proposed` and `retired` statuses in the item format stay unused:
a separate file says *not yet* more plainly than a status every reader must remember to skip -
which is what M28 left `retired` for, now settled the other way.

**M42 — accepting changes *Mine* through 3a's write path, as the person.** The page shows the
proposals above *Mine*, each with what it would change - the old items struck through, the new
words beside them - and *Accept* or *Not now*:

- **merge**: one new item, said by the person, superseding the first of the merged items; the
  others leave the file. All of them stay in the journal.
- **retire**: the item leaves the file, as a delete does (M25).
- **reword**: a new version of the item, as an edit does (M24).

`reason` records *accepted the memory keeper's proposal: …*, so the history says where the
change came from; the journal names the person.

**M43 — *Not now* is kept, so the keeper does not propose it again.** As for suggestions (M35):
a digest of the proposal - its kind, its items, its words - goes to `declined.md`, and the
keeper's handler leaves out anything declined before it writes `proposed.md`.

**M44 — the page shows the run.** After *Tidy up*, the page watches `@Keeper`'s state - *done*,
how many proposals, or why it failed - through `agent-states`, and reloads the memory when it is
done. *Nothing to tidy* is an answer too.

**What changes.**

| Where | What |
|---|---|
| `agents/src/meeting_agents/keeper.py` (new) | `MemoryKeeper`: the handler, the checks of M40, writing `proposed.md`; `KeeperState` |
| `agents/src/meeting_agents/messages.py`, `outputs.py` | `KeepMemoryRequest`; `KeeperAdvice` and `Proposal` |
| `agents/src/meeting_agents/memory.py` | the `Proposal` file format, `PROPOSED_FILE`, writing it through the card |
| `agents/catalog/memory-keeper/` (new) | the team, `@Keeper`, its prompt, its personal-only memory card |
| `server/src/meeting_server/memory_page.py` | `proposals` on `MyMemory`; accept and decline routes, through `_rewrite` |
| `gui/src/pages/MemoryPage.tsx`, `api/client.ts` | *Tidy up*, the run's state, the proposals with *Accept* and *Not now* |

**Spike, before building.**

- **S11** — a team in the third namespace, created by `POST /teams` as a logged-in person, binds
  that person's own tree for `@Keeper` and no one else's.
- **S12** — `@Keeper`'s state is readable through `agent-states` while it runs and when it is
  done, and a stopped keeper team is not revived by anything the page does.

**Order of work.** (1) the spike; (2) the format, the handler and its checks, with a scripted
model - every kind of proposal, and every way one is dropped; (3) the catalog namespace and its
card tests; (4) accept and decline on the server; (5) the page; (6) a live run on a *Mine* with
a duplicate and a contradiction in it; (7) the docs.

**3c built (2026-11-03).** As above, with two choices made while building:

- `KeepMemoryRequest`, `KeeperAdvice` and the keeper's state live in `meeting_agents/keeper.py`
  rather than in `messages.py` and `outputs.py`: the keeper team shares no message with the
  meeting teams, and keeping them apart leaves the meeting cards' `MESSAGE_TYPES` as they were.
- `MemoryTool` gained `shared: bool`; the keeper's card sets it false, so the shared tree is not
  even bound (S11, held by a test that finds no `_shared` folder after a run). `parse_blocks` and
  the card's `_read_as` read a proposal file in the same front-matter form as items.

Tests: `agents/tests/test_keeper.py`, seventeen - the card, every way `checked()` drops a
proposal, and runs of the real `@Keeper` with a scripted model (proposals written by `@Keeper`,
*Mine* untouched, nothing to ask with an empty *Mine*, a failed call in the state) - and
`server/tests/test_memory_proposals.py`, nine. 459 tests pass.

Verified live, against a copy of the stack's memory with a contradicting stand-up item and a
lunch item worded as an order added by hand: *Tidy up* showed *Tidying…*, then one proposal -
*Retire* the 30-minute stand-up item, *the later item says stand-ups last 15 minutes, which
conflicts with this item's 30-minute default*. Accepted: *Mine* lost it, and the journal read
`out-of-band`, `@Keeper | write: proposed.md`, then the person for `organiser.md` and
`proposed.md` (S12: the page read the keeper's state through `agent-states` until done). A
second run answered *Nothing to tidy*. It did not propose rewording *Choose soup for every
workshop* - a judgement it may make; the prompt names the case. Fixed on the way: the note
beside *Tidy up* counted the run's proposals, not the ones still open.

**Questions for 3c.**

- **Q14** — Only *Mine*, or also the shared lists? Proposed: only *Mine* for now. A place fact
  has many readers and one writer; whose yes would accept a proposal about it is a rule of its
  own, and the Campus case shows a reword there would be worth having.
- **Q15** — Five proposals at most per run? Proposed: yes - a person reads them all, or none.
- **Q16** — Should the keeper look at `review_when`? Nothing sets it today; proposed: not until
  something does.

### 10.7 One offer after the meeting is arranged (2026-11-04)

A refinement of 3b's conversation offer (M36), asked for after using it: the moment to offer
something worth remembering is when the meeting is **arranged**, not when it is requested -
then the person has seen the place that was chosen and the lunch that arrived, and *"shall I
remember that?"* is about something real. Checked against `@Intake`: when the coordinator
reports `PlanCompleted`, `receiveMsg_PlanCompleted` already tells the model *the meeting is
booked* with the title, the time, the room, the place and what lunch arrived (`describe`).

**M45 — the one offer moves to after the booking, and code says when.** The update for a booked
meeting - and only that one, never a failure or a cancel - ends with the invitation to offer one
thing, if something is worth remembering and is not remembered yet. Code decides the moment; the
model decides what, or nothing. Still at most once per conversation, still only on a clear yes,
still `about "organiser"`.

**M46 — what may be offered: one of four, the most useful one.**

| Offer | When |
|---|---|
| **a place for this kind of meeting** | the place was described, not named, and nothing remembered says where this kind goes - *"Shall I remember the Library for design reviews?"* |
| **lunch for this kind of meeting** | lunch was ordered, and nothing remembered is about lunch for this kind |
| **lunch for these people** | the same, for the people rather than the title - *"…soup when you meet with the review crew?"* |
| **a team** | three or more people, and no group remembered names them |

**Not a time.** A preferred time - *design reviews in the morning* - would be worth offering, but a
request has no field for it: the scheduler finds free slots and the person picks one. A
remembered time could not change anything yet, so it is not offered (Q17).

**M47 — lunch for these people is applied like lunch for a kind of meeting.** M37's rule reads
*for this kind of meeting, or for these people*: when the person says nothing about lunch, a
remembered lunch for either fills the wish, and `@Intake` says so.

**What changes.** `intake.py`: the booked update ends with the invitation (M45).
`intake_prompt.yaml`: the offer paragraph names the four offers and the moment; the lunch rule
reads *or for these people*. Tests: the invitation is in the update for a booked meeting and in
no other; the prompt names the four offers.

**Built (2026-11-04).** As above: `OFFER_NOW` ends the booked update in `intake.py`, and the
prompt's offer paragraph names the four offers and the moment. Tests: the invitation is in the
booked update and not in the cancelled or the time-question one (`test_intake.py`); the prompt
names the four offers and *nothing about the time* (`test_chat_team_card.py`). Verified live
against the running services: a design review *somewhere quiet, with soup* - no offer after the
request; booked at the Library, and then *"Your design review is booked for 1 December,
10:00-11:00, in the study room at the Library, with three soups; shall I remember the Library
for design reviews?"*. On *yes* it went to *Mine* as a preference, *design reviews: Design
reviews in the Library*. The meeting was cancelled afterwards, and the order, the room and the
meeting were released.

**And when there is nothing to offer, it says so** (2026-11-04, asked for after using it). The
booked update's invitation ends: *if there is nothing like that, say it is booked and, in a few
words, that you have nothing new to suggest remembering*; the prompt gives the line, *"Nothing
new to remember from this one."* Verified live: a one-to-one with Daan at Yuma, no lunch, ended
*"… in room room-a at Yuma, with no lunch. Nothing new to remember from this one."* - and was
cancelled and released afterwards.

- **Q17** — Should a request carry a preferred time, so the scheduler offers those slots first?
  Then *design reviews in the morning* could be remembered and used. A change to the request, the
  coordinator and the scheduler; proposed as a step of its own.

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
- 2026-11-02: **Spike run** (§10.1). The two trees, code-driven writes through the gate, the
  journal's attribution, the always block and its restore all hold. Found: two names for the
  workspace root (M12); the console can show only a top-level card's personal tree and never a
  shared one, so the Memory page needs its own route for `memory-shared`; a refused shared bind
  leaves a half-wired agent in a built team (M13); concurrent writers are refused, not merged, so
  every write re-reads first.
- 2026-11-02: **Phase 1 built** (§10.2): the two trees, `remember` and the always block on
  `@Intake`, memory with the lookup, `MemoryApplied` in the trace, M12 and M13 in the server. A
  lost update between two parallel `remember` calls of one agent was found live and fixed with a
  per-file lock. 378 tests pass.
- 2026-11-02: **A record names its owner** (§4.3). Read in the console, `scope: organiser` and
  `evidence: team …` looked like someone else's team. A personal item now says
  `scope: organiser:<email>` and `evidence: conversation <id>`. No support for the old format:
  start memory clean.
- 2026-11-02: **git in the server image.** `python:3.12-slim` has none, and without git on the
  PATH the workspace tool writes no journal and says nothing, so a deployed stack kept memory
  without its history (M1). The journal sets its own author, so the image needs no git config;
  the journal test passes inside the image.
- 2026-11-02: **A read-only Memory page first** (§4.8, M14–M16). The console shows the current
  file and no history, since no framework route reads a journal. Proposed `GET /me/memory`: your
  own items and those about you, each with the versions it replaced, read from the journal along
  `supersedes`. Editing stays in phase 3, now step 4.
- 2026-11-02: **The read-only Memory page built** (§10, step 3). Each item also carries
  `recorded`, when its current version was said; history entries are dated by the commit that
  first held them. 386 tests pass.
- 2026-11-02: **Phase 2 checked against the code** (§10.3, M17–M20). A place can only be named by
  the facility manager, so `@Intake` looks it up first; a room is chosen at booking, so place
  facts reach both handlers; the facility manager binds the shared tree only. Lessons wait for
  phase 3.
- 2026-11-02: **Phase 2 built** (§10.3): `look_up_place` and place facts, selection in both
  facility-manager handlers, the shared-only card, the wish, Places on the Memory page, and
  `permit_sharing` for the command line too. 397 tests pass.
- 2026-11-02: **Place facts count for more than a vague description** (M18). Live, a remembered
  "sportive environment means Campus" reached the facility manager and lost to Meeting in Nature,
  whose description mentions outdoor activities: *weigh it with the descriptions* let a line of
  marketing outweigh what a person said. The block now calls it first-hand knowledge that counts
  when it speaks to the request, still not an instruction, and the chosen location's reason says
  whether it was followed.

- 2026-11-03: **Phase 3 designed** (§10.4, M21-M28, Q6-Q9), checked against the installed
  workspace journal and write gate: the server can write as an agent does, with the person as the
  journal's author. 3a - edit, delete and a *Said by me* list on the Memory page - first; 3b
  proposals and 3c the memory keeper sketched. Three spike items, S7-S9.
- 2026-11-03: **3b given its first cases** (M29-M31, Q10, Q11), at the person's request: suggest a
  team when several people are invited, and a meal per kind of meeting. A suggestion is a
  question, offered in the conversation or computed on the Memory page from the person's own
  earlier meetings, and stored only on their yes. Q7 answered.
- 2026-11-03: **3a built** (§10.4): edit, delete and *Said by me* on the Memory page, the server
  writing as an agent does and committing as the person. Spike S7-S9 passed first; sixteen tests;
  verified live. 420 tests pass.
- 2026-11-03: **3b checked against the code** (§10.5, M32-M37, Q12-Q13). Spike S10 passed: the
  server reads a person's own meetings and their plans in process. Suggestions are computed from
  them on each read, accepted through 3a's write path, and a *Not now* is kept where no agent
  reads it; `@Intake` offers in the conversation by its prompt.
- 2026-11-03: **3b built** (§10.5): suggestions on the Memory page from the person's own
  meetings, accepted into *Mine* or declined into `declined.md`; `@Intake` offers once after the
  request and fills a remembered meal into the lunch wish. Verified live; one prompt fix found
  there (*about "organiser"*). 433 tests pass.
- 2026-11-03: **3c checked against the code** (§10.6, M38-M44, Q14-Q16): the memory keeper as a
  team of its own that the Memory tab starts, reading only *Mine*, proposing merges, retirements
  and rewordings that code checks, kept in `proposed.md` until the person accepts. M41 settles
  M28's open end: proposals are a file, not a status. Spike items S11 and S12.
- 2026-11-03: **3c built** (§10.6): the `memory-keeper` team, `@Keeper` reading only *Mine* and
  proposing through code's checks, proposals accepted or declined on the Memory page. Verified
  live. 459 tests pass. Phase 3 is done.
- 2026-11-04: **One offer after the meeting is arranged** (§10.7, M45-M47, Q17), asked for after
  using 3b: the conversation's offer moves from after the request to after the booking, and may be
  a place or a lunch for this kind of meeting, a lunch for these people, or a team. Not a time:
  a request cannot carry one yet. Built and verified live the same day.
- 2026-11-04: **Nothing to offer is said too** (§10.7): after a booking with nothing worth
  remembering, `@Intake` says *nothing new to remember from this one*.

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
