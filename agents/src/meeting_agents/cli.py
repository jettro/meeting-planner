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

from meeting_agents.bootstrap import load_team_card
from meeting_agents.human import QueueChannel, set_channel
from meeting_agents.messages import (
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
    parser.add_argument(
        "--day", required=True, type=date.fromisoformat, help="The day, as YYYY-MM-DD."
    )
    parser.add_argument("--minutes", type=int, default=60, help="Length in minutes.")
    parser.add_argument("--at", dest="location_id", required=True, help="Location id.")
    parser.add_argument(
        "--no-lunch", dest="with_lunch", action="store_false", help="Skip the lunch order."
    )
    parser.add_argument("--verbose", action="store_true", help="Show framework logging.")
    return parser.parse_args(argv)


def ask_for_approval(request: SlotApprovalRequest) -> SlotApprovalDecision:
    """The one question the team asks (D4). Nothing is booked yet."""
    print(f"\n{request.question()}")
    for index, slot in enumerate(request.candidates, start=1):
        print(f"  {index}) {slot.start:%H:%M} - {slot.end:%H:%M}")
    print("  n) none of these")

    while True:
        answer = input("Choose a slot: ").strip().lower()
        if answer in {"n", "no", "none", ""}:
            return SlotApprovalDecision(plan_id=request.plan_id, approved=False)
        if answer.isdigit() and 1 <= int(answer) <= len(request.candidates):
            chosen = request.candidates[int(answer) - 1]
            return SlotApprovalDecision(plan_id=request.plan_id, approved=True, slot=chosen)
        print(f"Please answer 1-{len(request.candidates)}, or n.")


def report_completed(message: PlanCompleted) -> None:
    plan = message.plan
    print(f"\nBooked '{plan.title}' on {plan.day}.")
    if plan.proposed_start and plan.proposed_end:
        print(f"  time    {plan.proposed_start:%H:%M} - {plan.proposed_end:%H:%M}")
    print(f"  room    {plan.room_code} at {plan.location_id} (booking {plan.booking_id})")
    print(f"  meeting {plan.meeting_id}")
    if plan.order_id:
        print(f"  lunch   ordered ({plan.order_id})")


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
                with_lunch=args.with_lunch,
            ),
        )
        return converse(runtime, channel)
    finally:
        system.shutdown()


if __name__ == "__main__":
    sys.exit(main())
