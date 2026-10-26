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
from akgentic.core import ActorSystem, AgentCard, BaseConfig
from akgentic.team import TeamCard, TeamCardMember, TeamFactory
from meeting_agents.human import ChannelHuman, QueueChannel, get_channel, set_channel
from meeting_agents.messages import (
    MESSAGE_TYPES,
    LunchApprovalRequest,
    PlanCompleted,
    PlanFailed,
    PlanMeetingRequest,
    ProposedSlot,
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
            members=[],
            message_types=MESSAGE_TYPES,
            agent_profiles=[],
        ),
        system,
        user_id="test",
    )
    yield runtime
    system.shutdown()


def test_an_approval_request_reaches_the_client(human, channel):
    human.send_from_to(
        "@Human",
        "@Human",
        SlotApprovalRequest(
            plan_id="p1", title="Jettro and Daniel", day=DAY, candidates=[SLOT]
        ),
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
    human.send_from_to(
        "@Human", "@Human", PlanFailed(plan=a_plan(), reason="no rooms free")
    )

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
