"""HTTP adapters for route-plan recalculation and queries (B)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query, Request

from roadguard.schemas import ErrorResponse

from .models import RoutePlan
from .service import PlanningService, RecalculateRequest, RecalculationResult, RouteQueryService


router = APIRouter(tags=["Route plans"])
ERRORS = {code: {"model": ErrorResponse} for code in (404, 409, 422, 503)}
PlanID = Annotated[str, Path(pattern=r"^plan-[0-9a-f]{32}$")]


def _planning(request: Request) -> PlanningService:
    return request.app.state.planning_service


def _queries(request: Request) -> RouteQueryService:
    return request.app.state.route_query_service


# Fixed paths are registered before /route-plans/{plan_id} to avoid route ambiguity.
@router.post("/route-plans/recalculate", response_model=RecalculationResult, responses=ERRORS,
             summary="Plan all active tasks with Greedy and GA on the same input and matrix, then save both",
             description="expected_revision must equal the current input_revision. If tasks or crews change "
                         "during calculation, nothing is saved and 409 stale_input_revision is returned. "
                         "Travel times come from the labelled simulated matrix, not road-network data.")
def recalculate(request: Request, payload: RecalculateRequest) -> RecalculationResult:
    return _planning(request).recalculate(payload)


@router.get("/route-plans/latest", response_model=RoutePlan, responses=ERRORS,
            summary="Latest saved plan for one algorithm; is_stale=true if inputs changed since it was computed",
            description="Returns 404 route_plan_not_found when no plan has been saved yet.")
def latest_plan(request: Request, algorithm: Annotated[Literal["ga", "greedy"], Query()]) -> RoutePlan:
    return _queries(request).latest(algorithm)


@router.get("/route-plans/{plan_id}", response_model=RoutePlan, responses=ERRORS,
            summary="A saved plan by ID, for display, explanation and before/after comparison")
def get_plan(request: Request, plan_id: PlanID) -> RoutePlan:
    return _queries(request).get(plan_id)
