"""What is remembered about you, and where it came from (design_memory.md §4.8).

The console shows a memory file as it is now and nothing more: no framework
route reads a journal, and none serves a shared tree. This route does both, for
the person logged in, and changes nothing (M14):

- **mine** - the items in their own `organiser.md`;
- **about me** - the items in `people/<me>.md`, whoever wrote them.

The email comes from the session, never from the request (M15), and the files
are read straight from the workspace root with the agents' own parser - a read
needs no actor and no gate.

Each item carries its **history** (M16): the versions it replaced, found by
following `supersedes` back through the journal's earlier versions of the
file. The journal's author is the agent that wrote (`@Intake`); who *said* it
is in the item. Without a journal - no git, or nothing recorded yet - the items
come without history and `journal` is false, so the gap shows.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from akgentic.infra.server.assembly import BaseAppModule, RouteSpec
from akgentic.infra.server.auth import RequestUser, get_request_user
from akgentic.tool.workspace import git_dir_for, resolve_workspace_path
from fastapi import APIRouter, Depends
from meeting_agents.memory import ORGANISER_FILE, MemoryItem, MemoryTool, parse_items, person_file
from pydantic import BaseModel, Field, computed_field

logger = logging.getLogger(__name__)

#: Most commits read per file; a demo's memory changes a handful of times.
MAX_VERSIONS = 50
GIT_TIMEOUT_SECONDS = 5.0
#: The journal's author for a change no agent made - a hand edit (akgentic's `OUT_OF_BAND_AUTHOR`).
OUTSIDE = "out-of-band"


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


class MyMemory(BaseModel):
    email: str
    mine: list[Remembered] = Field(default_factory=list)
    about_me: list[Remembered] = Field(default_factory=list)
    #: False when no history could be read for any file: no git, or no journal yet.
    journal: bool = False


# -- the trees ------------------------------------------------------------------


def _tree(root: Path, user_id: str, *, shared: bool) -> Path:
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
    return root / path


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


def my_memory(root: Path, user: RequestUser) -> MyMemory:
    email = (user.email or user.user_id).strip().lower()
    mine, mine_journal = _remembered(_tree(root, user.user_id, shared=False), ORGANISER_FILE)
    about_me, ours_journal = _remembered(_tree(root, user.user_id, shared=True), person_file(email))
    return MyMemory(email=email, mine=mine, about_me=about_me, journal=mine_journal or ours_journal)


# -- the route ------------------------------------------------------------------


def build_router(workspaces_root: Path) -> APIRouter:
    router = APIRouter(tags=["memory"])
    root = Path(workspaces_root).resolve()

    # Sync on purpose: reading the journal forks git, and FastAPI runs a sync
    # route in its thread pool rather than on the event loop.
    @router.get("/me/memory", response_model=MyMemory)
    def read_my_memory(user: RequestUser = Depends(get_request_user)) -> MyMemory:  # noqa: B008
        """What is remembered for and about the person logged in, with its history."""
        return my_memory(root, user)

    return router


class MemoryPageModule(BaseAppModule):
    """Splices `/me/memory` into the community composition."""

    name = "meeting-memory-page"

    def __init__(self, workspaces_root: Path) -> None:
        self._root = workspaces_root

    def contribute_routes(self) -> list[RouteSpec]:
        return [RouteSpec(router=build_router(self._root))]
