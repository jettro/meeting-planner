"""The memory keeper's proposals on the Memory page (design_memory.md §10.6, M41-M43).

`@Keeper` writes `proposed.md`; here the person accepts a proposal - applied to
*Mine* as an edit or a delete would be, said by them - or answers *Not now*,
which keeps its digest so it is not proposed again.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from akgentic.infra.server.auth import RequestUser, get_request_user
from fastapi import FastAPI
from fastapi.testclient import TestClient
from meeting_agents.memory import MemoryItem, Proposal, parse_blocks, parse_items, render_items
from meeting_server.memory_page import (
    ON_THE_PAGE,
    NotYours,
    Refused,
    accept_proposal,
    build_router,
    decline_proposal,
    my_memory,
)

JETTRO = "jettro@rag4p.org"
DAAN = "daan@rag4p.org"


def user(email: str = JETTRO) -> RequestUser:
    return RequestUser(user_id=email, email=email)


def tree(root: Path, email: str = JETTRO) -> Path:
    return root / email / "_id" / "memory"


def git(path: Path, *args: str) -> str:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env |= {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    env |= {f"GIT_{who}_{what}": "@Keeper" for who in ("AUTHOR", "COMMITTER") for what in ("NAME", "EMAIL")}
    return subprocess.run(
        ["git", "--git-dir", str(path.with_name(path.name + ".git")), "--work-tree", str(path), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout


def said(situation: str, text: str, item_id: str) -> MemoryItem:
    return MemoryItem(
        id=item_id,
        kind="preference",
        scope=f"organiser:{JETTRO}",
        situation=situation,
        text=text,
        said_by=JETTRO,
    )


STANDUPS = said("stand-ups", "30 minutes", "a1")
HALF_HOUR = said("stand-ups, how long", "half an hour", "a2")
FOCUS = said("focus sessions", "always the Library", "a3")


def laid_down(
    root: Path, *proposals: Proposal, mine: tuple[MemoryItem, ...] = (STANDUPS, HALF_HOUR, FOCUS)
) -> None:
    path = tree(root)
    path.mkdir(parents=True, exist_ok=True)
    (path / "organiser.md").write_text(render_items(list(mine)))
    (path / "proposed.md").write_text(render_items(list(proposals)))
    git(path, "init", "-q")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "write: proposed.md")


def merge() -> Proposal:
    return Proposal(
        kind="merge", items=["a1", "a2"], situation="stand-ups", text="30 minutes", reason="they say the same"
    )


def mine_now(root: Path) -> list[MemoryItem]:
    return parse_items((tree(root) / "organiser.md").read_text())


def open_now(root: Path) -> list[Proposal]:
    return parse_blocks((tree(root) / "proposed.md").read_text(), Proposal)


# -- what the page shows ---------------------------------------------------------


def test_the_page_shows_each_proposal_with_the_items_it_would_change(tmp_path):
    proposal = merge()
    laid_down(tmp_path, proposal)

    [view] = my_memory(tmp_path, user()).proposals

    assert view.proposal.id == proposal.id
    assert [item.id for item in view.targets] == ["a1", "a2"]


def test_a_proposal_about_an_item_that_is_gone_is_not_shown(tmp_path):
    laid_down(tmp_path, merge(), mine=(STANDUPS, FOCUS))

    assert my_memory(tmp_path, user()).proposals == []


def test_another_person_sees_none_of_it(tmp_path):
    proposal = merge()
    laid_down(tmp_path, proposal)

    assert my_memory(tmp_path, user(DAAN)).proposals == []
    with pytest.raises(NotYours):
        accept_proposal(tmp_path, user(DAAN), proposal.id)


# -- M42: accepting ----------------------------------------------------------------


def test_a_merge_becomes_one_item_said_by_the_person(tmp_path):
    proposal = merge()
    laid_down(tmp_path, proposal)

    memory = accept_proposal(tmp_path, user(), proposal.id)

    [standups, focus] = mine_now(tmp_path)
    assert (standups.situation, standups.text, standups.supersedes) == ("stand-ups", "30 minutes", "a1")
    assert (standups.said_by, standups.evidence) == (JETTRO, ON_THE_PAGE)
    assert standups.reason == "accepted the memory keeper's proposal: they say the same"
    assert focus.id == "a3"
    assert memory.proposals == [] and open_now(tmp_path) == []
    assert git(tree(tmp_path), "log", "--format=%an").split()[:2] == [JETTRO, JETTRO]


def test_a_retire_takes_the_item_out(tmp_path):
    proposal = Proposal(kind="retire", items=["a2"], reason="a1 says it already")
    laid_down(tmp_path, proposal)

    accept_proposal(tmp_path, user(), proposal.id)

    assert [item.id for item in mine_now(tmp_path)] == ["a1", "a3"]


def test_a_reword_is_a_new_version(tmp_path):
    proposal = Proposal(
        kind="reword",
        items=["a3"],
        situation="focus sessions",
        text="Focus sessions go to the Library.",
        reason="r",
    )
    laid_down(tmp_path, proposal)

    accept_proposal(tmp_path, user(), proposal.id)

    [_, _, focus] = mine_now(tmp_path)
    assert (focus.text, focus.supersedes, focus.said_by) == (
        "Focus sessions go to the Library.",
        "a3",
        JETTRO,
    )


def test_a_merge_onto_a_situation_another_item_holds_is_refused(tmp_path):
    proposal = Proposal(kind="merge", items=["a1", "a2"], situation="focus sessions", text="x", reason="r")
    laid_down(tmp_path, proposal)

    with pytest.raises(Refused, match="already about"):
        accept_proposal(tmp_path, user(), proposal.id)
    assert [item.id for item in mine_now(tmp_path)] == ["a1", "a2", "a3"]


# -- M43: Not now ------------------------------------------------------------------


def test_not_now_keeps_the_digest_and_takes_the_proposal_away(tmp_path):
    proposal = merge()
    laid_down(tmp_path, proposal)

    memory = decline_proposal(tmp_path, user(), proposal.id)

    assert memory.proposals == [] and open_now(tmp_path) == []
    assert [item.id for item in mine_now(tmp_path)] == ["a1", "a2", "a3"]
    [declined] = parse_items((tree(tmp_path) / "declined.md").read_text())
    assert (declined.situation, declined.status) == (proposal.key, "retired")


# -- the routes --------------------------------------------------------------------


def test_the_routes_answer_for_the_person_logged_in(tmp_path):
    accepted, declined = merge(), Proposal(kind="retire", items=["a3"], reason="r")
    laid_down(tmp_path, accepted, declined)
    app = FastAPI()
    app.include_router(build_router(tmp_path))
    app.dependency_overrides[get_request_user] = lambda: user()

    with TestClient(app) as client:
        assert len(client.get("/me/memory").json()["proposals"]) == 2
        assert client.post(f"/me/memory/proposals/{accepted.id}").status_code == 200
        body = client.delete(f"/me/memory/proposals/{declined.id}").json()
        assert body["proposals"] == []
        assert client.post(f"/me/memory/proposals/{accepted.id}").status_code == 404
