# Design — who is asking: authentication and authorization

> **Status:** built. Steps 2, 3 and 6 of §7 on 2026-10-31 - the login, the gate, the GUI's login
> page and the console's API-key login; step 5, the organiser, on 2026-11-02 (§12).
>
> **Dropped:** step 4, the *My agenda* page (A12), on 2026-11-03: the meeting service's own UI
> already shows a person's agenda. Step 7, the docs, is taken over by `design_docs.md`.
>
> **Lessons:** §11.
>
> *A design records what was decided and why, at the time; it is not kept current.*

Companion to `design_memory.md`, which stops at its Q1: *"Without authentication every request is
`anonymous`"*, so "per organiser" has no one to belong to. This document gives the sample real
users, using only what the open-source (community) tier of akgentic-infra ships, and keeps it
simple enough to stay a demo.

> **The one sentence to keep:** *the framework already checks who owns what; we only have to tell
> it who is asking.*

---

## 1. What the community tier already has

Read from the installed `akgentic-infra` 1.16.0, not from docs. The surprise is how much is there:
authorization is complete and wired; only authentication is a stub.

| Piece | Where | What it does in community |
|---|---|---|
| `RequestUser` | `server/auth.py` | the principal: `user_id`, `email`, `roles`, `scopes`, `entitlements` |
| `get_request_user(conn)` | `server/auth.py` | the **one** identity seam every route and the WebSocket read; falls back to `RequestUser(user_id="anonymous")` when nothing was stashed |
| `AuthStrategy` (protocol) | `protocols/auth.py` | two members: `async resolve_request_user(conn)` (raise 401 on bad credentials) and `get_auth_routes()` (the tier's `/auth/*` routes) |
| `NoAuth` | `adapters/community/no_auth.py` | always `anonymous`, no routes |
| `load_auth_strategy(name)` | `server/auth_loader.py` | `"noauth"` → `NoAuth`; any other name via the entry-point group `akgentic.infra.auth.strategies` (nothing is registered in our environment — the paid tiers ship their own) |
| `RequireAuthMiddleware` | `server/middleware/require_auth.py` | resolves the principal **once** per HTTP or WS request, stashes it, rejects with 401 / WS close 1008. **Community does not mount it** — that is why `get_request_user` always falls back |
| assembly band `IDENTITY = 400` | `server/assembly.py` | the slot an identity-gate module puts that middleware in; it receives the union of every module's `AllowlistSpec` (`/readiness`, `/auth/` by default) |
| `TeamAccessPolicy` (protocol) + `OwnerOrAdminPolicy` | `protocols/authz.py`, `adapters/shared/` | **already enforced** on create, list, get, stop, delete, restore, metadata, workspace and the WebSocket: allowed iff `process.user_id == user.user_id` or `"admin" in user.roles`; 404 rather than 403, so another user's team does not even exist |
| `admin_list_all_teams` | `CommunitySettings` | lets an admin's `GET /teams` list everyone's teams |
| owner on the team | `routes/teams.py` | `create_resolved_team(..., user_id=user.user_id, user_email=user.email)` → `Process.user_id`, kept through restore (`restorer.py`) |
| owner on every actor | `core/agent.py` | `self.user_id`, `self.user_email`, inherited by every child — so `@Intake` can know who it is talking to |
| per-principal workspaces | `tool/workspace/workspace.py` | `WorkspaceTool(workspace_id="memory")` resolves to `<user_id>/_id/memory`; an email is a legal segment; `workspace_sharable=True` gives `_shared/_id/memory`, if `AKGENTIC_WORKSPACE_SHARED_KINDS` permits `_id` |

So today, everything is owned by `anonymous` and everybody is `anonymous`, which is why every
check passes. Swap in a real principal and the list, the trace, cancel, restore and the socket are
all private per user **without a line of route code from us**.

What the community tier does **not** have: a login, a session, a way to get a user to the server.
That is the part this design adds.

---

## 2. The decisions

### 2.1 Identity: a demo login on our own `AuthStrategy`

**A1 — we write one small `AuthStrategy`, `DemoLogin`, and assign it to `services.auth` after
`wire_community`**, the same way `app.py` already replaces `services.catalog`. No entry point, no
package: the loader exists for tiers selected by config string, and we compose the app ourselves.

**A2 — the users are the people the meeting service already knows.** Its seed has ten people with
an email and a name. The login page lists **all of them** (Q1); you pick one. `user_id` is the **email** — the key
the meeting service, the scheduler's lookups and `design_memory.md`'s `people/<email>.md` already
use, so no mapping table is ever needed.

**A3 — there is no password, and the design says so.** This is a demo of *users*, not of
*security*: the point is that memory, the meeting list and cancel can be shown per person. Anyone
who can reach the GUI can be anyone. The value of the step is the seam: everything after the login
treats the principal as authenticated, so a real identity provider replaces only the login (A8).

**A4 — the session is a signed, HttpOnly cookie.** `POST /auth/login {email}` checks the email
against the meeting service and sets `mp_session` = the email, display name, roles and issue time,
signed with HMAC (stdlib `hmac`, key from the environment, never in the repo). `resolve_request_user`
verifies the signature and age, or raises 401.

Why a cookie and not a bearer header: **a browser cannot set headers on a WebSocket**, and the
trace lives on one. A token in the query string ends up in logs. A cookie travels with `fetch`
(`credentials: "include"`) and with the socket handshake by itself. `localhost:5173` and
`localhost:8200` are the same *site* (ports do not count for `SameSite`), so `SameSite=Lax` works;
CORS already runs with `allow_credentials=True` and explicit origins (`modules/core.py`).

**A5 — the strategy's routes follow the contract the akgentic console already speaks**
(found in the spike, §9.5), so one session serves our GUI and the console alike. Returned by
`get_auth_routes()`; `/auth/` is on the default allowlist, so they are reachable without a session,
as a login must be:

| Route | Body / answer |
|---|---|
| `GET /auth/users` | ours: the people who may log in (name, email) |
| `POST /auth/login/person` | ours: `{"email"}` → sets `mp_session`, answers `{"success": true, "user": …}` |
| `POST /auth/login/apikey` | the console's: `{"apikey"}` → same cookie, same answer (A14) |
| `GET /auth/me` | `{user_id, email, name, roles}`, or **401** — the console reads 401 as "go to login" |
| `GET /auth/logout` | clears the cookie and redirects — the console navigates to it, it does not fetch it |

Our GUI and the console run on the same host (`localhost`), so they share the cookie: logging in on
one logs you in on the other.

**A6 — an `AuthModule` mounts `RequireAuthMiddleware` at `IDENTITY`**, with the merged allowlist
the builder hands it. This is the one line community leaves out on purpose. `/platform/health`
joins the allowlist (compose health checks have no session).

**A7 — admins are named in configuration.** `ADMIN_EMAILS` gives those principals the role
`admin`; with `admin_list_all_teams=True` they see every team — including the ones created as
`anonymous` before this step, so old demo data is not lost, only hidden from ordinary users.

### 2.2 Later, a real identity provider — on the same seam

**A8 — OIDC replaces the login, not the session.** When a real login is wanted (Keycloak in
compose is the obvious one), the server does the authorization-code flow itself — the
*backend-for-frontend* pattern — and on the callback sets **the same `mp_session` cookie**. The
middleware, the policy, the GUI's `credentials: "include"`, the socket: unchanged. Only
`/auth/login` becomes a redirect and `/auth/users` disappears. The SPA never holds a token, which
is the safer shape for a browser anyway. This is why A4 chose a server session over a token in the
browser: it is the part that survives.

### 2.3 Authorization: three layers, one of them new

**A9 — teams: the framework's `OwnerOrAdminPolicy`, unchanged.** You see, resume, trace and
cancel the meetings you started; an admin sees all. Nothing to build.

**A10 — agents act on behalf of the owner, and know it.** `@Intake` reads `self.user_id` — the
email, by A2; `Akgent` has no public `user_email`, only a private `_user_email` — and says who it is talking to in its context ("you are arranging meetings for
Sanne de Vries"), so "me", "my team" and "my usual room" have a referent. The organiser is added
to `PlanMeetingRequest` as an optional `organiser` field, and the coordinator includes the organiser
among the participants unless told otherwise (Q2, decided): `@Intake` drops the organiser when the
person says it is not their meeting, and the form has an *I attend* checkbox, on by default. The
form page fills the organiser from `/auth/me`.

**A11 — what an agent may *do* stays the guardrails' business, not authentication's.** Booking
on someone's behalf, spending on lunch: that is the `before_tool_execute` seam noted for
guardrails, and it can now ask *who* — but deciding rules is a separate design.

**A12 — now: everyone sees their own agenda.** Not being able to see the meetings you are in
would feel like a missing feature (Q3), and the meeting service keeps every person's agenda. But
its API does not show it: `GET /persons/{email}/agenda?day=` answers only *free slots*, and
`GET /meetings` lists every meeting but not the busy blocks without one (`AgendaItem.meeting_id`
is optional). So the meeting service gains one read route — built 2026-11-02 as `GET /api/persons/{email}/meetings?from_day=&to_day=`, upcoming by default
— each item's time, title and `meeting_id` — a change in a service we own, and no MCP tool changes.
A **My agenda** page shows the logged-in person's day through a gated route on our server,
`GET /me/agenda?day=`, that takes the email **from the session, never from the request** — so
nobody reads another person's agenda by editing a URL. An item whose `meeting_id` matches
`plan.meeting_id` in one of *your* coordinators' states links to that team; the Meetings page
already loads those states.

**A13 — later: participants opening the team behind a meeting.** Seeing *that* you are invited is
A12; seeing *how* it was arranged (the trace, cancel) for a meeting someone else organised needs a
custom `TeamAccessPolicy` whose `list_filters` adds a metadata clause (`participant|<me>`) and
whose `can_get_team` allows read but not stop or cancel. The protocol supports exactly this
(`TeamListFilter.metadata`, OR-combined; `TeamAccessContext.metadata_indexes`). What makes it a
step of its own: in the chat team the participants are only known *after* the conversation, so the
team's metadata has to be updated when the plan settles, and who writes it is a design question.

### 2.4 The console: an API key

**A14 — an API key logs you in; it is a login, not a header on every request.** The spike
answered *how* the console sends a key: it does not send it on requests at all. Its login page has
an `apikey` provider that `POST`s `{"apikey"}` once to `/auth/login/apikey`, expects the session
cookie back, and from then on sends only the cookie (`withCredentials`) — on HTTP and on its
WebSocket alike, which is what makes the WebSocket question disappear. Turning it on is
configuration in `console/config.json`: `"hideLogin": false`, `"loginProviders": ["apikey"]`.

The keys are a small map in configuration, `API_KEYS`, from key to email: a known key logs in as
that person, roles included; an unknown key is a 401. Keys live only in the environment and `.env`
(a placeholder in `.env.example`), never in the repo.

For a script or the akgentic CLI, which send `X-API-Key` on each request (`ak_` prefix,
`infra/cli/client.py`), `resolve_request_user` also accepts that header — cheap, and verified. A
key in the WebSocket's query string also worked in the spike but is **not** adopted: a URL ends up
in logs.

---

## 3. What it gives memory

This is the reason for the step, so it is worth saying exactly:

- **Per organiser comes for free.** `WorkspaceTool(workspace_id="memory")` on `@Intake` already
  resolves under the team owner: `sanne@…/_id/memory`. `organisers/<id>.md` becomes simply the
  owner's own tree. `design_memory.md` Q1 recommended team metadata as a workaround; with real
  principals it is not needed.
- **Facts about people and places must not be per organiser.** "Sanne is vegetarian" is true
  whoever books the lunch. That calls for a **second, shared tree** — `workspace_id="memory-shared"`,
  `workspace_sharable=True`, with `AKGENTIC_WORKSPACE_SHARED_KINDS` permitting `_id` — holding
  `people/` and `places/`, while `organisers/` and later `episodes/` stay per principal. This is a
  change to M1 of `design_memory.md` (one tree becomes two) and is noted there when built.
- **Who wrote it** is now a person: the journal's author and the `evidence` field can name the
  principal, and "deletable on request" (case 3) has someone who can request it.

---

## 4. What changes, file by file

| Area | Change |
|---|---|
| `server/src/meeting_server/auth.py` (new) | `DemoLogin(AuthStrategy)`: cookie sign/verify, the four `/auth/*` routes, the people list from `MEETING_SERVICE_URL` |
| `server/src/meeting_server/app.py` | `services.auth = DemoLogin(...)`; `AuthModule` with `RequireAuthMiddleware` at `IDENTITY`; `admin_list_all_teams=True` |
| `server/src/meeting_server/auth.py` (cont.) | `/auth/login/apikey` and an `X-API-Key` header, both against `API_KEYS` (A14) |
| `server/src/meeting_server/agenda.py` (new) | `GET /me/agenda?day=` → the meeting service, for the session's email (A12) |
| `services/meeting-service` | `GET /api/persons/{email}/meetings`: a person's meetings in date order, with `meeting_id` and participants (A12) — **built** |
| `console/config.json` | `"hideLogin": false`, `"loginProviders": ["apikey"]` (A14) |
| `server/src/meeting_server/settings.py` | `AUTH_SECRET`, `ADMIN_EMAILS`, `API_KEYS`, `SESSION_MAX_AGE` (8 h); `AUTH=demo|off` so tests and the old behaviour stay one switch away |
| `agents/…/messages.py`, `plan.py` | optional `organiser` on the request and the plan |
| `agents/…/intake.py`, intake prompt | the owner in the context; `plan_meeting` passes `organiser` |
| `gui/src/api/client.ts` | `credentials: "include"` on every call; `me()`, `login()`, `logout()`; a 401 sends you to the login |
| `gui/src/pages/LoginPage.tsx` (new), `App.tsx` | pick a person; the user and *log out* in the app bar |
| `gui/src/pages/AgendaPage.tsx` (new) | *My agenda*: a day picker and the day's meetings, linked to their team when it is yours |
| compose / `.env.example` | `AUTH_SECRET` placeholder, `ADMIN_EMAILS` |
| CLI | unchanged: it drives `TeamManager` in-process as `cli`, never through the server |

---

## 5. Considered and not chosen

- **A header such as `X-User: sanne@…`** — the smallest possible strategy, but the browser cannot
  send it on the WebSocket, so the trace would be anonymous. A cookie costs one signature more.
- **Keycloak from the start** — real, but a realm export, a container, redirect URIs and a PKCE
  library in the SPA, for a demo whose point is memory. A8 keeps the door open at the cost of
  one route.
- **Registering `DemoLogin` under the entry-point group** — that path exists so a tier can be
  chosen by a config string without code. We compose the app in code already.
- **Team metadata naming the organiser** (`design_memory.md` Q1's recommendation) — works without
  authentication, but anyone could type any name, and the list, trace and cancel would still be
  shared. A principal fixes all of them at once.

---

## 6. Risks

- **The console** keeps `hideLogin: true` in today's config and would then send no credentials
  and get 401s; switching the gate on and the console's login on is one change (A14).
- **`localhost` and `127.0.0.1` are different sites.** A GUI opened on one and a server on the
  other would never get the cookie back. The compose files and `VITE_API_BASE` use `localhost`
  throughout; the README says so.
- **A closed socket is a 1008, not a 401.** The GUI's stream hook has to read close code 1008 as
  "log in again" rather than as a connection lost.
- **Teams created before the switch** belong to `anonymous`. Only admins see them (A7). Acceptable
  for demo data; a `make reset-data` is the other answer.
- **A demo login looks like security.** The login page says plainly that there is no password.

---

## 7. Order of work

1. Spike (§9) — go/no-go on the seams.
2. Server: `DemoLogin`, `AuthModule`, settings, tests (HTTP 401, WS 1008, owner isolation: Sanne
   cannot see, resume or cancel Daan's meeting — 404).
3. GUI: login page, `credentials: "include"`, app bar.
4. My agenda: `/me/agenda` and its page (A12).
5. Agents: organiser in context and request (A10; as checked in §12, A15–A19).
6. API key login and the console's config (A14).
7. Docs: README, `design_memory.md` Q1 answered here, M1's two trees.

Each step is usable on its own; after 2 and 3 the list is already private per person.

---

## 8. Questions answered (2026-10-31)

**Q1 — which people may log in?** All ten the meeting service knows (A2).

**Q2 — is the organiser automatically a participant?** Yes by default; `@Intake` drops it when the
person says it is not their meeting, and the form has an *I attend* checkbox (A10).

**Q3 — participants see their meetings?** Split in two. Seeing your own agenda is built now (A12):
without it the users would feel like a missing feature, and the meeting service already has the
data. Opening the *team* behind someone else's meeting stays a later step (A13).

**Q4 — the console.** With an API key. The spike found the console already has an API-key login
that ends in the session cookie, so our routes adopt its contract (A5, A14).

**Q5 — session length.** 8 hours, no refresh.

---

## 9. The spike — run 2026-10-31

Throwaway code in the session's scratchpad, not in the repo: a copy of `create_meeting_app` with a
`DemoLogin`, an `AuthModule` and `admin_list_all_teams=True`, driven with the real catalog and the
real `meeting-planner` team through FastAPI's `TestClient`; then the same app under uvicorn with a
page on another port in a browser. **Every seam holds; nothing in the framework had to be bent.**

1. **The gate.** `services.auth` replaced after `wire_community` and `RequireAuthMiddleware` at
   `IDENTITY` work together: no session → `GET /teams` 401, `/platform/health` and `/readiness`
   200 through the allowlist. The owner's WebSocket opens; another user's and an anonymous one
   are closed with **1008**.
2. **The cookie across ports, in a browser.** A page on `localhost:5181` logged in on
   `localhost:8211` with `fetch(..., {credentials: "include"})`: before login 401, after 200,
   `document.cookie` empty (HttpOnly), a team created (201), and the WebSocket opened and
   streamed with the cookie alone.
3. **Isolation.** A team Sanne created has `user_id` `sanne@rag4p.org`. Daan's `GET /teams` is
   empty; his `GET /teams/{id}`, `agent-states`, `restore` and `DELETE` are all **404**; the admin
   lists it. The catalog entries are owned by `anonymous`, and that did **not** stop Sanne from
   creating a team from them.
4. **Restore.** After `stop` and `restore` the team is still Sanne's, and a probe agent saw
   `user_id` `sanne@rag4p.org` in `on_start` both when created and when restored.
   `resolve_workspace_path` gives `sanne@rag4p.org/_id/memory` for `workspace_id="memory"`, and
   `_shared/_id/memory-shared` with `workspace_sharable=True` — §3 as written.
   One detail: `Akgent` has `user_id` but no public `user_email` (A10).
5. **The console** (`akgentic-frontend` at the pinned commit, read from source): it has a login
   page with providers `azure_ad`, `google`, `apikey` and `default`; `apikey` posts
   `{"apikey"}` to `/auth/login/apikey` and expects `{"success": true, "user"}` and the cookie;
   `/auth/me` 2xx or 401; logout navigates to `GET /auth/logout`. With `hideLogin: true` it
   sends no credentials at all. → A5, A14.
6. **The agenda data** is not exposed: the meeting service answers free slots per person, and
   `GET /meetings` misses blocks that are not meetings. → one new read route (A12).

---

## 11. What building it taught us

- **The framework did the authorization; we wrote none.** `server/src/meeting_server/auth.py` is
  a strategy, a cookie and a module; every 404 in `server/tests/test_auth.py` comes from the
  framework's `OwnerOrAdminPolicy`.
- **`AUTH=off` is the default in code, `demo` in the environment.** Tests that build
  `ServerSettings` directly keep the anonymous server unless they ask for a login, and the deployed
  server logs in unless told not to. `admin_list_all_teams` is always on: without a login nobody
  holds the role, so it changes nothing then.
- **A session that ends is noticed by any 401.** The cookie is HttpOnly, so the GUI cannot look
  at it; `send()` in `client.ts` announces every 401, and the session provider listens. A socket
  closed with 1008 asks `/auth/me` whether it was the session or the team. Verified live by
  restarting a server without `AUTH_SECRET`: the open page went to the login by itself.
- **A change of person starts the GUI afresh**: the team provider is keyed on the user, and the
  query cache is emptied, so the next person never sees the last one's cached meetings.
- **`/auth/logout` answers by `Accept`.** The console navigates to it and gets a redirect back to
  its own origin — only an origin in `CORS_ORIGINS`, never wherever a Referer points; our GUI
  fetches it and gets JSON.
- **The live check:** Sanne planned a meeting; Daan's Meetings page was empty; Femke, an admin,
  saw it at the slot gate. The console was not run against the gated server — its contract is
  read from source (§9.5) and held by the API-key tests.

## 12. Step 5, checked against the code (2026-11-02)

A10 read against `messages.py`, `plan.py`, `coordinator.py`, `intake.py`, the intake prompt and
`PlanPage.tsx` before building, and against two things the memory demos showed live: a workshop
for Sanne, Daan and the organiser went out *for 2 people*, and `@Intake` sometimes said what it
was about to request and then waited for a *yes*.

- **S1 — the headcount is `len(plan.participant_emails)`,** in three places in the coordinator:
  the location, the room and lunch. Nothing adds the organiser, so a meeting is always one short,
  and the organiser's own agenda is never searched for a free slot.
- **S2 — a client can put anything in a request.** A10 had the form fill `organiser` from
  `/auth/me`. But the form posts the `PlanMeetingRequest` itself, and so could name anyone - and
  the console can post one too. The one party that knows who the owner is, and cannot be told
  otherwise, is the team: every actor carries `user_id`, the owner, set at creation and kept on
  restore (§9.4).
- **S3 — `@Intake` refuses an unsettled participant,** so "me" must be looked up today, and the
  organiser is not in the address book by name in its context.
- **S4 — the pause is the prompt's.** *Before calling plan_meeting, say in one sentence what you
  are about to request, so a mistake can be caught while it is free* - and the model ends its turn
  on that sentence. But nothing is booked before the time is approved, and the slot card shows
  the place and the day: a mistake is still free there, and cancelling is one click. The people
  are in `@Intake`'s one sentence, said as it sends the request.

The decisions, replacing A10's mechanism and keeping its intent:

**A15 — the organiser is the team's owner, filled in by the coordinator, never by the request.**
`MeetingPlan` gets `organiser: str`, set in `receiveMsg_PlanMeetingRequest` from `self.user_id`;
`anonymous` (no login, the command line) leaves it empty, which is today's behaviour. The request
gets no `organiser` field at all.

**A16 — the organiser attends unless told otherwise (Q2).** The request gets
`organiser_attends: bool = True`; when it is true and there is an organiser, the coordinator adds
the organiser to `participant_emails` - once, if they were already listed. From there every
headcount, the slot search and the booked meeting include them, with no other change.

**A17 — `@Intake` knows who it talks to.** An always block names the organiser: *you are arranging
this meeting for `<email>`; they take part unless they say otherwise, so do not look them up or
list them*. `request_meeting` accepts the organiser's own email without a lookup, and
`plan_meeting` gets `organiser_attends`, false only when the person says it is not their meeting.

**A18 — the form says who attends.** *I attend*, a checkbox on by default, labelled with the name
from `/auth/me`; not shown when nobody is logged in (`AUTH=off`), because there is no organiser.

**A19 — `@Intake` requests at once, and the slot card is where a mistake is caught.** The prompt
says what it requests in the same turn as the call, instead of before it (S4). The demo script's
*say go ahead* step goes.

**Risk:** an organiser the meeting service does not know cannot have a free slot. The demo login
only offers known people, but `API_KEYS` can name any email, so a console user who is not in the
address book would see the slot search fail. The emails in `API_KEYS` should be people in the
meeting service; `.env.example` says so.

**Built (2026-11-02).** As above. One thing the check missed: the framework keys context
providers by function name per agent, and `MemoryTool` already exposes `organiser_block`, so
`@Intake`'s is `who_is_asking`. The saga's and specialists' test teams are now owned by
`anonymous`, so their participants stay exactly the request's; new tests cover an owner who
attends, one who does not, one already listed, and none.

---

## 10. Changelog

- 2026-10-31 — first proposal.
- 2026-10-31 — Q1–Q5 answered: everyone may log in; organiser attends by default; *My agenda*
  added now (A12), the participants' team access moved to A13; API key for the console (A14);
  8-hour sessions.
- 2026-10-31 — spike run (§9), every seam holds. A5 follows the console's `/auth/*` contract;
  A14 is a login that ends in the cookie, not a per-request header; A12 needs one read route in
  the meeting service; A10 reads `user_id` only. Two risks added: `localhost` vs `127.0.0.1`, and
  1008 on the socket.
- 2026-10-31 — steps 2, 3 and 6 built (§11): `DemoLogin`, `AuthModule`, the login page, the
  console's API-key login. 336 tests pass.
- 2026-11-02 — §12: step 5 checked against the code. The organiser is the team's owner, set by
  the coordinator, not sent by a client (A15); attends by default and so counts (A16); `@Intake`
  knows who it talks to (A17); *I attend* on the form (A18); `@Intake` requests without a pause (A19).
- 2026-11-02 — §12 built: organiser on the plan, set by the coordinator; *I attend* on the form;
  `@Intake` names the organiser and requests without a pause. 404 tests pass.
