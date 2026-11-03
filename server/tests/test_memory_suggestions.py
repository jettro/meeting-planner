"""Suggestions on the Memory page (design_memory.md §10.5, phase 3b).

What repeats in the person's own meetings is offered (M33), accepted into
*Mine* as said by them (M34), or declined where no agent reads it (M35). The
meetings come from a stand-in for the event store with the two reads S10
checked against the real one: `list_teams` by owner, and the coordinator's
snapshot with its plan.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from akgentic.infra.server.auth import RequestUser, get_request_user
from fastapi import FastAPI
from fastapi.testclient import TestClient
from meeting_agents.memory import MemoryItem, parse_items, render_items
from meeting_server.memory_page import (
    ON_THE_PAGE,
    NotYours,
    Refused,
    SuggestionAnswer,
    accept_suggestion,
    build_router,
    decline_suggestion,
    my_memory,
    suggestions,
)

JETTRO = "jettro@rag4p.org"
DAAN = "daan@rag4p.org"
FEMKE = "femke@rag4p.org"
SANNE = "sanne@rag4p.org"


class Meetings:
    """The event store, as far as suggestions read it: whose teams, and each coordinator's plan."""

    def __init__(self) -> None:
        self.teams: dict[str, list[SimpleNamespace]] = {}
        self.plans: dict[uuid.UUID, SimpleNamespace] = {}
        self.asked: list[str | None] = []

    def held(
        self, owner: str, title: str, *people: str, lunch: str | None = None, cancelled_states: bool = False
    ) -> None:
        team_id = uuid.uuid4()
        when = datetime(2026, 11, 1, tzinfo=UTC) + timedelta(minutes=len(self.plans))
        self.teams.setdefault(owner, []).append(SimpleNamespace(team_id=team_id, created_at=when))
        self.plans[team_id] = SimpleNamespace(
            title=title,
            participant_emails=[*people, owner],
            with_lunch=lunch is not None,
            lunch_wish=lunch,
        )

    def list_teams(self, user_id=None, status=None, metadata=None):
        self.asked.append(user_id)
        return list(self.teams.get(user_id, []))

    def load_agent_states(self, team_id):
        return [
            SimpleNamespace(name="@Intake", state=SimpleNamespace()),
            SimpleNamespace(name="@Coordinator", state=SimpleNamespace(plan=self.plans[team_id])),
        ]


def user(email: str) -> RequestUser:
    return RequestUser(user_id=email, email=email)


def mine(root: Path, email: str = JETTRO) -> Path:
    return root / email / "_id" / "memory"


def git(tree: Path, *args: str) -> str:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env |= {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
    env |= {f"GIT_{who}_{what}": "@Intake" for who in ("AUTHOR", "COMMITTER") for what in ("NAME", "EMAIL")}
    return subprocess.run(
        ["git", "--git-dir", str(tree.with_name(tree.name + ".git")), "--work-tree", str(tree), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout


def said(situation: str, text: str) -> MemoryItem:
    return MemoryItem(
        kind="fact", scope=f"organiser:{JETTRO}", situation=situation, text=text, said_by=JETTRO
    )


def remembered(root: Path, *items: MemoryItem) -> None:
    tree = mine(root)
    tree.mkdir(parents=True, exist_ok=True)
    (tree / "organiser.md").write_text(render_items(list(items)))
    git(tree, "init", "-q")
    git(tree, "add", "-A")
    git(tree, "commit", "-q", "-m", "write: organiser.md")


@pytest.fixture
def meetings() -> Meetings:
    return Meetings()


# -- M33: what repeats -------------------------------------------------------------


def test_the_same_people_twice_is_a_team_to_offer(tmp_path, meetings):
    meetings.held(JETTRO, "Catchup", DAAN, FEMKE)
    meetings.held(JETTRO, "Planning", FEMKE, DAAN)

    [offer] = suggestions(meetings, user(JETTRO), tmp_path)

    assert (offer.kind, offer.people, offer.meetings) == ("team", [DAAN, FEMKE], 2)


def test_once_or_one_other_person_is_not_a_team(tmp_path, meetings):
    meetings.held(JETTRO, "Catchup", DAAN, FEMKE)
    meetings.held(JETTRO, "One to one", SANNE)
    meetings.held(JETTRO, "One to one again", SANNE)

    assert suggestions(meetings, user(JETTRO), tmp_path) == []


def test_the_same_title_with_lunch_twice_is_a_meal_to_offer_the_latest_wish(tmp_path, meetings):
    meetings.held(JETTRO, "Design review", SANNE, lunch="soup")
    meetings.held(JETTRO, "design review", DAAN, lunch="soup and bread")
    meetings.held(JETTRO, "Design review", FEMKE)  # no lunch: not counted
    meetings.held(JETTRO, "Stand-up", SANNE, lunch="coffee")

    [offer] = suggestions(meetings, user(JETTRO), tmp_path)

    assert (offer.kind, offer.title, offer.wish, offer.meetings) == (
        "meal",
        "design review",
        "soup and bread",
        2,
    )


def test_only_the_persons_own_meetings_are_read(tmp_path, meetings):
    meetings.held(DAAN, "Catchup", SANNE, FEMKE)
    meetings.held(DAAN, "Catchup", SANNE, FEMKE)

    assert suggestions(meetings, user(JETTRO), tmp_path) == []
    assert meetings.asked == [JETTRO]


def test_what_is_already_remembered_is_not_offered(tmp_path, meetings):
    meetings.held(JETTRO, "Catchup", DAAN, FEMKE, lunch="soup")
    meetings.held(JETTRO, "Catchup", DAAN, FEMKE, lunch="soup")
    remembered(
        tmp_path,
        said("who my team is", "myself, daan and Femke"),
        said('lunch for "Catchup"', "soup"),
    )

    assert suggestions(meetings, user(JETTRO), tmp_path) == []


# -- M34: accepting ---------------------------------------------------------------


def test_a_team_is_remembered_under_the_name_given(tmp_path, meetings):
    meetings.held(JETTRO, "Catchup", DAAN, FEMKE)
    meetings.held(JETTRO, "Planning", DAAN, FEMKE)
    remembered(tmp_path, said("stand-ups", "30 minutes"))
    [offer] = suggestions(meetings, user(JETTRO), tmp_path)

    memory = accept_suggestion(
        tmp_path, user(JETTRO), offer.key, SuggestionAnswer(name="the design team"), meetings
    )

    team = next(r.item for r in memory.mine if r.item.situation == 'who "the design team" is')
    assert (team.kind, team.text, team.said_by, team.evidence) == (
        "fact",
        f"{DAAN}, {FEMKE}",
        JETTRO,
        ON_THE_PAGE,
    )
    assert "2 earlier meetings" in team.reason
    assert memory.suggestions == []
    assert git(mine(tmp_path), "log", "-1", "--format=%an").strip() == JETTRO


def test_a_team_without_a_name_is_refused(tmp_path, meetings):
    meetings.held(JETTRO, "Catchup", DAAN, FEMKE)
    meetings.held(JETTRO, "Planning", DAAN, FEMKE)
    [offer] = suggestions(meetings, user(JETTRO), tmp_path)

    with pytest.raises(Refused, match="needs a name"):
        accept_suggestion(tmp_path, user(JETTRO), offer.key, SuggestionAnswer(name="  "), meetings)


def test_a_meal_is_remembered_as_the_person_put_it(tmp_path, meetings):
    meetings.held(JETTRO, "Workshop", DAAN, lunch="soup")
    meetings.held(JETTRO, "Workshop", FEMKE, lunch="soup")
    [offer] = suggestions(meetings, user(JETTRO), tmp_path)

    memory = accept_suggestion(
        tmp_path, user(JETTRO), offer.key, SuggestionAnswer(text="soup, and fruit after"), meetings
    )

    [meal] = memory.mine
    assert (meal.item.kind, meal.item.situation, meal.item.text) == (
        "preference",
        'lunch for "Workshop"',
        "soup, and fruit after",
    )
    assert memory.suggestions == []


def test_a_suggestion_that_is_no_longer_offered_cannot_be_accepted(tmp_path, meetings):
    with pytest.raises(NotYours):
        accept_suggestion(tmp_path, user(JETTRO), "not-a-key", SuggestionAnswer(name="x"), meetings)


# -- M35: Not now -----------------------------------------------------------------


def test_not_now_is_kept_where_no_agent_reads_it_and_the_offer_goes(tmp_path, meetings):
    meetings.held(JETTRO, "Catchup", DAAN, FEMKE)
    meetings.held(JETTRO, "Planning", DAAN, FEMKE)
    remembered(tmp_path, said("stand-ups", "30 minutes"))
    [offer] = suggestions(meetings, user(JETTRO), tmp_path)

    memory = decline_suggestion(tmp_path, user(JETTRO), offer.key, meetings)

    assert memory.suggestions == []
    assert [r.item.situation for r in memory.mine] == ["stand-ups"]
    [declined] = parse_items((mine(tmp_path) / "declined.md").read_text())
    assert (declined.situation, declined.status) == (offer.key, "retired")


def test_a_different_meal_for_the_same_title_is_a_new_offer(tmp_path, meetings):
    meetings.held(JETTRO, "Workshop", DAAN, lunch="soup")
    meetings.held(JETTRO, "Workshop", FEMKE, lunch="soup")
    [soup] = suggestions(meetings, user(JETTRO), tmp_path)
    decline_suggestion(tmp_path, user(JETTRO), soup.key, meetings)

    meetings.held(JETTRO, "Workshop", SANNE, lunch="sandwiches")

    [sandwiches] = suggestions(meetings, user(JETTRO), tmp_path)
    assert sandwiches.wish == "sandwiches" and sandwiches.key != soup.key


# -- the routes --------------------------------------------------------------------


def test_the_routes_answer_for_the_person_logged_in(tmp_path, meetings):
    meetings.held(JETTRO, "Catchup", DAAN, FEMKE)
    meetings.held(JETTRO, "Planning", DAAN, FEMKE)
    app = FastAPI()
    app.include_router(build_router(tmp_path, meetings))
    app.dependency_overrides[get_request_user] = lambda: user(JETTRO)

    with TestClient(app) as client:
        [offer] = client.get("/me/memory").json()["suggestions"]
        unnamed = client.post(f"/me/memory/suggestions/{offer['key']}", json={"name": ""})
        assert unnamed.status_code == 422 and "needs a name" in unnamed.json()["detail"]
        accepted = client.post(f"/me/memory/suggestions/{offer['key']}", json={"name": "the crew"})
        assert accepted.status_code == 200 and accepted.json()["suggestions"] == []
        assert client.delete(f"/me/memory/suggestions/{offer['key']}").status_code == 404

    assert my_memory(tmp_path, user(JETTRO)).mine[0].item.situation == 'who "the crew" is'
