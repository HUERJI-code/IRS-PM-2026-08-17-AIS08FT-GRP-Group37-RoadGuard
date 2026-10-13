"""a-workflow-v2 detector modes; business tasks remain explicitly demo."""

from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, field_validator, model_validator

from .assessment import DemoOnly
from .common import ContractModel, LABEL_KEYS, Latitude, Longitude, NonEmptyString, NonNegativeInt, PositiveInt, UTCTimestamp
from .inspection import Inspection
from .task import Task


RequestId = Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9_-]{1,64}$")]
Note = Annotated[str, StringConstraints(strict=True, max_length=500)]
RoadType = Literal["public_motor_road"]
InspectionStatus = Literal["no_detection", "pending_review", "accepted", "rejected"]
TaskStatus = Literal["active", "completed", "cancelled"]


def _label(value: str | None) -> str | None:
    if value is not None and value not in LABEL_KEYS:
        raise ValueError("damage_label must be a central label key")
    return value


class UploadMetadata(ContractModel):
    mode: Literal["demo", "real"]
    scenario_id: Annotated[NonEmptyString, Field(max_length=64)] | None = None
    latitude: Latitude
    longitude: Longitude
    road_type: RoadType

    @model_validator(mode="after")
    def validate_mode(self) -> Self:
        if self.mode == "demo" and self.scenario_id is None:
            raise ValueError("demo mode requires a named scenario")
        if self.mode == "real" and "scenario_id" in self.model_fields_set:
            raise ValueError("real mode cannot select a demo scenario")
        return self


class ReviewRequest(ContractModel):
    request_id: RequestId
    expected_version: PositiveInt
    action: Literal["confirm", "correct", "dismiss"]
    detection_id: NonEmptyString | None = None
    damage_label: NonEmptyString | None = None
    note: Note | None = None

    _validate_label = field_validator("damage_label")(_label)

    @model_validator(mode="after")
    def validate_action(self) -> Self:
        if self.action in {"confirm", "correct"} and self.detection_id is None:
            raise ValueError("confirm/correct require detection_id")
        if self.action == "correct" and self.damage_label is None:
            raise ValueError("correct requires damage_label")
        if self.action == "confirm" and self.damage_label is not None:
            raise ValueError("confirm cannot correct damage_label")
        if self.action == "dismiss" and (self.detection_id is not None or self.damage_label is not None):
            raise ValueError("dismiss cannot select or correct a detection")
        return self


class TaskPatch(ContractModel):
    request_id: RequestId
    expected_version: PositiveInt
    status: Literal["completed", "cancelled"] | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    road_type: RoadType | None = None
    damage_label: NonEmptyString | None = None

    _validate_label = field_validator("damage_label")(_label)

    @model_validator(mode="after")
    def validate_changes(self) -> Self:
        changes = self.model_fields_set - {"request_id", "expected_version"}
        if not changes or any(getattr(self, key) is None for key in changes):
            raise ValueError("patch requires non-null editable fields")
        position = changes & {"latitude", "longitude", "road_type"}
        if position and position != {"latitude", "longitude", "road_type"}:
            raise ValueError("position changes require latitude, longitude and road_type together")
        return self


class ReviewHistoryEntry(ContractModel):
    request_id: RequestId
    action: Literal["confirm", "correct", "dismiss"]
    recorded_at: UTCTimestamp
    detection_id: NonEmptyString | None
    original_damage_label: NonEmptyString | None
    corrected_damage_label: NonEmptyString | None
    note: Note | None
    rule_version: NonEmptyString
    actor_source: Literal["user_declared_unverified"] = "user_declared_unverified"


class TaskAuditValues(ContractModel):
    status: TaskStatus
    latitude: Latitude
    longitude: Longitude
    damage_label: NonEmptyString
    severity: Literal["low", "medium", "high"]
    priority: Literal["P1", "P2", "P3"]
    service_minutes: Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)] | None
    rule_version: NonEmptyString


class TaskHistoryEntry(ContractModel):
    request_id: RequestId
    action: Literal["created", "updated"]
    recorded_at: UTCTimestamp
    changed_fields: list[NonEmptyString]
    before: TaskAuditValues | None
    after: TaskAuditValues
    actor_source: Literal["system_demo_rules", "user_declared_unverified"]


class InspectionRecord(Inspection):
    created_at: UTCTimestamp
    updated_at: UTCTimestamp
    record_version: PositiveInt
    mode: Literal["demo", "real"]
    demo_scenario_id: NonEmptyString | None
    model_version: NonEmptyString
    model_weights_sha256: Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")] | None = None
    model_manifest_version: Literal["roadguard-model-v1"] | None = None
    image_width: PositiveInt
    image_height: PositiveInt
    scope_version: NonEmptyString
    road_type: RoadType
    road_type_source: Literal["user_declared"] = "user_declared"
    review_history: list[ReviewHistoryEntry]
    is_demo: DemoOnly = True

    @model_validator(mode="after")
    def validate_provenance(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        if self.mode == "demo":
            if self.demo_scenario_id is None or self.model_weights_sha256 is not None or self.model_manifest_version is not None:
                raise ValueError("demo records require scenario provenance and no real checkpoint")
        elif (self.demo_scenario_id is not None or self.model_weights_sha256 is None
              or self.model_manifest_version is None or self.model_version.startswith("demo")):
            raise ValueError("real records require checkpoint provenance without a demo scenario")
        if self.mode == "real" and self.status == "accepted" and not any(
            entry.action in {"confirm", "correct"} and entry.detection_id == self.selected_detection_id
            for entry in self.review_history
        ):
            raise ValueError("real detections require explicit review before acceptance")
        if any((item.image_width, item.image_height, item.model_version) !=
               (self.image_width, self.image_height, self.model_version) or item.is_demo != (self.mode == "demo")
               for item in self.detections):
            raise ValueError("detections must match original image and detector mode provenance")
        return self


class TaskRecord(Task):
    updated_at: UTCTimestamp
    record_version: PositiveInt
    repair_recommendation: NonEmptyString
    history: list[TaskHistoryEntry]
    is_demo: DemoOnly = True

    @model_validator(mode="after")
    def validate_history(self) -> Self:
        if self.updated_at < self.created_at or not self.history:
            raise ValueError("task requires valid timestamps and audit history")
        return self


class InspectionMutation(ContractModel):
    inspection: InspectionRecord
    task: TaskRecord | None
    input_revision: NonNegativeInt
    planning_input_changed: Annotated[bool, Field(strict=True)]
    replayed: Annotated[bool, Field(strict=True)]


class TaskMutation(ContractModel):
    task: TaskRecord
    input_revision: NonNegativeInt
    planning_input_changed: Annotated[bool, Field(strict=True)]
    replayed: Annotated[bool, Field(strict=True)]


class InspectionList(ContractModel):
    items: list[InspectionRecord]
    total: NonNegativeInt
    limit: Annotated[PositiveInt, Field(le=100)]
    offset: NonNegativeInt


class TaskList(ContractModel):
    items: list[TaskRecord]
    total: NonNegativeInt
    limit: Annotated[PositiveInt, Field(le=100)]
    offset: NonNegativeInt
    input_revision: NonNegativeInt
