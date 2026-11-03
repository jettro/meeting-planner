# Who is asking

## What it is

The planner has users. You log in as a person - one of the people the meeting service knows - and
from then on the meetings you arrange are yours: your *Meetings* tab lists them, nobody else's
lists them, and asking for someone else's meeting by its id is answered as if it did not exist.
Your memory is yours too. And the team knows who you are, so *my team* and *me* mean something,
and you are counted among those who attend.

There is no password. You pick a person from a list. That is on purpose: the sample shows how
users and ownership work, not how to protect them - and the login page says so.

> **The one sentence to keep:** *the framework already checks who owns what; we only have to tell
> it who is asking.*

## How it works

### Logging in

- **In the planner**, you pick a person. The server checks that the meeting service knows them,
  and gives your browser a signed session cookie.
- **In the akgentic console**, you paste an API key from `.env`. Each key belongs to a person, so
  it logs you in as them - with the same kind of cookie.

From then on the browser sends only the cookie, on every request and on the socket that streams a
team's events. Both apps share the session, so logging in to one logs you in to the other on the
same host.

### What is yours

Every team has an **owner**: the person who was logged in when it was created. The framework
checks the owner on every team route and on the socket - to list teams, read a trace, send a
message, revive, cancel. You see the teams you own. Someone else's is a *404*, not a *403*: it
does not say that a meeting exists.

An **admin** - an email listed in `ADMIN_EMAILS` - sees every team. That is useful for a
presenter, and spoils a demo of *your meetings are yours*.

Memory follows the same owner: your own tree is resolved under your email
([memory](memory.md)), and the Memory tab reads your email from the session, never from the
request.

### The organiser

The coordinator fills in who arranges the meeting from the team's owner - never from what the
request says, so nobody can arrange a meeting in someone else's name. And the organiser attends
unless told otherwise:

- **the form** has an *I attend* checkbox, on by default, with your name on it;
- **`@Intake`** is told at every turn who it is talking to, does not look you up, and leaves you
  out only when you say it is not your meeting.

So a meeting with Sanne and Daan is a meeting for three, and the room is chosen for three.

## Why it is built this way

**Use the framework's checks; add none of our own.** The community tier already decides who may
see which team: the owner, or an admin. What it lacked was a way to know who is asking - without a
login, everybody is *anonymous*. The sample adds one small login strategy and turns on the
framework's gate. Every refusal in the tests comes from the framework's own policy, not from code
in this repository. ([`design_auth.md`](design/design_auth.md) A1, A9.)

**People, not accounts.** The users are the people the meeting service already knows. There is
no second list to keep in step, and the person who logs in is the person in the agendas.
(A2.)

**A cookie, not a token in a header.** A browser cannot put a header on a WebSocket, and the
trace lives on one. A signed, HttpOnly cookie works on both, and no script on the page can read
it. (A4.)

**The owner comes from the session, never from the request.** Whether it is the organiser of a
meeting or the email behind the Memory tab, it is read from who is logged in. A request cannot
claim to be someone else by changing a field. (A15.)

**Who is asking is not what an agent may do.** Knowing that it is Sanne asking does not decide
whether a lunch for twenty may be ordered on her behalf. That is a question for guardrails, a
separate step. (A11.)

### A lesson from building it

The login was the smallest step to build and the one that changed the most. No authorisation code
was written: the module is a strategy, a cookie and a route or two, and the 404s come from the
framework. But it gave every item of memory an owner, every meeting an organiser, and *me* a
meaning - and it is what made per-person memory possible at all.

## What it does not do

- **Passwords, or a real identity provider.** A real login - OIDC, for instance - would replace
  only the login page; the session and everything after it stay (A8).
- **Show participants the meetings they are in.** Only the organiser sees a meeting's team. A
  person's own agenda is in the meeting service's web page.
- **Decide what an agent may do on your behalf**, as above.

## Settings

| In `.env` | What it does |
|---|---|
| `AUTH` | `demo` to log in as a person; `off` makes everybody anonymous |
| `AUTH_SECRET` | signs the session cookie; left empty, every restart logs everybody out |
| `ADMIN_EMAILS` | who sees every team |
| `API_KEYS` | the keys the console logs in with, each mapped to a person's email |

## Where in the code

| File | What is there |
|---|---|
| `server/src/meeting_server/auth.py` | `DemoLogin` and `AuthModule`: the login, the cookie, the gate |
| `agents/src/meeting_agents/coordinator.py` | `_organiser`: the organiser, from the team's owner |
| `agents/src/meeting_agents/intake.py` | `who_is_asking`: what `@Intake` is told about you |
| `gui/src/session.ts`, `gui/src/pages/LoginPage.tsx` | the session in the planner, and the login page |
| `server/tests/test_auth.py` | who sees what, and what is a 404 |

The design: [`design_auth.md`](design/design_auth.md).

---

*Last checked against the code: 2026-11-03, `d36ea8a`.*
