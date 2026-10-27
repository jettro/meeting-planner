"""Liveness and readiness for the location service.

A health check that only answers "the process is running" is barely worth the
route. This one touches the database, because an unreachable or unmigrated
SQLite file is the failure a reader of this endpoint actually cares about -
and it is the one a container that is "up" will happily hide.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlmodel import Session

from location_service.db import DB_PATH, engine

router = APIRouter(tags=["health"])

SERVICE_NAME = "location-service"


def _database_status() -> tuple[bool, str | None]:
    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))  # type: ignore[call-overload]
    except Exception as exc:  # noqa: BLE001 - any failure here is unhealthy
        return False, str(exc)
    return True, None


@router.get("/health")
def health() -> JSONResponse:
    """Report the service and its database. 503 when the database is gone."""
    reachable, error = _database_status()
    body: dict[str, object] = {
        "service": SERVICE_NAME,
        "status": "ok" if reachable else "unhealthy",
        "database": {"path": DB_PATH, "reachable": reachable},
    }
    if error is not None:
        body["database"]["error"] = error  # type: ignore[index]
    return JSONResponse(body, status_code=200 if reachable else 503)
