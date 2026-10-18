"""a-workflow-v5: compact uploads with detailed, audited single-box inspections."""

from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, field_validator, model_validator

from .assessment import DemoOnly
from .common import ContractModel, FiniteNumber, LABEL_KEYS, Latitude, Longitude, NonEmptyString, NonNegativeInt, PositiveInt, UTCTimestamp
from .detection import Detection
from .inspection import Inspection
from .task import Task
from .primary import PrimarySuggestion


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
    actor_source: Literal["user_declared_unverified", "authenticated_user"] = "user_declared_unverified"


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
    actor_source: Literal["system_demo_rules", "system_confidence_policy", "user_declared_unverified", "authenticated_user"]


class AutoAcceptance(ContractModel):
    policy_version: Literal["single-primary-auto-v1"] = "single-primary-auto-v1"
    confidence_threshold: Annotated[FiniteNumber, Field(ge=0, le=1)]


class InspectionDetails(Inspection):
    created_at: UTCTimestamp
    updated_at: UTCTimestamp
    record_version: PositiveInt
    mode: Literal["demo", "real"]
    demo_scenario_id: NonEmptyString | None
    model_version: NonEmptyString
    model_weights_sha256: Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$")] | None = None
    model_manifest_version: Literal["roadguard-model-v1"] | None = None
    primary_suggestion: PrimarySuggestion | None = None
    auto_acceptance: AutoAcceptance | None = None
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
        if self.auto_acceptance is not None:
            selected = next((d for d in self.detections if d.detection_id == self.selected_detection_id), None)
            if (self.mode != "real" or self.status != "accepted" or selected is None
                    or selected.confidence < self.auto_acceptance.confidence_threshold
                    or self.review_history
                    or (self.primary_suggestion is not None
                        and self.primary_suggestion.detection_id != selected.detection_id)):
                raise ValueError("automatic acceptance requires the eligible real primary detection")
        if self.mode == "real" and self.status == "accepted" and self.auto_acceptance is None and not any(
            entry.action in {"confirm", "correct"} and entry.detection_id == self.selected_detection_id
            for entry in self.review_history
        ):
            raise ValueError("real detections require review or a recorded automatic acceptance policy")
        if any((item.image_width, item.image_height, item.model_version) !=
               (self.image_width, self.image_height, self.model_version) or item.is_demo != (self.mode == "demo")
               for item in self.detections):
            raise ValueError("detections must match original image and detector mode provenance")
        return self


class InspectionRecord(InspectionDetails):
    """Internal persisted evidence; never project this object before storing it."""

    @model_validator(mode="after")
    def validate_evidence_links(self) -> Self:
        if self.primary_suggestion is not None:
            suggestion = self.primary_suggestion
            ids = {item.detection_id for item in self.detections}
            if (self.mode != "real" or not set(suggestion.competing_detection_ids).issubset(ids)
                    or (suggestion.detection_id is not None and suggestion.detection_id not in ids)):
                raise ValueError("primary suggestion must reference this real inspection's evidence")
            if suggestion.detection_id is not None:
                item = next(d for d in self.detections if d.detection_id == suggestion.detection_id)
                if item.confidence < suggestion.threshold:
                    raise ValueError("primary suggestion is below its inference filter")
            elif any(item.confidence >= suggestion.threshold for item in self.detections):
                raise ValueError("primary suggestion cannot omit eligible evidence")
        return self


class InspectionResponse(InspectionDetails):
    """HTTP view; competing IDs may refer to retained, non-returned evidence."""

    detections: Annotated[list[Detection], Field(max_length=1)]

    @classmethod
    def from_record(cls, record: InspectionRecord) -> Self:
        # Accepted selection wins, including a human selection on a legacy record.
        target = record.selected_detection_id
        if target is None and record.primary_suggestion is not None:
            target = record.primary_suggestion.detection_id
        selected = next((d for d in record.detections if d.detection_id == target), None)
        if selected is None:
            selected = max(record.detections, key=lambda d: d.confidence, default=None)
        data = record.model_dump()
        data["detections"] = [selected.model_dump()] if selected else []
        return cls.model_validate(data)


class UploadDetection(ContractModel):
    """Only the values needed to display the uploaded image's primary damage."""

    label: NonEmptyString
    confidence: Annotated[FiniteNumber, Field(ge=0, le=1)]
    bbox_xyxy: tuple[FiniteNumber, FiniteNumber, FiniteNumber, FiniteNumber]
    image_width: PositiveInt
    image_height: PositiveInt

    @classmethod
    def from_detection(cls, detection: Detection) -> Self:
        return cls.model_validate(detection.model_dump(include=set(cls.model_fields)))


class InspectionUploadResponse(ContractModel):
    inspection_id: NonEmptyString
    status: InspectionStatus
    detection: UploadDetection | None
    task_id: NonEmptyString | None

    @classmethod
    def from_record(cls, record: InspectionRecord) -> Self:
        view = InspectionResponse.from_record(record)
        return cls(inspection_id=view.inspection_id, status=view.status, task_id=view.task_id,
                   detection=UploadDetection.from_detection(view.detections[0]) if view.detections else None)


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


class InspectionMutationResponse(InspectionMutation):
    inspection: InspectionResponse

    @classmethod
    def from_result(cls, result: InspectionMutation) -> Self:
        data = result.model_dump()
        data["inspection"] = InspectionResponse.from_record(result.inspection).model_dump()
        return cls.model_validate(data)


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


class InspectionListResponse(InspectionList):
    items: list[InspectionResponse]

    @classmethod
    def from_result(cls, result: InspectionList) -> Self:
        return cls(items=[InspectionResponse.from_record(item) for item in result.items],
                   total=result.total, limit=result.limit, offset=result.offset)


class TaskList(ContractModel):
    items: list[TaskRecord]
    total: NonNegativeInt
    limit: Annotated[PositiveInt, Field(le=100)]
    offset: NonNegativeInt
    input_revision: NonNegativeInt
