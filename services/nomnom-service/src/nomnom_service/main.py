"""FastAPI application entrypoint for the NomNom service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session

from nomnom_service.api import router as api_router
from nomnom_service.db import engine, init_db
from nomnom_service.seed import seed
from nomnom_service.ui import router as ui_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(engine) as session:
        seed(session)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="NomNom Service", lifespan=lifespan)
    app.include_router(api_router)
    app.include_router(ui_router)
    return app


app = create_app()
