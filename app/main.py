"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.runtime import ensure_directories
from app.db.database import initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    ensure_directories(settings.required_directories)
    configure_logging(settings)
    initialize_database()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.project_name,
        version=settings.app_version,
        summary="Local-first personal banking ingestion engine.",
        lifespan=lifespan,
    )
    application.include_router(api_router)
    return application


app = create_app()
