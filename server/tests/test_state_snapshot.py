"""The coordinator's state must survive the event store, or a team comes back empty.

`design_durability.md` makes the coordinator's state the only record of a
meeting. That only holds if a snapshot written by the server's YAML event store
reads back as the same state - concrete type, `time` values, enums and all. The
store has dropped a `time` before (`design_gui.md` §8.2), so this is tested
through the real `YamlEventStore` rather than assumed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time

from akgentic.team.models import AgentStateSnapshot
from akgentic.team.repositories.yaml import YamlEventStore
from meeting_agents.coordinator import CoordinatorState
from meeting_agents.messages import ProposedSlot
from meeting_agents.plan import Compensation, CompensationStep, MeetingPlan, PlanStatus
from meeting_server.yaml_types import install_yaml_representers

#: 09:30 is the case YAML 1.1 gets wrong without quoting: a leading zero keeps
#: it a string by accident, where 10:00 would turn into a sexagesimal integer.
SLOTS = [
    ProposedSlot(start=time(9, 30), end=time(10, 30)),
    ProposedSlot(start=time(10, 0), end=time(11, 0)),
]


def a_meeting_part_way_through() -> CoordinatorState:
    plan = MeetingPlan(
        title="Design review",
        participant_emails=["sanne@rag4p.org", "daan@rag4p.org"],
        day=date(2034, 6, 20),
        location_id="yuma",
        proposed_start=time(10, 0),
        proposed_end=time(11, 0),
        approved=True,
        meeting_id=7,
    )
    return CoordinatorState(
        plan=plan,
        candidates=SLOTS,
        awaiting_lunch=True,
        cancelling=[Compensation(step=CompensationStep.CANCEL_MEETING, reference="7")],
    )


def round_trip(state: CoordinatorState, tmp_path) -> object:
    install_yaml_representers()
    team_id = uuid.uuid4()
    store = YamlEventStore(tmp_path)
    store.save_agent_state(
        AgentStateSnapshot(
            team_id=team_id,
            agent_id=str(uuid.uuid4()),
            name="@Coordinator",
            state=state.serializable_copy(),
            updated_at=datetime.now(UTC),
        )
    )
    [snapshot] = store.load_agent_states(team_id)
    return snapshot.state


def test_the_state_comes_back_as_itself(tmp_path):
    state = a_meeting_part_way_through()

    restored = round_trip(state, tmp_path)

    assert type(restored) is CoordinatorState
    assert restored == state


def test_slot_times_come_back_as_times(tmp_path):
    restored = round_trip(a_meeting_part_way_through(), tmp_path)

    assert [slot.start for slot in restored.candidates] == [time(9, 30), time(10, 0)]


def test_the_status_is_derived_again_rather_than_read(tmp_path):
    """`status` is written out for readers and ignored on the way back in."""
    restored = round_trip(a_meeting_part_way_through(), tmp_path)

    assert restored.plan.status is PlanStatus.SCHEDULED


def test_an_empty_coordinator_survives_too(tmp_path):
    """A team that has not been asked for anything yet still has a state."""
    restored = round_trip(CoordinatorState(), tmp_path)

    assert restored == CoordinatorState()
