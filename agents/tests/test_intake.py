"""@Intake in a real actor system, with only the model replaced.

The real coordinator sits behind it, configured to treat @Intake as its human
(`human_name: "@Intake"`), and the real `ChannelHuman` sits in front - so the
relay is exercised the way the server drives it, including the call that routes
a gate's answer by the question's recipient. The specialists are stubs: nothing
here is about their judgement.

What is worth proving is the shape of design_chat.md: one typed request, a
relay in code, no way for the model to approve anything, and a model that is
told what happened at every step.
"""

from __future__ import annotations

import asyncio
from datetime import date, time
from types import SimpleNamespace

import pytest
from akgentic.agent.config import AgentConfig
from akgentic.agent.output_models import Request, StructuredOutput
from akgentic.core import ActorAddress, ActorSystem, AgentCard, Akgent, BaseConfig, BaseState
from akgentic.team import TeamCard, TeamCardMember, TeamFactory
from meeting_agents.coordinator import Coordinator, CoordinatorConfig
from meeting_agents.human import ChannelHuman, QueueChannel, get_channel, set_channel
from meeting_agents.intake import OFFER_NOW, IntakeAgent, IntakeConfig, IntakeTools, TalkOnlyToHuman
from meeting_agents.messages import (
    MESSAGE_TYPES,
    BookFacilitiesAssignment,
    BookMeetingAssignment,
    CancelAssignment,
    Cancelled,
    FacilitiesBooked,
    FindLocationAssignment,
    FindPeopleAssignment,
    FindSlotsAssignment,
    LocationFound,
    MeetingBooked,
    NameMatch,
    PeopleFound,
    Person,
    PlanCancelled,
    PlanCompleted,
    PlanMeetingRequest,
    ProposedSlot,
    SlotApprovalRequest,
    SlotsFound,
)
from pydantic_ai import ModelRetry

DAY = date(2034, 7, 11)
SLOT = ProposedSlot(start=time(9, 0), end=time(10, 0))
SANNE = Person(name="Sanne Visser", email="sanne@rag4p.org")
DAAN = Person(name="Daan de Vries", email="daan@rag4p.org")
OTHER_DAAN = Person(name="Daan Jansen", email="daan.jansen@rag4p.org")
ADDRESS_BOOK = {"Sanne": [SANNE], "Daan": [DAAN, OTHER_DAAN], "Daan de Vries": [DAAN]}


class Model:
    """What @Intake's model was told. It never answers, so it never speaks."""

    updates: list[str] = []

    @classmethod
    def reset(cls) -> None:
        cls.updates = []


class ScriptedIntake(IntakeAgent):
    def act(self, message, output_type):
        Model.updates.append(message.rendering())
        return output_type()


class StubScheduler(Akgent[BaseConfig, BaseState]):
    def receiveMsg_FindPeopleAssignment(  # noqa: N802
        self, message: FindPeopleAssignment, sender: ActorAddress
    ) -> None:
        matches = [NameMatch(asked=name, candidates=ADDRESS_BOOK.get(name, [])) for name in message.names]
        self.send(sender, PeopleFound(matches=matches))

    def receiveMsg_FindSlotsAssignment(  # noqa: N802
        self, message: FindSlotsAssignment, sender: ActorAddress
    ) -> None:
        self.send(sender, SlotsFound(plan_id=message.plan_id, candidates=[SLOT]))

    def receiveMsg_BookMeetingAssignment(  # noqa: N802
        self, message: BookMeetingAssignment, sender: ActorAddress
    ) -> None:
        self.send(sender, MeetingBooked(plan_id=message.plan_id, meeting_id=42))

    def receiveMsg_CancelAssignment(  # noqa: N802
        self, message: CancelAssignment, sender: ActorAddress
    ) -> None:
        self.send(sender, Cancelled(plan_id=message.plan_id, step=message.step, succeeded=True))


class StubFacilityManager(Akgent[BaseConfig, BaseState]):
    def receiveMsg_FindLocationAssignment(  # noqa: N802
        self, message: FindLocationAssignment, sender: ActorAddress
    ) -> None:
        self.send(
            sender,
            LocationFound(
                plan_id=message.plan_id,
                location_id="meet-nature",
                name="Meeting in Nature",
                reason="outdoors",
            ),
        )

    def receiveMsg_BookFacilitiesAssignment(  # noqa: N802
        self, message: BookFacilitiesAssignment, sender: ActorAddress
    ) -> None:
        self.send(sender, FacilitiesBooked(plan_id=message.plan_id, room_code="forest", booking_id=7))

    def receiveMsg_CancelAssignment(  # noqa: N802
        self, message: CancelAssignment, sender: ActorAddress
    ) -> None:
        self.send(sender, Cancelled(plan_id=message.plan_id, step=message.step, succeeded=True))


def member(agent_class, config, children=None) -> TeamCardMember:
    return TeamCardMember(
        card=AgentCard(agent_class=agent_class, description=config.role, config=config),
        headcount=1,
        members=children or [],
    )


def build_card() -> TeamCard:
    return TeamCard(
        name="intake-test",
        entry_point=member(
            ChannelHuman,
            BaseConfig(name="@Human", role="Human"),
            [
                member(
                    ScriptedIntake,
                    IntakeConfig(name="@Intake", role="Intake", tools=[IntakeTools()]),
                    [
                        member(
                            Coordinator,
                            CoordinatorConfig(human_name="@Intake"),
                            [
                                member(StubScheduler, BaseConfig(name="@Scheduler", role="Scheduler")),
                                member(
                                    StubFacilityManager,
                                    BaseConfig(name="@FacilityManager", role="FacilityManager"),
                                ),
                            ],
                        )
                    ],
                )
            ],
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


@pytest.fixture
def team(channel):
    Model.reset()
    system = ActorSystem()
    runtime = TeamFactory.build(build_card(), system, user_id="test")
    yield runtime
    system.shutdown()


def intake(runtime) -> IntakeAgent:
    """The live agent, called on its own thread - which is where its tools run."""
    return runtime.actor_system.proxy_ask(runtime.addrs["@Intake"], IntakeAgent)


def expect(channel: QueueChannel, kind: type, timeout: float = 5.0):
    message = channel.take(timeout=timeout)
    assert isinstance(message, kind), f"expected {kind.__name__}, got {message!r}"
    return message


def wait_for_update(fragment: str, timeout: float = 5.0) -> str:
    import time as clock

    deadline = clock.monotonic() + timeout
    while clock.monotonic() < deadline:
        for update in Model.updates:
            if fragment in update:
                return update
        clock.sleep(0.02)
    raise AssertionError(f"the model was never told {fragment!r}; it was told {Model.updates!r}")


def request(**overrides) -> PlanMeetingRequest:
    fields = {
        "title": "Offsite",
        "participant_emails": ["sanne@rag4p.org", "daan@rag4p.org"],
        "day": DAY,
        "location_wish": "somewhere in nature",
        "with_lunch": False,
    }
    return PlanMeetingRequest(**{**fields, **overrides})


def settle_both(runtime) -> None:
    intake(runtime).look_up(["Sanne", "Daan de Vries"])
    wait_for_update("Daan de Vries <daan@rag4p.org>")


def book(runtime, channel) -> SlotApprovalRequest:
    settle_both(runtime)
    assert intake(runtime).request_meeting(request()).startswith("Requested")
    question = expect(channel, SlotApprovalRequest)
    runtime.process_human_input("1", question)
    expect(channel, PlanCompleted)
    return question


# -- the people lookup --------------------------------------------------------


def test_a_lookup_with_one_match_settles_the_email(team):
    intake(team).look_up(["Sanne"])

    update = wait_for_update("Sanne Visser")
    assert '"Sanne" is Sanne Visser <sanne@rag4p.org>.' in update
    assert intake(team).state.settled_emails == ["sanne@rag4p.org"]


def test_an_ambiguous_name_becomes_a_question_not_a_guess(team):
    intake(team).look_up(["Daan"])

    update = wait_for_update("could be")
    assert "Ask the person which one" in update
    assert intake(team).state.settled_emails == []


def test_an_unknown_name_is_said_plainly(team):
    intake(team).look_up(["Bram"])

    assert "Ask the person who they mean" in wait_for_update("Nobody called")


def test_an_email_no_lookup_settled_is_refused(team):
    """A guessed address is a meeting in a stranger's agenda."""
    answer = intake(team).request_meeting(request())

    assert answer.startswith("Refused")
    assert "look_up_people" in answer
    assert intake(team).state.requested is False


# -- one request, then the relay ---------------------------------------------


def test_the_gate_reaches_the_human_as_a_fresh_question(team, channel):
    """Addressed to @Human, sent by @Intake: the only copy /human-input can route."""
    settle_both(team)
    intake(team).request_meeting(request())

    question = expect(channel, SlotApprovalRequest)

    assert question.recipient.name == "@Human"
    assert question.sender.name == "@Intake"
    assert question.location_name == "Meeting in Nature"


def test_the_coordinators_own_copy_could_not_have_been_answered(team, channel):
    """Why the relay sends a fresh copy (I5): the server routes an answer by the
    question's recipient, and refuses one that is not a UserProxy."""
    settle_both(team)
    intake(team).request_meeting(request())
    question = expect(channel, SlotApprovalRequest)

    as_the_coordinator_sent_it = question.model_copy(update={"recipient": team.addrs["@Intake"]})
    with pytest.raises(ValueError):
        team.process_human_input("1", as_the_coordinator_sent_it)


def test_the_answer_on_the_card_books_the_meeting(team, channel):
    """Answered the way the server answers it, read by answers.py, forwarded by @Intake."""
    book(team, channel)

    assert "the meeting is booked" in wait_for_update("booked")
    assert "Meeting in Nature" in wait_for_update("booked")


def test_the_booked_update_and_only_that_one_invites_one_offer(team, channel):
    """design_memory.md M45: code says when to offer something worth remembering."""
    book(team, channel)
    assert intake(team).cancel().startswith("Asked the team to cancel")
    expect(channel, PlanCancelled)

    assert OFFER_NOW in wait_for_update("the meeting is booked")
    assert "nothing new to suggest remembering" in OFFER_NOW
    assert OFFER_NOW not in wait_for_update("cancelled")
    assert OFFER_NOW not in wait_for_update("choose a time")


def test_the_model_is_told_what_is_on_the_screen(team, channel):
    settle_both(team)
    intake(team).request_meeting(request())
    expect(channel, SlotApprovalRequest)

    update = wait_for_update("choose a time")
    assert "09:00-10:00" in update
    assert "not in this conversation" in update


def test_one_conversation_requests_one_meeting(team, channel):
    book(team, channel)

    assert intake(team).request_meeting(request()).startswith("Refused")


def test_cancelling_releases_the_meeting_and_says_so(team, channel):
    book(team, channel)

    assert intake(team).cancel().startswith("Asked the team to cancel")
    expect(channel, PlanCancelled)
    assert "cancelled" in wait_for_update("cancelled")
    assert intake(team).cancel() == "Refused: the meeting is already cancelled."


def test_nothing_requested_is_nothing_to_cancel(team):
    assert intake(team).cancel().startswith("Refused: nothing has been requested")


def test_the_state_survives_as_an_intake_state_with_its_backstory(team):
    """The step-5 lesson was about a fresh state; this one carries the prompt across."""
    state = intake(team).state

    assert type(state).__name__ == "IntakeState"
    assert state.backstory == AgentConfig(name="x", role="x").prompt.render()


# -- the guard ---------------------------------------------------------------


def run_context(retry: int = 0, max_retries: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        partial_output=False,
        retry=retry,
        max_retries=max_retries,
        usage_limits=None,
        usage=SimpleNamespace(requests=0),
    )


def output(*recipients: str) -> StructuredOutput:
    return StructuredOutput(
        messages=[Request(message_type="notification", message="hi", recipient=r) for r in recipients]
    )


def check(ctx, out):
    return asyncio.run(TalkOnlyToHuman().after_output_validate(ctx, output_context=None, output=out))


def test_writing_to_the_human_passes():
    out = output("@Human")
    assert check(run_context(), out) is out


def test_writing_to_anyone_else_is_sent_back():
    with pytest.raises(ModelRetry, match="@Scheduler"):
        check(run_context(), output("@Human", "@Scheduler"))


def test_when_no_retry_is_left_the_strays_are_dropped_not_delivered():
    kept = check(run_context(retry=1, max_retries=1), output("@Human", "@Catering"))
    assert [request.recipient for request in kept.messages] == ["@Human"]


# -- who is asking (design_auth.md A17) ------------------------------------------

JETTRO = "jettro@rag4p.org"


@pytest.fixture
def jettros(channel):
    """A conversation for someone logged in."""
    Model.reset()
    system = ActorSystem()
    runtime = TeamFactory.build(build_card(), system, user_id=JETTRO)
    yield runtime
    system.shutdown()


def context_of(runtime) -> str:
    tools = next(card for card in intake(runtime).config.tools if isinstance(card, IntakeTools))
    states = [provider() for provider in tools.get_context_states()]
    return "".join(state.render_full() for state in states if state is not None)


def test_the_model_is_told_who_it_arranges_for(jettros):
    context = context_of(jettros)

    assert f"arranging this meeting for {JETTRO}" in context
    assert "do not look them up" in context


def test_without_a_login_nobody_is_named(team):
    """`user_id="test"` is a login too; only anonymous has no organiser."""
    system = ActorSystem()
    try:
        anonymous = TeamFactory.build(build_card(), system, user_id="anonymous")
        assert context_of(anonymous) == ""
    finally:
        system.shutdown()


def test_the_organiser_needs_no_lookup(jettros):
    intake(jettros).look_up(["Sanne"])
    wait_for_update("Sanne Visser")

    answer = intake(jettros).request_meeting(request(participant_emails=["sanne@rag4p.org", JETTRO]))

    assert answer.startswith("Requested")
