"""Contract boundaries and synthetic fixture consistency; no business-service mocks."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from roadguard.schemas import (
    Detection, ErrorResponse, HealthResponse, Inspection, PlanningRevision, Task,
)

SYSTEM_CODE = Path(__file__).resolve().parents[1]
EXAMPLES = SYSTEM_CODE / "contracts" / "examples"
MODEL_TYPES = {
    model.__name__: model
    for model in (Inspection, Task, ErrorResponse, HealthResponse, PlanningRevision)
}
MANIFEST = json.loads((EXAMPLES / "manifest.json").read_text(encoding="utf-8"))


def fixture(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def detection() -> dict:
    return fixture("demo_inspection_accepted.json")["detections"][0]


@pytest.mark.parametrize("name,model_name", MANIFEST["examples"].items())
def test_all_fixed_examples_validate_and_round_trip(name, model_name):
    model = MODEL_TYPES[model_name]
    raw = (EXAMPLES / name).read_text(encoding="utf-8")
    value = model.model_validate_json(raw)
    assert model.model_validate_json(value.model_dump_json()) == value


def test_fixture_snapshot_links_and_demo_provenance():
    assert MANIFEST["is_demo"] is True
    accepted = Inspection.model_validate(fixture("demo_inspection_accepted.json"))
    task = Task.model_validate(fixture("demo_task.json"))
    assert accepted.task_id == task.task_id
    assert task.inspection_id == accepted.inspection_id
    selected = next(d for d in accepted.detections if d.detection_id == accepted.selected_detection_id)
    assert task.damage_label == selected.label
    assert (task.latitude, task.longitude) == (accepted.latitude, accepted.longitude)
    assert task.rule_version == accepted.decision_trace[0].rule_version
    assert task.is_demo and accepted.is_demo and selected.is_demo
    for name, model in MANIFEST["examples"].items():
        if model == "Inspection":
            value = Inspection.model_validate(fixture(name))
            assert value.is_demo
            assert all(d.is_demo for d in value.detections)
            assert all(trace.is_demo for trace in value.decision_trace)
            if value.status != "accepted":
                assert value.task_id is None
    health = fixture("demo_health.json")
    revision = fixture("demo_planning_revision.json")
    assert health["input_revision"] == revision["input_revision"] == 1


def test_all_eight_labels_come_from_the_central_table():
    labels = json.loads((SYSTEM_CODE / "model" / "label_schema.json").read_text(encoding="utf-8"))
    assert {entry["class_id"] for entry in labels["classes"]} == set(range(8))
    for entry in labels["classes"]:
        payload = detection() | {"class_id": entry["class_id"], "label": entry["label_key"]}
        assert Detection.model_validate(payload).label == entry["label_key"]


@pytest.mark.parametrize("change", [
    {"class_id": 8}, {"class_id": -1}, {"class_id": True}, {"class_id": 6.0},
    {"class_id": "6"}, {"label": "D40"}, {"label": "pothole_deep"},
    {"confidence": -0.1}, {"confidence": 1.01}, {"confidence": "0.9"},
    {"confidence": True}, {"confidence": float("nan")}, {"confidence": float("inf")},
    {"image_width": 0}, {"image_height": -1}, {"image_width": "640"},
    {"image_height": True}, {"is_demo": 1}, {"detection_id": "   "},
    {"model_version": ""}, {"unknown": "field"},
    {"bbox_xyxy": [0, 0, 0, 100]}, {"bbox_xyxy": [20, 0, 10, 100]},
    {"bbox_xyxy": [-1, 0, 20, 100]}, {"bbox_xyxy": [0, 0, 641, 100]},
    {"bbox_xyxy": [0, 0, 20, 481]}, {"bbox_xyxy": [0, 0, 20]},
    {"bbox_xyxy": [0, 0, "20", 100]}, {"bbox_xyxy": [False, 0, 20, 100]},
])
def test_detection_rejects_invalid_source_numeric_and_box_values(change):
    with pytest.raises(ValidationError):
        Detection.model_validate(detection() | change)


def test_detection_accepts_full_image_pixel_boundary_and_confidence_edges():
    for confidence in (0, 1):
        payload = detection() | {"bbox_xyxy": [0, 0, 640, 480], "confidence": confidence}
        assert Detection.model_validate_json(json.dumps(payload)).confidence == confidence


@pytest.mark.parametrize("change", [
    {"selected_detection_id": "missing"}, {"selected_detection_id": None},
    {"task_id": None}, {"status": "pending_review"}, {"status": "rejected"},
    {"status": "no_detection"}, {"detections": []}, {"is_demo": False},
    {"inspection_id": ""}, {"latitude": 90.1}, {"longitude": -180.1},
    {"latitude": "1.34"}, {"longitude": True}, {"latitude": float("nan")},
])
def test_accepted_inspection_rejects_invalid_links_and_coordinates(change):
    with pytest.raises(ValidationError):
        Inspection.model_validate(fixture("demo_inspection_accepted.json") | change)


def test_duplicate_detection_ids_are_rejected():
    payload = fixture("demo_inspection_accepted.json")
    payload["detections"].append(payload["detections"][0].copy())
    with pytest.raises(ValidationError, match="unique"):
        Inspection.model_validate(payload)


def test_real_detection_with_demo_rules_preserves_mixed_provenance():
    payload = fixture("demo_inspection_accepted.json")
    payload["detections"][0]["is_demo"] = False
    value = Inspection.model_validate(payload)
    assert value.is_demo and not value.detections[0].is_demo
    assert value.decision_trace[0].is_demo


@pytest.mark.parametrize("status", ["pending_review", "rejected"])
def test_unaccepted_inspection_requires_detection_and_no_task(status):
    payload = fixture("demo_inspection_pending_review.json") | {"status": status}
    assert Inspection.model_validate(payload).task_id is None
    for change in ({"task_id": "task-unaccepted"}, {"detections": []}):
        with pytest.raises(ValidationError):
            Inspection.model_validate(payload | change)


def test_no_detection_cannot_acquire_a_task_or_selection():
    payload = fixture("demo_inspection_no_detection.json")
    for change in ({"task_id": "task-empty"}, {"selected_detection_id": "missing"}):
        with pytest.raises(ValidationError):
            Inspection.model_validate(payload | change)


@pytest.mark.parametrize("change", [
    {"service_minutes": 0}, {"service_minutes": -1}, {"service_minutes": True},
    {"service_minutes": "45"}, {"service_minutes": float("inf")},
    {"severity": "deep"}, {"priority": "urgent"}, {"status": "pending_review"},
    {"damage_label": "D40"}, {"task_id": ""}, {"inspection_id": " "},
    {"latitude": -90.1}, {"longitude": 180.1}, {"is_demo": "true"},
    {"rule_version": ""},
])
def test_task_rejects_invalid_vocabulary_numeric_values_and_ids(change):
    with pytest.raises(ValidationError):
        Task.model_validate(fixture("demo_task.json") | change)


def test_unknown_service_time_and_deadline_remain_null():
    task = Task.model_validate(fixture("demo_task.json") | {"service_minutes": None})
    assert task.model_dump(mode="json")["service_minutes"] is None
    assert task.due_at is None


def test_timestamps_normalize_offset_and_python_datetime_to_utc():
    payload = fixture("demo_task.json") | {
        "created_at": "2026-10-12T10:00:00+08:00",
        "due_at": datetime(2026, 10, 12, 11, tzinfo=timezone(timedelta(hours=8))),
    }
    task = Task.model_validate(payload)
    output = task.model_dump(mode="json")
    assert output["created_at"] == "2026-10-12T02:00:00Z"
    assert output["due_at"] == "2026-10-12T03:00:00Z"


@pytest.mark.parametrize("field", ["created_at", "due_at"])
@pytest.mark.parametrize("value", [
    "2026-10-12T10:00:00", datetime(2026, 10, 12), 1791763200, True,
    "1", "1791763200", "1791763200.5", "20261012", "2026-10-12",
])
def test_timestamps_reject_naive_or_numeric_inputs(field, value):
    with pytest.raises(ValidationError):
        Task.model_validate(fixture("demo_task.json") | {field: value})


@pytest.mark.parametrize("value", [-1, True, "1", 1.0])
def test_revision_rejects_negative_or_coerced_values(value):
    with pytest.raises(ValidationError):
        PlanningRevision(input_revision=value)


def test_revision_zero_and_health_literals():
    assert PlanningRevision(input_revision=0).input_revision == 0
    assert HealthResponse(status="ok", database="ok", input_revision=0).api_version == "v1"
    for change in ({"status": "ready"}, {"database": "failed"}, {"api_version": "v2"}):
        with pytest.raises(ValidationError):
            HealthResponse.model_validate(fixture("demo_health.json") | change)


@pytest.mark.parametrize("details", [
    "raw exception", ("tuple",), {1: "non-string key"}, {"value": object()},
    {"value": float("nan")}, {"nested": [float("inf")]},
])
def test_error_details_reject_non_json_metadata(details):
    with pytest.raises(ValidationError):
        ErrorResponse(code="INVALID_INPUT", message="Invalid input.", details=details)


def test_error_details_allow_nullable_and_nested_json_metadata():
    assert ErrorResponse(code="INVALID_INPUT", message="Invalid input.").details is None
    details = [{"field": "latitude", "error_count": 1, "nested": [None, True, 1.5]}]
    response = ErrorResponse(code="INVALID_INPUT", message="Invalid input.", details=details)
    assert json.loads(response.model_dump_json())["details"] == details
