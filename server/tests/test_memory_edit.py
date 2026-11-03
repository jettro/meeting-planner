"""Changing memory from the Memory page (design_memory.md §10.4, phase 3a).

Who may change what (M22), an edit as a new version (M24), a delete that leaves
the journal alone (M25), and a write that lands beside the agents' own (M26):
real files and real journals, and for the last, the real `@Intake`.
"""

from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

import pytest
from akgentic.core import ActorSystem, AgentCard, BaseConfig
from akgentic.infra.server import state_keys
from akgentic.infra.server.auth import RequestUser
from akgentic.team import TeamCard, TeamCardMember, TeamFactory
from fastapi.testclient import TestClient
from meeting_agents.human import ChannelHuman, QueueChannel, get_channel, set_channel
from meeting_agents.intake import IntakeAgent, IntakeConfig, IntakeTools
from meeting_agents.memory import MemoryItem, MemoryTool, parse_items, render_items
from meeting_agents.messages import MESSAGE_TYPES
from meeting_server.app import create_meeting_app
from meeting_server.auth import Person
from meeting_server.memory_page import (
    ON_THE_PAGE,
    ItemChange,
    NotYours,
    Refused,
    change_item,
    delete_item,
    my_memory,
)
from meeting_server.settings import AuthSettings, ServerSettings
from pydantic import SecretStr

JETTRO = "jettro@rag4p.org"
DAAN = "daan@rag4p.org"
SANNE = "sanne@rag4p.org"


def mine(root: Path, email: str) -> Path:
    return root / email / "_id" / "memory"


def ours(root: Path) -> Path:
    return root / "_shared" / "_id" / "memory-shared"


def git(tree: Path, *args: str, author: str = "@Intake") -> str:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env |= {
        "GIT_AUTHOR_NAME": author,
        "GIT_AUTHOR_EMAIL": author,
        "GIT_COMMITTER_NAME": author,
        "GIT_COMMITTER_EMAIL": author,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
    }
    return subprocess.run(
        ["git", "--git-dir", str(tree.with_name(tree.name + ".git")), "--work-tree", str(tree), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout


def write(tree: Path, path: str, items: list[MemoryItem], *, journal: bool = True) -> None:
    """Lay a file down as an agent's write would, with its journal commit."""
    file = tree / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(render_items(items))
    if not journal:
        return
    if not tree.with_name(tree.name + ".git").is_dir():
        git(tree, "init", "-q")
    git(tree, "add", "-A")
    git(tree, "commit", "-q", "-m", f"write: {path}")


def said(situation: str, text: str, *, by: str = JETTRO, scope: str = f"organiser:{JETTRO}") -> MemoryItem:
    return MemoryItem(kind="preference", scope=scope, situation=situation, text=text, said_by=by)


def user(email: str, *, admin: bool = False) -> RequestUser:
    return RequestUser(user_id=email, email=email, roles=["admin"] if admin else [])


def edit(root: Path, who: RequestUser, item_id: str, situation: str, text: str):
    return change_item(root, who, item_id, ItemChange(situation=situation, text=text))


def authors(tree: Path) -> list[str]:
    return git(tree, "log", "--format=%an").split()


# -- M24: an edit is a new version ------------------------------------------------


def test_an_edit_is_a_new_version_said_by_whoever_edited_it(tmp_path):
    first = said("stand-ups", "60 minutes")
    write(mine(tmp_path, JETTRO), "organiser.md", [first])

    memory = edit(tmp_path, user(JETTRO), first.id, "stand-ups", "30 minutes")

    [standup] = memory.mine
    assert standup.item.text == "30 minutes"
    assert standup.item.supersedes == first.id and standup.item.id != first.id
    assert (standup.item.said_by, standup.item.evidence) == (JETTRO, ON_THE_PAGE)
    assert [version.item.text for version in standup.history] == ["60 minutes"]
    assert standup.recorded is not None and standup.recorded.by == JETTRO


def test_the_situation_can_change_too(tmp_path):
    first = said("who my team is", "Sanne and Daan")
    write(mine(tmp_path, JETTRO), "organiser.md", [first])

    memory = change_item(
        tmp_path,
        user(JETTRO),
        first.id,
        ItemChange(situation="who the design team is", text="Sanne and Daan"),
    )

    assert [(r.item.situation, r.item.text) for r in memory.mine] == [
        ("who the design team is", "Sanne and Daan")
    ]


def test_an_edit_keeps_the_place_of_the_item_in_the_file(tmp_path):
    items = [said("a", "1"), said("b", "2"), said("c", "3")]
    write(mine(tmp_path, JETTRO), "organiser.md", items)

    memory = edit(tmp_path, user(JETTRO), items[1].id, "b", "two")

    assert [r.item.text for r in memory.mine] == ["1", "two", "3"]


def test_what_memory_does_not_keep_is_refused_and_nothing_is_written(tmp_path):
    first = said("stand-ups", "60 minutes")
    tree = mine(tmp_path, JETTRO)
    write(tree, "organiser.md", [first])
    before = (tree / "organiser.md").read_text()

    for change in (
        ItemChange(situation="stand-ups", text="my password is hunter2"),
        ItemChange(situation="stand-ups", text="booking id 123456"),
        ItemChange(situation="stand-ups", text="   "),
        ItemChange(situation="  ", text="30 minutes"),
    ):
        with pytest.raises(Refused):
            change_item(tmp_path, user(JETTRO), first.id, change)

    assert (tree / "organiser.md").read_text() == before
    assert authors(tree) == ["@Intake"]


def test_two_items_cannot_end_up_about_the_same_situation(tmp_path):
    standups, reviews = said("stand-ups", "30 minutes"), said("reviews", "60 minutes")
    write(mine(tmp_path, JETTRO), "organiser.md", [standups, reviews])

    with pytest.raises(Refused, match="already about"):
        edit(tmp_path, user(JETTRO), reviews.id, "Stand-ups", "60 minutes")


def test_an_unchanged_edit_writes_nothing(tmp_path):
    first = said("stand-ups", "30 minutes")
    tree = mine(tmp_path, JETTRO)
    write(tree, "organiser.md", [first])

    edit(tmp_path, user(JETTRO), first.id, "stand-ups", "30 minutes")

    assert [item.id for item in parse_items((tree / "organiser.md").read_text())] == [first.id]


# -- M25: a delete leaves the journal ---------------------------------------------


def test_a_delete_takes_the_item_out_of_the_file_and_not_out_of_the_journal(tmp_path):
    first = said("stand-ups", "60 minutes")
    tree = mine(tmp_path, JETTRO)
    write(tree, "organiser.md", [first])

    memory = delete_item(tmp_path, user(JETTRO), first.id)

    assert memory.mine == []
    assert parse_items((tree / "organiser.md").read_text()) == []
    assert authors(tree) == [JETTRO, "@Intake"]
    assert "60 minutes" in git(tree, "show", "HEAD~1:organiser.md")


# -- M22: who may change what ----------------------------------------------------


def test_what_is_said_about_you_is_yours_to_change(tmp_path):
    vegetarian = said("lunch", "vegetarian", scope=f"person:{SANNE}")
    write(ours(tmp_path), f"people/{SANNE}.md", [vegetarian])

    memory = edit(tmp_path, user(SANNE), vegetarian.id, "lunch", "vegan")

    [about] = memory.about_me
    assert (about.item.text, about.item.said_by, about.can_change) == ("vegan", SANNE, True)
    assert [version.item.said_by for version in about.history] == [JETTRO]
    # Her words now: no longer among what Jettro said about others.
    assert my_memory(tmp_path, user(JETTRO)).said_by_me == []


def test_what_you_said_about_someone_else_you_can_see_and_withdraw(tmp_path):
    vegetarian = said("lunch", "vegetarian", scope=f"person:{SANNE}")
    write(ours(tmp_path), f"people/{SANNE}.md", [vegetarian])

    [listed] = my_memory(tmp_path, user(JETTRO)).said_by_me
    assert (listed.item.id, listed.can_change) == (vegetarian.id, True)

    assert delete_item(tmp_path, user(JETTRO), vegetarian.id).said_by_me == []
    assert my_memory(tmp_path, user(SANNE)).about_me == []


def test_somebody_else_cannot_change_it_and_is_not_told_it_exists(tmp_path):
    vegetarian = said("lunch", "vegetarian", scope=f"person:{SANNE}")
    standups = said("stand-ups", "30 minutes")
    write(ours(tmp_path), f"people/{SANNE}.md", [vegetarian])
    write(mine(tmp_path, JETTRO), "organiser.md", [standups])

    for item_id in (vegetarian.id, standups.id, "no-such-item"):
        with pytest.raises(NotYours):
            delete_item(tmp_path, user(DAAN), item_id)
        with pytest.raises(NotYours):
            edit(tmp_path, user(DAAN), item_id, "x", "y")

    assert my_memory(tmp_path, user(DAAN)).said_by_me == []


def test_a_place_fact_is_for_whoever_said_it_and_an_admin(tmp_path):
    noisy = said("the meadow room, for workshops", "too noisy", scope="place:meet-nature")
    write(ours(tmp_path), "places/meet-nature.md", [noisy])

    assert [r.can_change for r in my_memory(tmp_path, user(DAAN)).places] == [False]
    assert [r.can_change for r in my_memory(tmp_path, user(DAAN, admin=True)).places] == [True]
    assert [r.can_change for r in my_memory(tmp_path, user(JETTRO)).places] == [True]

    with pytest.raises(NotYours):
        delete_item(tmp_path, user(DAAN), noisy.id)
    memory = change_item(
        tmp_path,
        user(DAAN, admin=True),
        noisy.id,
        ItemChange(situation="the meadow room", text="fine since May"),
    )
    assert [(r.item.text, r.item.said_by) for r in memory.places] == [("fine since May", DAAN)]


# -- M26: written as an agent writes ----------------------------------------------


def test_without_a_journal_the_change_is_still_written(tmp_path):
    first = said("stand-ups", "60 minutes")
    tree = mine(tmp_path, JETTRO)
    write(tree, "organiser.md", [first], journal=False)

    memory = edit(tmp_path, user(JETTRO), first.id, "stand-ups", "30 minutes")

    assert [r.item.text for r in memory.mine] == ["30 minutes"]
    assert not memory.journal


def test_a_hand_edit_before_the_page_edit_is_committed_as_one(tmp_path):
    first = said("stand-ups", "60 minutes")
    tree = mine(tmp_path, JETTRO)
    write(tree, "organiser.md", [first])
    (tree / "notes.txt").write_text("typed by hand")

    edit(tmp_path, user(JETTRO), first.id, "stand-ups", "30 minutes")

    assert authors(tree) == [JETTRO, "out-of-band", "@Intake"]


class ScriptedIntake(IntakeAgent):
    def act(self, message, output_type):
        return output_type()


@pytest.fixture
def intake(tmp_path, monkeypatch):
    """The real `@Intake` with the real memory card, writing under `tmp_path`."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("AKGENTIC_WORKSPACES_ROOT", str(tmp_path))
    monkeypatch.setenv("AKGENTIC_WORKSPACE_SHARED_KINDS", "id")
    previous = get_channel()
    set_channel(QueueChannel())
    system = ActorSystem()

    def member(agent_class, config, children=None) -> TeamCardMember:
        return TeamCardMember(
            card=AgentCard(agent_class=agent_class, description=config.role, config=config),
            headcount=1,
            members=children or [],
        )

    intake_config = IntakeConfig(name="@Intake", role="Intake", tools=[IntakeTools(), MemoryTool()])
    card = TeamCard(
        name="memory-edit-test",
        entry_point=member(
            ChannelHuman, BaseConfig(name="@Human", role="Human"), [member(ScriptedIntake, intake_config)]
        ),
        members=[],
        message_types=MESSAGE_TYPES,
        agent_profiles=[],
    )
    runtime = TeamFactory.build(card, system, user_id=JETTRO)
    yield system.proxy_ask(runtime.addrs["@Intake"], ScriptedIntake)
    system.shutdown()
    set_channel(previous)


def test_an_agent_writing_after_a_page_edit_keeps_both(intake, tmp_path):
    intake.remember_said("fact", "organiser", "who my team is", "Sanne and Daan")
    [team] = my_memory(tmp_path, user(JETTRO)).mine
    change_item(
        tmp_path,
        user(JETTRO),
        team.item.id,
        ItemChange(situation="who my team is", text="Sanne, Daan, Femke"),
    )
    intake.remember_said("preference", "organiser", "stand-ups", "30 minutes")

    memory = my_memory(tmp_path, user(JETTRO))
    assert [(r.item.situation, r.item.text) for r in memory.mine] == [
        ("who my team is", "Sanne, Daan, Femke"),
        ("stand-ups", "30 minutes"),
    ]
    assert authors(mine(tmp_path, JETTRO))[:3] == ["@Intake", JETTRO, "@Intake"]


def test_page_and_agent_writing_at_once_lose_nothing(intake, tmp_path):
    intake.remember_said("fact", "organiser", "seed", "planted")
    seed = my_memory(tmp_path, user(JETTRO)).mine[0].item
    for n in range(6):
        intake.remember_said("fact", "organiser", f"page {n}", "before")
    edits = {r.item.situation: r.item.id for r in my_memory(tmp_path, user(JETTRO)).mine}
    failures: list[BaseException] = []

    def run(action) -> None:
        try:
            action()
        except BaseException as exc:  # noqa: BLE001 - any failure fails the test below
            failures.append(exc)

    threads = [
        threading.Thread(
            target=run,
            args=(
                lambda n=n: change_item(
                    tmp_path,
                    user(JETTRO),
                    edits[f"page {n}"],
                    ItemChange(situation=f"page {n}", text="after"),
                ),
            ),
        )
        for n in range(6)
    ] + [
        threading.Thread(
            target=run, args=(lambda n=n: intake.remember_said("fact", "organiser", f"agent {n}", "x"),)
        )
        for n in range(6)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not any(thread.is_alive() for thread in threads), "a writer is stuck"
    assert failures == []
    texts = {r.item.situation: r.item.text for r in my_memory(tmp_path, user(JETTRO)).mine}
    assert texts[seed.situation] == "planted"
    assert all(texts[f"page {n}"] == "after" for n in range(6))
    assert all(f"agent {n}" in texts for n in range(6))


# -- M27: the routes --------------------------------------------------------------


async def people() -> list[Person]:
    return [Person(email=JETTRO, name="Jettro Coenradie"), Person(email=SANNE, name="Sanne de Vries")]


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "not-used-by-these-tests")
    monkeypatch.delenv("AKGENTIC_WORKSPACE_SHARED_KINDS", raising=False)
    monkeypatch.delenv("AKGENTIC_WORKSPACES_ROOT", raising=False)
    built = create_meeting_app(
        ServerSettings(
            catalog_path="agents/catalog",
            event_store_path=tmp_path / "events",
            workspaces_root=tmp_path / "workspaces",
            cors_origins=["http://localhost:5173"],
            auth=AuthSettings(mode="demo", secret=SecretStr("a-secret-for-tests-only")),
        ),
        people=people,
    )
    yield built
    state_keys.SERVICES.require(built).actor_system.shutdown()


def test_the_routes_change_only_what_the_person_logged_in_may(app, tmp_path):
    root = tmp_path / "workspaces"
    standups = said("stand-ups", "60 minutes")
    write(mine(root, JETTRO), "organiser.md", [standups])
    url = f"/me/memory/items/{standups.id}"

    with TestClient(app) as client:
        assert client.put(url, json={"situation": "x", "text": "y"}).status_code == 401

        assert client.post("/auth/login/person", json={"email": SANNE}).status_code == 200
        assert client.delete(url).status_code == 404

        assert client.post("/auth/login/person", json={"email": JETTRO}).status_code == 200
        refused = client.put(
            f"/me/memory/items/{standups.id}", json={"situation": "stand-ups", "text": "token abc"}
        )
        assert refused.status_code == 422 and "secret" in refused.json()["detail"]

        edited = client.put(
            f"/me/memory/items/{standups.id}", json={"situation": "stand-ups", "text": "30 minutes"}
        )
        assert edited.status_code == 200
        [item] = edited.json()["mine"]
        assert item["item"]["text"] == "30 minutes" and item["can_change"]

        deleted = client.delete(f"/me/memory/items/{item['item']['id']}")
        assert deleted.status_code == 200 and deleted.json()["mine"] == []
