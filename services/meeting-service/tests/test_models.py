"""Unit tests for the availability algorithm (port of the old Agenda logic)."""

from datetime import date, time

import pytest
from meeting_service.models import (
    AgendaItem,
    availability_for_day,
    check_availability,
    common_free_windows,
)


def make_item(start: str, end: str, day: date, person_id: int = 1, title: str = "x") -> AgendaItem:
    sh, sm = map(int, start.split(":"))
    eh, em = map(int, end.split(":"))
    return AgendaItem(person_id=person_id, day=day, start=time(sh, sm), end=time(eh, em), title=title)


def test_check_availability_no_overlap():
    day = date(2026, 1, 5)
    items = [make_item("09:00", "10:00", day)]
    assert check_availability(items, day, time(10, 0), time(11, 0)) is True


def test_check_availability_overlap():
    day = date(2026, 1, 5)
    items = [make_item("09:00", "10:00", day)]
    assert check_availability(items, day, time(9, 30), time(10, 30)) is False


def test_check_availability_different_day():
    day = date(2026, 1, 5)
    other_day = date(2026, 1, 6)
    items = [make_item("09:00", "17:00", day)]
    assert check_availability(items, other_day, time(9, 0), time(10, 0)) is True


def test_availability_for_day_full_day_free():
    day = date(2026, 1, 5)
    slots = availability_for_day([], day)
    assert slots == ["09:00-17:00"]


def test_availability_for_day_with_bookings():
    day = date(2026, 1, 5)
    items = [
        make_item("10:00", "11:00", day),
        make_item("14:00", "15:00", day),
    ]
    slots = availability_for_day(items, day)
    assert slots == ["09:00-10:00", "11:00-14:00", "15:00-17:00"]


def test_agenda_item_rejects_end_before_start():
    try:
        make_item("10:00", "09:00", date(2026, 1, 5))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_common_free_windows_empty_agendas_gives_whole_day():
    day = date(2026, 1, 5)
    assert common_free_windows([[], []], day, 60) == [(time(9, 0), time(17, 0))]


def test_common_free_windows_intersects_two_people():
    day = date(2026, 1, 5)
    jettro = [make_item("09:00", "11:00", day, person_id=1)]
    daniel = [make_item("13:00", "14:00", day, person_id=2)]
    assert common_free_windows([jettro, daniel], day, 60) == [
        (time(11, 0), time(13, 0)),
        (time(14, 0), time(17, 0)),
    ]


def test_common_free_windows_skips_windows_shorter_than_duration():
    day = date(2026, 1, 5)
    agenda = [make_item("09:00", "11:00", day), make_item("11:30", "17:00", day)]
    assert common_free_windows([agenda], day, 60) == []
    assert common_free_windows([agenda], day, 30) == [(time(11, 0), time(11, 30))]


def test_common_free_windows_merges_overlapping_busy_blocks():
    day = date(2026, 1, 5)
    one = [make_item("09:00", "12:00", day, person_id=1)]
    two = [make_item("10:00", "14:00", day, person_id=2)]
    assert common_free_windows([one, two], day, 60) == [(time(14, 0), time(17, 0))]


def test_common_free_windows_ignores_other_days():
    day = date(2026, 1, 5)
    agenda = [make_item("09:00", "17:00", date(2026, 1, 6))]
    assert common_free_windows([agenda], day, 60) == [(time(9, 0), time(17, 0))]


def test_common_free_windows_rejects_non_positive_duration():
    with pytest.raises(ValueError):
        common_free_windows([[]], date(2026, 1, 5), 0)
