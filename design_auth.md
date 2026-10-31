# Design — who is asking: authentication and authorization

Companion to `design_memory.md`, which stops at its Q1: *"Without authentication every request is
`anonymous`"*, so "per organiser" has no one to belong to. This document gives the sample real
users, using only what the open-source (community) tier of akgentic-infra ships, and keeps it
simple enough to stay a demo.

> **The one sentence to keep:** *the framework already checks who owns what; we only have to tell
> it who is asking.*

**Status:** proposal (2026-10-31). Nothing is built. §8 lists the questions still open, §9 the
spike that comes first.

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
an email and a name. The login page lists them; you pick one. `user_id` is the **email** — the key
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

**A5 — the strategy's routes are `/auth/users`, `/auth/login`, `/auth/logout`, `/auth/me`**,
returned by `get_auth_routes()`. `/auth/` is on the default allowlist, so they are reachable
without a session, as a login must be.

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

**A10 — agents act on behalf of the owner, and know it.** `@Intake` reads `self.user_id` /
`self.user_email` and says who it is talking to in its context ("you are arranging meetings for
Sanne de Vries"), so "me", "my team" and "my usual room" have a referent. The organiser is added
to `PlanMeetingRequest` as an optional `organiser` field, and the coordinator includes the organiser
among the participants unless told otherwise (Q2). The form page fills it from `/auth/me`.

**A11 — what an agent may *do* stays the guardrails' business, not authentication's.** Booking
on someone's behalf, spending on lunch: that is the `before_tool_execute` seam noted for
guardrails, and it can now ask *who* — but deciding rules is a separate design.

**A12 — not now: participants seeing meetings they are invited to.** It needs a custom
`TeamAccessPolicy` whose `list_filters` adds a metadata clause (`participants` ⊇ me) and team
metadata written at creation. The protocol supports exactly this (`TeamListFilter.metadata`, OR-
combined); it is a later step, worth doing when there is a reason to show it.

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
| `server/src/meeting_server/settings.py` | `AUTH_SECRET`, `ADMIN_EMAILS`, `SESSION_MAX_AGE`; `AUTH=demo|off` so tests and the old behaviour stay one switch away |
| `agents/…/messages.py`, `plan.py` | optional `organiser` on the request and the plan |
| `agents/…/intake.py`, intake prompt | the owner in the context; `plan_meeting` passes `organiser` |
| `gui/src/api/client.ts` | `credentials: "include"` on every call; `me()`, `login()`, `logout()`; a 401 sends you to the login |
| `gui/src/pages/LoginPage.tsx` (new), `App.tsx` | pick a person; the user and *log out* in the app bar |
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

- **The console.** `akgentic-frontend` talks to the same server. With the gate on, it gets 401
  unless it carries the cookie (it would, from the same site, after logging in on our GUI — to be
  verified) or knows the paid tiers' login. Fallback: run the console against a second server
  process with `AUTH=off`, read-only by convention.
- **Teams created before the switch** belong to `anonymous`. Only admins see them (A7). Acceptable
  for demo data; a `make reset-data` is the other answer.
- **A demo login looks like security.** The login page says plainly that there is no password.

---

## 7. Order of work

1. Spike (§9) — go/no-go on the seams.
2. Server: `DemoLogin`, `AuthModule`, settings, tests (HTTP 401, WS 1008, owner isolation: Sanne
   cannot see, resume or cancel Daan's meeting — 404).
3. GUI: login page, `credentials: "include"`, app bar.
4. Agents: organiser in context and request (A10).
5. Docs: README, `design_memory.md` Q1 answered here, M1's two trees.

Each step is usable on its own; after 2 and 3 the list is already private per person.

---

## 8. Questions open

**Q1 — which people may log in?** All ten from the meeting service, or a short list in
configuration? *Recommendation:* all ten — the demo is more convincing when anyone in the address
book can be the organiser, and the list needs no upkeep.

**Q2 — is the organiser automatically a participant?** Usually yes, but "book a room for Sanne and
Daan" is a real request. *Recommendation:* yes by default; `@Intake` drops it when the person says
it is not their meeting, and the form has a checkbox.

**Q3 — participants see their meetings (A12): now or later?** *Recommendation:* later. Ownership
alone already shows per-user memory; the metadata policy is its own small design.

**Q4 — the console.** Verify in the spike whether the cookie is enough; otherwise the `AUTH=off`
second process. *Recommendation:* decide after the spike, not before.

**Q5 — session length.** *Recommendation:* 8 hours, no refresh — re-picking a person costs a
click.

---

## 9. The spike — what must be true before building

1. `services.auth` can be replaced after `wire_community`, and a module contributing
   `RequireAuthMiddleware` at `IDENTITY` makes `get_request_user` return our principal on **both**
   an HTTP route and `/ws/{team_id}`.
2. The cookie set by `/auth/login` on `:8200` is sent by a page on `:5173` with `fetch`
   `credentials: "include"` **and** on the WebSocket handshake.
3. A team created as Sanne is invisible to Daan — `GET /teams`, `/teams/{id}`, `/restore`, the
   socket — and visible to an admin.
4. After stop and restore, the team's actors still have `self.user_id` (the restorer passes
   `process.user_id`; check it reaches the agents), and `@Intake`'s `memory` workspace resolves
   under the owner, not `anonymous`.
5. What the console does against the gated server.

---

## 10. Changelog

- 2026-10-31 — first proposal.
