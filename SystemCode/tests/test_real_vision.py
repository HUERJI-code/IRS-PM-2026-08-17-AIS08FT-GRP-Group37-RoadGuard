"""Local inference safety and genuine/demonstration provenance, without YOLO."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import io
import json
import sqlite3
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError
import pytest

from roadguard.config import REPOSITORY_ROOT, load_settings
from roadguard.database import Database
from roadguard.errors import AppError
from roadguard.geography import JurongScope
from roadguard.images import ImageStore
from roadguard.inspections import WorkflowService
from auth_test_support import create_app
from roadguard.rules import RuleService, load_rule_policy
from roadguard.schemas import Detection
from roadguard.schemas.workflow import InspectionRecord, ReviewRequest, UploadMetadata
from roadguard.tasks import TaskQueryService
from roadguard.vision import DemoDetector
from roadguard.vision.real import LocalVisionDetector, source_class_names
from roadguard.vision.primary import PrimaryPolicy


def png(width=80, height=60):
    output = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(output, format="PNG")
    return output.getvalue()


def metadata(**changes):
    data = dict(mode="real", latitude=1.3405, longitude=103.706, road_type="public_motor_road")
    data.update(changes)
    return UploadMetadata.model_validate(data)


class FakeDetector:
    model_version = "rdd2022es-experimental-test-v1"
    weights_sha256 = "a" * 64
    manifest_version = "roadguard-model-v1"

    def __init__(self, confidence=0.55):
        self.confidence, self.calls = confidence, 0
        self.on_detect = None

    def detect(self, image):
        self.calls += 1
        if self.on_detect:
            self.on_detect()
        if self.confidence is None:
            return []
        return [Detection(detection_id="real-test-0", class_id=6, label="pothole", confidence=self.confidence,
                          bbox_xyxy=(1, 1, image.width - 1, image.height - 1),
                          image_width=image.width, image_height=image.height,
                          model_version=self.model_version, is_demo=False)]


@pytest.fixture
def service(tmp_path):
    database = Database(tmp_path / "db.sqlite3")
    database.initialize()
    rules = RuleService(load_rule_policy(REPOSITORY_ROOT / "SystemCode/config/demo_rules.example.json"))
    return WorkflowService(database, rules, DemoDetector(), JurongScope(), ImageStore(tmp_path / "images"),
                           real_detector=FakeDetector())


@pytest.fixture
def image(service):
    return service.images.prepare(png())


@pytest.mark.parametrize("confidence", [0.05, 0.59, 0.599999, 0.60, 0.600001, 0.99])
def test_real_primary_uses_inclusive_confidence_gate(service, image, confidence):
    service.real_detector.confidence = confidence
    result = service.create(metadata(), image, "real")
    assert result.inspection.mode == "real" and result.inspection.demo_scenario_id is None
    assert result.inspection.is_demo and not result.inspection.detections[0].is_demo
    accepted = confidence >= .6
    assert result.inspection.status == ("accepted" if accepted else "pending_review")
    assert (result.task is not None) == accepted
    assert result.input_revision == int(accepted) and result.planning_input_changed == accepted
    assert result.inspection.model_weights_sha256 == "a" * 64
    codes = {trace.code for trace in result.inspection.decision_trace}
    assert ("real_primary_auto_accepted" if accepted else "real_primary_review_required") in codes
    if accepted:
        assert result.inspection.auto_acceptance.confidence_threshold == .6
        assert result.task.history[0].actor_source == "system_confidence_policy"
        assert result.inspection.review_history == []
    assert service.get_inspection(result.inspection.inspection_id) == result.inspection


def test_real_no_detection_has_no_task_and_cannot_be_confirmed(service, image):
    service.real_detector.confidence = None
    result = service.create(metadata(), image, "empty")
    assert result.inspection.status == "no_detection" and result.inspection.detections == []
    assert result.task is None and result.input_revision == 0
    with pytest.raises(AppError) as error:
        service.review(result.inspection.inspection_id, ReviewRequest(request_id="review", expected_version=1, action="dismiss"))
    assert error.value.code == "invalid_state"


def test_review_real_evidence_creates_demo_business_task_and_snapshot(service, image):
    initial = service.create(metadata(), image, "real")
    original = initial.inspection.detections[0]
    reviewed = service.review(initial.inspection.inspection_id, ReviewRequest(
        request_id="review", expected_version=1, action="correct", detection_id=original.detection_id,
        damage_label="pothole_deep"))
    assert reviewed.task.is_demo and reviewed.task.damage_label == "pothole_deep"
    assert reviewed.inspection.detections[0] == original
    assert reviewed.inspection.is_demo and reviewed.inspection.mode == "real"
    assert reviewed.input_revision == 1
    snapshot = TaskQueryService(service.database).snapshot()
    assert snapshot.is_demo and snapshot.tasks[0].is_demo
    assert snapshot.tasks[0].task_id == reviewed.task.task_id


def test_restart_and_replay_do_not_require_available_real_detector(service, image):
    initial = service.create(metadata(), image, "real")
    restarted = WorkflowService(service.database, service.rules, service.detector, service.scope, service.images)
    assert restarted.get_inspection(initial.inspection.inspection_id) == initial.inspection
    replay = restarted.create(metadata(), image, "real")
    assert replay.replayed and replay.inspection == initial.inspection
    with pytest.raises(AppError) as error:
        restarted.create(metadata(), image, "new")
    assert error.value.code == "detector_unavailable"
    assert restarted.list_inspections().total == 1


def test_duplicate_inference_single_flight_and_not_under_database_write_lock(service, image):
    def check_other_write_can_acquire():
        with service.database.transaction() as connection:
            connection.execute("SELECT COUNT(*) FROM inspections").fetchone()
    service.real_detector.on_detect = check_other_write_can_acquire
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: service.create(metadata(), image, "real"), range(4)))
    assert service.real_detector.calls == 1
    assert sum(not item.replayed for item in results) == 1
    assert len(list(service.images.root.glob("*.png"))) == 1
    assert service._create_locks == {}


@pytest.mark.parametrize("confidence", [.55, .8])
def test_real_persistence_failure_rolls_back_image_record_and_key(service, image, monkeypatch, confidence):
    service.real_detector.confidence = confidence
    transaction = service.database.transaction
    @contextmanager
    def fail_transaction(*args, **kwargs):
        with transaction(*args, **kwargs) as connection:
            yield connection
            raise sqlite3.OperationalError("private detail")
    monkeypatch.setattr(service.database, "transaction", fail_transaction)
    with pytest.raises(AppError) as error:
        service.create(metadata(), image, "real")
    assert error.value.code == "database_unavailable"
    assert service.list_inspections().total == 0 and service.list_tasks().input_revision == 0
    assert list(service.images.root.glob("*.png")) == []
    with service.database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM operation_keys").fetchone()[0] == 0


@pytest.mark.parametrize("changes", [
    {"scenario_id": "high_confidence"}, {"scenario_id": None}, {"mode": "demo"},
    {"mode": "automatic"}, {"model_version": "custom"},
])
def test_upload_metadata_rejects_invalid_mode_combinations(changes):
    with pytest.raises(ValidationError):
        metadata(**changes)


@pytest.mark.parametrize("field,value", [
    ("demo_scenario_id", "high_confidence"), ("model_weights_sha256", None),
    ("model_manifest_version", None), ("model_version", "demo-detector-v1"),
])
def test_persisted_real_provenance_is_validated(service, image, field, value):
    record = service.create(metadata(), image, "real").inspection.model_dump()
    record[field] = value
    with pytest.raises(ValidationError):
        InspectionRecord.model_validate(record)


class Tensor:
    def __init__(self, data):
        self.data = data
    def cpu(self):
        return self
    def tolist(self):
        return self.data


class FakeModel:
    task = "detect"
    def __init__(self):
        self.names = dict(enumerate(source_class_names()))
        self.coordinates, self.classes, self.scores = [[1., 2., 40., 50.]], [6.], [0.8]
        self.options = None
    def predict(self, **options):
        self.options = options
        source = options["source"]
        return [SimpleNamespace(orig_shape=(source.height, source.width), boxes=SimpleNamespace(
            xyxy=Tensor(self.coordinates), cls=Tensor(self.classes), conf=Tensor(self.scores)))]


@pytest.fixture
def local_manifest(tmp_path):
    weights = tmp_path / "weights.pt"
    weights.write_bytes(b"test-only artifact; never deserialized")
    payload = dict(schema_version="roadguard-model-v1", model_version="rdd2022es-test-v1",
                   status="experimental", weights_path=str(weights),
                   weights_sha256=hashlib.sha256(weights.read_bytes()).hexdigest(),
                   source_class_names=source_class_names(),
                   source_dataset={"ref": "juusos/rdd2022es", "version": 1, "manifest_sha256": "b" * 64},
                   inference={"conf": 0.25, "iou": 0.7, "imgsz": 640}, evaluation_path="test-eval.json")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, payload


def test_local_detector_lazy_load_exact_names_digest_pixel_dimensions(local_manifest, service, image):
    path, payload = local_manifest
    model, calls = FakeModel(), []
    def loader(path, **options):
        calls.append((path, options))
        return model
    detector = LocalVisionDetector(path, model_loader=loader)
    assert not calls
    detections = detector.detect(image)
    detector.detect(image)
    assert len(calls) == 1 and calls[0][1] == {"task": "detect"}
    assert detections[0].label == "pothole" and not detections[0].is_demo
    assert detections[0].bbox_xyxy == (1., 2., 40., 50.)
    assert detector.weights_sha256 == payload["weights_sha256"]
    assert model.options["device"] == "cpu" and model.options["max_det"] == 100
    assert model.options["save"] is False and model.options["stream"] is False
    assert isinstance(model.options["source"], Image.Image)
    assert model.options["quantize"] is None
    assert detector.primary_policy is None


def test_released_default_manifest_and_explicit_disable():
    assert load_settings({}).vision_manifest_path == REPOSITORY_ROOT / "SystemCode/model/releases/roadguard-single-v1.json"
    assert load_settings({"ROADGUARD_VISION_MANIFEST_PATH": "disabled"}).vision_manifest_path is None


@pytest.mark.parametrize("state", ["present", "missing", "corrupt"])
def test_default_model_folder_loads_directly_without_cwd_or_old_dataset_fallback(tmp_path, monkeypatch, image, state):
    import roadguard.vision.real as real

    monkeypatch.chdir(tmp_path)
    payload = json.loads(load_settings({}).vision_manifest_path.read_text(encoding="utf-8"))
    relative = "SystemCode/backend/roadguard/model/roadguard-yolo11s-single-v1.pt"
    assert payload["weights_path"] == relative
    contents = b"test-only approved weight; never deserialized"
    payload["weights_sha256"] = hashlib.sha256(contents).hexdigest()
    payload["weights_bytes"] = len(contents)
    destination = tmp_path / relative
    destination.parent.mkdir(parents=True)
    if state != "missing":
        destination.write_bytes(contents if state == "present" else b"wrong model")
    old_weight = tmp_path / "Dataset/models/roadguard-yolo11s-single-v1.pt"
    old_weight.parent.mkdir(parents=True)
    old_weight.write_bytes(contents)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    model, calls = FakeModel(), []

    def loader(path, **options):
        calls.append(path)
        return model

    monkeypatch.setattr(real, "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(real, "source_class_names", lambda: payload["source_class_names"])
    detector = LocalVisionDetector(manifest, model_loader=loader)
    if state == "present":
        assert detector.detect(image)[0].label == "pothole"
        assert calls == [str(destination.resolve())]
    else:
        with pytest.raises(AppError) as error:
            detector.detect(image)
        assert error.value.code == "detector_unavailable"
        assert calls == []


def test_manifest_primary_policy_is_validated_before_loading(local_manifest, image):
    path, payload = local_manifest
    payload["primary_policy"] = {"policy_version": "single-damage-v1", "strategy": "area_quarter", "threshold": .25}
    path.write_text(json.dumps(payload))
    detector = LocalVisionDetector(path, model_loader=lambda *a, **k: FakeModel())
    detector.detect(image)
    assert detector.primary_policy == PrimaryPolicy("area_quarter", .25)


@pytest.mark.parametrize("policy", [None, [], {},
    {"policy_version": "single-damage-v2", "strategy": "area_quarter", "threshold": .25},
    {"policy_version": "single-damage-v1", "strategy": "unknown", "threshold": .25},
    {"policy_version": "single-damage-v1", "strategy": "area_quarter", "threshold": .2},
    {"policy_version": "single-damage-v1", "strategy": "area_quarter", "threshold": .25, "auto_accept": True},
])
def test_malformed_primary_policy_never_loads_weights(local_manifest, image, policy):
    path, payload = local_manifest
    payload["primary_policy"] = policy
    path.write_text(json.dumps(payload))
    calls = []
    detector = LocalVisionDetector(path, model_loader=lambda *a, **k: calls.append(a))
    with pytest.raises(AppError) as error:
        detector.detect(image)
    assert error.value.status_code == 503 and not calls


def test_primary_suggestion_remains_separate_from_acceptance_and_survives_restart(service, image):
    service.real_detector.primary_policy = PrimaryPolicy("area_quarter", .2)
    initial = service.create(metadata(), image, "suggestion")
    suggestion = initial.inspection.primary_suggestion
    assert suggestion.detection_id == initial.inspection.detections[0].detection_id
    assert initial.inspection.selected_detection_id is None
    assert initial.inspection.status == "pending_review" and initial.task is None and initial.input_revision == 0
    restarted = WorkflowService(service.database, service.rules, service.detector, service.scope, service.images)
    replay = restarted.create(metadata(), image, "suggestion")
    assert replay.replayed and replay.inspection.primary_suggestion == suggestion
    reviewed = restarted.review(initial.inspection.inspection_id, ReviewRequest(
        request_id="confirm-primary", expected_version=1, action="confirm", detection_id=suggestion.detection_id))
    assert reviewed.inspection.primary_suggestion == suggestion and reviewed.task is not None
    assert reviewed.input_revision == 1


def test_empty_primary_suggestion_and_legacy_records(service, image):
    service.real_detector.primary_policy = PrimaryPolicy("area_quarter", .2)
    service.real_detector.confidence = None
    record = service.create(metadata(), image, "empty-primary").inspection
    assert record.primary_suggestion.detection_id is None and record.status == "no_detection"
    old = record.model_dump()
    del old["primary_suggestion"]
    assert InspectionRecord.model_validate(old).primary_suggestion is None


def test_foreign_primary_id_rejected(service, image):
    service.real_detector.primary_policy = PrimaryPolicy("area_quarter", .2)
    record = service.create(metadata(), image, "bad-primary").inspection.model_dump()
    record["primary_suggestion"]["detection_id"] = "another-inspection"
    with pytest.raises(ValidationError):
        InspectionRecord.model_validate(record)


@pytest.mark.parametrize("changes", [
    {"weights_sha256": "0" * 64}, {"weights_path": "https://example.com/model.pt"},
    {"source_class_names": ["person"] * 8}, {"source_class_names": source_class_names()[::-1]},
    {"schema_version": "unknown"}, {"inference": {"conf": 0.25, "iou": 0.7, "imgsz": 100000}},
])
def test_invalid_manifest_never_loads_downloads_or_falls_back(local_manifest, image, changes):
    path, payload = local_manifest
    payload.update(changes)
    path.write_text(json.dumps(payload), encoding="utf-8")
    calls = []
    detector = LocalVisionDetector(path, model_loader=lambda *a, **k: calls.append(a))
    with pytest.raises(AppError) as error:
        detector.detect(image)
    assert error.value.code == "detector_unavailable" and error.value.status_code == 503
    assert calls == []


def test_checkpoint_coco_names_cannot_be_relabelled_as_road_damage(local_manifest, image):
    model = FakeModel()
    model.names = dict(enumerate(["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck"]))
    detector = LocalVisionDetector(local_manifest[0], model_loader=lambda *a, **k: model)
    with pytest.raises(AppError) as error:
        detector.detect(image)
    assert error.value.code == "detector_unavailable" and model.options is None


@pytest.mark.parametrize("coordinates,classes,scores", [
    ([[-1., 2., 40., 50.]], [6.], [0.8]), ([[1., 2., 81., 50.]], [6.], [0.8]),
    ([[1., 2., 40., 50.]], [8.], [0.8]), ([[1., 2., 40., 50.]], [6.5], [0.8]),
    ([[1., 2., 40., 50.]], [6.], [float("nan")]), ([[1., 2., 40., 50.]], [], []),
])
def test_invalid_prediction_is_502_never_clipped_or_saved(local_manifest, image, coordinates, classes, scores):
    model = FakeModel()
    model.coordinates, model.classes, model.scores = coordinates, classes, scores
    detector = LocalVisionDetector(local_manifest[0], model_loader=lambda *a, **k: model)
    with pytest.raises(AppError) as error:
        detector.detect(image)
    assert error.value.status_code == 502 and error.value.code == "detector_inference_failed"


def test_missing_dependency_returns_503_without_affecting_demo(local_manifest, service, image, monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "ultralytics", None)
    service.real_detector = LocalVisionDetector(local_manifest[0])
    with pytest.raises(AppError) as error:
        service.create(metadata(), image, "real")
    assert error.value.code == "detector_unavailable" and service.list_inspections().total == 0
    demo = service.create(metadata(mode="demo", scenario_id="high_confidence"), image, "demo")
    assert demo.inspection.mode == "demo" and demo.task is not None


def test_runtime_configuration_filters_supported_integrations(local_manifest, image, monkeypatch):
    import os
    import sys
    class Settings(dict):
        def update(self, changes):
            assert set(changes) <= set(self)
            super().update(changes)
    settings = Settings(sync=True, clearml=True, wandb=True)
    model = FakeModel()
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(
        YOLO=lambda *a, **k: model, settings=settings))
    for name in ("YOLO_OFFLINE", "YOLO_AUTOINSTALL", "YOLO_CONFIG_DIR"):
        monkeypatch.setenv(name, "test-original-value")
    LocalVisionDetector(local_manifest[0]).detect(image)
    assert not any(settings.values())
    assert os.environ["YOLO_OFFLINE"] == "true" and os.environ["YOLO_AUTOINSTALL"] == "false"
    assert os.environ["YOLO_CONFIG_DIR"].endswith("ultralytics-backend")


def test_exif_normalized_dimensions_are_model_and_persisted_dimensions(service):
    output = io.BytesIO()
    source = Image.new("RGB", (80, 60), "white")
    exif = source.getexif()
    exif[274] = 6
    source.save(output, format="JPEG", exif=exif)
    image = service.images.prepare(output.getvalue())
    assert (image.width, image.height) == (60, 80)
    record = service.create(metadata(), image, "oriented").inspection
    assert (record.image_width, record.image_height) == (60, 80)
    assert (record.detections[0].image_width, record.detections[0].image_height) == (60, 80)


def test_inference_exception_has_no_synthetic_fallback_or_saved_image(service, image):
    def fail():
        raise RuntimeError("private runtime path / credential")
    service.real_detector.on_detect = fail
    with pytest.raises(AppError) as error:
        service.create(metadata(), image, "failed")
    assert error.value.code == "detector_inference_failed" and error.value.status_code == 502
    assert "private" not in str(error.value)
    assert service.list_inspections().total == 0 and service.list_tasks().input_revision == 0
    assert not service.images.root.exists()


def test_http_real_upload_review_snapshot_restart_and_errors(tmp_path):
    settings = load_settings({"ROADGUARD_DB_PATH": str(tmp_path / "db.sqlite3")})
    with TestClient(create_app(settings)) as client:
        client.app.state.workflow_service.real_detector = FakeDetector()
        form = {"metadata": json.dumps(metadata().model_dump(exclude_none=True))}
        response = client.post("/api/v1/inspections", data=form, files={"image": ("photo.png", png())},
                               headers={"Idempotency-Key": "http-real"})
        assert response.status_code == 201
        summary = response.json()
        record = client.get(f'/api/v1/inspections/{summary["inspection_id"]}').json()
        assert record["mode"] == "real" and record["is_demo"] and not record["detections"][0]["is_demo"]
        client.app.state.workflow_service.real_detector = None
        replay = client.post("/api/v1/inspections", data=form, files={"image": ("photo.png", png())},
                             headers={"Idempotency-Key": "http-real"})
        assert replay.status_code == 200 and replay.json() == summary
        unavailable = client.post("/api/v1/inspections", data=form, files={"image": ("photo.png", png())},
                                  headers={"Idempotency-Key": "new"})
        assert unavailable.status_code == 503 and unavailable.json()["code"] == "detector_unavailable"
        review = client.post(f"/api/v1/inspections/{record['inspection_id']}/review", json={
            "request_id": "confirm", "expected_version": 1, "action": "confirm",
            "detection_id": record["detections"][0]["detection_id"]})
        assert review.status_code == 200 and review.json()["task"]["is_demo"]
        assert client.get("/api/v1/tasks/snapshot").json()["is_demo"]
        invalid = client.post("/api/v1/inspections", data={"metadata": json.dumps({**metadata().model_dump(), "scenario_id": "high_confidence"})},
                              files={"image": ("photo.png", png())}, headers={"Idempotency-Key": "invalid"})
        assert invalid.status_code == 422
    with TestClient(create_app(settings)) as restarted:
        restored = restarted.get(f"/api/v1/inspections/{record['inspection_id']}")
        assert restored.status_code == 200 and restored.json()["mode"] == "real"
        assert restored.json()["model_weights_sha256"] == "a" * 64
