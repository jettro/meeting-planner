"""One scalar the community event store cannot write by itself.

The community tier persists every event with `yaml.safe_dump`, deliberately:
the safe dumper and the safe loader are the same dialect, so a value that
cannot be read back fails the *write* instead of corrupting a file. The safe
dumper knows `date` and `datetime`. It does not know `time`.

Our slots are `time` (the day lives on the plan, so the slot only carries the
hours), which means every message carrying a slot - `SlotsFound`,
`SlotApprovalRequest`, `SlotApprovalDecision` - was silently dropped by the
persistence subscriber with `cannot represent an object`. The team still ran,
because the actors do not depend on the store; but the question never reached
the event feed, so a browser watching the trace waited forever for a question
that had already been asked.

Two ways out. Change the domain so storage can swallow it - a worse model
chosen to suit a backend - or teach this process's dumper the one scalar it is
missing. This is the second.

The quoting is not cosmetic. YAML 1.1 reads a bare `10:00:00` as a
sexagesimal integer - 36000 - so an unquoted slot comes back as a number.
Pydantic then charitably interprets 36000 as seconds since midnight and
produces the right time anyway, which is the worst possible outcome: correct
by accident, and only for the times whose digits happen to parse. `09:30:00`
has a leading zero, so it stays a string. Quoting removes the coin toss.
"""

from __future__ import annotations

import datetime

import yaml


def _represent_time(dumper: yaml.SafeDumper, value: datetime.time) -> yaml.Node:
    """Write a `time` as a quoted ISO 8601 string."""
    return dumper.represent_scalar("tag:yaml.org,2002:str", value.isoformat(), style="'")


def install_yaml_representers() -> None:
    """Make `datetime.time` writable by the safe dumper. Idempotent."""
    yaml.SafeDumper.add_representer(datetime.time, _represent_time)
