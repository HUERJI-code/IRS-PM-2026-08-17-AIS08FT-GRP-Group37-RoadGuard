"""Exercise real upload, review, persisted task and failure HTTP boundaries."""

from dataclasses import replace
import io
import json

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from roadguard.config import ConfigurationError, load_settings
from auth_test_support import create_app
from roadguard.images import MAX_UPLOAD_BYTES


@pytest.fixture
def settings(tmp_path):
    return load_settings({"ROADGUARD_DB_PATH": str(tmp_path / "workflow.sqlite3")})


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def png():
    stream = io.BytesIO()
    Image.new("RGB", (80, 40), "gray").save(stream, format="PNG")
    return stream.getvalue()


def metadata(scenario="low_confidence", **changes):
    return {"mode": "demo", "scenario_id": scenario, "latitude": 1.34,
            "longitude": 103.72, "road_type": "public_motor_road", **changes}


def upload(client, png, scenario="low_confidence", key="upload-1", **changes):
    return client.post("/api/v1/inspections", headers={"Idempotency-Key": key},
                       files={"image": ("../../untrusted-name.png", png, "image/png")},
                       data={"metadata": json.dumps(metadata(scenario, **changes))})


def test_upload_validation_survives_lazy_vision_decoder_patch(client, png, settings, monkeypatch):
    # Ultralytics 8.4.176 replaces Image.open on lazy model import. Its fallback
    # imports optional pi_heif after *any* decode error, including corrupt PNGs.
    # Exercise that interaction without installing vision dependencies in CI.
    pillow_open = Image.open

    def optional_format_fallback(*args, **kwargs):
        try:
            return pillow_open(*args, **kwargs)
        except Exception:
            raise ModuleNotFoundError("No module named 'pi_heif'") from None

    monkeypatch.setattr(Image, "open", optional_format_fallback)
    for index, data in enumerate((b"not a PNG image", png[:32])):
        response = upload(client, data, key=f"invalid-after-vision-{index}")
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "invalid_image"
    assert client.get("/api/v1/inspections").json()["total"] == 0
    assert client.get("/api/v1/tasks/snapshot").json()["total"] == 0
    assert client.get("/api/v1/health").json()["input_revision"] == 0
    assert not settings.upload_path.exists() or not list(settings.upload_path.iterdir())
    assert upload(client, png, key="valid-after-vision").status_code == 201


def test_upload_review_correction_task_completion_and_replay(client, png):
    response = upload(client, png)
    assert response.status_code == 201, response.text
    created = response.json()
    assert set(created) == {"inspection_id", "status", "detection", "task_id"}
    identifier = created["inspection_id"]
    inspection = client.get(f"/api/v1/inspections/{identifier}").json()
    assert inspection["status"] == created["status"] == "pending_review" and created["task_id"] is None
    assert inspection["is_demo"] is True and inspection["road_type_source"] == "user_declared"
    assert (inspection["image_width"], inspection["image_height"]) == (80, 40)
    original = inspection["detections"][0]
    assert original["confidence"] == 0.42 and original["image_width"] == 80
    assert original["bbox_xyxy"][2] <= 80 and original["bbox_xyxy"][3] <= 40
    assert created["detection"] == {key: original[key] for key in created["detection"]}
    assert client.get("/api/v1/tasks/snapshot").json()["input_revision"] == 0
    image = client.get(inspection["image_url"])
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"
    assert image.headers["x-content-type-options"] == "nosniff"
    with Image.open(io.BytesIO(image.content)) as stored:
        assert stored.size == (80, 40)
    review = {"request_id": "review-1", "expected_version": inspection["record_version"],
              "action": "correct", "detection_id": original["detection_id"], "damage_label": "pothole_deep",
              "note": "Selected the deeper pothole class for this demonstration."}
    response = client.post(f"/api/v1/inspections/{identifier}/review", json=review)
    assert response.status_code == 200, response.text
    accepted = response.json()
    assert accepted["inspection"]["status"] == "accepted"
    assert accepted["inspection"]["detections"][0] == original
    assert accepted["inspection"]["review_history"][0]["action"] == "correct"
    task = accepted["task"]
    assert task["damage_label"] == "pothole_deep" and task["priority"] == "P1"
    assert task["service_minutes"] == 240 and task["due_at"] is None
    assert task["inspection_id"] == identifier and accepted["input_revision"] == 1
    assert accepted["planning_input_changed"] and not accepted["replayed"]
    repeated = client.post(f"/api/v1/inspections/{identifier}/review", json=review).json()
    assert repeated["replayed"] and not repeated["planning_input_changed"]
    assert repeated["task"]["task_id"] == task["task_id"] and repeated["input_revision"] == 1
    task_id = task["task_id"]
    assert client.get(f"/api/v1/tasks/{task_id}").json() == task
    patch = {"request_id": "complete-1", "expected_version": task["record_version"], "status": "completed"}
    completed = client.patch(f"/api/v1/tasks/{task_id}", json=patch)
    assert completed.status_code == 200, completed.text
    assert completed.json()["task"]["status"] == "completed"
    assert completed.json()["input_revision"] == 2
    assert client.get("/api/v1/tasks").json()["items"] == []
    assert client.get("/api/v1/tasks?status=completed").json()["total"] == 1
    assert client.get(f"/api/v1/inspections/{identifier}").json()["task_id"] == task_id
    assert client.patch(f"/api/v1/tasks/{task_id}", json=patch).json()["replayed"]
    assert client.get("/api/v1/health").json()["input_revision"] == 2
    replayed_upload = upload(client, png)
    assert replayed_upload.status_code == 200
    assert replayed_upload.json()["status"] == "accepted"
    assert replayed_upload.json()["task_id"] == task_id


@pytest.mark.parametrize("scenario,status,has_task", [
    ("high_confidence", "accepted", True), ("low_confidence", "pending_review", False),
    ("no_detection", "no_detection", False), ("multiple_detections", "accepted", True),
    ("mixed_confidence", "pending_review", False), ("threshold_boundary", "accepted", True),
    ("below_threshold", "pending_review", False),
])
def test_all_scenarios_persist_with_correct_task_gate(client, png, scenario, status, has_task):
    response = upload(client, png, scenario)
    assert response.status_code == 201, response.text
    result = response.json()
    assert set(result) == {"inspection_id", "status", "detection", "task_id"}
    assert result["status"] == status
    assert (result["task_id"] is not None) is has_task
    assert (result["detection"] is None) == (status == "no_detection")
    assert client.get("/api/v1/tasks/snapshot").json()["input_revision"] == int(has_task)
    assert client.get("/api/v1/inspections").json()["total"] == 1
    assert client.get("/api/v1/tasks").json()["total"] == int(has_task)


def test_dismiss_keeps_inspection_history_without_task(client, png):
    inspection = upload(client, png).json()
    request = {"action": "dismiss", "request_id": "dismiss-1", "expected_version": 1, "note": "False positive."}
    url = f'/api/v1/inspections/{inspection["inspection_id"]}/review'
    response = client.post(url, json=request)
    assert response.status_code == 200, response.text
    assert response.json()["inspection"]["status"] == "rejected"
    assert response.json()["task"] is None and response.json()["input_revision"] == 0
    assert client.get("/api/v1/inspections?status=rejected").json()["total"] == 1
    assert client.post(url, json={**request, "request_id": "different", "expected_version": 2}).status_code == 409


def test_reused_upload_key_and_stale_task_versions_do_not_write(client, png):
    created = upload(client, png, "high_confidence").json()
    assert upload(client, png, "low_confidence").status_code == 409
    url = f'/api/v1/tasks/{created["task_id"]}'
    patch = {"request_id": "edit-1", "expected_version": 1, "damage_label": "pothole_deep"}
    edited = client.patch(url, json=patch)
    assert edited.status_code == 200, edited.text
    assert edited.json()["task"]["priority"] == "P1"
    stale = client.patch(url, json={"request_id": "stale", "expected_version": 1, "status": "cancelled"})
    assert stale.status_code == 409
    assert client.patch(url, json={**patch, "damage_label": "pothole"}).status_code == 409
    assert client.get(url).json()["status"] == "active"
    assert client.get("/api/v1/health").json()["input_revision"] == 2


@pytest.mark.parametrize("changes", [
    {"latitude": 1.292149, "longitude": 103.776551},
    {"latitude": 91}, {"latitude": "1.34"}, {"longitude": True},
    {"road_type": "expressway"}, {"road_type": "unknown"}, {"mode": "real"},
    {"unexpected": "do-not-echo"},
])
def test_invalid_scope_and_metadata_leave_no_records_or_images(client, png, settings, changes):
    response = upload(client, png, **changes)
    assert response.status_code == 422, response.text
    assert "do-not-echo" not in response.text
    assert client.get("/api/v1/inspections").json()["items"] == []
    assert client.get("/api/v1/health").json()["input_revision"] == 0
    assert not list(settings.upload_path.glob("*.png"))


@pytest.mark.parametrize("raw", ["{}", "not-json-secret", '{"mode":"demo","mode":"demo"}', "[]", "null"])
def test_bad_json_metadata_has_safe_error(client, png, raw):
    response = client.post("/api/v1/inspections", headers={"Idempotency-Key": "a"},
                           files={"image": ("secret.png", png)}, data={"metadata": raw})
    assert response.status_code == 422 and "secret" not in response.text


def test_missing_key_extra_parts_and_unsupported_body(client, png):
    assert client.post("/api/v1/inspections", files={"image": ("a.png", png)},
                       data={"metadata": json.dumps(metadata())}).status_code == 422
    assert client.post("/api/v1/inspections", headers={"Idempotency-Key": "../bad"}).status_code == 422
    assert client.post("/api/v1/inspections", headers={"Idempotency-Key": "a"}, json=metadata()).status_code == 415
    duplicated = [("image", ("a.png", png)), ("metadata", (None, json.dumps(metadata()))),
                  ("metadata", (None, json.dumps(metadata())))]
    assert client.post("/api/v1/inspections", headers={"Idempotency-Key": "a"}, files=duplicated).status_code == 422


def test_binary_size_and_stream_body_limits(client, png):
    too_large = upload(client, b"x" * (MAX_UPLOAD_BYTES + 1))
    assert too_large.status_code == 413, too_large.text
    response = client.post("/api/v1/inspections", headers={"Idempotency-Key": "stream",
                            "Content-Type": "multipart/form-data; boundary=x", "Content-Length": "1"},
                           content=iter([b"x" * (1024 * 1024)] * 9))
    assert response.status_code == 413, response.text
    assert client.get("/api/v1/inspections").json()["total"] == 0


def test_bad_image_unknown_scenario_and_missing_resource_are_safe(client, settings, png):
    bad = upload(client, b"not-image-secret")
    assert bad.status_code in (415, 422) and "secret" not in bad.text
    unknown = upload(client, png, "unknown-secret")
    assert unknown.status_code == 404 and unknown.json()["code"] == "demo_scenario_not_found"
    assert "unknown-secret" not in unknown.text
    assert client.get("/api/v1/inspections").json()["total"] == 0
    assert client.get("/api/v1/health").json()["input_revision"] == 0
    for url in ("/api/v1/tasks/" + "a" * 32, "/api/v1/inspections/" + "a" * 32,
                "/api/v1/inspections/" + "a" * 32 + "/image"):
        assert client.get(url).status_code == 404
    assert not list(settings.upload_path.glob("*.png"))


def test_pagination_state_errors_and_illegal_task_fields(client, png):
    upload(client, png, "no_detection", key="one")
    created = upload(client, png, "high_confidence", key="two").json()
    task = client.get(f'/api/v1/tasks/{created["task_id"]}').json()
    listing = client.get("/api/v1/inspections?limit=1&offset=1").json()
    assert listing["total"] == 2 and len(listing["items"]) == 1
    for query in ("limit=0", "limit=101", "offset=-1", "status=secret"):
        response = client.get("/api/v1/tasks?" + query)
        assert response.status_code == 422 and "secret" not in response.text
    for changes in ({"priority": "P1"}, {"status": "active"}, {}, {"latitude": 1.34}, {"due_at": None}):
        response = client.patch(f'/api/v1/tasks/{task["task_id"]}',
                                json={"request_id": "bad", "expected_version": 1, **changes})
        assert response.status_code == 422, response.text


def test_restart_preserves_records_and_images(settings, png):
    with TestClient(create_app(settings)) as client:
        created = upload(client, png, "high_confidence").json()
        task = client.get(f'/api/v1/tasks/{created["task_id"]}').json()
        inspection = client.get(f'/api/v1/inspections/{created["inspection_id"]}').json()
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/tasks").json()["items"][0] == task
        assert client.get(inspection["image_url"]).status_code == 200
        replay = upload(client, png, "high_confidence")
        assert replay.status_code == 200 and replay.json() == created
        assert client.get("/api/v1/health").json()["input_revision"] == 1


def test_upload_storage_override_and_scope_mismatch_fail_before_db(tmp_path):
    settings = load_settings({"ROADGUARD_DB_PATH": str(tmp_path / "test.sqlite3"),
                              "ROADGUARD_UPLOAD_PATH": str(tmp_path / "custom-images")})
    assert settings.upload_path == tmp_path / "custom-images"
    with pytest.raises(ConfigurationError):
        load_settings({"ROADGUARD_UPLOAD_PATH": " "})
    project = json.loads(settings.config_path.read_text(encoding="utf-8"))
    project["scenario"]["study_boundary"]["scope_version"] = "wrong-version"
    with pytest.raises(ConfigurationError), TestClient(create_app(replace(settings, project=project))):
        pass
    assert not settings.database_path.exists()
