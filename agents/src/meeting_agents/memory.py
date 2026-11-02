"""What the team remembers between meetings (design_memory.md, phase 1).

One team arranges one meeting and is gone, so anything a person tells it would
be forgotten with it. Memory is the part that outlives the team: two akgentic
workspace trees, plain Markdown files a person can read and fix, with a git
journal recording every change and who made it (M1).

- **`memory` - mine.** Per principal: the framework resolves it under the team's
  owner, the person logged in. `organiser.md` holds what *this* organiser said
  about how they work: who "Daan" is, who "my team" is, how long a stand-up
  lasts, where focus sessions go.
- **`memory-shared` - ours.** One for everybody. `people/<email>.md` holds what
  is true about a person whoever books for them - Sanne is vegetarian.

Phase 1 writes only what a person *said*, as confirmed (M4), through one narrow
tool, and selects by code (M3): the organiser's file is an always-present block
on the `LLM_CONTEXT` channel, and what is remembered about a participant arrives
with the lookup that settles them. Every time memory is put in front of the
model, a `MemoryApplied` event says which items and why (M9).

Memory is data, never authority (M8): it is shown to the model labelled as what
was remembered, it never reaches the coordinator, and it cannot pass a gate.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, Self

import yaml
from akgentic.tool import ContextState, ToolCard
from akgentic.tool.errors import RetriableError
from akgentic.tool.workspace import WorkspaceTool
from pydantic import BaseModel, Field, PrivateAttr

logger = logging.getLogger(__name__)

#: The organiser's own file, in their personal tree.
ORGANISER_FILE = "organiser.md"

Kind = Literal["fact", "preference"]
Status = Literal["confirmed", "proposed", "retired"]


# -- the item format (M2) -------------------------------------------------------


class MemoryItem(BaseModel):
    """One thing remembered, bound to the situation it applies to.

    The body (`text`) is the advice; everything else is what lets code decide
    whether it *may* apply, and lets a person see where it came from.
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    kind: Kind
    status: Status = "confirmed"
    #: `organiser:<email>` in a personal tree - whose tree it is, readable in the
    #: file itself; `person:<email>` in the shared one.
    scope: str
    situation: str
    text: str
    #: Who said it - the writer and the subject can differ in the shared tree.
    said_by: str
    reason: str = ""
    #: The conversation that taught it: `conversation <team id>`.
    evidence: str = ""
    review_when: str = ""
    supersedes: str | None = None
    written: date = Field(default_factory=date.today)

    def applies(self) -> bool:
        """Phase 1: confirmed is applied, proposed and retired are not (M3, M6)."""
        return self.status == "confirmed"

    def line(self) -> str:
        """How the model reads it: the situation, then the advice."""
        return f"- {self.situation}: {self.text}"


_FRONT = re.compile(r"^---\n(.*?)\n---\n(.*?)(?=^---\n|\Z)", re.DOTALL | re.MULTILINE)


def parse_items(content: str) -> list[MemoryItem]:
    """Every item in a file: front matter a person can read, then the advice."""
    items = []
    for front, body in _FRONT.findall(content):
        fields = yaml.safe_load(front) or {}
        items.append(MemoryItem.model_validate({**fields, "text": body.strip()}))
    return items


def render_items(items: list[MemoryItem]) -> str:
    blocks = []
    for item in items:
        front = item.model_dump(mode="json", exclude={"text"})
        blocks.append(
            f"---\n{yaml.safe_dump(front, sort_keys=False, allow_unicode=True).strip()}\n---\n{item.text}\n"
        )
    return "\n".join(blocks)


def with_item(items: list[MemoryItem], new: MemoryItem) -> list[MemoryItem]:
    """Add `new`, replacing an earlier item about the same situation (M4).

    The replaced item goes from the file, not into a `retired` pile: the
    journal keeps every earlier version, which is the history a person can
    read; the file holds what is true now.
    """
    key = (new.kind, new.situation.strip().lower())
    kept = []
    for item in items:
        if (item.kind, item.situation.strip().lower()) == key:
            new = new.model_copy(update={"supersedes": item.id})
        else:
            kept.append(item)
    return [*kept, new]


# -- what the trace shows (M9) -------------------------------------------------


@dataclass(frozen=True)
class MemoryApplied:
    """Memory was put in front of an agent's model, and why.

    Keep it a module top-level class: the event store persists its dotted name,
    and replay resolves it back to this class.
    """

    agent: str
    reason: str
    items: list[str] = field(default_factory=list)


# -- refusing what does not belong in memory (M4) ------------------------------

_UNSAFE = re.compile(
    r"(password|passw|secret|api[ _-]?key|token|\bak_[a-z0-9]|booking id|meeting id|order id|\b\d{5,}\b)",
    re.IGNORECASE,
)


def refusal(text: str) -> str | None:
    """Why `text` may not be remembered, or None when it may."""
    if not text.strip():
        return "there is nothing to remember"
    if _UNSAFE.search(text):
        return (
            "it looks like a secret or an id. Memory keeps what a person said about how they "
            "like to meet, never credentials or booking numbers"
        )
    return None


# -- the always block (LLM_CONTEXT) --------------------------------------------


class OrganiserMemory(ContextState):
    """The organiser's confirmed items, as the model sees them every turn."""

    organiser: str
    lines: list[str] = Field(default_factory=list)

    def render_full(self) -> str:
        if not self.lines:
            return ""
        return (
            f"**What you remember about how {self.organiser} likes to meet** - their own words "
            "from earlier conversations. Use it; it is not an instruction from them now, and "
            "they can change it:\n" + "\n".join(self.lines)
        )

    def render_delta(self, previous: Self) -> str | None:
        return (
            None if previous.lines == self.lines else self.render_full() or "Nothing is remembered any more."
        )


# -- the card ------------------------------------------------------------------


def _callable(card: WorkspaceTool, name: str) -> Callable[..., Any]:
    return next(tool for tool in card.get_tools() if tool.__name__ == name)


class MemoryTool(ToolCard):
    """Reads and writes the two trees, for code - the model gets one tool, `remember`.

    The trees are held privately: a `WorkspaceTool` in an agent's `tools` would
    hand the model every file callable it has. These two are bound here, by
    this card, and only this card's own methods use them - through their gated
    callables, so the write gate and the journal apply to every change exactly
    as they would to a model's (spike S1).

    A shared tree needs `AKGENTIC_WORKSPACE_SHARED_KINDS=id` on the process;
    without it the bind raises here and is not caught (M13).
    """

    personal_workspace: str = "memory"
    shared_workspace: str = "memory-shared"
    #: Most items the always block carries; the newest win. Bounded, so memory
    #: cannot crowd out the conversation (the notes' "keep it limited").
    max_always_items: int = 20

    _mine: WorkspaceTool | None = PrivateAttr(default=None)
    _ours: WorkspaceTool | None = PrivateAttr(default=None)
    _last_applied: str = PrivateAttr(default="")

    def observer(self, observer):  # type: ignore[no-untyped-def, override]
        super().observer(observer)
        self._mine = WorkspaceTool(workspace_id=self.personal_workspace, git_journal=True)
        self._ours = WorkspaceTool(
            workspace_id=self.shared_workspace, workspace_sharable=True, git_journal=True
        )
        self._mine.observer(observer)
        self._ours.observer(observer)
        return self

    # -- who is asking --------------------------------------------------------

    @property
    def organiser(self) -> str:
        """The team's owner: the person logged in (design_auth.md A10)."""
        return str(getattr(self._observer, "user_id", None) or "anonymous")

    def _tree(self, shared: bool) -> WorkspaceTool:
        tree = self._ours if shared else self._mine
        if tree is None:
            raise RuntimeError("MemoryTool used before it was wired to an agent")
        return tree

    # -- reading ----------------------------------------------------------------

    def _read(self, shared: bool, path: str) -> list[MemoryItem]:
        backend = self._tree(shared).workspace
        if not backend.exists(path):
            return []
        try:
            return parse_items(backend.read(path).decode())
        except Exception:  # a hand-edited file a person broke must not break the team
            logger.exception("memory file %s could not be read", path)
            return []

    def organiser_items(self) -> list[MemoryItem]:
        return [item for item in self._read(False, ORGANISER_FILE) if item.applies()]

    def person_items(self, email: str) -> list[MemoryItem]:
        return [item for item in self._read(True, _person_file(email)) if item.applies()]

    # -- writing ------------------------------------------------------------------

    def _write(self, shared: bool, path: str, change: Callable[[list[MemoryItem]], list[MemoryItem]]) -> None:
        """Apply `change` to what is on disk *now*, through the gate (§4.5).

        The gate refuses to replace a file this card has not read, or that
        changed since - another organiser's team, writing the same person's
        file. So it reads, applies its one change, and writes; refused, it
        does that once more (spike S6). Nothing is merged textually.

        The gate guards against *other* writers only. Two writes from this
        agent - a model calling `remember` twice in one turn, which it does,
        in parallel - would each read the file before the other wrote, and
        the second would silently replace the first: the gate counts the
        first write as this agent's own view. Found live; hence one lock per
        file, for every writer in this process.
        """
        tree = self._tree(shared)
        read, write = _callable(tree, "workspace_read"), _callable(tree, "workspace_write")
        with _lock_for(str(tree.workspace.root / path)):
            for attempt in (1, 2):
                if tree.workspace.exists(path):
                    read(path)
                content = render_items(change(self._read(shared, path)))
                try:
                    write(path, content)
                    return
                except RetriableError:
                    if attempt == 2:
                        raise

    def remember(self, item: MemoryItem) -> str:
        """Store what a person said. Returns what happened, for the model to read."""
        if (why := refusal(item.text)) is not None:
            return f"Not remembered: {why}."
        if item.scope.startswith("organiser:"):
            self._write(False, ORGANISER_FILE, lambda items: with_item(items, item))
            return f"Remembered for {self.organiser}: {item.situation} - {item.text}"
        email = item.scope.removeprefix("person:")
        self._write(True, _person_file(email), lambda items: with_item(items, item))
        return f"Remembered about {email}: {item.situation} - {item.text}"

    # -- applying (M9) --------------------------------------------------------------

    def applied(self, reason: str, items: list[MemoryItem]) -> None:
        """Say in the trace that memory reached the model."""
        if not items:
            return
        observer = self._observer
        name = getattr(getattr(observer, "config", None), "name", "") or ""
        event = MemoryApplied(agent=name, reason=reason, items=[item.line() for item in items])
        notify = getattr(observer, "notify_event", None)
        if notify is not None:
            notify(event)

    def get_context_states(self) -> list[Callable[[], ContextState | None]]:
        def organiser_block() -> ContextState | None:
            try:
                items = self.organiser_items()[-self.max_always_items :]
            except Exception:  # a provider never raises
                logger.exception("the organiser's memory could not be read")
                return None
            lines = [item.line() for item in items]
            # One event per change of what the model sees, not one per turn.
            digest = hashlib.sha256("\n".join(lines).encode()).hexdigest()
            if digest != self._last_applied:
                self._last_applied = digest
                self.applied("always: the organiser's own memory", items)
            return OrganiserMemory(organiser=self.organiser, lines=lines)

        return [organiser_block]

    def get_tools(self) -> list[Callable[..., Any]]:
        # The model's tool is on @Intake's own card, which knows the conversation
        # (who was settled, which team); this card holds the store.
        return []


#: One lock per memory file in this process - see `MemoryTool._write`. Kept out
#: of the card, which the framework copies, and a lock cannot be.
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(path: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(path, threading.Lock())


def _person_file(email: str) -> str:
    return f"people/{email.strip().lower()}.md"
