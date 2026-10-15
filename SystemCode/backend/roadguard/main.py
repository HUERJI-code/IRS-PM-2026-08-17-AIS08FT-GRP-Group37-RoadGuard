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
from roadguard.vision.real import LocalVisionDetector
from roadguard.geography import JurongScope
from roadguard.images import ImageStore
from roadguard.inspections import WorkflowService
from roadguard.tasks import TaskQueryService
from roadguard.crews import CrewService
from roadguard.routing.service import PlanningService, RouteQueryService
from roadguard.routing.settings import depot_from_project, load_routing_config


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        active_settings = settings if settings is not None else load_settings()
        # Validate the explicit demo policy before creating any runtime files.
        rule_service = RuleService(load_rule_policy(active_settings.demo_rules_path))
        # B's routing assumptions are validated before any runtime files are created.
        try:
            routing_config = load_routing_config()
            depot = depot_from_project(active_settings.project)
            crew_ids = list(active_settings.project["planning"]["crew_ids"])
            CrewService(None, crew_ids, depot.depot_id)  # validate the roster before startup writes
        except (OSError, KeyError, TypeError, ValueError) as exc:
            raise ConfigurationError("The routing configuration is invalid.") from exc
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
        application.state.real_detector = LocalVisionDetector(active_settings.vision_manifest_path)
        application.state.workflow_service = WorkflowService(
            database, rule_service, application.state.demo_detector, scope, images,
            real_detector=application.state.real_detector,
        )
        application.state.task_query_service = TaskQueryService(database)
        application.state.crew_service = CrewService(database, crew_ids, depot.depot_id)
        application.state.planning_service = PlanningService(
            database, routing_config, depot, application.state.crew_service)
        application.state.route_query_service = RouteQueryService(database)
        try:
            yield
        finally:
            # Connections belong to operation contexts; there is no global connection.
            application.state.database = None
            application.state.rule_service = None
            application.state.demo_detector = None
            application.state.real_detector = None
            application.state.workflow_service = None
            application.state.task_query_service = None
            application.state.crew_service = None
            application.state.planning_service = None
            application.state.route_query_service = None

    application = FastAPI(
        title="RoadGuard API",
        version="0.8.0",
        description=(
            "Persisted inspections using explicit demo scenarios or the locally installed released detector. "
            "Inspection responses contain at most one box; raw evidence is retained internally. "
            "Uploads return only inspection_id, status, detection and task_id; details are queried separately. "
            "Real primary detections meeting the configured confidence threshold (default 0.60) create one task. "
            "Lower-confidence detections require review; business rules and tasks remain demo assumptions. "
            "Road type is user-declared. Four-crew Greedy/GA route plans use the configured travel matrix "
            "(labelled simulated by default, or Google Routes when enabled) and demo shift/objective "
            "assumptions; recalculation is explicit and never automatic. "
            "The separate /demo endpoints remain stateless previews."
        ),
        lifespan=lifespan,
    )
    install_error_handlers(application)
    application.include_router(create_api_router())
    return application


app = create_app()
