"""Unit tests for the room availability algorithm."""

from datetime import date, time

from location_service.models import RoomBooking, check_availability


def make_booking(start: str, end: str, day: date, room_id: int = 1) -> RoomBooking:
    sh, sm = map(int, start.split(":"))
    eh, em = map(int, end.split(":"))
    return RoomBooking(room_id=room_id, day=day, start=time(sh, sm), end=time(eh, em))


def test_no_overlap_is_available():
    day = date(2026, 1, 5)
    bookings = [make_booking("09:00", "10:00", day)]
    assert check_availability(bookings, day, time(10, 0), time(11, 0)) is True


def test_overlap_is_unavailable():
    day = date(2026, 1, 5)
    bookings = [make_booking("09:00", "10:00", day)]
    assert check_availability(bookings, day, time(9, 30), time(10, 30)) is False


def test_different_day_is_available():
    day = date(2026, 1, 5)
    other_day = date(2026, 1, 6)
    bookings = [make_booking("09:00", "17:00", day)]
    assert check_availability(bookings, other_day, time(9, 0), time(10, 0)) is True


def test_booking_rejects_end_before_start():
    try:
        make_booking("10:00", "09:00", date(2026, 1, 5))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
