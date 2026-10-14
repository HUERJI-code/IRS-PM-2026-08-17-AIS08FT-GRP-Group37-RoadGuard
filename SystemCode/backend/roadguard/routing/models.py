import math
from typing import Annotated, Any, Literal, Self

from pydantic import Field, model_validator

from roadguard.schemas.common import (
    ContractModel, FiniteNumber, Latitude, Longitude, NonEmptyString, NonNegativeInt,
    UTCTimestamp,
)
from roadguard.schemas.task import Task

NonNegativeMinutes = Annotated[FiniteNumber, Field(ge=0)]
PositiveNumber = Annotated[FiniteNumber, Field(gt=0)]
Priority = Literal["P1", "P2", "P3"]
UnassignedReason = Literal[
    "unknown_service_minutes",  # service_minutes=None cannot be scheduled as zero
    "unreachable_from_depot",
    "unreachable_to_depot",  # only when return_to_depot is true
    "no_available_crew",
    "exceeds_shift_limit",
    "no_feasible_route_position",  # unreachable from every feasible predecessor chosen
]


class Depot(ContractModel):
    depot_id: NonEmptyString
    latitude: Latitude
    longitude: Longitude


class Crew(ContractModel):
    crew_id: NonEmptyString
    name: NonEmptyString
    available: bool
    depot_id: NonEmptyString


class ShiftLimit(ContractModel):
    """Explicit policy; an absent limit must be chosen as mode=unlimited, never inferred."""

    mode: Literal["unlimited", "limited"]
    minutes: PositiveNumber | None = None

    @model_validator(mode="after")
    def validate_mode(self) -> Self:
        if (self.mode == "limited") != (self.minutes is not None):
            raise ValueError("limited shifts require minutes; unlimited shifts must not set minutes")
        return self


class ObjectiveWeights(ContractModel):
    makespan_minutes: Annotated[FiniteNumber, Field(ge=0)]
    total_travel_minutes: Annotated[FiniteNumber, Field(ge=0)]
    workload_std_minutes: Annotated[FiniteNumber, Field(ge=0)]
    priority_weighted_completion_minutes: Annotated[FiniteNumber, Field(ge=0)]


class PlanningSettings(ContractModel):
    config_version: NonEmptyString
    is_demo: bool
    return_to_depot: bool
    shift_limit: ShiftLimit
    objective_version: NonEmptyString
    weights: ObjectiveWeights
    priority_weights: dict[Priority, PositiveNumber]

    @model_validator(mode="after")
    def validate_priorities(self) -> Self:
        if set(self.priority_weights) != {"P1", "P2", "P3"}:
            raise ValueError("priority_weights must define P1, P2 and P3")
        return self


class PlanningInput(ContractModel):
    contract_version: Literal["b-planning-input-v1-draft"] = "b-planning-input-v1-draft"
    task_source: Literal["persisted_workflow", "synthetic_fixture"]
    input_revision: NonNegativeInt
    planning_start_at: UTCTimestamp
    depot: Depot
    crews: list[Crew]
    tasks: list[Task]
    settings: PlanningSettings

    @model_validator(mode="after")
    def validate_input(self) -> Self:
        if not self.crews:
            raise ValueError("planning input requires the configured crew records")
        if len({crew.crew_id for crew in self.crews}) != len(self.crews):
            raise ValueError("crew IDs must be unique")
        if any(crew.depot_id != self.depot.depot_id for crew in self.crews):
            raise ValueError("all crews must start from the shared depot")
        if len({task.task_id for task in self.tasks}) != len(self.tasks):
            raise ValueError("task IDs must be unique")
        if self.depot.depot_id in {task.task_id for task in self.tasks}:
            raise ValueError("depot ID must not collide with a task ID")
        if any(task.status != "active" for task in self.tasks):
            raise ValueError("only active tasks may be planned")
        return self


class TravelMatrix(ContractModel):
    """duration_minutes[i][j] is travel from node_ids[i] to node_ids[j]; not assumed symmetric."""

    contract_version: Literal["b-travel-matrix-v1-draft"] = "b-travel-matrix-v1-draft"
    node_ids: list[NonEmptyString]
    duration_minutes: list[list[NonNegativeMinutes | None]]
    provider: NonEmptyString
    is_simulated: bool
    generated_at: UTCTimestamp
    parameters: dict[str, Any]

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        size = len(self.node_ids)
        if size == 0 or len(set(self.node_ids)) != size:
            raise ValueError("matrix node IDs must be non-empty and unique")
        if len(self.duration_minutes) != size or any(len(row) != size for row in self.duration_minutes):
            raise ValueError("matrix must be square and match node_ids")
        if any(self.duration_minutes[i][i] != 0 for i in range(size)):
            raise ValueError("matrix diagonal must be zero minutes")
        return self


class Stop(ContractModel):
    sequence: Annotated[int, Field(strict=True, ge=1)]
    task_id: NonEmptyString
    latitude: Latitude
    longitude: Longitude
    priority: Priority
    travel_minutes_from_previous: NonNegativeMinutes
    arrival_minute: NonNegativeMinutes
    service_minutes: PositiveNumber
    completion_minute: NonNegativeMinutes


class CrewRoute(ContractModel):
    crew_id: NonEmptyString
    available: bool
    status: Literal["assigned", "idle", "unavailable"]
    stops: list[Stop]
    travel_minutes: NonNegativeMinutes
    return_travel_minutes: NonNegativeMinutes | None
    service_minutes: NonNegativeMinutes
    total_work_minutes: NonNegativeMinutes
    end_minute: NonNegativeMinutes
    geometry: None = None
    geometry_note: Literal["no_road_geometry_straight_lines_are_illustrative_only"] = (
        "no_road_geometry_straight_lines_are_illustrative_only"
    )


class UnassignedTask(ContractModel):
    task_id: NonEmptyString
    reason: UnassignedReason


class PlanMetrics(ContractModel):
    assigned_task_count: NonNegativeInt
    unassigned_task_count: NonNegativeInt
    total_travel_minutes: NonNegativeMinutes
    total_service_minutes: NonNegativeMinutes
    makespan_minutes: NonNegativeMinutes
    workload_std_minutes: NonNegativeMinutes | None
    priority_weighted_completion_minutes: NonNegativeMinutes | None
    tasks_with_due_at: NonNegativeInt
    total_lateness_minutes: NonNegativeMinutes | None
    late_task_count: NonNegativeInt | None
    objective_value: NonNegativeMinutes
    algorithm_runtime_ms: NonNegativeMinutes


class RoutePlan(ContractModel):
    contract_version: Literal["b-route-plan-v1-draft"] = "b-route-plan-v1-draft"
    plan_id: NonEmptyString
    input_revision: NonNegativeInt
    task_source: Literal["persisted_workflow", "synthetic_fixture"]
    algorithm: Literal["ga", "greedy"]
    planning_start_at: UTCTimestamp
    depot: Depot
    crew_routes: list[CrewRoute]
    unassigned_tasks: list[UnassignedTask]
    metrics: PlanMetrics
    matrix_provider: NonEmptyString
    matrix_is_simulated: bool
    settings: PlanningSettings
    random_seed: int | None
    algorithm_parameters: dict[str, Any]
    is_stale: bool = False
    is_demo: Literal[True] = True

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        assigned = [stop.task_id for route in self.crew_routes for stop in route.stops]
        unassigned = [item.task_id for item in self.unassigned_tasks]
        if len(set(assigned)) != len(assigned) or set(assigned) & set(unassigned):
            raise ValueError("each task may appear only once across routes and unassigned tasks")
        if len(set(unassigned)) != len(unassigned):
            raise ValueError("unassigned task IDs must be unique")
        if any(not route.available and route.stops for route in self.crew_routes):
            raise ValueError("unavailable crews must not receive tasks")
        if self.algorithm == "greedy" and self.random_seed is not None:
            raise ValueError("greedy is deterministic and has no random seed")
        if not math.isfinite(self.metrics.objective_value):
            raise ValueError("objective must be finite")
        return self
