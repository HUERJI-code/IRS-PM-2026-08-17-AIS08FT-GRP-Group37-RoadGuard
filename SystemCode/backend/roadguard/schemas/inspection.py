"""Inspection snapshots and descriptive decision traces, without a review service."""

from typing import Literal, Self

from pydantic import model_validator

from .common import ContractModel, DemoFlag, Latitude, Longitude, NonEmptyString
from .detection import Detection


class DecisionTrace(ContractModel):
    code: NonEmptyString
    message: NonEmptyString
    rule_version: NonEmptyString | None
    is_demo: DemoFlag


class Inspection(ContractModel):
    inspection_id: NonEmptyString
    image_url: NonEmptyString
    annotated_image_url: NonEmptyString | None
    latitude: Latitude
    longitude: Longitude
    detections: list[Detection]
    selected_detection_id: NonEmptyString | None
    status: Literal["no_detection", "pending_review", "accepted", "rejected"]
    task_id: NonEmptyString | None
    decision_trace: list[DecisionTrace]
    is_demo: DemoFlag

    @model_validator(mode="after")
    def validate_links(self) -> Self:
        ids = [detection.detection_id for detection in self.detections]
        if len(set(ids)) != len(ids):
            raise ValueError("detection_id values must be unique within an inspection")
        if self.selected_detection_id is not None and self.selected_detection_id not in ids:
            raise ValueError("selected_detection_id must refer to a detection in this inspection")
        if self.status == "no_detection":
            if self.detections or self.selected_detection_id is not None or self.task_id is not None:
                raise ValueError("no_detection requires empty detections and no selection or task")
        elif not self.detections:
            raise ValueError("this inspection status requires at least one detection")
        if self.status in ("pending_review", "rejected") and self.task_id is not None:
            raise ValueError("unaccepted inspections must not link to a task")
        if self.status == "accepted" and (
            self.selected_detection_id is None or self.task_id is None
        ):
            raise ValueError("accepted inspections require a selected detection and task_id")
        if not self.is_demo and any(item.is_demo for item in self.detections + self.decision_trace):
            raise ValueError("an inspection containing demo detections or traces must be marked demo")
        return self
