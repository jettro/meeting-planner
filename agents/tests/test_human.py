"""The human bridge: what reaches the client, and what stays out of the actor.

The point of these tests is less the relaying - which is three lines - than the
properties that keep a GUI possible: the actor holds no client, it never blocks,
and the channel can be swapped underneath it (§4.2).
"""

from __future__ import annotations

import queue
import threading
from datetime import date, time

import pytest
from akgentic.core import ActorAddress, ActorSystem, AgentCard, BaseConfig, BaseState
from akgentic.core.agent import Akgent
from akgentic.team import TeamCard, TeamCardMember, TeamFactory
from meeting_agents.answers import UnreadableAnswer
from meeting_agents.human import ChannelHuman, QueueChannel, get_channel, set_channel
from meeting_agents.messages import (
    MESSAGE_TYPES,
    LunchApprovalDecision,
    LunchApprovalRequest,
    PlanCompleted,
    PlanFailed,
    PlanMeetingRequest,
    ProposedSlot,
    SlotApprovalDecision,
    SlotApprovalRequest,
)

DAY = date(2031, 9, 15)
SLOT = ProposedSlot(start=time(10, 0), end=time(11, 0))


def a_plan():
    return PlanMeetingRequest(
        title="Jettro and Daniel",
        participant_emails=["jettro@example.com"],
        day=DAY,
        duration_minutes=60,
        location_id="AMS",
    ).to_plan()


class Answers:
    """What the coordinator heard back, as decisions rather than prose."""

    received: queue.Queue = queue.Queue()


class StubCoordinator(Akgent[BaseConfig, BaseState]):
    """Stands in for @Coordinator so a reply has somewhere real to land."""

    def receiveMsg_SlotApprovalDecision(  # noqa: N802
        self, message: SlotApprovalDecision, sender: ActorAddress
    ) -> None:
        Answers.received.put(message)

    def receiveMsg_LunchApprovalDecision(  # noqa: N802
        self, message: LunchApprovalDecision, sender: ActorAddress
    ) -> None:
        Answers.received.put(message)


@pytest.fixture
def channel():
    """A fresh channel per test, restored afterwards - it is module state."""
    previous = get_channel()
    replacement = QueueChannel()
    set_channel(replacement)
    yield replacement
    set_channel(previous)


@pytest.fixture
def human(channel):
    """The real @Human actor, in a real actor system."""
    system = ActorSystem()
    runtime = TeamFactory.build(
        TeamCard(
            name="human-test",
            entry_point=TeamCardMember(
                card=AgentCard(
                    agent_class=ChannelHuman,
                    description="Human",
                    config=BaseConfig(name="@Human", role="Human"),
                ),
                headcount=1,
                members=[],
            ),
            members=[
                TeamCardMember(
                    card=AgentCard(
                        agent_class=StubCoordinator,
                        description="Coordinator",
                        config=BaseConfig(name="@Coordinator", role="Coordinator"),
                    ),
                    headcount=1,
                    members=[],
                )
            ],
            message_types=MESSAGE_TYPES,
            agent_profiles=[],
        ),
        system,
        user_id="test",
    )
    Answers.received = queue.Queue()
    yield runtime
    system.shutdown()


def test_an_approval_request_reaches_the_client(human, channel):
    human.send_from_to(
        "@Human",
        "@Human",
        SlotApprovalRequest(plan_id="p1", title="Jettro and Daniel", day=DAY, candidates=[SLOT]),
    )

    message = channel.take(timeout=5)

    assert isinstance(message, SlotApprovalRequest)
    assert message.plan_id == "p1"
    assert message.candidates == [SLOT]


def test_the_lunch_question_reaches_the_client(human, channel):
    """The second gate is useless if @Human drops it: an unhandled message
    type is logged and silently discarded, so the plan would simply hang."""
    human.send_from_to(
        "@Human",
        "@Human",
        LunchApprovalRequest(plan_id="p1", title="Jettro and Daniel", day=DAY, headcount=2),
    )

    message = channel.take(timeout=5)

    assert isinstance(message, LunchApprovalRequest)
    assert message.plan_id == "p1"


def test_a_result_reaches_the_client(human, channel):
    human.send_from_to("@Human", "@Human", PlanCompleted(plan=a_plan()))

    assert isinstance(channel.take(timeout=5), PlanCompleted)


def test_a_failure_reaches_the_client(human, channel):
    human.send_from_to("@Human", "@Human", PlanFailed(plan=a_plan(), reason="no rooms free"))

    message = channel.take(timeout=5)

    assert isinstance(message, PlanFailed)
    assert message.reason == "no rooms free"


def test_the_actor_never_blocks_on_the_client(human, channel):
    """Delivery must not wait for anyone to be listening.

    Nothing reads the channel here, and the actor still accepts the next
    message. A client that blocks the actor thread is the deadlock §4.2 exists
    to prevent - and it is exactly how the first stdin proxy in the blog had to
    be thrown away.
    """
    for index in range(5):
        human.send_from_to("@Human", "@Human", PlanCompleted(plan=a_plan()))
        assert index >= 0

    assert isinstance(channel.take(timeout=5), PlanCompleted)


def test_the_channel_can_be_swapped_without_touching_the_actor(human, channel):
    """The GUI swap, in miniature: a different client, same running agent."""
    seen: list[str] = []

    class RecordingChannel:
        def deliver(self, message) -> None:
            seen.append(type(message).__name__)

    set_channel(RecordingChannel())
    human.send_from_to("@Human", "@Human", PlanCompleted(plan=a_plan()))

    for _ in range(50):
        if seen:
            break
        threading.Event().wait(0.05)

    assert seen == ["PlanCompleted"]


def test_taking_from_an_empty_channel_times_out(channel):
    """The client waits, but not forever - a wedged run must end by itself."""
    with pytest.raises(queue.Empty):
        channel.take(timeout=0.05)


# -- answering with text, the way a browser has to ------------------------
#
# The terminal builds its own typed decision and never enters this path. The
# server cannot: an HTTP body carries a string. These tests cover the bridge
# that turns the one into the other, inside a real actor.


def ask(human, channel, build):
    """Put a question to the human and hand back the copy it received.

    Two details of the real coordinator are reproduced here because the reply
    path depends on both: the question names its `recipient` (that is how the
    framework finds the proxy to answer), and the copy that comes out of the
    channel carries a `sender` (that is how the answer finds its way back).
    """
    question = build(human.orchestrator_proxy.get_team_member("@Human"))
    human.send_from_to("@Coordinator", "@Human", question)
    return channel.take(timeout=5)


def a_slot_question(recipient):
    return SlotApprovalRequest(
        plan_id="p1", title="Jettro and Daniel", day=DAY, candidates=[SLOT], recipient=recipient
    )


def a_lunch_question(recipient):
    return LunchApprovalRequest(
        plan_id="p1", title="Jettro and Daniel", day=DAY, headcount=2, recipient=recipient
    )


def test_text_answers_the_slot_question_as_a_typed_decision(human, channel):
    question = ask(
        human,
        channel,
        a_slot_question,
    )

    human.process_human_input("1", question)

    decision = Answers.received.get(timeout=5)
    assert isinstance(decision, SlotApprovalDecision)
    assert decision.approved
    assert decision.slot == SLOT


def test_declining_the_slots_in_text_reaches_the_coordinator(human, channel):
    question = ask(
        human,
        channel,
        a_slot_question,
    )

    human.process_human_input("no", question)

    decision = Answers.received.get(timeout=5)
    assert not decision.approved


def test_a_lunch_wish_is_passed_through_untouched(human, channel):
    """Nothing here tries to understand "something warm" - @Catering holds the
    menu, and it is the only one that should be reading the words (D9)."""
    question = ask(
        human,
        channel,
        a_lunch_question,
    )

    human.process_human_input("something warm", question)

    decision = Answers.received.get(timeout=5)
    assert isinstance(decision, LunchApprovalDecision)
    assert decision.wants_lunch
    assert decision.wish == "something warm"


def test_refusing_lunch_in_text_is_still_an_answer(human, channel):
    question = ask(
        human,
        channel,
        a_lunch_question,
    )

    human.process_human_input("no", question)

    assert not Answers.received.get(timeout=5).wants_lunch


def test_an_answer_that_fits_no_slot_is_refused_rather_than_guessed(human, channel):
    """A 4xx is the point: picking a time on somebody's behalf because they
    typed nonsense is worse than making them type it again."""
    question = ask(
        human,
        channel,
        a_slot_question,
    )

    with pytest.raises(UnreadableAnswer):
        human.process_human_input("banana", question)

    with pytest.raises(queue.Empty):
        Answers.received.get(timeout=0.2)
