"""The CLI runner: a thin client over the team (§4.2 rule 1).

It builds the team, sends one request, renders what comes back, asks the one
question the team asks, and exits. There is no orchestration here, no booking
rule and no saga: all of that lives in `@Coordinator`, where a future GUI can
reuse it untouched. If something in this file starts looking like a decision
about meetings, it is in the wrong place.

The approval gate is a blocking prompt *on this thread only*. The coordinator
has long since returned; it is waiting for a message, not for a human.
"""

from __future__ import annotations

import argparse
import logging
import queue
import sys
from datetime import date

from akgentic.core import ActorSystem
from akgentic.team import TeamFactory, TeamRuntime

from meeting_agents.answers import (
    UnreadableAnswer,
    interpret_lunch_answer,
    interpret_slot_answer,
)
from meeting_agents.bootstrap import load_team_card
from meeting_agents.human import QueueChannel, set_channel
from meeting_agents.messages import (
    LunchApprovalDecision,
    LunchApprovalRequest,
    PlanCompleted,
    PlanFailed,
    PlanMeetingRequest,
    SlotApprovalDecision,
    SlotApprovalRequest,
)
from meeting_agents.settings import Settings

#: The safety net for a wedged run, not a performance target. A specialist may
#: spend up to its 240s HTTP timeout on one call, and three run back to back
#: between approval and a booked meeting, so anything near that sum turns a slow
#: provider into a spurious failure. Fifteen minutes is far past any healthy run.
REPLY_TIMEOUT_SECONDS = 900.0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="plan-meeting",
        description="Ask the agent team to plan a meeting.",
    )
    parser.add_argument("--title", required=True, help="What the meeting is called.")
    parser.add_argument(
        "--with",
        dest="participants",
        required=True,
        nargs="+",
        metavar="EMAIL",
        help="Email address of every participant.",
    )
    parser.add_argument("--day", required=True, type=date.fromisoformat, help="The day, as YYYY-MM-DD.")
    parser.add_argument("--minutes", type=int, default=60, help="Length in minutes.")
    # Where: an id, or a description the facility manager turns into one. The
    # parser enforces the same "exactly one" the request does, so a mistake is
    # reported before a team is built.
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--at", dest="location_id", default="", help="Location id.")
    where.add_argument(
        "--place",
        dest="location_wish",
        default="",
        metavar="DESCRIPTION",
        help='What kind of place, in your own words - "somewhere in nature". The team chooses.',
    )
    parser.add_argument("--no-lunch", dest="with_lunch", action="store_false", help="Skip the lunch order.")
    parser.add_argument(
        "--lunch",
        dest="lunch_wish",
        metavar="WISH",
        help=(
            "What kind of lunch, in your own words. Given here, the team does not "
            "stop to ask - which is what a scripted run needs."
        ),
    )
    parser.add_argument("--verbose", action="store_true", help="Show framework logging.")
    return parser.parse_args(argv)


def ask_for_approval(request: SlotApprovalRequest) -> SlotApprovalDecision:
    """The one question the team asks (D4). Nothing is booked yet.

    The terminal collects the answer; `answers.py` decides what it means, so
    the browser cannot drift to a different reading of the same words.
    """
    print(f"\n{request.question()}")
    for index, slot in enumerate(request.candidates, start=1):
        print(f"  {index}) {slot.start:%H:%M} - {slot.end:%H:%M}")
    print("  n) none of these")

    while True:
        try:
            return interpret_slot_answer(request, input("Choose a slot: "))
        except UnreadableAnswer as unreadable:
            print(unreadable)


def lunch_wish_from(args: argparse.Namespace) -> str | None:
    """Decide whether this run has to stop and ask about lunch.

    ``None`` is the only answer that opens the gate. Both ``--no-lunch`` and
    ``--lunch "..."`` settle the question up front, so a scripted run never
    blocks on a prompt nobody is there to answer.
    """
    if not args.with_lunch:
        return ""
    wish: str | None = args.lunch_wish
    return wish


def ask_for_lunch(request: LunchApprovalRequest) -> LunchApprovalDecision:
    """The second question (D9). Free text, because a menu is not shown.

    This client interprets only the two answers that are *not* descriptions -
    a refusal and a shrug. Everything else is passed through untouched for
    @Catering to make sense of, because reading "something vegetarian" is the
    job of the agent with the menu, not of a terminal.
    """
    print(f"\n{request.question()}")
    return interpret_lunch_answer(request, input("Lunch (or 'no'): "))


def report_completed(message: PlanCompleted) -> None:
    plan = message.plan
    print(f"\nBooked '{plan.title}' on {plan.day}.")
    if plan.proposed_start and plan.proposed_end:
        print(f"  time    {plan.proposed_start:%H:%M} - {plan.proposed_end:%H:%M}")
    print(f"  room    {plan.room_code} at {plan.location_id} (booking {plan.booking_id})")
    print(f"  meeting {plan.meeting_id}")
    if plan.order_id:
        detail = plan.lunch_summary or "ordered"
        print(f"  lunch   {detail}")
        print(f"          order {plan.order_id}")


def report_failed(message: PlanFailed) -> None:
    print(f"\nThe meeting was not booked: {message.reason}", file=sys.stderr)
    if "Timeout" in message.reason:
        print(
            "The model did not answer in time. Nothing was booked - run it again.",
            file=sys.stderr,
        )
    if message.outstanding:
        print("Still booked, and not yet undone:", file=sys.stderr)
        for step in message.outstanding:
            print(f"  {step.step.value} {step.reference}", file=sys.stderr)


def converse(runtime: TeamRuntime, channel: QueueChannel) -> int:
    """Render what the team says until the plan ends, one way or the other."""
    while True:
        try:
            message = channel.take(timeout=REPLY_TIMEOUT_SECONDS)
        except queue.Empty:
            print(
                f"\nNo answer within {REPLY_TIMEOUT_SECONDS:.0f}s - giving up.",
                file=sys.stderr,
            )
            return 1

        if isinstance(message, SlotApprovalRequest):
            runtime.send_from_to("@Human", "@Coordinator", ask_for_approval(message))
        elif isinstance(message, LunchApprovalRequest):
            runtime.send_from_to("@Human", "@Coordinator", ask_for_lunch(message))
        elif isinstance(message, PlanCompleted):
            report_completed(message)
            return 0
        elif isinstance(message, PlanFailed):
            report_failed(message)
            return 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s %(message)s",
    )

    settings = Settings.from_env()
    if not settings.openai_api_key:
        print(
            "No OPENAI_API_KEY set. The team cannot think without one: put it in .env "
            "and start this through `make plan-meeting` or `make plan-meeting-docker`.",
            file=sys.stderr,
        )
        return 2
    card = load_team_card(settings)

    channel = QueueChannel()
    set_channel(channel)

    system = ActorSystem()
    try:
        runtime = TeamFactory.build(card, system, user_id="cli")
        runtime.send_from_to(
            "@Human",
            "@Coordinator",
            PlanMeetingRequest(
                title=args.title,
                participant_emails=args.participants,
                day=args.day,
                duration_minutes=args.minutes,
                location_id=args.location_id,
                location_wish=args.location_wish,
                with_lunch=args.with_lunch,
                lunch_wish=lunch_wish_from(args),
            ),
        )
        return converse(runtime, channel)
    finally:
        system.shutdown()


if __name__ == "__main__":
    sys.exit(main())
