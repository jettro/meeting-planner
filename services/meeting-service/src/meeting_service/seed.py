"""Seed demo data, mirroring the sample participants from the old Java project."""

from __future__ import annotations

from sqlmodel import Session, select

from meeting_service.models import Person

SAMPLE_PEOPLE = [
    ("jettro@rag4j.org", "Jettro Coenradie"),
    ("daniel@rag4j.org", "Daniel Spee"),
    ("joey@rag4j.org", "Joey Visbeen"),
]


def seed(session: Session) -> None:
    existing = session.exec(select(Person)).first()
    if existing is not None:
        return

    for email, name in SAMPLE_PEOPLE:
        session.add(Person(email=email, name=name))
    session.commit()
