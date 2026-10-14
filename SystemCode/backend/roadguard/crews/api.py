"""HTTP adapters for crew availability (B)."""

from typing import Annotated

from fastapi import APIRouter, Path, Request

from roadguard.schemas import ErrorResponse

from .schemas import CrewList, CrewMutation, CrewPatch
from .service import CrewService


router = APIRouter(tags=["Crews"])
ERRORS = {code: {"model": ErrorResponse} for code in (404, 409, 422, 503)}
CrewID = Annotated[str, Path(pattern=r"^[a-z0-9-]{1,32}$")]


def _service(request: Request) -> CrewService:
    return request.app.state.crew_service


@router.get("/crews", response_model=CrewList, responses=ERRORS,
            summary="List all configured crews, including unavailable ones, with the current input revision")
def list_crews(request: Request) -> CrewList:
    return _service(request).list()


@router.patch("/crews/{crew_id}", response_model=CrewMutation, responses=ERRORS,
              summary="Change crew availability; increments input_revision and marks existing plans stale",
              description="Does not compute a new plan. Call POST /route-plans/recalculate with the returned "
                          "input_revision. Retrying with the same request_id replays the stored outcome.")
def update_crew(request: Request, crew_id: CrewID, payload: CrewPatch) -> CrewMutation:
    return _service(request).update(crew_id, payload)
