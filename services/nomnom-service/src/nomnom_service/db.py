"""SQLite-backed engine/session management for the NomNom service."""

import os
from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

DB_PATH = os.environ.get("NOMNOM_SERVICE_DB", "nomnom.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
