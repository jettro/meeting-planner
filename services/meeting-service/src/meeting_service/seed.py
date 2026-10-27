"""Seed demo data: the people whose agendas this service keeps.

Ten of them, because a meeting between two people out of three is not much of a
scheduling problem - with ten, finding a window everyone is free in is a real
question to ask the team.
"""

from __future__ import annotations

from sqlmodel import Session, select

from meeting_service.models import Person

SAMPLE_PEOPLE = [
    ("sanne@rag4p.org", "Sanne de Vries"),
    ("daan@rag4p.org", "Daan Jansen"),
    ("femke@rag4p.org", "Femke Bakker"),
    ("bram@rag4p.org", "Bram van Dijk"),
    ("lotte@rag4p.org", "Lotte Visser"),
    ("thijs@rag4p.org", "Thijs de Jong"),
    ("anouk@rag4p.org", "Anouk Smit"),
    ("joris@rag4p.org", "Joris Mulder"),
    ("marieke@rag4p.org", "Marieke Hendriks"),
    ("sven@rag4p.org", "Sven Peters"),
]


def seed(session: Session) -> None:
    existing = session.exec(select(Person)).first()
    if existing is not None:
        return

    for email, name in SAMPLE_PEOPLE:
        session.add(Person(email=email, name=name))
    session.commit()
