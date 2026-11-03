"""The memory keeper (design_memory.md §10.6, phase 3c).

The catalog's card (M38, M39), the checks code makes on every proposal (M40),
and a run of the real `@Keeper` with the model replaced: it reads only the
person's own tree, writes `proposed.md`, and changes nothing that is applied.
"""

from __future__ import annotations

import os
import subprocess
import time as clock
from pathlib import Path

import pytest
from akgentic.core import ActorSystem, AgentCard, BaseConfig
from akgentic.team import TeamCard, TeamCardMember, TeamFactory
from akgentic.tool.mcp import MCPTool
from meeting_agents.bootstrap import load_team_card
from meeting_agents.human import ChannelHuman, QueueChannel, get_channel, set_channel
from meeting_agents.keeper import (
    KEEPER_MESSAGE_TYPES,
    MAX_PROPOSALS,
    KeeperAdvice,
    KeeperConfig,
    KeepMemoryRequest,
    MemoryKeeper,
    ProposedChange,
    checked,
)
from meeting_agents.memory import MemoryItem, MemoryTool, Proposal, parse_blocks, parse_items, render_items
from meeting_agents.settings import Settings

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "catalog"
JETTRO = "jettro@rag4p.org"


def said(situation: str, text: str, item_id: str) -> MemoryItem:
    return MemoryItem(
        id=item_id,
        kind="preference",
        scope=f"organiser:{JETTRO}",
        situation=situation,
        text=text,
        said_by=JETTRO,
    )


MINE = [
    said("stand-ups", "30 minutes", "a1"),
    said("stand-ups, how long", "half an hour", "a2"),
    said("focus sessions", "always the Library", "a3"),
]


# -- M38, M39: the card ------------------------------------------------------------


@pytest.fixture
def card() -> TeamCard:
    settings = Settings.from_env().model_copy(update={"catalog_path": CATALOG_ROOT})
    return load_team_card(settings, "memory-keeper")


def test_the_keeper_is_one_agent_below_the_human(card: TeamCard):
    assert card.entry_point.card.config.name == "@Human"
    [keeper] = card.entry_point.members
    assert keeper.card.config.name == "@Keeper" and keeper.members == []
    assert card.message_types == KEEPER_MESSAGE_TYPES


def test_the_keeper_reaches_no_service_and_only_the_persons_own_tree(card: TeamCard):
    tools = card.entry_point.members[0].card.config.tools
    assert not any(isinstance(tool, MCPTool) for tool in tools)
    [memory] = tools
    assert isinstance(memory, MemoryTool) and memory.personal and not memory.shared


def test_the_keeper_prompt_renders(card: TeamCard):
    prompt = card.entry_point.members[0].card.config.prompt.render()
    assert "You change nothing yourself" in prompt


# -- M40: what code lets through ---------------------------------------------------


def change(
    kind: str, *items: str, situation: str = "", text: str = "", reason: str = "why"
) -> ProposedChange:
    return ProposedChange(kind=kind, items=list(items), situation=situation, text=text, reason=reason)


def test_each_kind_of_proposal_is_kept_when_it_holds():
    kept = checked(
        [
            change("merge", "a1", "a2", situation="stand-ups", text="30 minutes"),
            change("retire", "a3"),
            change("reword", "a3", text="Focus sessions go to the Library."),
        ],
        MINE,
        set(),
        "keeper t1",
    )

    assert [(p.kind, p.items) for p in kept] == [
        ("merge", ["a1", "a2"]),
        ("retire", ["a3"]),
        ("reword", ["a3"]),
    ]
    assert kept[1].text == "" and kept[2].situation == "focus sessions"
    assert {p.evidence for p in kept} == {"keeper t1"}


@pytest.mark.parametrize(
    "proposal",
    [
        change("merge", "a1", situation="stand-ups", text="30 minutes"),  # one item is not a merge
        change("merge", "a1", "a2", situation="", text="30 minutes"),  # a merge needs the new item
        change("merge", "a1", "zz", situation="stand-ups", text="30 minutes"),  # an id not in Mine
        change("retire", "a1", "a2"),  # a retire names one item
        change("reword", "a3", text=""),  # a reword needs new words
        change("reword", "a3", text="always the Library"),  # ...that differ
        change("reword", "a3", text="my password is hunter2"),  # ...that memory keeps
        change("retire"),  # names nothing
    ],
)
def test_a_proposal_that_does_not_hold_is_dropped(proposal: ProposedChange):
    assert checked([proposal], MINE, set(), "keeper t1") == []


def test_declined_and_repeated_proposals_are_dropped_and_at_most_five_are_kept():
    retire = change("retire", "a3")
    declined = {checked([retire], MINE, set(), "x")[0].key}

    assert checked([retire], MINE, declined, "keeper t1") == []
    assert len(checked([change("retire", "a1")] * 3, MINE, set(), "t")) == 1

    many = [change("reword", "a3", text=f"Focus sessions: Library, version {n}") for n in range(8)]
    assert len(checked(many, MINE, set(), "t")) == MAX_PROPOSALS


# -- a run: the real @Keeper, the model replaced -------------------------------------


class Scripted:
    advice = KeeperAdvice()
    prompts: list[str] = []
    fail = False


class ScriptedKeeper(MemoryKeeper):
    def act(self, message, output_type):
        Scripted.prompts.append(message.rendering())
        if Scripted.fail:
            raise TimeoutError("the model took too long")
        return Scripted.advice


def member(agent_class, config, children=None) -> TeamCardMember:
    return TeamCardMember(
        card=AgentCard(agent_class=agent_class, description=config.role, config=config),
        headcount=1,
        members=children or [],
    )


@pytest.fixture
def root(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("AKGENTIC_WORKSPACES_ROOT", str(tmp_path))
    monkeypatch.setenv("AKGENTIC_WORKSPACE_SHARED_KINDS", "id")
    Scripted.advice, Scripted.prompts, Scripted.fail = KeeperAdvice(), [], False
    return tmp_path


def tree(root: Path) -> Path:
    return root / JETTRO / "_id" / "memory"


def remembered(root: Path, items: list[MemoryItem]) -> None:
    (tree(root)).mkdir(parents=True, exist_ok=True)
    (tree(root) / "organiser.md").write_text(render_items(items))


@pytest.fixture
def keeper_run(root):
    previous = get_channel()
    set_channel(QueueChannel())
    system = ActorSystem()

    def run() -> ScriptedKeeper:
        keeper = member(
            ScriptedKeeper, KeeperConfig(name="@Keeper", role="Keeper", tools=[MemoryTool(shared=False)])
        )
        card = TeamCard(
            name="keeper-test",
            entry_point=member(ChannelHuman, BaseConfig(name="@Human", role="Human"), [keeper]),
            members=[],
            message_types=KEEPER_MESSAGE_TYPES,
            agent_profiles=[],
        )
        runtime = TeamFactory.build(card, system, user_id=JETTRO)
        runtime.send_from_to("@Human", "@Keeper", KeepMemoryRequest())
        agent = system.proxy_ask(runtime.addrs["@Keeper"], ScriptedKeeper)
        deadline = clock.monotonic() + 5
        while not agent.state.done:
            assert clock.monotonic() < deadline, "the keeper never finished"
            clock.sleep(0.02)
        return agent

    yield run
    system.shutdown()
    set_channel(previous)


def authors(path: Path) -> list[str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return subprocess.run(
        [
            "git",
            "--git-dir",
            str(path.with_name(path.name + ".git")),
            "--work-tree",
            str(path),
            "log",
            "--format=%an|%s",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    ).stdout.split("\n")


def test_a_run_writes_proposals_and_changes_nothing_that_is_applied(root, keeper_run):
    remembered(root, MINE)
    before = (tree(root) / "organiser.md").read_text()
    Scripted.advice = KeeperAdvice(
        proposals=[
            change("merge", "a1", "a2", situation="stand-ups", text="30 minutes"),
            change("merge", "a1", "nope", situation="x", text="y"),  # dropped by code
        ]
    )

    keeper = keeper_run()

    assert (keeper.state.done, keeper.state.proposed, keeper.state.failure) == (True, 1, "")
    [proposal] = parse_blocks((tree(root) / "proposed.md").read_text(), Proposal)
    assert (proposal.kind, proposal.items, proposal.evidence.startswith("keeper ")) == (
        "merge",
        ["a1", "a2"],
        True,
    )
    assert (tree(root) / "organiser.md").read_text() == before
    assert "@Keeper|write: proposed.md" in authors(tree(root))
    [prompt] = Scripted.prompts
    assert "a1 | stand-ups | 30 minutes" in prompt and "a3 | focus sessions" in prompt


def test_the_keeper_binds_only_the_persons_own_tree(root, keeper_run):
    remembered(root, MINE)

    keeper_run()

    assert not (root / "_shared").exists()
    assert [path.name for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")] == [
        JETTRO
    ]


def test_with_nothing_remembered_there_is_nothing_to_ask(root, keeper_run):
    keeper = keeper_run()

    assert (keeper.state.done, keeper.state.proposed) == (True, 0)
    assert Scripted.prompts == []


def test_a_failed_model_call_is_said_in_the_state(root, keeper_run):
    remembered(root, MINE)
    Scripted.fail = True

    keeper = keeper_run()

    assert keeper.state.done and "TimeoutError" in keeper.state.failure
    assert parse_items((tree(root) / "organiser.md").read_text()) == MINE
