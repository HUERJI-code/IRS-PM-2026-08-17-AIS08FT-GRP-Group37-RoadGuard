"""Persisted planning (B-4): recalculate, store and query GA/Greedy route plans.

Consistency rules (see Miscellaneous/BC_HANDOFF.md):
- Tasks and crews are read in one read transaction, so they share one input_revision.
- Matrix and algorithms run after that transaction closes (no long-held DB locks).
- Both plans are saved in one write transaction that re-checks the input revision; if
  inputs changed during calculation nothing is saved and 409 stale_input_revision is
  raised, so an outdated result can never become the latest plan.
- Saving plans never increments input_revision. is_stale is derived on read by
  comparing a plan's input_revision with the current one.
- The travel matrix provider is chosen by configuration (simulated or google_routes).
  A Google failure returns 503 travel_matrix_unavailable and saves nothing; it never
  falls back to the simulated matrix (B-5).
"""

from datetime import datetime, timezone
from functools import wraps
import logging
import sqlite3
import uuid
from typing import Literal

from pydantic import ValidationError

from roadguard.crews.service import CrewService
from roadguard.database import Database, DatabaseStateError, read_revision
from roadguard.errors import AppError
from roadguard.schemas.common import ContractModel, NonEmptyString, NonNegativeInt, UTCTimestamp
from roadguard.tasks import TaskQueryService

from .google_matrix import GoogleRoutesMatrixProvider, TravelMatrixError
from .matrix import simulated_travel_matrix
from .models import Depot, NonNegativeMinutes, PlanningInput, RoutePlan, TravelMatrix
from .planner import plan_routes
from .settings import RoutingConfig, build_planning_input


Algorithm = Literal["ga", "greedy"]
logger = logging.getLogger(__name__)


class RecalculateRequest(ContractModel):
    # Required: callers state which input version they reviewed, so a recalculation never
    # silently plans a different queue than the one the user was looking at.
    expected_revision: NonNegativeInt
    planning_start_at: UTCTimestamp | None = None


class PlanSummary(ContractModel):
    algorithm: Algorithm
    plan_id: NonEmptyString
    assigned_task_count: NonNegativeInt
    unassigned_task_count: NonNegativeInt
    objective_value: NonNegativeMinutes


class RecalculationResult(ContractModel):
    contract_version: Literal["b-recalculation-v1"] = "b-recalculation-v1"
    status: Literal["completed"] = "completed"
    input_revision: NonNegativeInt
    planning_start_at: UTCTimestamp
    task_count: NonNegativeInt
    matrix_provider: NonEmptyString
    matrix_is_simulated: bool
    # For a cached Google matrix this is the original fetch time.
    matrix_generated_at: UTCTimestamp
    plans: list[PlanSummary]


def _db_operation(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except (sqlite3.Error, DatabaseStateError):
            raise AppError("database_unavailable", "The route plan database is unavailable.", 503) from None
    return wrapped


class PlanningService:
    def __init__(self, database: Database, config: RoutingConfig, depot: Depot, crews: CrewService,
                 google_matrix: GoogleRoutesMatrixProvider | None = None) -> None:
        self.database = database
        self.crews = crews
        self.config = config
        self.depot = depot
        self.tasks = TaskQueryService(database)
        self.google_matrix = google_matrix or GoogleRoutesMatrixProvider(config.google_routes)

    def _travel_matrix(self, planning_input: PlanningInput) -> TravelMatrix:
        if self.config.travel_matrix_provider == "simulated":
            return simulated_travel_matrix(planning_input, self.config.simulated_matrix)
        try:
            return self.google_matrix.build(planning_input)
        except TravelMatrixError as exc:
            # Only the constant reason is logged; the key never reaches logs or responses.
            logger.warning("Google travel matrix failed: %s", exc.reason)
            details = {"provider": self.config.google_routes.provider, "reason": exc.reason}
            if exc.http_status is not None:
                details["http_status"] = exc.http_status
            raise AppError("travel_matrix_unavailable",
                           "Travel times could not be obtained. No route plan was saved.", 503, details) from None

    @_db_operation
    def recalculate(self, payload: RecalculateRequest) -> RecalculationResult:
        with self.database.connect() as connection:
            snapshot = self.tasks.snapshot(payload.expected_revision, connection=connection)
            crews = self.crews.read_planning_crews(connection)
        start = payload.planning_start_at or datetime.now(timezone.utc).replace(microsecond=0)
        planning_input = build_planning_input(snapshot, crews, self.depot, self.config.settings, start)
        matrix = self._travel_matrix(planning_input)
        # The online GA may start from the Greedy solution (planning_service.seed_with_greedy);
        # the plan's algorithm_parameters record which setting produced it.
        online_ga = self.config.ga.model_copy(
            update={"seed_with_greedy": self.config.planning_service.seed_with_greedy})
        plans = [
            plan_routes(planning_input, matrix, "greedy", plan_id=f"plan-{uuid.uuid4().hex}")[0],
            plan_routes(planning_input, matrix, "ga", ga_parameters=online_ga,
                        random_seed=self.config.planning_service.ga_seed, plan_id=f"plan-{uuid.uuid4().hex}")[0],
        ]
        created_at = datetime.now(timezone.utc).isoformat()
        # Raises StaleRevisionError (409) before writing if tasks/crews changed meanwhile.
        with self.database.transaction(expected_revision=snapshot.input_revision) as connection:
            for plan in plans:
                connection.execute("INSERT INTO route_plans VALUES (?,?,?,?,?)",
                                   (plan.plan_id, plan.algorithm, plan.input_revision, created_at,
                                    plan.model_dump_json()))
        return RecalculationResult(
            input_revision=snapshot.input_revision, planning_start_at=start, task_count=snapshot.total,
            matrix_provider=matrix.provider, matrix_is_simulated=matrix.is_simulated,
            matrix_generated_at=matrix.generated_at,
            plans=[PlanSummary(algorithm=p.algorithm, plan_id=p.plan_id,
                               assigned_task_count=p.metrics.assigned_task_count,
                               unassigned_task_count=p.metrics.unassigned_task_count,
                               objective_value=p.metrics.objective_value) for p in plans],
        )


class RouteQueryService:
    """plan_id -> saved plan facts; used by C's map and assistant."""

    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _load(connection: sqlite3.Connection, row) -> RoutePlan:
        try:
            plan = RoutePlan.model_validate_json(row[1])
        except ValidationError:
            raise DatabaseStateError("Stored route plan is invalid.") from None
        if (plan.plan_id, plan.algorithm, plan.input_revision) != (row[0], row[2], row[3]):
            raise DatabaseStateError("Stored route plan columns do not match the record.")
        return plan.model_copy(update={"is_stale": plan.input_revision != read_revision(connection)})

    @_db_operation
    def get(self, plan_id: str) -> RoutePlan:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT plan_id,plan_json,algorithm,input_revision FROM route_plans WHERE plan_id=?",
                (plan_id,)).fetchone()
            if row is None:
                raise AppError("route_plan_not_found", "No saved route plan matches the request.", 404)
            return self._load(connection, row)

    @_db_operation
    def latest(self, algorithm: Algorithm) -> RoutePlan:
        if algorithm not in ("ga", "greedy"):
            raise AppError("validation_error", "Algorithm must be ga or greedy.", 422)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT plan_id,plan_json,algorithm,input_revision FROM route_plans WHERE algorithm=? "
                "ORDER BY created_at DESC, rowid DESC LIMIT 1", (algorithm,)).fetchone()
            if row is None:
                # No plan is not an empty valid plan.
                raise AppError("route_plan_not_found", "No saved route plan matches the request.", 404)
            return self._load(connection, row)
