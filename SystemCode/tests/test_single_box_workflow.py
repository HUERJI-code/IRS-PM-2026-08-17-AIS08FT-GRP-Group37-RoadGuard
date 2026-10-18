"""Public one-box views, primary-only confidence gates and persistent task safety."""

from concurrent.futures import ThreadPoolExecutor
import json

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from roadguard.config import load_settings
from roadguard.errors import AppError
from auth_test_support import create_app
from roadguard.schemas.workflow import InspectionRecord, InspectionResponse, ReviewRequest
from roadguard.tasks import TaskQueryService
from roadguard.vision.primary import PrimaryPolicy
from test_real_vision import FakeDetector, image, metadata, png, service


class TwoDetections(FakeDetector):
    primary_policy = PrimaryPolicy("area_quarter", .2)

    def detect(self, image):
        main = super().detect(image)[0]
        secondary = main.model_copy(update={"detection_id": "secondary", "confidence": .99,
                                           "bbox_xyxy": (1., 1., 3., 3.)})
        return [secondary, main]


@pytest.mark.parametrize("score,accepted", [(.59, False), (.6, True)])
def test_gate_uses_primary_raw_confidence_not_best_score_or_ranking(service, image, score, accepted):
    service.real_detector = TwoDetections(score)
    result = service.create(metadata(), image, "primary")
    assert len(result.inspection.detections) == 2
    assert result.inspection.primary_suggestion.detection_id == "real-test-0"
    assert result.inspection.primary_suggestion.ranking_score < .6
    assert (result.task is not None) == accepted
    view = InspectionResponse.from_record(result.inspection)
    assert len(view.detections) == 1 and view.detections[0].confidence == score
    assert len(service.get_inspection(result.inspection.inspection_id).detections) == 2


def test_auto_task_is_exactly_once_including_concurrent_replay_and_restart(service, image):
    service.real_detector = TwoDetections(.6)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: service.create(metadata(), image, "auto"), range(4)))
    assert service.real_detector.calls == 1
    assert sum(item.planning_input_changed for item in results) == 1
    assert len({item.task.task_id for item in results}) == 1
    assert all(item.input_revision == 1 for item in results)
    snapshot = TaskQueryService(service.database).snapshot()
    assert len(snapshot.tasks) == 1 and snapshot.tasks[0].task_id == results[0].task.task_id
    service.real_detector = None
    replay = service.create(metadata(), image, "auto")
    assert replay.replayed and not replay.planning_input_changed
    assert replay.inspection.auto_acceptance.confidence_threshold == .6
    with pytest.raises(AppError) as error:
        service.review(replay.inspection.inspection_id, ReviewRequest(
            request_id="again", expected_version=1, action="confirm", detection_id="real-test-0"))
    assert error.value.code == "invalid_state"


@pytest.mark.parametrize("change", ["missing", "lower_confidence", "wrong_threshold", "demo", "pending"])
def test_invalid_automatic_acceptance_cannot_bypass_persisted_provenance(service, image, change):
    service.real_detector = FakeDetector(.6)
    data = service.create(metadata(), image, "auto").inspection.model_dump()
    if change == "missing":
        data.pop("auto_acceptance")
    elif change == "lower_confidence":
        data["detections"][0]["confidence"] = .599999
    elif change == "wrong_threshold":
        data["auto_acceptance"]["confidence_threshold"] = .7
    elif change == "demo":
        data["mode"] = "demo"
    else:
        data.update(status="pending_review", task_id=None, selected_detection_id=None)
    with pytest.raises(ValidationError):
        InspectionRecord.model_validate(data)


def test_http_auto_upload_get_list_replay_all_have_one_box_and_raw_db_is_unchanged(tmp_path):
    settings = load_settings({"ROADGUARD_DB_PATH": str(tmp_path / "workflow.sqlite3")})
    with TestClient(create_app(settings)) as client:
        workflow = client.app.state.workflow_service
        workflow.real_detector = TwoDetections(.6)
        request = dict(data={"metadata": json.dumps(metadata().model_dump(exclude_none=True))},
                       files={"image": ("photo.png", png(), "image/png")},
                       headers={"Idempotency-Key": "single-auto"})
        created = client.post("/api/v1/inspections", **request)
        assert created.status_code == 201, created.text
        result = created.json()
        assert set(result) == {"inspection_id", "status", "detection", "task_id"}
        assert set(result["detection"]) == {"label", "confidence", "bbox_xyxy", "image_width", "image_height"}
        record = client.get(f'/api/v1/inspections/{result["inspection_id"]}').json()
        assert len(record["detections"]) == 1 and record["status"] == "accepted"
        task = client.get(f'/api/v1/tasks/{result["task_id"]}').json()
        assert task["history"][0]["actor_source"] == "system_confidence_policy"
        assert record["auto_acceptance"]["confidence_threshold"] == .6
        identifier = record["inspection_id"]
        assert client.get(f"/api/v1/inspections/{identifier}").json() == record
        assert client.get("/api/v1/inspections").json()["items"] == [record]
        replay = client.post("/api/v1/inspections", **request)
        assert replay.status_code == 200 and replay.json() == result
        assert client.get("/api/v1/tasks/snapshot").json()["input_revision"] == 1
        with workflow.database.connect() as connection:
            stored = json.loads(connection.execute("SELECT record_json FROM inspections").fetchone()[0])
        assert len(stored["detections"]) == 2
        openapi = client.get("/openapi.json").json()
        schema = openapi["components"]["schemas"]["InspectionResponse"]
        assert schema["properties"]["detections"]["maxItems"] == 1
        upload_schema = openapi["components"]["schemas"]["InspectionUploadResponse"]
        assert set(upload_schema["properties"]) == {"inspection_id", "status", "detection", "task_id"}
        for status in ("200", "201"):
            assert openapi["paths"]["/api/v1/inspections"]["post"]["responses"][status]["content"]["application/json"]["schema"] == {
                "$ref": "#/components/schemas/InspectionUploadResponse"}
    with TestClient(create_app(settings)) as client:
        assert client.get(f"/api/v1/inspections/{identifier}").json() == record
        assert len(client.get("/api/v1/tasks/snapshot").json()["tasks"]) == 1


def test_review_of_another_retained_candidate_returns_only_the_accepted_box(service, image):
    service.real_detector = TwoDetections(.59)
    created = service.create(metadata(), image, "low")
    reviewed = service.review(created.inspection.inspection_id, ReviewRequest(
        request_id="review-secondary", expected_version=1, action="confirm", detection_id="secondary"))
    view = InspectionResponse.from_record(reviewed.inspection)
    assert [d.detection_id for d in view.detections] == ["secondary"]
    assert view.primary_suggestion.detection_id == "real-test-0"
    assert view.auto_acceptance is None
    assert len(service.get_inspection(view.inspection_id).detections) == 2


def test_ambiguity_is_retained_as_warning_without_overriding_requested_gate(service, image):
    detector = FakeDetector(.8)
    detector.primary_policy = PrimaryPolicy("area_quarter", .2)
    original = detector.detect
    def detect(prepared):
        first = original(prepared)[0]
        return [first, first.model_copy(update={"detection_id": "rival", "class_id": 4, "label": "alligator_crack"})]
    detector.detect = detect
    service.real_detector = detector
    record = service.create(metadata(), image, "ambiguous").inspection
    assert record.status == "accepted" and record.primary_suggestion.ambiguous
    view = InspectionResponse.from_record(record)
    assert len(view.detections) == 1 and view.primary_suggestion.competing_detection_ids == ["real-test-0", "rival"]
