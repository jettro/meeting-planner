"""@Keeper: tidies a person's own memory, and only suggests (design_memory.md §10.6).

The one place a model concludes something *from* memory - two items say the
same, a later one contradicts an earlier one - so it is the place where "an
agent may suggest, a person decides" matters most. One team per run, started by
*Tidy up* on the Memory tab, owned by the person; one model call.

The handler has the shape every specialist has: code reads *Mine* and puts it
in the request (M39), the model answers a `KeeperAdvice`, and code checks each
proposal before it is kept (M40) - an id that is not in *Mine*, a merge of fewer
than two items, words memory would refuse, something declined before, all
dropped. What survives goes to `proposed.md`, which nothing applies (M41); the
person accepts or refuses each one on the page (M42, M43).
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from akgentic.agent import BaseAgent
from akgentic.agent.config import AgentConfig, AgentState
from akgentic.core import ActorAddress, Akgent
from akgentic.core.messages import Message
from pydantic import BaseModel, Field

from meeting_agents.memory import MemoryItem, MemoryTool, Proposal, refusal

logger = logging.getLogger(__name__)

#: At most this many proposals from one run: a person reads them all, or none (Q15).
MAX_PROPOSALS = 5


class KeepMemoryRequest(Message):
    """*Tidy up*: look at my own memory and suggest what to merge, retire or reword."""

    #: *Mine*, as code put it in front of the model (M39). The page sends it empty.
    remembered: list[str] = Field(default_factory=list)

    def rendering(self) -> str:
        items = "\n".join(self.remembered) or "(nothing)"
        return (
            "These are the items this person keeps in their own memory, one per line: id | when it "
            "applies | what it says | when it was written.\n"
            f"{items}\n\n"
            "Suggest what would make this memory clearer, at most "
            f"{MAX_PROPOSALS} proposals, each one of:\n"
            "- merge: two or more items say the same thing; name their ids, and give the one item "
            "that replaces them - when it applies and what it says;\n"
            "- retire: an item is contradicted by a later one, or is plainly out of date; name its id;\n"
            "- reword: an item is unclear, or says an order where a fact is meant; name its id and "
            "give the new words.\n"
            "Give a short reason a person can check for each. Use only the ids above. Keep the "
            "person's meaning; do not add anything they did not say. If nothing needs tidying, "
            "propose nothing - that is a good answer."
        )


class ProposedChange(BaseModel):
    """One change, as the model proposes it. Code decides whether it is kept."""

    kind: Literal["merge", "retire", "reword"]
    items: list[str] = Field(description="The ids of the items it changes, exactly as listed.")
    situation: str = Field(default="", description="For a merge: when the new item applies.")
    text: str = Field(default="", description="For a merge or a reword: the new words. Empty for a retire.")
    reason: str = Field(description="Why, in one sentence a person can check.")


class KeeperAdvice(BaseModel):
    """@Keeper's answer: what it would change, possibly nothing."""

    proposals: list[ProposedChange] = Field(default_factory=list)


class KeeperConfig(AgentConfig):
    human_name: str = "@Human"


class KeeperState(AgentState):
    """How the run went, for the page to watch (M44)."""

    done: bool = False
    proposed: int = 0
    failure: str = ""


def checked(
    changes: list[ProposedChange], mine: list[MemoryItem], declined: set[str], run: str
) -> list[Proposal]:
    """The proposals that hold, in order, at most `MAX_PROPOSALS` (M40, M43)."""
    by_id = {item.id: item for item in mine}
    kept: list[Proposal] = []
    for change in changes:
        ids = list(dict.fromkeys(change.items))  # once each, in the model's order
        if not ids or any(item_id not in by_id for item_id in ids):
            continue
        situation, text = change.situation.strip(), change.text.strip()
        if change.kind == "merge":
            if len(ids) < 2 or not situation or not text:
                continue
        elif len(ids) != 1:
            continue
        elif change.kind == "reword":
            if not text or text == by_id[ids[0]].text:
                continue
            situation = situation or by_id[ids[0]].situation
        else:  # retire
            situation, text = "", ""
        if any(refusal(words) is not None for words in (situation, text) if words):
            continue
        proposal = Proposal(
            kind=change.kind,
            items=ids,
            situation=situation,
            text=text,
            reason=change.reason.strip(),
            evidence=run,
        )
        if proposal.key in declined or any(other.key == proposal.key for other in kept):
            continue
        kept.append(proposal)
        if len(kept) == MAX_PROPOSALS:
            break
    return kept


class MemoryKeeper(BaseAgent, Akgent[KeeperConfig, KeeperState]):
    """Reads *Mine*, proposes, and changes nothing a person reads as memory."""

    config: KeeperConfig
    state: KeeperState

    def on_start(self) -> None:
        super().on_start()
        # As @Intake does: keep the backstory and the observer BaseAgent set up,
        # so the run's outcome is snapshotted and the page can read it.
        self.state = KeeperState(backstory=self.state.backstory, tool_state=self.state.tool_state)
        self.state.observer(self)

    def _memory(self) -> MemoryTool | None:
        return next((card for card in self.config.tools if isinstance(card, MemoryTool)), None)

    def _finish(self, **outcome: Any) -> None:
        self.init_state(self.state.model_copy(update={"done": True, **outcome}))

    def receiveMsg_KeepMemoryRequest(  # noqa: N802
        self, message: KeepMemoryRequest, sender: ActorAddress
    ) -> None:
        memory = self._memory()
        if memory is None:
            self._finish(failure="this team has no memory")
            return
        try:
            mine = memory.organiser_items()
            declined = memory.declined_keys()
        except Exception as exc:  # noqa: BLE001 - the page must hear why
            logger.exception("[%s] could not read memory", self.config.name)
            self._finish(failure=f"memory could not be read: {exc}")
            return
        if not mine:
            memory.propose([])
            self._finish(proposed=0)
            return

        memory.applied("tidying the organiser's own memory", mine)
        lines = [f"{item.id} | {item.situation} | {item.text} | {item.written}" for item in mine]
        request = message.model_copy(update={"remembered": lines})
        try:
            advice = self.act(request, KeeperAdvice)
        except Exception as exc:  # noqa: BLE001 - a model call fails for a dozen reasons
            logger.error("[%s] the keeper's run failed: %s", self.config.name, exc)
            self._finish(failure=f"{type(exc).__name__}: {exc}")
            return

        proposals = checked(advice.proposals, mine, declined, f"keeper {self.team_id}")
        memory.propose(proposals)
        self._finish(proposed=len(proposals))


#: What a keeper team sends: one request in, nothing back but its state.
KEEPER_MESSAGE_TYPES = [KeepMemoryRequest]
