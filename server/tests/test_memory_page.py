"""`GET /me/memory`: what is remembered for and about you, with its history (design_memory.md §4.8).

The trees are written here the way the workspace tool lays them out - a tree,
and its journal beside it as `<tree>.git` - and committed with the journal's
author convention: the agent's name, or `out-of-band` for a hand edit.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from akgentic.infra.server import state_keys
from akgentic.infra.server.auth import RequestUser
from fastapi.testclient import TestClient
from meeting_agents.memory import MemoryItem, render_items, with_item
from meeting_server.app import create_meeting_app
from meeting_server.auth import Person
from meeting_server.memory_page import my_memory
from meeting_server.settings import AuthSettings, ServerSettings
from pydantic import SecretStr

JETTRO = "jettro@rag4p.org"
DAAN = "daan@rag4p.org"
SANNE = "sanne@rag4p.org"


def mine(root: Path, email: str) -> Path:
    return root / email / "_id" / "memory"


def ours(root: Path) -> Path:
    return root / "_shared" / "_id" / "memory-shared"


def git(tree: Path, *args: str, author: str = "@Intake") -> None:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env |= {
        "GIT_AUTHOR_NAME": author,
        "GIT_AUTHOR_EMAIL": author,
        "GIT_COMMITTER_NAME": author,
        "GIT_COMMITTER_EMAIL": author,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
    }
    subprocess.run(
        ["git", "--git-dir", str(tree.with_name(tree.name + ".git")), "--work-tree", str(tree), *args],
        check=True,
        capture_output=True,
        env=env,
    )


def write(
    tree: Path, path: str, items: list[MemoryItem], *, author: str = "@Intake", journal: bool = True
) -> None:
    file = tree / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(render_items(items))
    if not journal:
        return
    if not tree.with_name(tree.name + ".git").is_dir():
        git(tree, "init", "-q")
    git(tree, "add", "-A")
    git(tree, "commit", "-q", "-m", f"write: {path}", author=author)


def said(situation: str, text: str, *, by: str = JETTRO, scope: str = f"organiser:{JETTRO}") -> MemoryItem:
    return MemoryItem(kind="preference", scope=scope, situation=situation, text=text, said_by=by)


def user(email: str) -> RequestUser:
    return RequestUser(user_id=email, email=email)


# -- what it reads ----------------------------------------------------------------


def test_a_correction_shows_what_it_replaced(tmp_path):
    tree = mine(tmp_path, JETTRO)
    first = said("stand-ups", "60 minutes")
    write(tree, "organiser.md", [first])
    write(tree, "organiser.md", with_item([first], said("stand-ups", "30 minutes")))

    memory = my_memory(tmp_path, user(JETTRO))

    assert memory.journal
    [standup] = memory.mine
    assert standup.item.text == "30 minutes"
    assert standup.recorded is not None and standup.recorded.by == "@Intake"
    assert [(v.item.text, v.by) for v in standup.history] == [("60 minutes", "@Intake")]


def test_history_follows_supersedes_back_newest_first(tmp_path):
    tree = mine(tmp_path, JETTRO)
    items = [said("stand-ups", "60 minutes")]
    for text in ("45 minutes", "30 minutes"):
        write(tree, "organiser.md", items)
        items = with_item(items, said("stand-ups", text))
    write(tree, "organiser.md", items)

    [standup] = my_memory(tmp_path, user(JETTRO)).mine

    assert [v.item.text for v in standup.history] == ["45 minutes", "60 minutes"]


def test_about_me_is_what_anyone_said_and_mine_is_only_mine(tmp_path):
    write(mine(tmp_path, JETTRO), "organiser.md", [said("who my team is", "me, Sanne and Daan")])
    write(ours(tmp_path), f"people/{SANNE}.md", [said("lunch", "vegetarian", scope=f"person:{SANNE}")])

    sanne = my_memory(tmp_path, user(SANNE))
    daan = my_memory(tmp_path, user(DAAN))

    assert sanne.mine == []
    assert [(r.item.text, r.item.said_by) for r in sanne.about_me] == [("vegetarian", JETTRO)]
    assert daan.mine == [] and daan.about_me == []


def test_without_a_journal_the_items_come_without_history_and_say_so(tmp_path):
    write(mine(tmp_path, JETTRO), "organiser.md", [said("stand-ups", "30 minutes")], journal=False)

    memory = my_memory(tmp_path, user(JETTRO))

    assert not memory.journal
    [standup] = memory.mine
    assert standup.recorded is None and standup.history == []


def test_a_hand_edit_is_named_as_one(tmp_path):
    tree = mine(tmp_path, JETTRO)
    first = said("stand-ups", "60 minutes")
    write(tree, "organiser.md", [first])
    write(tree, "organiser.md", with_item([first], said("stand-ups", "15 minutes")), author="out-of-band")

    [standup] = my_memory(tmp_path, user(JETTRO)).mine

    assert standup.recorded is not None and standup.recorded.outside
    assert not standup.history[0].outside


def test_a_broken_file_reads_as_empty(tmp_path):
    tree = mine(tmp_path, JETTRO)
    write(tree, "organiser.md", [said("stand-ups", "30 minutes")])
    (tree / "organiser.md").write_text("---\nkind: [unclosed\n---\nboom\n")

    assert my_memory(tmp_path, user(JETTRO)).mine == []


# -- the route ----------------------------------------------------------------------


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


def test_the_route_answers_for_the_person_logged_in(app, tmp_path):
    root = tmp_path / "workspaces"
    write(mine(root, JETTRO), "organiser.md", [said("stand-ups", "30 minutes")])
    write(ours(root), f"people/{SANNE}.md", [said("lunch", "vegetarian", scope=f"person:{SANNE}")])

    with TestClient(app) as client:
        assert client.post("/auth/login/person", json={"email": SANNE}).status_code == 200
        body = client.get("/me/memory").json()

    assert body["email"] == SANNE
    assert body["mine"] == []
    assert [r["item"]["text"] for r in body["about_me"]] == ["vegetarian"]


def test_the_route_needs_a_login(app):
    with TestClient(app) as client:
        assert client.get("/me/memory").status_code == 401
