"""The CLI runner.

Two things are worth testing here and nothing else is. First, that the client
really is thin: it renders, it asks, it sends - no decisions about meetings.
Second, the approval loop, because a human answering "3" or "n" or "banana" is
the one place a person touches this system.

The last test drives `converse` over the real coordinator and repository with
stub specialists, so the client is exercised against the actual saga rather
than against a mock of it.
"""

from __future__ import annotations

from datetime import date, time

import pytest
from akgentic.core import ActorSystem, AgentCard, Akgent, BaseConfig, BaseState
from akgentic.team import TeamCard, TeamCardMember, TeamFactory
from meeting_agents.cli import (
    REPLY_TIMEOUT_SECONDS,
    ask_for_approval,
    converse,
    main,
    parse_args,
    report_completed,
    report_failed,
)
from meeting_agents.coordinator import Coordinator, CoordinatorConfig
from meeting_agents.human import ChannelHuman, QueueChannel, get_channel, set_channel
from meeting_agents.messages import (
    MESSAGE_TYPES,
    Compensation,
    FacilitiesBooked,
    MeetingBooked,
    PlanCompleted,
    PlanFailed,
    PlanMeetingRequest,
    ProposedSlot,
    SlotApprovalDecision,
    SlotApprovalRequest,
    SlotsFound,
)
from meeting_agents.plan_repository import PlanRepository, PlanRepositoryConfig

DAY = date(2031, 9, 15)
MORNING = ProposedSlot(start=time(9, 0), end=time(10, 0))
LATER = ProposedSlot(start=time(14, 0), end=time(15, 0))


def a_request() -> SlotApprovalRequest:
    return SlotApprovalRequest(
        plan_id="p1", title="Jettro and Daniel", day=DAY, candidates=[MORNING, LATER]
    )


def a_plan(**overrides):
    plan = PlanMeetingRequest(
        title="Jettro and Daniel",
        participant_emails=["jettro@example.com", "daniel@example.com"],
        day=DAY,
        duration_minutes=60,
        location_id="luminis",
    ).to_plan()
    return plan.model_copy(update=overrides)


# -- arguments --------------------------------------------------------------


def test_a_meeting_is_described_entirely_on_the_command_line():
    args = parse_args(
        [
            "--title",
            "Jettro and Daniel",
            "--with",
            "jettro@rag4j.org",
            "daniel@rag4j.org",
            "--day",
            "2034-06-14",
            "--at",
            "luminis",
            "--minutes",
            "45",
        ]
    )

    assert args.title == "Jettro and Daniel"
    assert args.participants == ["jettro@rag4j.org", "daniel@rag4j.org"]
    assert args.day == date(2034, 6, 14)
    assert args.minutes == 45
    assert args.location_id == "luminis"
    assert args.with_lunch is True


def test_lunch_is_on_unless_it_is_turned_off():
    base = ["--title", "T", "--with", "a@b.c", "--day", "2034-06-14", "--at", "luminis"]

    assert parse_args(base).with_lunch is True
    assert parse_args([*base, "--no-lunch"]).with_lunch is False


def test_a_missing_day_is_refused_rather_than_guessed():
    with pytest.raises(SystemExit):
        parse_args(["--title", "T", "--with", "a@b.c", "--at", "luminis"])


# -- the approval gate ------------------------------------------------------


def test_choosing_a_slot_approves_exactly_that_slot(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "2")

    decision = ask_for_approval(a_request())

    assert decision.approved is True
    assert decision.slot == LATER
    assert decision.plan_id == "p1"


def test_declining_carries_no_slot(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "n")

    decision = ask_for_approval(a_request())

    assert decision.approved is False
    assert decision.slot is None


def test_an_empty_answer_is_treated_as_declining(monkeypatch):
    """Nothing is booked at this point, so the safe reading of silence is no."""
    monkeypatch.setattr("builtins.input", lambda _: "")

    assert ask_for_approval(a_request()).approved is False


def test_a_nonsense_answer_is_asked_again_rather_than_guessed(monkeypatch, capsys):
    answers = iter(["banana", "7", "0", "1"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    decision = ask_for_approval(a_request())

    assert decision.slot == MORNING
    assert "Please answer 1-2" in capsys.readouterr().out


def test_the_candidates_are_shown_before_the_question(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "1")

    ask_for_approval(a_request())

    shown = capsys.readouterr().out
    assert "09:00 - 10:00" in shown
    assert "14:00 - 15:00" in shown


# -- rendering --------------------------------------------------------------


def test_a_booked_meeting_shows_every_id_the_user_needs(capsys):
    report_completed(
        PlanCompleted(
            plan=a_plan(
                proposed_start=time(10, 0),
                proposed_end=time(11, 0),
                approved=True,
                meeting_id=2,
                room_code="room-a",
                booking_id=7,
                order_id="order-abc",
            )
        )
    )

    shown = capsys.readouterr().out
    assert "10:00 - 11:00" in shown
    assert "room-a" in shown
    assert "7" in shown
    assert "2" in shown
    assert "order-abc" in shown


def test_a_failure_says_what_is_still_booked(capsys):
    report_failed(
        PlanFailed(
            plan=a_plan(meeting_id=2),
            reason="no rooms free",
            outstanding=[Compensation(step="cancel_meeting", reference="2")],
        )
    )

    shown = capsys.readouterr().err
    assert "no rooms free" in shown
    assert "cancel_meeting 2" in shown


# -- the loop ---------------------------------------------------------------


class FakeRuntime:
    """Records what the client sends back, so the loop can be driven alone."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, object]] = []

    def send_from_to(self, sender: str, recipient: str, message: object) -> None:
        self.sent.append((sender, recipient, message))


def test_the_loop_answers_the_question_then_reports_the_result(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "1")
    runtime = FakeRuntime()
    channel = QueueChannel()
    channel.deliver(a_request())
    channel.deliver(PlanCompleted(plan=a_plan(meeting_id=2, booking_id=7)))

    assert converse(runtime, channel) == 0

    sender, recipient, decision = runtime.sent[0]
    assert (sender, recipient) == ("@Human", "@Coordinator")
    assert isinstance(decision, SlotApprovalDecision)
    assert decision.slot == MORNING


def test_a_failed_plan_is_a_failed_command(monkeypatch):
    channel = QueueChannel()
    channel.deliver(PlanFailed(plan=a_plan(), reason="nobody is free"))

    assert converse(FakeRuntime(), channel) == 1


def test_silence_ends_the_command_rather_than_hanging(monkeypatch, capsys):
    """A terminal must come back, even when the team never answers."""
    monkeypatch.setattr("meeting_agents.cli.REPLY_TIMEOUT_SECONDS", 0.05)

    assert converse(FakeRuntime(), QueueChannel()) == 1
    assert "giving up" in capsys.readouterr().err


def test_the_client_decides_nothing_about_meetings():
    """§4.2 rule 1, enforced rather than reviewed.

    Anything the client knows about rooms, lunch or booking is logic that a GUI
    would have to reimplement. The one thing it may do is relay a decision.
    """
    import inspect

    import meeting_agents.cli as cli

    source = inspect.getsource(cli)

    for forbidden in ("book_room", "catering", "order_lunch", "MCPTool", "compensations("):
        assert forbidden not in source


# -- the client against the real saga ---------------------------------------


class StubScheduler(Akgent[BaseConfig, BaseState]):
    def receiveMsg_FindSlotsAssignment(self, message, sender) -> None:  # noqa: N802
        self.send(sender, SlotsFound(plan_id=message.plan_id, candidates=[MORNING, LATER]))

    def receiveMsg_BookMeetingAssignment(self, message, sender) -> None:  # noqa: N802
        self.send(sender, MeetingBooked(plan_id=message.plan_id, meeting_id=2))


class StubFacilityManager(Akgent[BaseConfig, BaseState]):
    def receiveMsg_BookFacilitiesAssignment(self, message, sender) -> None:  # noqa: N802
        self.send(
            sender,
            FacilitiesBooked(
                plan_id=message.plan_id,
                room_code="room-a",
                booking_id=7,
                order_id="order-abc" if message.with_lunch else None,
            ),
        )


def member(agent_class, config, children=None) -> TeamCardMember:
    return TeamCardMember(
        card=AgentCard(agent_class=agent_class, description=config.role, config=config),
        headcount=1,
        members=children or [],
    )


@pytest.fixture
def live_team(tmp_path):
    """The real @Coordinator and @PlanRepository behind the real @Human."""
    previous = get_channel()
    channel = QueueChannel()
    set_channel(channel)

    system = ActorSystem()
    card = TeamCard(
        name="cli-test",
        entry_point=member(
            ChannelHuman,
            BaseConfig(name="@Human", role="Human"),
            [
                member(
                    Coordinator,
                    CoordinatorConfig(),
                    [
                        member(
                            PlanRepository,
                            PlanRepositoryConfig(
                                store_class="meeting_agents.store.JsonPlanStore",
                                store_path=str(tmp_path / "plans.json"),
                            ),
                        ),
                        member(
                            StubScheduler, BaseConfig(name="@Scheduler", role="Scheduler")
                        ),
                        member(
                            StubFacilityManager,
                            BaseConfig(name="@FacilityManager", role="FacilityManager"),
                        ),
                    ],
                )
            ],
        ),
        members=[],
        message_types=MESSAGE_TYPES,
        agent_profiles=[],
    )
    runtime = TeamFactory.build(card, system, user_id="test")
    yield runtime, channel
    system.shutdown()
    set_channel(previous)


def test_the_client_plans_a_whole_meeting_through_the_real_saga(live_team, monkeypatch, capsys):
    """Terminal in, booked meeting out - with the actual coordinator in between."""
    runtime, channel = live_team
    monkeypatch.setattr("builtins.input", lambda _: "1")

    runtime.send_from_to(
        "@Human",
        "@Coordinator",
        PlanMeetingRequest(
            title="Jettro and Daniel",
            participant_emails=["jettro@example.com", "daniel@example.com"],
            day=DAY,
            duration_minutes=60,
            location_id="luminis",
        ),
    )

    assert converse(runtime, channel) == 0

    shown = capsys.readouterr().out
    assert "09:00 - 10:00" in shown
    assert "room-a" in shown
    assert "order-abc" in shown


def test_declining_at_the_terminal_leaves_nothing_booked(live_team, monkeypatch):
    runtime, channel = live_team
    monkeypatch.setattr("builtins.input", lambda _: "n")

    runtime.send_from_to(
        "@Human",
        "@Coordinator",
        PlanMeetingRequest(
            title="Jettro and Daniel",
            participant_emails=["jettro@example.com"],
            day=DAY,
            duration_minutes=60,
            location_id="luminis",
        ),
    )

    assert converse(runtime, channel) == 1


def test_missing_api_key_says_so_instead_of_failing_at_the_provider(monkeypatch, capsys):
    """Easy to hit in a container with no .env. Failing here, by name, beats
    failing later inside a provider call with a less obvious message."""
    for name in ("OPENAI_API_KEY", "CATALOG_PATH"):
        monkeypatch.delenv(name, raising=False)

    exit_code = main(
        [
            "--title",
            "Jettro and Daniel",
            "--with",
            "jettro@example.com",
            "--day",
            DAY.isoformat(),
            "--at",
            "luminis",
        ]
    )

    assert exit_code == 2
    assert "OPENAI_API_KEY" in capsys.readouterr().err


def test_a_timeout_is_explained_rather_than_just_named(capsys):
    """A provider timeout is the one failure a user can simply retry, and the
    exception name alone does not say that nothing was booked."""
    report_failed(PlanFailed(plan=a_plan(), reason="ModelTimeoutError: Request timed out."))

    shown = capsys.readouterr().err
    assert "did not answer in time" in shown
    assert "Nothing was booked" in shown


def test_the_reply_timeout_outlasts_three_slow_specialists():
    """Between approval and a booked meeting the scheduler, facility manager and
    catering each run once, and each may spend its full HTTP timeout. A reply
    budget below that sum reports a failure for a plan that is merely slow."""
    slowest_agent_call = 240.0
    assert REPLY_TIMEOUT_SECONDS > 3 * slowest_agent_call
