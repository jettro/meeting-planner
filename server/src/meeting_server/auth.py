"""Who is asking: a demo login on the framework's own seams (design_auth.md).

The community tier already decides who may see which team: every team route
and the WebSocket ask the wired `TeamAccessPolicy`, which allows the owner or an
admin. What it lacks is a way to tell it who is asking - its `NoAuth` makes
everybody `anonymous`, and it leaves the identity gate unmounted. This module
supplies both halves and nothing else:

- `DemoLogin`, an `AuthStrategy`: a session cookie says who you are. You get
  one by picking a person the meeting service knows (there is no password, and
  the login page says so - A3), or by presenting an API key (A14).
- `AuthModule`, which mounts the framework's `RequireAuthMiddleware` in the
  `IDENTITY` band with the merged allowlist, and the strategy's `/auth/*`
  routes.

The routes follow the contract the akgentic console already speaks (A5), so
our GUI and the console share one session: `POST /auth/login/apikey` with
`{"apikey"}`, `GET /auth/me` answering 401 when nobody is logged in, and a
`GET /auth/logout` the console navigates to rather than fetches.

A cookie and not a bearer header, because a browser cannot put a header on a
WebSocket, and the trace lives on one (A4). The cookie is HttpOnly, so no script
on the page ever sees it.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

import httpx
from akgentic.infra.server.assembly import (
    IDENTITY,
    AllowlistSpec,
    BaseAppModule,
    BuildContext,
    MiddlewareSpec,
    RouteSpec,
)
from akgentic.infra.server.auth import RequestUser
from akgentic.infra.server.middleware import RequireAuthMiddleware
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from starlette.requests import HTTPConnection
from starlette.routing import BaseRoute

from meeting_server.settings import AuthSettings

logger = logging.getLogger(__name__)

COOKIE = "mp_session"
ADMIN = "admin"


class Person(BaseModel):
    """Somebody who may log in: a person the meeting service keeps an agenda for."""

    email: str
    name: str


class PersonLogin(BaseModel):
    email: str


class ApiKeyLogin(BaseModel):
    """The console's body, field name and all."""

    apikey: str


class Me(BaseModel):
    """`/auth/me`: what the console and our GUI read about the session."""

    user_id: str
    email: str
    name: str
    roles: list[str]


#: Where the people come from. A function rather than a URL, so a test hands
#: over a list instead of standing up the meeting service.
People = Callable[[], Awaitable[list[Person]]]


def people_from(meeting_service_url: str) -> People:
    """The people the meeting service knows (Q1: all of them may log in)."""

    async def fetch() -> list[Person]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{meeting_service_url}/api/persons")
            response.raise_for_status()
            return [Person.model_validate(item) for item in response.json()]

    return fetch


class Sessions:
    """Signs and reads the session cookie: base64 JSON, then an HMAC of it."""

    def __init__(self, settings: AuthSettings) -> None:
        secret = settings.secret.get_secret_value()
        if not secret:
            # No secret configured: a fresh one per process. Sessions end at a
            # restart, which a demo can live with.
            logger.warning("AUTH_SECRET is not set; sessions will not survive a restart")
            secret = secrets.token_hex(32)
        self._key = secret.encode()
        self.max_age = settings.session_max_age_seconds

    def _mac(self, body: str) -> str:
        return hmac.new(self._key, body.encode(), hashlib.sha256).hexdigest()

    def issue(self, person: Person) -> str:
        payload = {"email": person.email, "name": person.name, "iat": int(time.time())}
        body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
        return f"{body}.{self._mac(body)}"

    def read(self, token: str) -> Person | None:
        """The person a token names, or None when it is forged, mangled or old."""
        body, _, mac = token.rpartition(".")
        if not body or not hmac.compare_digest(mac, self._mac(body)):
            return None
        try:
            payload = json.loads(base64.urlsafe_b64decode(body))
        except ValueError:
            return None
        if time.time() - payload.get("iat", 0) > self.max_age:
            return None
        return Person(email=payload["email"], name=payload["name"])


class DemoLogin:
    """The `AuthStrategy`: a signed cookie, or an API key, names the principal.

    `user_id` is the email (A2) - the key the meeting service, the scheduler's
    lookups and the memory design already use. Roles are decided when a
    request is resolved, not when the cookie is issued, so a change to
    `ADMIN_EMAILS` applies to sessions that already exist.
    """

    def __init__(self, settings: AuthSettings, people: People, cors_origins: list[str]) -> None:
        self._settings = settings
        self._people = people
        self._sessions = Sessions(settings)
        self._origins = set(cors_origins)

    def _principal(self, person: Person) -> RequestUser:
        roles = [ADMIN] if person.email in self._settings.admin_emails else []
        return RequestUser(user_id=person.email, email=person.email, roles=roles)

    def _person_for_key(self, key: str) -> Person | None:
        # Compared in constant time against every key, so a timing difference
        # does not tell an attacker how much of a guess was right.
        found = None
        for known, email in self._settings.api_keys.items():
            if hmac.compare_digest(known.encode(), key.encode()):
                found = Person(email=email, name=email)
        return found

    def _session(self, connection: HTTPConnection) -> Person | None:
        token = connection.cookies.get(COOKIE)
        return self._sessions.read(token) if token else None

    async def resolve_request_user(self, connection: HTTPConnection) -> RequestUser:
        # A script or the akgentic CLI sends its key on every request (A14). A
        # key in a URL is not accepted: URLs end up in logs.
        key = connection.headers.get("x-api-key")
        if key:
            person = self._person_for_key(key)
            if person is None:
                raise HTTPException(status_code=401, detail="Unknown API key")
            return self._principal(person)
        person = self._session(connection)
        if person is None:
            raise HTTPException(status_code=401, detail="Not logged in")
        return self._principal(person)

    def _logged_in(self, person: Person) -> JSONResponse:
        response = JSONResponse({"success": True, "user": self._me(person).model_dump()})
        response.set_cookie(
            COOKIE,
            self._sessions.issue(person),
            max_age=self._sessions.max_age,
            httponly=True,
            samesite="lax",
        )
        return response

    def _me(self, person: Person) -> Me:
        principal = self._principal(person)
        return Me(user_id=principal.user_id, email=principal.email, name=person.name, roles=principal.roles)

    def get_auth_routes(self) -> list[BaseRoute]:
        router = APIRouter(prefix="/auth", tags=["auth"])

        @router.get("/users")
        async def users() -> list[Person]:
            """Who may log in. Reachable without a session: it is the login page."""
            return await self._people()

        @router.post("/login/person")
        async def login_as_person(body: PersonLogin) -> JSONResponse:
            email = body.email.strip().lower()
            person = next((p for p in await self._people() if p.email.lower() == email), None)
            if person is None:
                raise HTTPException(status_code=401, detail="Nobody by that email may log in")
            return self._logged_in(person)

        @router.post("/login/apikey")
        async def login_with_api_key(body: ApiKeyLogin) -> JSONResponse:
            person = self._person_for_key(body.apikey)
            if person is None:
                raise HTTPException(status_code=401, detail="Unknown API key")
            # A key names an email; when that email is a person, the session
            # carries their name as well.
            known = next((p for p in await self._people() if p.email == person.email), None)
            return self._logged_in(known or person)

        @router.get("/me")
        async def me(request: Request) -> Me:
            person = self._session(request)
            if person is None:
                raise HTTPException(status_code=401, detail="Not logged in")
            return self._me(person)

        @router.get("/logout")
        async def logout(request: Request) -> Response:
            # The console navigates here, so it gets sent back where it came
            # from - but only to an origin we serve, never to wherever a
            # Referer points. Our GUI fetches it and reads the JSON.
            referer = request.headers.get("referer", "")
            parts = urlsplit(referer)
            origin = f"{parts.scheme}://{parts.netloc}"
            navigated = "text/html" in request.headers.get("accept", "")
            response: Response = (
                RedirectResponse(referer, status_code=303)
                if navigated and origin in self._origins
                else JSONResponse({"success": True})
            )
            response.delete_cookie(COOKIE, httponly=True, samesite="lax")
            return response

        return list(router.routes)


class AuthModule(BaseAppModule):
    """Mounts the identity gate the community composition leaves out (A6)."""

    name = "meeting-auth"

    def __init__(self, strategy: DemoLogin) -> None:
        self._strategy = strategy

    def contribute_routes(self) -> list[RouteSpec]:
        router = APIRouter()
        router.routes.extend(self._strategy.get_auth_routes())
        return [RouteSpec(router=router)]

    def contribute_allowlist(self) -> AllowlistSpec:
        # Compose health checks and the platform screen's dots carry no session.
        return AllowlistSpec(exact=frozenset({"/platform/health"}))

    def contribute_middleware(self, context: BuildContext) -> list[MiddlewareSpec]:
        return [
            MiddlewareSpec(
                middleware_class=RequireAuthMiddleware,
                layer=IDENTITY,
                options={
                    "exact_allowlist": frozenset({"/readiness"}) | context.allowlist.exact,
                    "prefix_allowlist": ("/auth/", *context.allowlist.prefixes),
                },
            )
        ]
