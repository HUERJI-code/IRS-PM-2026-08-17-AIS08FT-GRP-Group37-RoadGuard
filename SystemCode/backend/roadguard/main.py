"""One application factory and export; startup owns config and DB initialization."""

from contextlib import asynccontextmanager
from collections.abc import Mapping
from typing import AsyncIterator

from fastapi import FastAPI

from roadguard.api import create_api_router
from roadguard.config import ConfigurationError, Settings, load_settings
from roadguard.database import Database
from roadguard.errors import install_error_handlers
from roadguard.rules import RuleService, load_rule_policy
from roadguard.vision import DemoDetector
from roadguard.geography import JurongScope
from roadguard.images import ImageStore
from roadguard.inspections import WorkflowService


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        active_settings = settings if settings is not None else load_settings()
        # Validate the explicit demo policy before creating any runtime files.
        rule_service = RuleService(load_rule_policy(active_settings.demo_rules_path))
        scope = JurongScope()
        boundary = active_settings.project["scenario"].get("study_boundary", {})
        if (not isinstance(boundary, Mapping) or boundary.get("scope_version") != scope.scope_version
                or boundary.get("geojson_path") != "Miscellaneous/geography/jurong-boundary-mp2025.geojson"):
            raise ConfigurationError("The workflow requires the frozen Jurong scope configuration.")
        images = ImageStore(active_settings.upload_path)
        database = Database(active_settings.database_path, active_settings.database_busy_timeout_ms)
        database.initialize()
        application.state.settings = active_settings
        application.state.database = database
        application.state.rule_service = rule_service
        application.state.demo_detector = DemoDetector()
        application.state.workflow_service = WorkflowService(
            database, rule_service, application.state.demo_detector, scope, images,
        )
        try:
            yield
        finally:
            # Connections belong to operation contexts; there is no global connection.
            application.state.database = None
            application.state.rule_service = None
            application.state.demo_detector = None
            application.state.workflow_service = None

    application = FastAPI(
        title="RoadGuard API",
        version="0.3.0",
        description=(
            "Persisted image inspections, review and task management using explicit synthetic detection. "
            "Road type is user-declared. No real image inference or route planning is performed. "
            "The separate /demo endpoints remain stateless previews."
        ),
        lifespan=lifespan,
    )
    install_error_handlers(application)
    application.include_router(create_api_router())
    return application


app = create_app()
