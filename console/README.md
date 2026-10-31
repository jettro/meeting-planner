# The Akgentic console

This directory holds **no source code**. The console is
[`akgentic-frontend`](https://github.com/b12consulting/akgentic-frontend), the
framework's own Angular client, and we run it exactly as published: Docker
builds it straight from the upstream git repository, at a pinned commit, using
upstream's own `frontend.Dockerfile`.

What lives here is the only thing that is ours — the runtime configuration.

## Why there is no checkout

The console is a *tool for watching the framework*, not a part of this project.
Vendoring its source would make every upstream fix a merge, and a fork is the
one thing we have no use for: we want to see what the framework shows, not what
we decided it should show.

Docker's remote git build context removes the dilemma. `docker-compose.yml`
names the repository and a full commit SHA, so the build is reproducible
without a submodule, a vendored tree, or a `git pull` anyone has to remember.

Upstream is AGPL-3.0. We run it unmodified and link to the source, which is why
the configuration below is a mounted file rather than a patch.

## config.json

Upstream resolves configuration in two layers: build-time defaults baked into
the bundle, and a `config.json` fetched from the web root before the app
renders. The second wins, which is what lets one published image serve several
backends.

So we do not rebuild to configure — `config.json` is **mounted over** the one
in the image. Change it and reload the browser; there is no build step.

| Key | Why it is set |
| --- | --- |
| `api` | Our server, on the host's port mapping. The browser runs on the host, so `http://server:8200` would not resolve - the same reasoning as the SPA's `VITE_API_BASE` |
| `hideLogin` | `false`: our server has a login (design_auth.md), and the console's own login page is how it gets a session. With `true` the console sends no credentials at all and every call is a 401. Back to `true` only with `AUTH=off` |
| `loginProviders` | `["apikey"]`: the console posts the key once to `/auth/login/apikey` and sends only the session cookie afterwards, on its WebSocket too. The keys are `API_KEYS` in `.env`, as `key=email` pairs - you log in as that person. Logging in on our GUI at `localhost:8300` logs you in here as well: same host, same cookie |
| `welcomeMessage` | Names the deployment, so it is obvious which backend the console is looking at |

The full key list is in upstream's README. To see what a running container
actually resolved, open <http://localhost:8400/config.json>.

## Cancel before you delete

A team run *is* its meeting: the coordinator's state is the only record of which meeting, room
booking and lunch order belong together (`design_durability.md`). The framework serves
`DELETE /teams/{id}`, and anything that calls it - this console included, if it offers it -
forgets that record while the three bookings stay in the services with nothing left to link
them. Cancel the meeting from our Meetings screen first; then delete the run if you want it gone.

## Upgrading

Change `AKGENTIC_CONSOLE_REF` in `.env` (or the default in `docker-compose.yml`)
to a newer **full** commit SHA — a short SHA is refused by the git context — and
run `make build`. Nothing else here needs to change unless upstream renames a
configuration key.
