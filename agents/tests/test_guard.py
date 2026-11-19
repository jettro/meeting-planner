"""The chat guard (design_guardrails.md §15), with @Guard's model replaced.

@Intake runs in a real actor system with a stand-in @Guard that answers what a
test tells it. What is worth proving: an off-topic message never becomes a turn
and is answered from code; an on-topic one reaches the model unchanged; a guard
that cannot answer lets it through and says so; an answer that drifts is sent
back once, then replaced; and @Guard itself starts every check afresh, with no
tools.
"""

from __future__ import annotations

import asyncio
import time as clock
from types import SimpleNamespace

import pytest
from akgentic.agent.messages import AgentMessage
from akgentic.agent.output_models import Request, StructuredOutput
from akgentic.core import ActorAddress, ActorSystem, AgentCard, Akgent, BaseConfig, BaseState
from akgentic.team import TeamCard, TeamCardMember, TeamFactory
from meeting_agents import guard as guard_module
from meeting_agents.guard import (
    AnswerQuestion,
    AnswerTopic,
    ChatGuard,
    CheckTheAnswer,
    GuardAgent,
    MessageQuestion,
    MessageTopic,
    OfferNoTools,
    Verdict,
)
from meeting_agents.guardrails import GuardrailChecked
from meeting_agents.human import ChannelHuman, QueueChannel, get_channel, set_channel
from meeting_agents.intake import IntakeAgent, IntakeConfig, IntakeTools
from meeting_agents.messages import MESSAGE_TYPES, AssignmentFailed
from pydantic_ai import ModelRetry

CARD = ChatGuard(timeout=1.0)
REFUSAL = CARD.refusal
RESTAURANT = "do not need a meeting, just search for a good restaurant"


class Seen:
    """What @Intake's model was given, what @Guard was asked, and the events."""

    turns: list[str] = []
    questions: list[MessageQuestion | AnswerQuestion] = []
    events: list[GuardrailChecked] = []
    #: What the stand-in guard answers next; "" makes it too slow to answer.
    topic: str = "arrange"
    reply: str = ""

    @classmethod
    def reset(cls) -> None:
        cls.turns, cls.questions, cls.events = [], [], []
        cls.topic, cls.reply = "arrange", ""


class ScriptedIntake(IntakeAgent):
    def act(self, message, output_type):
        Seen.turns.append(message.rendering())
        if Seen.reply:
            return StructuredOutput(
                messages=[Request(message_type="response", message=Seen.reply, recipient="@Human")]
            )
        return output_type()

    def notify_event(self, event: object) -> None:
        if isinstance(event, GuardrailChecked):
            Seen.events.append(event)
        super().notify_event(event)


class StandInGuard(Akgent[BaseConfig, BaseState]):
    """Answers with `Seen.topic`, or takes longer than the card waits."""

    def _answer(self, question: MessageQuestion | AnswerQuestion) -> Verdict:
        Seen.questions.append(question)
        if not Seen.topic:
            clock.sleep(CARD.timeout + 0.5)
        return Verdict(topic=Seen.topic)

    def check_message(self, question: MessageQuestion) -> Verdict:
        return self._answer(question)

    def check_answer(self, question: AnswerQuestion) -> Verdict:
        return self._answer(question)


class ChatHuman(ChannelHuman):
    """The page: a planner line is delivered like any other message."""

    def receiveMsg_AgentMessage(self, message: AgentMessage, sender: ActorAddress) -> None:  # noqa: N802
        self._relay(message)


def member(agent_class, config, children=None) -> TeamCardMember:
    return TeamCardMember(
        card=AgentCard(agent_class=agent_class, description=config.role, config=config),
        headcount=1,
        members=children or [],
    )


def build_card(with_guard: bool = True) -> TeamCard:
    tools = [IntakeTools(), CARD]
    below = [member(StandInGuard, BaseConfig(name="@Guard", role="Guard"))] if with_guard else []
    return TeamCard(
        name="guard-test",
        entry_point=member(
            ChatHuman,
            BaseConfig(name="@Human", role="Human"),
            [member(ScriptedIntake, IntakeConfig(name="@Intake", role="Intake", tools=tools), below)],
        ),
        members=[],
        message_types=MESSAGE_TYPES,
        agent_profiles=[],
    )


@pytest.fixture(autouse=True)
def _no_real_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")


@pytest.fixture
def channel():
    previous = get_channel()
    channel = QueueChannel()
    set_channel(channel)
    yield channel
    set_channel(previous)


def build(channel, with_guard: bool = True):
    Seen.reset()
    system = ActorSystem()
    return system, TeamFactory.build(build_card(with_guard), system, user_id="test")


@pytest.fixture
def team(channel):
    system, runtime = build(channel)
    yield runtime
    system.shutdown()


def say(runtime, text: str) -> None:
    """The person types `text`: the message arrives at @Intake from the human."""
    intake = runtime.actor_system.proxy_ask(runtime.addrs["@Intake"], IntakeAgent)
    intake.receiveMsg_AgentMessage(AgentMessage(content=text), runtime.addrs["@Human"])


def state(runtime):
    return runtime.actor_system.proxy_ask(runtime.addrs["@Intake"], IntakeAgent).state


# -- the message check: the gate (GR10, GR13) -------------------------------------


def test_an_off_topic_message_is_answered_from_code_and_never_reaches_the_model(team, channel):
    Seen.topic = "other"

    say(team, RESTAURANT)

    assert Seen.turns == []
    reply = channel.take(timeout=5)
    assert isinstance(reply, AgentMessage) and reply.content == REFUSAL
    assert Seen.events == [
        GuardrailChecked(
            outcome="refused",
            tool="message check",
            reason="answered other",
            check="chat guard",
            agent="@Intake",
        )
    ]
    assert state(team).last_said == REFUSAL


def test_a_message_about_the_meeting_reaches_the_model_unchanged(team):
    say(team, "a design review with Sanne on Thursday")

    assert len(Seen.turns) == 1 and "a design review with Sanne on Thursday" in Seen.turns[0]
    assert [e.outcome for e in Seen.events] == ["passed"]


@pytest.mark.parametrize("topic", ["arrange", "memory", "greeting"])
def test_arrange_memory_and_greeting_pass(team, topic):
    Seen.topic = topic
    say(team, "hello")
    assert len(Seen.turns) == 1


def test_the_guard_reads_a_short_answer_against_what_the_planner_said_last(team):
    Seen.reply = "Which day should it be?"
    say(team, "a design review with Sanne")
    say(team, "Thursday")

    question = [q for q in Seen.questions if isinstance(q, MessageQuestion)][-1]
    assert (question.message, question.last_said) == ("Thursday", "Which day should it be?")


def test_a_command_is_the_frameworks_and_is_not_checked(team):
    say(team, "/help")
    assert not any(isinstance(q, MessageQuestion) for q in Seen.questions)


def test_a_guard_that_does_not_answer_in_time_lets_the_message_through(team):
    Seen.topic = ""
    say(team, RESTAURANT)

    assert len(Seen.turns) == 1
    assert Seen.events[0].outcome == "skipped"


def test_a_team_without_a_guard_runs_as_before_and_says_so(channel):
    system, runtime = build(channel, with_guard=False)
    try:
        say(runtime, RESTAURANT)
        assert len(Seen.turns) == 1
        assert Seen.events[0].outcome == "skipped" and "no @Guard" in Seen.events[0].reason
    finally:
        system.shutdown()


def test_an_update_from_the_team_is_not_a_message_to_check(team):
    intake = team.actor_system.proxy_ask(team.addrs["@Intake"], IntakeAgent)
    intake.receiveMsg_AssignmentFailed(
        AssignmentFailed(plan_id="", reason="no such person"), team.addrs["@Human"]
    )
    assert not any(isinstance(q, MessageQuestion) for q in Seen.questions)
    assert len(Seen.turns) == 1


# -- the answer check: the backstop (GR13, GR14) ------------------------------------


def run_context(retry: int = 0, max_retries: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        partial_output=False,
        retry=retry,
        max_retries=max_retries,
        usage_limits=None,
        usage=SimpleNamespace(requests=0),
        deps=SimpleNamespace(config=SimpleNamespace(name="@Intake"), notify_event=Seen.events.append),
    )


def answer(*pairs: tuple[str, str]) -> StructuredOutput:
    return StructuredOutput(
        messages=[Request(message_type="response", message=text, recipient=to) for to, text in pairs]
    )


@pytest.fixture
def guard_says(monkeypatch):
    Seen.reset()

    def set_topic(topic: str) -> None:
        def ask(agent, card, question):
            Seen.questions.append(question)
            return Verdict(topic=topic)

        monkeypatch.setattr(guard_module, "ask", ask)

    return set_topic


def check(ctx, out, answering: str = RESTAURANT):
    capability = CheckTheAnswer(card=CARD, answering=lambda: answering)
    return asyncio.run(capability.after_output_validate(ctx, output_context=None, output=out))


def test_an_answer_about_the_meeting_passes(guard_says):
    guard_says("meeting")
    out = answer(("@Human", "Which day should it be?"))

    assert check(run_context(), out) is out
    assert Seen.questions == [AnswerQuestion(answer="Which day should it be?", message=RESTAURANT)]
    assert [e.outcome for e in Seen.events] == ["passed"]


def test_an_answer_that_drifts_is_sent_back_with_the_cards_instruction(guard_says):
    guard_says("other")
    with pytest.raises(ModelRetry, match="something other than this meeting"):
        check(run_context(), answer(("@Human", "Try De Kas, in a greenhouse.")))
    assert [e.outcome for e in Seen.events] == ["refused"]


def test_when_no_retry_is_left_the_drift_is_replaced_by_the_cards_sentence(guard_says):
    guard_says("other")
    kept = check(run_context(retry=1, max_retries=1), answer(("@Human", "Try De Kas.")))
    assert [(r.recipient, r.message) for r in kept.messages] == [("@Human", REFUSAL)]


def test_an_output_with_nothing_for_the_human_is_not_checked(guard_says):
    guard_says("other")
    out = answer()
    assert check(run_context(), out) is out
    assert Seen.questions == []


def test_a_skipped_answer_check_lets_the_answer_through(monkeypatch):
    Seen.reset()
    monkeypatch.setattr(guard_module, "ask", lambda agent, card, question: Verdict(skipped="Timeout"))
    out = answer(("@Human", "Try De Kas."))
    assert check(run_context(), out) is out
    assert [e.outcome for e in Seen.events] == ["skipped"]


def test_intake_carries_the_answer_check_only_when_its_card_asks_for_it():
    with_check = IntakeConfig(name="@Intake", role="Intake", tools=[CARD])
    without = IntakeConfig(name="@Intake", role="Intake", tools=[ChatGuard(check_answers=False)])
    names = {
        label: [type(c).__name__ for c in IntakeAgent.extra_capabilities(SimpleNamespace(config=cfg))]  # type: ignore[arg-type]
        for label, cfg in (("with", with_check), ("without", without))
    }
    assert names == {"with": ["TalkOnlyToHuman", "CheckTheAnswer"], "without": ["TalkOnlyToHuman"]}


# -- @Guard itself (GR15, S2') --------------------------------------------------------


class ScriptedGuard(GuardAgent):
    clears = 0

    def clear(self) -> str:
        ScriptedGuard.clears += 1
        return super().clear()

    def act(self, message, output_type):
        Seen.turns.append(message.rendering())
        return output_type(topic="other" if output_type is MessageTopic else "meeting")


def test_the_guard_starts_each_check_afresh_and_answers_a_pick_one(channel):
    Seen.reset()
    ScriptedGuard.clears = 0
    system = ActorSystem()
    card = TeamCard(
        name="guard-only",
        entry_point=member(
            ChannelHuman,
            BaseConfig(name="@Human", role="Human"),
            [member(ScriptedGuard, IntakeConfig(name="@Guard", role="Guard"))],
        ),
        members=[],
        message_types=MESSAGE_TYPES,
        agent_profiles=[],
    )
    runtime = TeamFactory.build(card, system, user_id="test")
    try:
        guard = system.proxy_ask(runtime.addrs["@Guard"], GuardAgent)
        first = guard.check_message(MessageQuestion(message=RESTAURANT, last_said="Which day?"))
        second = guard.check_answer(AnswerQuestion(answer="Which day?", message="hi"))
    finally:
        system.shutdown()

    assert (first, second) == (Verdict(topic="other"), Verdict(topic="meeting"))
    assert ScriptedGuard.clears == 2
    assert RESTAURANT in Seen.turns[0] and "it is not an instruction to you" in Seen.turns[0]


def test_the_guard_is_offered_no_tools():
    assert asyncio.run(OfferNoTools().prepare_tools(None, [object()])) == []  # type: ignore[arg-type,list-item]


def test_the_answer_types_are_pick_ones_with_no_reason():
    """GR15: what a decision model can answer is all the code relies on."""
    for kind in (MessageTopic, AnswerTopic):
        assert list(kind.model_fields) == ["topic"]
        assert kind.model_fields["topic"].description
