"""FastAPI application entrypoint for the location service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session

from location_service.api import router as api_router
from location_service.db import engine, init_db
from location_service.health import router as health_router
from location_service.seed import seed
from location_service.ui import router as ui_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(engine) as session:
        seed(session)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Location Service", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(api_router)
    app.include_router(ui_router)
    return app


app = create_app()
