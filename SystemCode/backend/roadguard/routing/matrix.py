"""Travel matrix providers. Only the clearly labelled simulated provider exists so far."""

from datetime import datetime, timezone
import math

from .models import PlanningInput, TravelMatrix
from .settings import SimulatedMatrixParameters

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi, d_lambda = phi2 - phi1, math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def node_ids(planning_input: PlanningInput) -> list[str]:
    """Node 0 is the shared depot; task nodes follow snapshot order (not a visit order)."""
    return [planning_input.depot.depot_id, *(task.task_id for task in planning_input.tasks)]


def simulated_travel_matrix(planning_input: PlanningInput, parameters: SimulatedMatrixParameters,
                            generated_at: datetime | None = None) -> TravelMatrix:
    """Great-circle distance x detour factor / average speed.

    This is a reproducible stand-in, not road-network travel time. It is symmetric only
    as a by-product; planners must never rely on symmetry, because real matrices differ.
    """
    points = [(planning_input.depot.latitude, planning_input.depot.longitude),
              *((task.latitude, task.longitude) for task in planning_input.tasks)]
    minutes_per_km = 60.0 / parameters.average_speed_kmh
    durations = [
        [0.0 if i == j else round(haversine_km(*a, *b) * parameters.detour_factor * minutes_per_km,
                                  parameters.minutes_decimals)
         for j, b in enumerate(points)]
        for i, a in enumerate(points)
    ]
    return TravelMatrix(
        node_ids=node_ids(planning_input),
        duration_minutes=durations,
        provider=parameters.provider,
        is_simulated=True,
        generated_at=generated_at or datetime.now(timezone.utc),
        parameters=parameters.model_dump(mode="json"),
    )
