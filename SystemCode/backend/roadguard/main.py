"""One application factory and export; startup owns config and DB initialization."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from roadguard.api import create_api_router
from roadguard.config import Settings, load_settings
from roadguard.database import Database
from roadguard.errors import install_error_handlers


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        active_settings = settings if settings is not None else load_settings()
        database = Database(active_settings.database_path, active_settings.database_busy_timeout_ms)
        database.initialize()
        application.state.settings = active_settings
        application.state.database = database
        try:
            yield
        finally:
            # Connections belong to operation contexts; there is no global connection.
            application.state.database = None

    application = FastAPI(
        title="RoadGuard API",
        version="0.1.0",
        description="Shared backend foundation. Only infrastructure health is implemented.",
        lifespan=lifespan,
    )
    install_error_handlers(application)
    application.include_router(create_api_router())
    return application


app = create_app()
