# Demo script

A walk through the sample, in the order that tells the story best: the services, the team that
books, who is asking, the conversation, and then memory, one kind at a time. Every act stands on
its own, so for a short demo pick acts 1, 4 and 5.

Times are rough: the whole script is about 40 minutes, act 5 alone about 15.

| Act | What it shows | Minutes |
|---|---|---|
| [0](#0-before-you-start) | getting a clean stack | before |
| [1](#1-the-services-and-the-team-that-books) | services, the form, the two gates, the trace | 8 |
| [2](#2-who-is-asking) | the login: your meetings are yours | 4 |
| [3](#3-the-framework-underneath) | the akgentic console: the team, not the meeting | 4 |
| [4](#4-the-team-you-talk-to) | a meeting from a conversation | 5 |
| [5](#5-it-remembers) | memory: yours, about a person, about a place, suggestions, the keeper, and its limits | 15 |
| [6](#6-cancelling) | cancelling releases everything | 2 |

---

## 0. Before you start

**Build and start** from the repository root, with an `OPENAI_API_KEY`, `AUTH_SECRET`,
`ADMIN_EMAILS` and `API_KEYS` in `.env` (see `.env.example`):

```bash
make build && make up
```

**A clean start.** `make reset` wipes everything - meetings, traces and memory - and the seed
puts the people, places and menu back on the next `make up`. To keep the meetings but start
memory over:

```bash
docker compose exec server sh -c 'rm -rf /data/workspaces/*/_id/memory*'
```

**Open these tabs, all on `localhost`** - not `127.0.0.1`, which is a different site and gets no
login cookie:

| Tab | URL |
|---|---|
| The planner | <http://localhost:8300> |
| The console | <http://localhost:8400> |
| Meeting service (people, agendas) | <http://localhost:8001> |
| Location service (places, rooms) | <http://localhost:8002> |

**The people.** Anyone the meeting service knows can log in: Sanne de Vries, Daan Jansen, Femke
Bakker, Bram van Dijk, Lotte Visser, Thijs de Jong, Anouk Smit, Joris Mulder, Marieke Hendriks,
Sven Peters and Jettro Coenradie. Use your own login as the presenter, and **Sanne** and **Daan**
as the other two people - check they are not in `ADMIN_EMAILS`, because an admin sees everyone's
meetings and that spoils act 2.

**Pick a day** a week or so ahead, on a weekday. The examples say *Tuesday 10 November*; use your
own.

---

## 1. The services and the team that books

**Say:** three ordinary services - people and agendas, places and rooms, a lunch menu - each with
its own database and REST API, and each with an MCP server for agents. A team of four agents
plans a meeting across them. Each agent can reach exactly one service; a test holds that line.

1. **Platform tab.** The three services, polled every ten seconds. *Degraded* and *unreachable*
   are kept apart: a 503 and a silence have different causes.
2. **Plan a meeting.** Title *Design review*, participants Sanne and Daan, the day, 60 minutes,
   and under *Describe the place*: **somewhere quiet**. *I attend* is ticked: you are the
   organiser, and you count - the team takes who you are from your login, not from the form.
   Send it.
3. **The first gate: the time.** The card names the place the facility manager chose - the
   Library, probably - and **why**. Point out that approving the time approves the place, and
   that nothing is booked yet. Pick a slot.
4. **The second gate: lunch.** Answer in your own words: *something vegetarian, no bread*. Only
   `@Catering` sees the menu, so only it reads the words.
5. **The confirmation** says what was booked, including what lunch actually arrived.
6. **Trace tab.** About twenty rows that read like a story: who asked whom for what. Click a row
   for the whole message. Then switch on **Framework events**: the actor system starting,
   receiving and processing - the "what happens underneath" view.
7. **Meeting service tab → Persons → Sanne.** Her agenda now lists the design review under
   *Upcoming meetings*; below it, the free-slot picker the scheduler uses.

**Point to make:** the coordinator is plain code, not a model. It never learns lunch exists -
the facility manager arranges it with `@Catering` - and it is the meeting's only record.

---

## 2. Who is asking

**Say:** the framework already decides who may see which team - the owner, or an admin. The
sample tells it who is asking. There is no password: this shows users, not security.

1. **Log out**, and log in as **Daan**. **Meetings** is empty: the design review is not his - he
   did not arrange it - and asking for it by id answers 404, as if it did not exist.
2. Log out, and log in as **yourself** again. The meeting is back.
3. If you are in `ADMIN_EMAILS`, mention that an admin sees everybody's meetings.

---

## 3. The framework underneath

**Say:** the planner shows the *meeting*; the akgentic console shows the *team*. It is the
framework's own front end, unmodified, against the same server.

1. **Console tab.** Log in with the API key from `API_KEYS` that maps to your email.
2. Open the design review's team: the transcript with each agent's thinking, the roster, the
   hierarchy as a graph, and what the run cost.
3. Open an agent's **LLM context** and **system prompt**: this is exactly what the model saw.

---

## 4. The team you talk to

**Say:** the same team, with one agent in front - `@Intake` - that holds the conversation and
makes one typed request, the same one the form sends. It cannot approve anything: the time is
still answered on its card.

1. **Talk to the planner.** *A design review with Sanne and Daan on Tuesday 10 November,
   somewhere in nature, no lunch.*
2. `@Intake` looks the names up through `@Scheduler` - a name is never guessed into an email.
   You are not looked up: it knows who it is talking to, and you attend unless you say so.
3. It requests the meeting at once and says in one sentence what it asked for.
4. The time card appears inline, with the place and why. Pick a slot; type *the second one* in
   the chat instead to show it is understood but **authorises nothing**.
5. **Trace** shows `@Intake` in front of the same team as act 1.

---

## 5. It remembers

**Say:** one team arranges one meeting and is gone, so anything you tell it would be forgotten.
Memory is what outlives the team: plain files a person can read, each change recorded with who
made it, and always shown to the model as *what was remembered*, never as an order.

There are four kinds, each in its own place:

| Kind | Example | Where | Who reads it |
|---|---|---|---|
| **Yours** | who "my team" is, how long your stand-ups are | your own tree | only your conversations |
| **About a person** | Sanne is vegetarian | the shared tree, `people/` | anyone who books with Sanne |
| **About a place** | the meadow room is too noisy for workshops | the shared tree, `places/` | the facility manager, for everyone |
| **Your place preferences** | focus sessions go to the Library | your own tree | `@Intake` puts it in the wish |

### 5.1 Yours - and it arrives on its own

1. **Talk to the planner**, as yourself: *Please remember: my team is me, Sanne and Daan. And my
   stand-ups last 60 minutes. No meeting to plan now.* It says it will remember.
2. **New conversation:** *Plan a stand-up with my team on Tuesday 10 November, no lunch.* It
   knows who "my team" is and should make it 60 minutes, without asking - it is a model using
   what it was told, so check what it says before you move on. Stop at the time card - or
   pick a slot, and cancel it in act 6.
3. **Trace:** a `MemoryApplied` row from `@Intake` - *always: the organiser's own memory* - and
   the items it got. This is the answer to "how did it know?".
4. **Console → this team → `@Intake` → LLM context:** the block *What you remember about how … likes
   to meet*, labelled as their own words and not an instruction now.

### 5.2 Changing your mind, and the history

1. In a conversation: *Correction: my stand-ups last 30 minutes, not 60. Remember that instead.*
2. **Memory tab → Mine:** *stand-ups*, 30 minutes, said by you, with a link to the conversation.
   Open **History (1)**: the 60 minutes, struck through, with when you said it.
3. **Say:** nothing is overwritten silently. The file holds what is true now; the journal - a git
   repository beside it - keeps every version, and who wrote it.
4. For the technical audience, the journal itself:

   ```bash
   docker compose exec server git --git-dir "/data/workspaces/<your email>/_id/memory.git" log --format="%ad %an  %s" --date=short
   ```

   The author is the agent that wrote (`@Intake`); who *said* it is in the item.
5. **Change it yourself:** on the stand-ups item, **Edit**, make it *15 minutes*, **Save**. It now
   says *changed on the Memory page by you*, and the 30 minutes joins the history. Run the
   journal command again: the newest commit is yours, by email - not `@Intake`. Try an id in the
   text (*booking id 123456*): it is refused, and says why.

### 5.3 About a person - true whoever books

1. As yourself: *Please remember that Sanne is vegetarian, for lunches. No meeting now.* It
   looks Sanne up first: it only remembers things about someone it has settled.
2. **Log out, log in as Daan.** **Talk to the planner:** *Lunch meeting with Sanne on Tuesday 10
   November, one hour.* When `@Intake` looks Sanne up, the lookup brings what is remembered about
   her, and the lunch wish it sends should say vegetarian - Daan never said so. The
   confirmation says what lunch arrived.
3. **Trace:** `MemoryApplied`, *a lookup settled sanne@…*.
4. **Log in as Sanne → Memory → About me:** *vegetarian*, said by you, *in their conversation* -
   she sees what is said about her, but not your conversation. It is about her, so she may
   **Edit** or **Delete** it.
5. **Log in as yourself → Memory → Said by me:** the same fact, *about Sanne de Vries*. You said
   it, so you may withdraw it too. Daan sees neither.

### 5.4 About a place - before the choice

1. As yourself: *Please remember: the meadow room at Meeting in Nature is too noisy for
   workshops.* `@Intake` cannot see the places - only the facility manager can - so it asks the
   facility manager which place that is, and files the fact under its id, `meet-nature`.
2. **Memory → Places:** the fact, with a `meet-nature` chip and who said it. Everybody can read
   it.
3. **New conversation:** *A workshop with Sanne and Daan on Tuesday 10 November, two hours,
   somewhere in nature, no lunch.*
4. **Trace:** `MemoryApplied` from **`@FacilityManager`**, *choosing a location for "somewhere in
   nature"*, with the meadow fact. Code chose what to show it, before the model chose - and it
   gets the location's facts again when it picks the room at booking.
5. **Say:** if Meeting in Nature is still chosen, that is right - the fact is about one room,
   and the room is chosen when booking, where the fact is shown again.

### 5.5 Your place preference, in the wish

1. As yourself: *Please remember: my focus sessions always go to the Library.*
2. **New conversation:** *A focus session with Sanne on Wednesday 11 November, one hour, no lunch.*
3. `@Intake` says it will be *at the Library, as remembered for focus sessions*, and the time
   card names the Library.

### 5.6 Suggestions - less to say next time

1. **Memory tab → Suggestions.** If you planned two meetings with the same people, it offers
   them as a team: give a name - *the review crew* - and **Remember this**. It moves to *Mine*,
   said by you. (Nothing to offer yet? Plan two meetings with Sanne and Daan first.)
2. **New conversation:** *A workshop with the review crew on Thursday 26 November, two hours.*
   The name is enough. If a lunch was remembered for workshops - accept one the same way, after
   two workshops with a lunch wish - `@Intake` says *"with soup, as remembered for Workshop"* and
   the lunch question is not asked.
3. **New conversation** with three people nobody named as a group, and a lunch: *A retro with
   Femke, Lotte and Thijs on Monday 30 November, at yuma, with pizza.* After the request it
   offers once - a team, or the meal. Say *yes, call them the retro group*.
4. **Say:** a suggestion is a question, never a conclusion. Code works out what repeats; nothing
   is used until a person said yes; *Not now* is kept so it is not asked again.

### 5.7 The memory keeper - tidying, only suggested

1. Make *Mine* a little untidy first: say *my stand-ups last 15 minutes* in a conversation, after
   the 30 minutes from 5.1 - or edit one item so two say the same.
2. **Memory tab → Mine → Tidy up.** One agent, `@Keeper`, reads only your own list - the console
   shows the run and what it cost. A moment later: *Proposed by the memory keeper* - for example,
   *Retire* the 30 minutes, because the later 15 minutes contradicts it.
3. **Accept** it. *Mine* changes, as you; the journal shows `@Keeper` writing the proposal and
   you applying it. **Not now** on another keeps it from being proposed again.
4. **Say:** the one agent that concludes something from memory is the one that may only suggest.
   Code checks every proposal before you see it, and nothing changes without your yes.

### 5.8 What it will not do

Each takes under a minute; pick one or two.

- **Not yours, not theirs.** Log in as **Daan**, *plan a stand-up with my team*: it asks who his
  team is. Your memory never reaches his conversations.
- **No secrets, no ids.** *Remember my booking id 123456* - it will not: the tool refuses
  anything that looks like an id or a secret, and nothing is written.
  Memory keeps what a person said about how they like to meet, never credentials or booking
  numbers.
- **No strangers.** *Remember that Bram likes tea*: it looks Bram up first. The tool refuses a
  fact about anyone this conversation has not settled, so a guessed email never becomes a fact
  about a stranger.
- **Never authority.** Memory can change what an agent is *told*; it never approves a time, books
  a room or passes a gate. The facility manager - the agent that can book - is given only facts
  about places, never what you said about yourself.

### 5.9 Where it lives

- **On disk**, in the server's `/data/workspaces` volume - your tree under your email, the shared
  one under `_shared`:

  ```bash
  docker compose exec server find /data/workspaces -name "*.md"
  ```

- **The console's workspace tab** shows your own tree, as a file browser.
- **The Memory tab** shows all four lists with their history - the only view of the shared tree,
  because the framework's routes never serve a shared path.

---

## 6. Cancelling

1. **Meetings tab.** Every run you arranged, with the ids nothing else links together - meeting,
   room booking, lunch order - and what it is waiting for.
2. **Cancel** the design review from act 1. The cancel goes to the team that made it - revived if
   it had stopped - and releases the lunch order, the room and the meeting.
3. **Location service tab → the place it booked**: the booking is gone. **Meeting service → Sanne**: so
   is the meeting.
4. A meeting still waiting at a gate offers **Resume** instead.

---

## When something looks off

| You see | Why, and what to do |
|---|---|
| Logged out in one tab but not the other | one tab is on `127.0.0.1`; use `localhost` everywhere |
| Logged out after a restart | `AUTH_SECRET` is empty in `.env` |
| The meeting is booked without you | you said it was not your meeting, or unticked *I attend* on the form |
| The Memory tab says *no history is recorded* | the server image predates git; `make build` and `make up` again |
| The trace has no `MemoryApplied` row | nothing was remembered yet for that person or place, or memory was cleared |
| A plan fails at the first step | the Platform tab: a service is down |
