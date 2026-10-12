"""One application factory and export; startup owns config and DB initialization."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from roadguard.api import create_api_router
from roadguard.config import Settings, load_settings
from roadguard.database import Database
from roadguard.errors import install_error_handlers
from roadguard.rules import RuleService, load_rule_policy
from roadguard.vision import DemoDetector


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        active_settings = settings if settings is not None else load_settings()
        # Validate the explicit demo policy before creating any runtime files.
        rule_service = RuleService(load_rule_policy(active_settings.demo_rules_path))
        database = Database(active_settings.database_path, active_settings.database_busy_timeout_ms)
        database.initialize()
        application.state.settings = active_settings
        application.state.database = database
        application.state.rule_service = rule_service
        application.state.demo_detector = DemoDetector()
        try:
            yield
        finally:
            # Connections belong to operation contexts; there is no global connection.
            application.state.database = None
            application.state.rule_service = None
            application.state.demo_detector = None

    application = FastAPI(
        title="RoadGuard API",
        version="0.2.0",
        description=(
            "Shared backend and explicit synthetic detection/rule demonstrations. "
            "Demo assessments are stateless previews: no image inference, stored tasks or routing."
        ),
        lifespan=lifespan,
    )
    install_error_handlers(application)
    application.include_router(create_api_router())
    return application


app = create_app()
