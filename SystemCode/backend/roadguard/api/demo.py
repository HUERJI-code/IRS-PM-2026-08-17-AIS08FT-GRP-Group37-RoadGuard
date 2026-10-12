"""Explicit simulation endpoints; never store an inspection or planning task."""

from typing import Annotated, Literal

from fastapi import APIRouter, Request
from pydantic import Field

from roadguard.errors import AppError
from roadguard.rules import RuleService
from roadguard.schemas import ErrorResponse, RuleAssessment
from roadguard.schemas.common import ContractModel, FiniteNumber, NonEmptyString, PositiveInt
from roadguard.vision import DemoDetector, DemoScenarioNotFound, SCENARIOS


router = APIRouter(prefix="/demo", tags=["Demonstration"])


class DemoAssessmentRequest(ContractModel):
    scenario_id: Annotated[NonEmptyString, Field(max_length=64)]


class DemoScenarioInfo(ContractModel):
    scenario_id: NonEmptyString
    description: NonEmptyString


class DemoScenarioCatalogue(ContractModel):
    is_demo: Literal[True] = True
    model_version: NonEmptyString
    image_width: PositiveInt
    image_height: PositiveInt
    scenarios: list[DemoScenarioInfo]


class DemoAssessmentResponse(ContractModel):
    is_demo: Literal[True] = True
    scenario_id: NonEmptyString
    model_version: NonEmptyString
    image_width: PositiveInt
    image_height: PositiveInt
    confidence_threshold: Annotated[FiniteNumber, Field(ge=0, le=1)]
    assessment: RuleAssessment


def _services(request: Request) -> tuple[DemoDetector, RuleService]:
    detector = getattr(request.app.state, "demo_detector", None)
    rules = getattr(request.app.state, "rule_service", None)
    if detector is None or rules is None:
        raise AppError("demo_unavailable", "The demonstration service is unavailable.", 503)
    return detector, rules


@router.get(
    "/scenarios", response_model=DemoScenarioCatalogue,
    responses={503: {"model": ErrorResponse}},
    summary="List fixed synthetic scenarios (no image inference)",
)
def list_demo_scenarios(request: Request) -> DemoScenarioCatalogue:
    detector, _ = _services(request)
    return DemoScenarioCatalogue(
        model_version=detector.model_version,
        image_width=detector.image_width, image_height=detector.image_height,
        scenarios=[DemoScenarioInfo(scenario_id=key, description=value) for key, value in SCENARIOS.items()],
    )


@router.post(
    "/assessments", response_model=DemoAssessmentResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    summary="Run a synthetic detector and demo rules without saving tasks",
)
def assess_demo(payload: DemoAssessmentRequest, request: Request) -> DemoAssessmentResponse:
    detector, rules = _services(request)
    try:
        detections = detector.detect(payload.scenario_id)
    except DemoScenarioNotFound as exc:
        raise AppError("demo_scenario_not_found", "The demonstration scenario was not found.", 404) from exc
    assessment = rules.evaluate(detections)
    return DemoAssessmentResponse(
        scenario_id=payload.scenario_id, model_version=detector.model_version,
        image_width=detector.image_width, image_height=detector.image_height,
        confidence_threshold=rules.policy.confidence_threshold, assessment=assessment,
    )
