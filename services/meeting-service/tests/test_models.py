"""Unit tests for the availability algorithm (port of the old Agenda logic)."""

from datetime import date, time

from meeting_service.models import AgendaItem, availability_for_day, check_availability


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
