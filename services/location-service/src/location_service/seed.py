"""Seed demo data: the 11 sample locations/rooms from the old Java project, plus a
handful of sample bookings so the UI isn't empty on first run.
"""

from datetime import date, time, timedelta

from sqlmodel import Session, select

from location_service.models import Location, Room, RoomBooking

LOCATIONS: dict[str, tuple[str, str, list[tuple[str, int]]]] = {
    "luminis": (
        "Luminis",
        "Business meeting rooms across the Netherlands.",
        [("room-a", 4), ("room-b", 8), ("room-c", 12)],
    ),
    "like-home": (
        "Meeting like Home",
        "Homely settings for a relaxing meeting.",
        [("living", 6), ("kitchen", 10), ("garden", 5)],
    ),
    "meet-nature": (
        "Meeting in Nature",
        "Combine meetings with outdoor activities.",
        [("forest", 8), ("lake", 14), ("meadow", 6)],
    ),
    "techhub": ("TechHub", "Modern tech-focused meeting spaces.", [("alpha", 5), ("beta", 9), ("gamma", 15)]),
    "cityview": (
        "CityView",
        "Panoramic city views for inspiring meetings.",
        [("sky", 7), ("cloud", 12), ("sun", 20)],
    ),
    "greenspace": (
        "GreenSpace",
        "Eco-friendly meeting rooms surrounded by plants.",
        [("ivy", 4), ("fern", 8), ("moss", 10)],
    ),
    "harbor": (
        "Harbor",
        "Meetings with a view of the water and ships.",
        [("dock", 6), ("pier", 11), ("cabin", 8)],
    ),
    "library": (
        "Library",
        "Quiet spaces for focused meetings.",
        [("study", 3), ("archive", 7), ("reading", 10)],
    ),
    "loft": ("Loft", "Trendy loft-style meeting rooms.", [("brick", 5), ("beam", 9), ("glass", 13)]),
    "villa": (
        "Villa",
        "Luxurious villa for exclusive meetings.",
        [("salon", 8), ("terrace", 16), ("suite", 6)],
    ),
    "campus": (
        "Campus",
        "Academic-style meeting rooms for workshops and seminars.",
        [("lab", 10), ("hall", 18), ("class", 7)],
    ),
}


def seed(session: Session) -> None:
    existing = session.exec(select(Location)).first()
    if existing is not None:
        return

    room_by_key: dict[tuple[str, str], Room] = {}
    for location_id, (name, description, rooms) in LOCATIONS.items():
        session.add(Location(location_id=location_id, name=name, description=description))
        for room_code, capacity in rooms:
            room = Room(location_id=location_id, room_code=room_code, capacity=capacity)
            session.add(room)
            room_by_key[(location_id, room_code)] = room
    session.commit()

    for room in room_by_key.values():
        session.refresh(room)

    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sample_bookings = [
        ("luminis", "room-a", monday, time(9, 0), time(10, 30), "Monday Team Stand-up"),
        ("techhub", "alpha", monday, time(14, 0), time(15, 30), "Code Review Monday"),
        ("luminis", "room-b", monday + timedelta(days=1), time(10, 0), time(11, 30), "Sprint Planning"),
        ("cityview", "sky", monday + timedelta(days=2), time(9, 30), time(11, 0), "Midweek Strategy"),
        ("harbor", "dock", monday + timedelta(days=3), time(14, 30), time(16, 0), "Waterfront Meeting"),
        ("villa", "salon", monday + timedelta(days=4), time(15, 0), time(17, 0), "End of Week VIP Meeting"),
    ]
    for location_id, room_code, day, start, end, description in sample_bookings:
        booking_room = room_by_key.get((location_id, room_code))
        if booking_room is None:
            continue
        session.add(
            RoomBooking(
                room_id=booking_room.id,  # type: ignore[arg-type]
                day=day,
                start=start,
                end=end,
                reference="seed",
                description=description,
            )
        )
    session.commit()
