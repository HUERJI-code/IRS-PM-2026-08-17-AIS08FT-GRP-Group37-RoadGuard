"""Demo rule results are candidates, never persisted/accepted tasks."""

from typing import Annotated, Literal, Self

from pydantic import BeforeValidator, Field, field_validator, model_validator

from .common import ContractModel, FiniteNumber, LABEL_KEYS, NonEmptyString
from .detection import Detection
from .inspection import DecisionTrace


def _strict_demo(value: object) -> object:
    if type(value) is not bool or value is not True:
        raise ValueError("this demonstration contract requires is_demo=true")
    return value


DemoOnly = Annotated[Literal[True], BeforeValidator(_strict_demo)]
ServiceMinutes = Annotated[FiniteNumber, Field(gt=0)] | None


class RuleCandidate(ContractModel):
    detection_id: NonEmptyString
    damage_label: NonEmptyString
    severity: Literal["low", "medium", "high"]
    priority: Literal["P1", "P2", "P3"]
    service_minutes: ServiceMinutes
    repair_recommendation: NonEmptyString
    rule_version: NonEmptyString
    is_demo: DemoOnly = True

    @field_validator("damage_label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        if value not in LABEL_KEYS:
            raise ValueError("damage_label must be a central RDD2022ES label_key")
        return value


class RuleAssessment(ContractModel):
    status: Literal["no_detection", "pending_review", "ready_for_task"]
    detections: list[Detection]
    selected_detection_id: NonEmptyString | None
    candidate: RuleCandidate | None
    decision_trace: list[DecisionTrace]
    rule_version: NonEmptyString
    is_demo: DemoOnly = True

    @model_validator(mode="after")
    def validate_consistency(self) -> Self:
        ids = [detection.detection_id for detection in self.detections]
        if len(ids) != len(set(ids)):
            raise ValueError("detection_id values must be unique")
        dimensions = {(item.image_width, item.image_height) for item in self.detections}
        if len(dimensions) > 1:
            raise ValueError("detections must describe one original image size")
        if self.status == "no_detection":
            if self.detections:
                raise ValueError("no_detection requires no detections")
        elif not self.detections:
            raise ValueError("this status requires detections")
        if self.status != "ready_for_task":
            if self.selected_detection_id is not None or self.candidate is not None:
                raise ValueError("unready assessments cannot select or create a candidate")
        else:
            if self.candidate is None or self.selected_detection_id not in ids:
                raise ValueError("ready_for_task requires a selected detection and candidate")
            selected = next(item for item in self.detections if item.detection_id == self.selected_detection_id)
            if self.candidate.detection_id != selected.detection_id or self.candidate.damage_label != selected.label:
                raise ValueError("candidate must refer to the selected detection and label")
            if self.candidate.rule_version != self.rule_version:
                raise ValueError("candidate must use the assessment rule version")
        if not self.decision_trace or any(
            trace.rule_version != self.rule_version or not trace.is_demo
            for trace in self.decision_trace
        ):
            raise ValueError("all assessment traces must use the demo rule version")
        return self
