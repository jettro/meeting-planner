"""What is remembered about you, where it came from, and changing it (design_memory.md §4.8, §10.4).

The console shows a memory file as it is now and nothing more: no framework
route reads a journal, and none serves a shared tree. These routes do both, for
the person logged in:

- **mine** - the items in their own `organiser.md`;
- **about me** - the items in `people/<me>.md`, whoever wrote them;
- **said by me** - what they said about other people, in `people/<other>.md` (M23);
- **places** - what anyone said about a place, everybody's to read (M11, §10.3).

The email comes from the session, never from the request (M15), and the files
are read straight from the workspace root with the agents' own parser - a read
needs no actor and no gate.

Each item carries its **history** (M16): the versions it replaced, found by
following `supersedes` back through the journal's earlier versions of the
file. The journal's author is the agent that wrote (`@Intake`); who *said* it
is in the item. Without a journal - no git, or nothing recorded yet - the items
come without history and `journal` is false, so the gap shows.

**Changing** (phase 3a, M22-M27). A person may edit or delete the items M22
gives them - their own, those about them, what they said about others, and the
place facts they said (an admin: every place fact). An edit is a new version
that supersedes the old one; a delete takes the item out of the file and leaves
the journal as it was. The server writes the way an agent does - the
in-process lock, the framework's per-file `flock`, a re-read, an atomic write -
and commits under the person's own name, so the journal says who changed it.
An item the person may not change answers 404, as if it were not there.

**Suggestions** (phase 3b, M32-M35). What a person keeps repeating is worked
out on every read from their own meetings - the coordinators' records the
Meetings tab reads, in this process: the same people in two or more meetings,
or a lunch wish that came back for meetings with the same title. Accepting one
writes it to *Mine* through the same path as an edit; *Not now* is kept in
`declined.md` beside `organiser.md`, which no agent reads. Nothing about a
suggestion is stored until the person answers it.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import subprocess
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from akgentic.infra.server.assembly import BaseAppModule, RouteSpec
from akgentic.infra.server.auth import RequestUser, get_request_user
from akgentic.tool.workspace import git_dir_for, resolve_workspace_path
from akgentic.tool.workspace.journal import GitJournal
from akgentic.tool.workspace.locks import atomic_write, hold
from akgentic.tool.workspace.models import DEFAULT_GIT_TIMEOUT_S, META_DIR_SUFFIX, Identity
from akgentic.tool.workspace.write.gate import lock_file_for
from fastapi import APIRouter, Depends, HTTPException
from meeting_agents.memory import (
    ORGANISER_FILE,
    PLACES_FOLDER,
    MemoryItem,
    MemoryTool,
    file_lock,
    parse_items,
    person_file,
    refusal,
    render_items,
    with_item,
)
from pydantic import BaseModel, Field, computed_field

logger = logging.getLogger(__name__)

#: Most commits read per file; a demo's memory changes a handful of times.
MAX_VERSIONS = 50
GIT_TIMEOUT_SECONDS = 5.0
#: The journal's author for a change no agent made - a hand edit (akgentic's `OUT_OF_BAND_AUTHOR`).
OUTSIDE = "out-of-band"
#: What an edit on the page records as its evidence and reason (M24).
ON_THE_PAGE = "memory page"
CHANGED_ON_THE_PAGE = "changed on the Memory page"
#: The journal commit's first field for a page change, beside the agents' `write`.
PAGE_CAPABILITY = "memory-page"
#: Who may change any place fact (M22): the framework's admin role.
ADMIN = "admin"
PEOPLE_FOLDER = "people"
#: Where a declined suggestion is kept, in the person's own tree; no agent reads it (M35).
DECLINED_FILE = "declined.md"
#: How often something must repeat before it is offered (M33, Q12).
GROUP_AT = 2
MEAL_AT = 2
COORDINATOR = "@Coordinator"


class Version(BaseModel):
    """An item as it was, and the journal commit that first held it."""

    item: MemoryItem
    changed: datetime | None = None
    #: The journal's author: the agent that wrote it, or `out-of-band`.
    by: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def outside(self) -> bool:
        """Changed by hand, outside the planner."""
        return self.by == OUTSIDE


class Remembered(BaseModel):
    item: MemoryItem
    #: When the current version was recorded, if the journal has it.
    recorded: Version | None = None
    #: What it replaced, newest first.
    history: list[Version] = Field(default_factory=list)
    #: Whether the person reading may edit or delete it (M22). The page shows
    #: the buttons by this; the routes check again.
    can_change: bool = False


class Suggestion(BaseModel):
    """Something the person keeps repeating, offered to be remembered (M33)."""

    #: A digest of what is offered, so a declined offer is not made again (M35).
    key: str
    kind: Literal["team", "meal"]
    #: How many of the person's meetings it was seen in.
    meetings: int
    #: For a team: everyone besides the person, as emails.
    people: list[str] = Field(default_factory=list)
    #: For a meal: the meetings' title, and the most recent lunch wish for it.
    title: str = ""
    wish: str = ""


class MyMemory(BaseModel):
    email: str
    mine: list[Remembered] = Field(default_factory=list)
    about_me: list[Remembered] = Field(default_factory=list)
    said_by_me: list[Remembered] = Field(default_factory=list)
    places: list[Remembered] = Field(default_factory=list)
    #: What the person keeps repeating, worked out from their own meetings (M32).
    suggestions: list[Suggestion] = Field(default_factory=list)
    #: False when no history could be read for any file: no git, or no journal yet.
    journal: bool = False


# -- the trees ------------------------------------------------------------------


def _workspace_path(user_id: str, *, shared: bool) -> str:
    """The tree's path under the root, as the framework resolves it for the agents."""
    defaults = MemoryTool.model_fields
    workspace = defaults["shared_workspace" if shared else "personal_workspace"].default
    path = resolve_workspace_path(
        workspace_id=workspace,
        workspace_metadata_keys=[],
        team_id="",
        user_id=user_id,
        metadata=None,
        workspace_sharable=shared,
    )
    return str(path)


def _tree(root: Path, user_id: str, *, shared: bool) -> Path:
    return root / _workspace_path(user_id, shared=shared)


def _items(tree: Path, path: str) -> list[MemoryItem]:
    file = tree / path
    if not file.is_file():
        return []
    try:
        items: list[MemoryItem] = parse_items(file.read_text())
    except Exception:  # a hand-broken file shows as empty, as it does to the agents
        logger.exception("memory file %s could not be read", file)
        return []
    return items


# -- the journal ----------------------------------------------------------------


def _git(tree: Path, *args: str) -> str | None:
    """Run a read-only git command on a tree's journal; None when it cannot.

    The environment is scrubbed the way the journal's own is: an inherited
    `GIT_DIR` or a person's `~/.gitconfig` must not change what is read.
    """
    git_dir = git_dir_for(tree)
    if shutil.which("git") is None or not git_dir.is_dir():
        return None
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env |= {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    try:
        result = subprocess.run(
            ["git", "--git-dir", str(git_dir), "--work-tree", str(tree), *args],
            capture_output=True,
            text=True,
            env=env,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        logger.exception("could not read the journal of %s", tree)
        return None
    return result.stdout if result.returncode == 0 else None


def _versions(tree: Path, path: str) -> list[tuple[datetime, str, list[MemoryItem]]] | None:
    """Every recorded version of one file, oldest first; None without a journal."""
    log = _git(tree, "log", f"-n{MAX_VERSIONS}", "--format=%H%x09%aI%x09%an", "--", path)
    if log is None:
        return None
    versions = []
    for line in reversed(log.strip().splitlines()):
        sha, when, author = line.split("\t", 2)
        content = _git(tree, "show", f"{sha}:{path}")
        try:
            items = parse_items(content) if content else []
        except Exception:  # a version a person broke by hand has no items to offer
            items = []
        versions.append((datetime.fromisoformat(when), author, items))
    return versions


def _remembered(tree: Path, path: str) -> tuple[list[Remembered], bool]:
    """The file's items now, each with what it replaced; and whether a journal was read."""
    current = _items(tree, path)
    versions = _versions(tree, path)
    if versions is None:
        return [Remembered(item=item) for item in current], False

    # Each item id, as first recorded - the commit that introduced it.
    first: dict[str, Version] = {}
    for when, author, items in versions:
        for item in items:
            first.setdefault(item.id, Version(item=item, changed=when, by=author))

    remembered = []
    for item in current:
        history: list[Version] = []
        seen = {item.id}
        previous = item.supersedes
        while previous and previous not in seen and previous in first:
            seen.add(previous)
            history.append(first[previous])
            previous = first[previous].item.supersedes
        remembered.append(Remembered(item=item, recorded=first.get(item.id), history=history))
    return remembered, True


def _files(tree: Path, folder: str) -> list[str]:
    """Every memory file in one folder of a tree, in name order."""
    directory = tree / folder
    return [f"{folder}/{file.name}" for file in sorted(directory.glob("*.md"))] if directory.is_dir() else []


# -- who may change what (M22) ----------------------------------------------------


def _email(user: RequestUser) -> str:
    return (user.email or user.user_id).strip().lower()


@dataclass(frozen=True)
class _List:
    """One list on the page: which files it reads, which items it shows, and which it lets you change."""

    shared: bool
    files: Callable[[Path], list[str]]
    shows: Callable[[MemoryItem], bool]
    may_change: Callable[[MemoryItem], bool]


def _lists(user: RequestUser) -> dict[str, _List]:
    email = _email(user)
    admin = ADMIN in user.roles
    mine_file = person_file(email)
    return {
        "mine": _List(False, lambda tree: [ORGANISER_FILE], lambda item: True, lambda item: True),
        "about_me": _List(True, lambda tree: [mine_file], lambda item: True, lambda item: True),
        "said_by_me": _List(
            True,
            lambda tree: [path for path in _files(tree, PEOPLE_FOLDER) if path != mine_file],
            lambda item: item.said_by == email,
            lambda item: True,
        ),
        "places": _List(
            True,
            lambda tree: _files(tree, PLACES_FOLDER),
            lambda item: True,
            lambda item: admin or item.said_by == email,
        ),
    }


def my_memory(root: Path, user: RequestUser, store: MeetingStore | None = None) -> MyMemory:
    lists: dict[str, list[Remembered]] = {}
    journal = False
    for name, spec in _lists(user).items():
        tree = _tree(root, user.user_id, shared=spec.shared)
        shown: list[Remembered] = []
        for path in spec.files(tree):
            remembered, read = _remembered(tree, path)
            journal = journal or read
            shown += [
                entry.model_copy(update={"can_change": spec.may_change(entry.item)})
                for entry in remembered
                if spec.shows(entry.item)
            ]
        lists[name] = shown
    offered = suggestions(store, user, root) if store is not None else []
    return MyMemory(email=_email(user), journal=journal, suggestions=offered, **lists)


# -- changing (M24-M27) -----------------------------------------------------------


class ItemChange(BaseModel):
    """What the page may change about an item: where it applies, and what it says."""

    situation: str
    text: str


class NotYours(LookupError):
    """No such item among the ones this person may change - answered as 404."""


class Refused(ValueError):
    """The change is not one memory keeps - answered as 422, with the reason."""


def _locate(root: Path, user: RequestUser, item_id: str) -> tuple[str, str]:
    """The tree and the file of an item this person may change; never a path from the request."""
    for spec in _lists(user).values():
        workspace = _workspace_path(user.user_id, shared=spec.shared)
        tree = root / workspace
        for path in spec.files(tree):
            items = _items(tree, path)
            if any(item.id == item_id and spec.shows(item) and spec.may_change(item) for item in items):
                return workspace, path
    raise NotYours(item_id)


def _rewrite(
    root: Path,
    workspace: str,
    path: str,
    change: Callable[[list[MemoryItem]], list[MemoryItem]],
    author: str,
) -> None:
    """Apply one change to a memory file the way an agent's write would (M26).

    The in-process lock first, then the framework's per-file `flock` - the two
    an agent's `remember` takes, in the same order - then a re-read inside
    them, so the change lands on what is there *now*. Anything changed by hand
    is committed as `out-of-band` first, as the write gate does, and the change
    itself under the person's name. Without a journal the file is still
    written; the page says *no history* then, as it does for reading.
    """
    tree = (root / workspace).resolve()
    tree.mkdir(parents=True, exist_ok=True)  # a first suggestion accepted before anything was said
    meta = tree.parent / f"{tree.name}{META_DIR_SUFFIX}"  # the framework's `meta_dir_for`, from our root
    journal = None
    if (git_dir_for(tree) / "HEAD").is_file():
        journal = GitJournal(tree, enabled=True, timeout_s=DEFAULT_GIT_TIMEOUT_S, meta_dir=meta)
        if not journal.initialise():
            journal = None
    file = tree / path
    with file_lock(str(file)):
        if journal is not None:
            journal.commit_out_of_band()
        with hold([lock_file_for(meta, path)], on_failure=_unlocked):
            items = parse_items(file.read_text()) if file.is_file() else []
            atomic_write(file, render_items(change(items)))
        if journal is not None:
            journal.commit_paths([path], Identity(author, author.split("@")[0]), PAGE_CAPABILITY)


def _unlocked(exc: OSError) -> None:
    """The framework degrades to an unserialised write when a lock cannot be taken; so do we."""
    logger.warning("memory file lock could not be taken, writing unserialised: %s", exc)


def change_item(
    root: Path, user: RequestUser, item_id: str, change: ItemChange, store: MeetingStore | None = None
) -> MyMemory:
    """Edit an item: a new version that supersedes it, said by whoever edited it (M24)."""
    situation, text = change.situation.strip(), change.text.strip()
    if not situation:
        raise Refused("there is no situation to remember it for")
    if (why := refusal(text)) is not None:
        raise Refused(why)
    workspace, path = _locate(root, user, item_id)
    email = _email(user)

    def edit(items: list[MemoryItem]) -> list[MemoryItem]:
        old = next((item for item in items if item.id == item_id), None)
        if old is None:
            raise NotYours(item_id)  # gone between the lookup and the lock
        if (old.situation, old.text) == (situation, text):
            return items
        key = (old.kind, situation.lower())
        if any(item.id != item_id and (item.kind, item.situation.strip().lower()) == key for item in items):
            raise Refused(f"another {old.kind} in this file is already about {situation!r}")
        new = old.model_copy(
            update={
                "id": uuid.uuid4().hex[:12],
                "status": "confirmed",
                "situation": situation,
                "text": text,
                "said_by": email,
                "reason": CHANGED_ON_THE_PAGE,
                "evidence": ON_THE_PAGE,
                "supersedes": old.id,
                "written": date.today(),
            }
        )
        return [new if item.id == item_id else item for item in items]

    _rewrite(root, workspace, path, edit, email)
    return my_memory(root, user, store)


def delete_item(root: Path, user: RequestUser, item_id: str, store: MeetingStore | None = None) -> MyMemory:
    """Take an item out of the file; the journal keeps it (M25)."""
    workspace, path = _locate(root, user, item_id)

    def without(items: list[MemoryItem]) -> list[MemoryItem]:
        if not any(item.id == item_id for item in items):
            raise NotYours(item_id)
        return [item for item in items if item.id != item_id]

    _rewrite(root, workspace, path, without, _email(user))
    return my_memory(root, user, store)


# -- suggestions (M32-M35) --------------------------------------------------------


class MeetingStore(Protocol):
    """The two reads of the framework's event store that suggestions need (S10)."""

    def list_teams(self, user_id: str | None = ..., status: Any = ..., metadata: Any = ...) -> list[Any]: ...

    def load_agent_states(self, team_id: uuid.UUID) -> list[Any]: ...


@dataclass(frozen=True)
class _Meeting:
    title: str
    people: frozenset[str]
    lunch_wish: str


def _meetings(store: MeetingStore, user: RequestUser) -> list[_Meeting]:
    """The person's own meetings, oldest first, read from each coordinator's record.

    `list_teams` by the session's id is the framework's owner filter - the
    one `GET /teams` applies - so nobody else's meetings are read.
    """
    email = _email(user)
    rows = sorted(
        store.list_teams(user_id=user.user_id, status=None, metadata=None), key=lambda row: row.created_at
    )
    meetings = []
    for row in rows:
        try:
            snapshots = store.load_agent_states(row.team_id)
        except Exception:  # one unreadable team must not hide the rest
            logger.exception("could not read the states of team %s", row.team_id)
            continue
        for snapshot in snapshots:
            plan = (
                getattr(getattr(snapshot, "state", None), "plan", None)
                if snapshot.name == COORDINATOR
                else None
            )
            if plan is None:
                continue
            others = frozenset(e.strip().lower() for e in plan.participant_emails) - {email}
            wish = (plan.lunch_wish or "").strip() if plan.with_lunch else ""
            meetings.append(_Meeting(title=plan.title.strip(), people=others, lunch_wish=wish))
    return meetings


def _key(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:16]


def _names(item: MemoryItem, email: str) -> bool:
    """Whether an item names this person - by email, or by the name before the @."""
    words = item.text.lower()
    local = email.split("@")[0]
    return email in words or re.search(rf"\b{re.escape(local)}\b", words) is not None


def suggestions(store: MeetingStore, user: RequestUser, root: Path) -> list[Suggestion]:
    """What the person keeps repeating and has not remembered or declined (M33)."""
    mine = _items(_tree(root, user.user_id, shared=False), ORGANISER_FILE)
    declined = {item.situation for item in _items(_tree(root, user.user_id, shared=False), DECLINED_FILE)}
    meetings = _meetings(store, user)
    offers: list[Suggestion] = []

    groups = Counter(meeting.people for meeting in meetings if len(meeting.people) >= 2)
    for people, count in groups.most_common():
        if count < GROUP_AT:
            continue
        if any(all(_names(item, email) for email in people) for item in mine):
            continue
        key = _key("team", *sorted(people))
        if key not in declined:
            offers.append(Suggestion(key=key, kind="team", meetings=count, people=sorted(people)))

    by_title: dict[str, list[_Meeting]] = {}
    for meeting in meetings:
        if meeting.lunch_wish:
            by_title.setdefault(meeting.title.casefold(), []).append(meeting)
    for folded, alike in by_title.items():
        if len(alike) < MEAL_AT:
            continue
        if any("lunch" in item.situation.lower() and folded in item.situation.casefold() for item in mine):
            continue
        latest = alike[-1]
        key = _key("meal", folded, latest.lunch_wish.casefold())
        if key not in declined:
            offers.append(
                Suggestion(
                    key=key, kind="meal", meetings=len(alike), title=latest.title, wish=latest.lunch_wish
                )
            )
    return offers


class SuggestionAnswer(BaseModel):
    """What the person settles when accepting: a team's name, or the meal as they want it."""

    name: str = ""
    text: str = ""


def _offered(store: MeetingStore, user: RequestUser, root: Path, key: str) -> Suggestion:
    offer = next((offer for offer in suggestions(store, user, root) if offer.key == key), None)
    if offer is None:
        raise NotYours(key)
    return offer


def accept_suggestion(
    root: Path, user: RequestUser, key: str, answer: SuggestionAnswer, store: MeetingStore
) -> MyMemory:
    """Remember an offer in *Mine*, said by the person who accepted it (M34)."""
    offer = _offered(store, user, root, key)
    email = _email(user)
    if offer.kind == "team":
        name = answer.name.strip()
        if not name:
            raise Refused("a team needs a name, so you can ask for it next time")
        kind, situation, text = "fact", f'who "{name}" is', ", ".join(offer.people)
    else:
        kind, situation, text = (
            "preference",
            f'lunch for "{offer.title}"',
            (answer.text.strip() or offer.wish),
        )
    for words in (situation, text):
        if (why := refusal(words)) is not None:
            raise Refused(why)
    item = MemoryItem(
        kind=kind,  # type: ignore[arg-type]
        scope=f"organiser:{email}",
        situation=situation,
        text=text,
        said_by=email,
        reason=f"accepted a suggestion from {offer.meetings} earlier meetings",
        evidence=ON_THE_PAGE,
    )
    _rewrite(
        root,
        _workspace_path(user.user_id, shared=False),
        ORGANISER_FILE,
        lambda items: with_item(items, item),
        email,
    )
    return my_memory(root, user, store)


def decline_suggestion(root: Path, user: RequestUser, key: str, store: MeetingStore) -> MyMemory:
    """Keep *Not now*, so the offer is not made again; nothing an agent reads (M35)."""
    offer = _offered(store, user, root, key)
    email = _email(user)
    what = ", ".join(offer.people) if offer.kind == "team" else f"{offer.wish} for {offer.title}"
    item = MemoryItem(
        kind="fact",
        status="retired",
        scope=f"organiser:{email}",
        situation=key,
        text=f"declined: {offer.kind} - {what}",
        said_by=email,
        reason="not now, on the Memory page",
        evidence=ON_THE_PAGE,
    )
    _rewrite(
        root, _workspace_path(user.user_id, shared=False), DECLINED_FILE, lambda items: [*items, item], email
    )
    return my_memory(root, user, store)


# -- the route ------------------------------------------------------------------


def build_router(workspaces_root: Path, store: MeetingStore | None = None) -> APIRouter:
    router = APIRouter(tags=["memory"])
    root = Path(workspaces_root).resolve()

    # Sync on purpose: reading the journal forks git, and FastAPI runs a sync
    # route in its thread pool rather than on the event loop.
    @router.get("/me/memory", response_model=MyMemory)
    def read_my_memory(user: RequestUser = Depends(get_request_user)) -> MyMemory:  # noqa: B008
        """What is remembered for and about the person logged in, with its history."""
        return my_memory(root, user, store)

    @router.put("/me/memory/items/{item_id}", response_model=MyMemory)
    def edit_item(
        item_id: str,
        change: ItemChange,
        user: RequestUser = Depends(get_request_user),  # noqa: B008
    ) -> MyMemory:
        """Change where an item applies, or what it says (M24)."""
        try:
            return change_item(root, user, item_id, change, store)
        except NotYours:
            raise HTTPException(status_code=404, detail="no such item") from None
        except Refused as why:
            raise HTTPException(status_code=422, detail=f"Not changed: {why}.") from None

    @router.delete("/me/memory/items/{item_id}", response_model=MyMemory)
    def remove_item(item_id: str, user: RequestUser = Depends(get_request_user)) -> MyMemory:  # noqa: B008
        """Take an item out of memory; its history stays in the journal (M25)."""
        try:
            return delete_item(root, user, item_id, store)
        except NotYours:
            raise HTTPException(status_code=404, detail="no such item") from None

    @router.post("/me/memory/suggestions/{key}", response_model=MyMemory)
    def accept(
        key: str,
        answer: SuggestionAnswer,
        user: RequestUser = Depends(get_request_user),  # noqa: B008
    ) -> MyMemory:
        """Remember a suggestion in *Mine* (M34)."""
        if store is None:
            raise HTTPException(status_code=404, detail="no such suggestion")
        try:
            return accept_suggestion(root, user, key, answer, store)
        except NotYours:
            raise HTTPException(status_code=404, detail="no such suggestion") from None
        except Refused as why:
            raise HTTPException(status_code=422, detail=f"Not remembered: {why}.") from None

    @router.delete("/me/memory/suggestions/{key}", response_model=MyMemory)
    def decline(key: str, user: RequestUser = Depends(get_request_user)) -> MyMemory:  # noqa: B008
        """*Not now*: the suggestion is not made again (M35)."""
        if store is None:
            raise HTTPException(status_code=404, detail="no such suggestion")
        try:
            return decline_suggestion(root, user, key, store)
        except NotYours:
            raise HTTPException(status_code=404, detail="no such suggestion") from None

    return router


class MemoryPageModule(BaseAppModule):
    """Splices `/me/memory` and its two changing routes into the community composition."""

    name = "meeting-memory-page"

    def __init__(self, workspaces_root: Path, store: MeetingStore | None = None) -> None:
        self._root = workspaces_root
        self._store = store

    def contribute_routes(self) -> list[RouteSpec]:
        return [RouteSpec(router=build_router(self._root, self._store))]
