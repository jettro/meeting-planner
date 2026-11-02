"""Memory, phase 1 (design_memory.md): the scenarios of §6, against a scripted model.

Real actor systems, real workspace trees on disk, real git journals; only the
model is replaced, so these say what the *code* guarantees - what reaches the
model, what is stored, who can see it - and nothing about what a model does
with it. Two organisers, Jettro and Daan, each have their own teams, the way a
login gives them (design_auth.md).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from akgentic.core import ActorAddress, ActorSystem, AgentCard, Akgent, BaseConfig, BaseState
from akgentic.team import TeamCard, TeamCardMember, TeamFactory
from meeting_agents.human import ChannelHuman, QueueChannel, get_channel, set_channel
from meeting_agents.intake import IntakeAgent, IntakeConfig, IntakeTools
from meeting_agents.memory import (
    MemoryApplied,
    MemoryItem,
    MemoryTool,
    parse_items,
    refusal,
    render_items,
    with_item,
)
from meeting_agents.messages import MESSAGE_TYPES, FindPeopleAssignment, NameMatch, PeopleFound, Person

JETTRO = "jettro@rag4p.org"
DAAN = "daan@rag4p.org"
SANNE = Person(name="Sanne de Vries", email="sanne@rag4p.org")


class Seen:
    """What reached the model, and what the trace was told, across teams."""

    updates: list[str] = []
    events: list[MemoryApplied] = []

    @classmethod
    def reset(cls) -> None:
        cls.updates, cls.events = [], []


class ScriptedIntake(IntakeAgent):
    def act(self, message, output_type):
        Seen.updates.append(message.rendering())
        return output_type()

    def notify_event(self, event: object) -> None:
        if isinstance(event, MemoryApplied):
            Seen.events.append(event)
        super().notify_event(event)

    def context_block(self) -> str:
        """The Context update the model would get on its next turn."""
        return self._context_updater.compose_update([]) or ""


class StubScheduler(Akgent[BaseConfig, BaseState]):
    def receiveMsg_FindPeopleAssignment(  # noqa: N802
        self, message: FindPeopleAssignment, sender: ActorAddress
    ) -> None:
        matches = [
            NameMatch(asked=name, candidates=[SANNE] if name == "Sanne" else []) for name in message.names
        ]
        self.send(sender, PeopleFound(matches=matches))


def member(agent_class, config, children=None) -> TeamCardMember:
    return TeamCardMember(
        card=AgentCard(agent_class=agent_class, description=config.role, config=config),
        headcount=1,
        members=children or [],
    )


def card() -> TeamCard:
    return TeamCard(
        name="memory-test",
        entry_point=member(
            ChannelHuman,
            BaseConfig(name="@Human", role="Human"),
            [
                member(
                    ScriptedIntake,
                    IntakeConfig(name="@Intake", role="Intake", tools=[IntakeTools(), MemoryTool()]),
                    [member(StubScheduler, BaseConfig(name="@Scheduler", role="Scheduler"))],
                )
            ],
        ),
        members=[],
        message_types=MESSAGE_TYPES,
        agent_profiles=[],
    )


@pytest.fixture
def root(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("AKGENTIC_WORKSPACES_ROOT", str(tmp_path))
    monkeypatch.setenv("AKGENTIC_WORKSPACE_SHARED_KINDS", "id")
    return tmp_path


@pytest.fixture
def system(root):
    Seen.reset()
    previous = get_channel()
    set_channel(QueueChannel())
    actors = ActorSystem()
    yield actors
    actors.shutdown()
    set_channel(previous)


def intake_for(system, organiser: str) -> ScriptedIntake:
    """A fresh team - a new conversation - for this organiser."""
    runtime = TeamFactory.build(card(), system, user_id=organiser)
    return runtime.actor_system.proxy_ask(runtime.addrs["@Intake"], ScriptedIntake)


def settle_sanne(intake: ScriptedIntake) -> str:
    """Look Sanne up and return the update the model got about it."""
    import time as clock

    before = len(Seen.updates)
    intake.look_up(["Sanne"])
    deadline = clock.monotonic() + 5
    while clock.monotonic() < deadline:
        for update in Seen.updates[before:]:
            if "sanne@rag4p.org" in update:
                return update
        clock.sleep(0.02)
    raise AssertionError("the lookup never reached the model")


def journal(root: Path, tree: str) -> list[str]:
    repo = root / f"{tree}.git"
    result = subprocess.run(
        ["git", "--git-dir", str(repo), "--work-tree", str(root / tree), "log", "--format=%s | %an"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip().splitlines()


# -- the item format ------------------------------------------------------------


def item(situation: str, text: str, **fields) -> MemoryItem:
    return MemoryItem(
        kind="preference",
        scope=f"organiser:{JETTRO}",
        situation=situation,
        text=text,
        said_by=JETTRO,
        **fields,
    )


def test_an_item_survives_the_file_a_person_can_read():
    items = [
        item("who Daan is", "Daan Jansen"),
        item("stand-ups", "30 minutes", review_when="the team changes"),
    ]

    text = render_items(items)

    assert "situation: who Daan is" in text
    assert parse_items(text) == items


def test_saying_it_again_replaces_it_and_names_what_it_replaced():
    first = item("stand-ups", "60 minutes")

    items = with_item([first, item("who Daan is", "Daan Jansen")], item("Stand-ups", "30 minutes"))

    assert [i.text for i in items] == ["Daan Jansen", "30 minutes"]
    assert items[-1].supersedes == first.id


@pytest.mark.parametrize(
    "text",
    ["my password is hunter2", "use api key ak_live_x", "the booking id is 48213", "token abc"],
)
def test_secrets_and_ids_are_not_memory(text):
    assert refusal(text) is not None


def test_a_plain_preference_is(text="Sanne is vegetarian"):
    assert refusal(text) is None


# -- §6: applied when it should be ----------------------------------------------


def test_what_the_organiser_said_is_there_in_their_next_conversation(system):
    """Case 1: the second conversation knows who "Daan" is without asking."""
    first = intake_for(system, JETTRO)
    assert first.remember_said("preference", "organiser", "who Daan is", "Daan means Daan Jansen").startswith(
        "Remembered"
    )

    block = intake_for(system, JETTRO).context_block()

    assert "Daan means Daan Jansen" in block
    assert JETTRO in block


def test_what_is_known_about_a_person_arrives_with_the_lookup(system):
    """Case 3: said once by Jettro, it reaches Daan's lunch for Sanne."""
    jettro = intake_for(system, JETTRO)
    settle_sanne(jettro)
    assert jettro.remember_said("fact", "sanne@rag4p.org", "lunch", "vegetarian").startswith("Remembered")

    update = settle_sanne(intake_for(system, DAAN))

    assert "Remembered about sanne@rag4p.org: lunch: vegetarian." in update


# -- §6: not applied out of scope -----------------------------------------------


def test_one_organisers_memory_never_reaches_another(system):
    intake_for(system, JETTRO).remember_said("preference", "organiser", "focus sessions", "the Library")

    assert "the Library" not in intake_for(system, DAAN).context_block()


def test_a_fact_about_a_stranger_is_refused(system):
    """Only someone this conversation settled - a guessed address is a stranger."""
    answer = intake_for(system, JETTRO).remember_said("fact", "sanne@rag4p.org", "lunch", "vegetarian")

    assert answer.startswith("Refused")


def test_a_secret_is_refused_and_nothing_is_written(system, root):
    answer = intake_for(system, JETTRO).remember_said("fact", "organiser", "login", "my password is hunter2")

    assert answer.startswith("Not remembered")
    assert not (root / JETTRO / "_id" / "memory" / "organiser.md").exists()


# -- §6: superseded, proposed, abstains ----------------------------------------


def test_a_correction_replaces_the_earlier_item_and_the_journal_keeps_both(system, root):
    intake = intake_for(system, JETTRO)
    intake.remember_said("preference", "organiser", "focus sessions", "the Library")
    intake.remember_said("preference", "organiser", "focus sessions", "actually, the Loft")

    block = intake_for(system, JETTRO).context_block()

    assert "the Loft" in block
    assert "the Library" not in block
    writes = [line for line in journal(root, f"{JETTRO}/_id/memory") if line.startswith("write:")]
    assert writes == ["write: organiser.md | @Intake", "write: organiser.md | @Intake"]


def test_a_proposed_item_is_not_applied(system, root):
    """M6: status decides, not wording. A person promotes it before it counts."""
    intake = intake_for(system, JETTRO)
    intake.remember_said("preference", "organiser", "who Daan is", "Daan Jansen")
    path = root / JETTRO / "_id" / "memory" / "organiser.md"
    path.write_text(
        path.read_text() + "\n" + render_items([item("stand-ups", "30 minutes", status="proposed")])
    )

    block = intake_for(system, JETTRO).context_block()

    assert "Daan Jansen" in block
    assert "30 minutes" not in block


def test_with_no_memory_behaviour_is_exactly_todays(system):
    intake = intake_for(system, JETTRO)

    assert "remember" not in intake.context_block().lower()
    assert "Remembered" not in settle_sanne(intake)
    assert Seen.events == []


def test_a_hand_broken_file_does_not_break_the_conversation(system, root):
    intake = intake_for(system, JETTRO)
    intake.remember_said("preference", "organiser", "who Daan is", "Daan Jansen")
    (root / JETTRO / "_id" / "memory" / "organiser.md").write_text("---\nkind: [unclosed\n---\nboom\n")

    assert "Daan Jansen" not in intake_for(system, JETTRO).context_block()


# -- where it lives, and what the trace says ------------------------------------


def test_the_organisers_tree_is_theirs_and_the_shared_tree_is_everybodys(system, root):
    jettro = intake_for(system, JETTRO)
    jettro.remember_said("preference", "organiser", "who Daan is", "Daan Jansen")
    settle_sanne(jettro)
    jettro.remember_said("fact", "sanne@rag4p.org", "lunch", "vegetarian")

    mine = parse_items((root / JETTRO / "_id" / "memory" / "organiser.md").read_text())
    ours = parse_items(
        (root / "_shared" / "_id" / "memory-shared" / "people" / "sanne@rag4p.org.md").read_text()
    )

    assert [(i.scope, i.said_by) for i in mine] == [(f"organiser:{JETTRO}", JETTRO)]
    assert [(i.scope, i.said_by, i.text) for i in ours] == [("person:sanne@rag4p.org", JETTRO, "vegetarian")]
    assert ours[0].evidence == f"conversation {jettro.team_id}"


def test_every_application_is_an_event(system):
    """M9: the trace can answer "why did it know that?"."""
    jettro = intake_for(system, JETTRO)
    jettro.remember_said("preference", "organiser", "who Daan is", "Daan Jansen")
    settle_sanne(jettro)
    jettro.remember_said("fact", "sanne@rag4p.org", "lunch", "vegetarian")
    Seen.reset()

    daan = intake_for(system, DAAN)
    daan.context_block()
    settle_sanne(daan)
    jettros_next = intake_for(system, JETTRO)
    jettros_next.context_block()
    jettros_next.context_block()  # unchanged: no second event

    reasons = [event.reason for event in Seen.events]
    assert reasons == ["a lookup settled sanne@rag4p.org", "always: the organiser's own memory"]
    assert Seen.events[0].items == ["- lunch: vegetarian"]


def test_the_event_survives_the_event_store():
    """The trace is persisted and replayed; the event must come back as itself."""
    from akgentic.core.messages import EventMessage
    from akgentic.core.utils.serializer import serialize

    sent = EventMessage(event=MemoryApplied(agent="@Intake", reason="always", items=["- lunch: vegetarian"]))

    back = EventMessage.model_validate(serialize(sent))

    assert back.event == sent.event


def test_two_things_remembered_at_once_are_both_kept(system):
    """Found live: a model calls `remember` twice in one turn, and pydantic-ai runs
    the two calls in parallel. Without the lock, one write replaced the other and
    both answered "Remembered"."""
    from concurrent.futures import ThreadPoolExecutor

    intake = intake_for(system, JETTRO)
    memory = next(c for c in intake.config.tools if isinstance(c, MemoryTool))
    items = [item(f"situation {n}", f"text {n}") for n in range(8)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(memory.remember, items))

    kept = {i.situation for i in memory.organiser_items()}
    assert kept == {f"situation {n}" for n in range(8)}
