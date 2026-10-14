"""Load B's explicit demo routing assumptions and build planning inputs."""

from collections.abc import Mapping
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from pydantic import Field

from roadguard.schemas.common import ContractModel, FiniteNumber, NonEmptyString, PositiveInt
from roadguard.schemas.task_query import TaskSnapshot

from .models import Crew, Depot, PlanningInput, PlanningSettings, ShiftLimit, ObjectiveWeights


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_ROUTING_CONFIG = REPOSITORY_ROOT / "SystemCode/config/routing.example.json"


class SimulatedMatrixParameters(ContractModel):
    provider: NonEmptyString
    detour_factor: FiniteNumber = Field(ge=1)
    average_speed_kmh: FiniteNumber = Field(gt=0)
    minutes_decimals: int = Field(strict=True, ge=0, le=3)


class GAParameters(ContractModel):
    population_size: PositiveInt = Field(ge=4)
    max_generations: PositiveInt
    patience_generations: PositiveInt
    crossover_rate: FiniteNumber = Field(ge=0, le=1)
    mutation_rate: FiniteNumber = Field(ge=0, le=1)
    tournament_size: PositiveInt = Field(ge=2)
    elite_count: int = Field(strict=True, ge=0)
    # Seeding GA with the greedy result would bias the GA/Greedy comparison; off by default.
    seed_with_greedy: bool


class RoutingConfig(ContractModel):
    settings: PlanningSettings
    simulated_matrix: SimulatedMatrixParameters
    ga: GAParameters
    experiment: dict[str, Any]


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("routing config contains duplicate keys")
    return dict(pairs)


def load_routing_config(path: Path | None = None) -> RoutingConfig:
    source = json.loads(Path(path or DEFAULT_ROUTING_CONFIG).read_text(encoding="utf-8"),
                        object_pairs_hook=_reject_duplicates)
    objective = source["objective"]
    settings = PlanningSettings(
        config_version=source["config_version"],
        is_demo=source["is_demo"],
        return_to_depot=source["return_to_depot"],
        shift_limit=ShiftLimit.model_validate(source["shift_limit"]),
        objective_version=objective["objective_version"],
        weights=ObjectiveWeights.model_validate(objective["weights"]),
        priority_weights=objective["priority_weights"],
    )
    ga = GAParameters.model_validate(source["ga"])
    if ga.elite_count >= ga.population_size:
        raise ValueError("elite_count must be smaller than population_size")
    return RoutingConfig(
        settings=settings,
        simulated_matrix=SimulatedMatrixParameters.model_validate(source["simulated_matrix"]),
        ga=ga,
        experiment=source["experiment"],
    )


def depot_from_project(project: Mapping[str, Any]) -> Depot:
    depot = project["scenario"]["depot"]
    return Depot(depot_id=depot["depot_id"], latitude=depot["latitude"], longitude=depot["longitude"])


def default_crews(project: Mapping[str, Any], unavailable: frozenset[str] = frozenset()) -> list[Crew]:
    """Configured crew IDs (default four); persisted crew state arrives with CrewService."""
    depot_id = project["scenario"]["depot"]["depot_id"]
    crew_ids = list(project["planning"]["crew_ids"])
    unknown = unavailable - set(crew_ids)
    if unknown:
        raise ValueError("unavailable crew IDs must be configured crews")
    return [
        Crew(crew_id=crew_id, name=f"Crew {crew_id.rsplit('-', 1)[-1]}",
             available=crew_id not in unavailable, depot_id=depot_id)
        for crew_id in crew_ids
    ]


def build_planning_input(snapshot: TaskSnapshot, crews: list[Crew], depot: Depot,
                         settings: PlanningSettings, planning_start_at: datetime | str) -> PlanningInput:
    return PlanningInput(
        task_source=snapshot.source,
        input_revision=snapshot.input_revision,
        planning_start_at=planning_start_at,
        depot=depot,
        crews=crews,
        tasks=snapshot.tasks,
        settings=settings,
    )
