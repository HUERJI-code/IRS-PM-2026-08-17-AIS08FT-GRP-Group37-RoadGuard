"""HTTP snapshot consumers see one revision and the exact original Task DTO."""

import io
import json

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from roadguard.config import load_settings
from auth_test_support import create_app
from roadguard.schemas import Task, TaskSnapshot


@pytest.fixture
def client(tmp_path):
    settings = load_settings({"ROADGUARD_DB_PATH": str(tmp_path / "snapshot.sqlite3")})
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client


def create_task(client, key):
    stream = io.BytesIO()
    Image.new("RGB", (80, 40), "gray").save(stream, format="PNG")
    response = client.post("/api/v1/inspections", headers={"Idempotency-Key": key},
                           files={"image": ("test.png", stream.getvalue(), "image/png")},
                           data={"metadata": json.dumps({"mode": "demo", "scenario_id": "high_confidence",
                                 "latitude": 1.34, "longitude": 103.72, "road_type": "public_motor_road"})})
    assert response.status_code == 201, response.text
    return client.get(f'/api/v1/tasks/{response.json()["task_id"]}').json()


def test_empty_snapshot_is_read_only_and_static_route_wins(client):
    response = client.get("/api/v1/tasks/snapshot?expected_revision=0")
    assert response.status_code == 200, response.text
    snapshot = TaskSnapshot.model_validate(response.json())
    assert snapshot.total == 0 and snapshot.tasks == [] and snapshot.input_revision == 0
    assert snapshot.source == "persisted_workflow" and snapshot.is_demo
    assert client.get("/api/v1/health").json()["input_revision"] == 0
    schema = client.get("/openapi.json").json()["paths"]["/api/v1/tasks/snapshot"]["get"]
    assert {item["name"] for item in schema["parameters"]} == {"expected_revision"}


def test_snapshot_projects_active_tasks_without_audit_fields(client):
    first = create_task(client, "first")
    second = create_task(client, "second")
    response = client.patch(f'/api/v1/tasks/{first["task_id"]}', json={
        "request_id": "complete", "expected_version": 1, "status": "completed",
    })
    assert response.status_code == 200, response.text
    response = client.get("/api/v1/tasks/snapshot?expected_revision=3")
    snapshot = TaskSnapshot.model_validate(response.json())
    assert snapshot.input_revision == 3 and snapshot.total == 1
    assert snapshot.tasks[0].task_id == second["task_id"]
    assert snapshot.tasks[0].due_at is None
    assert snapshot.tasks[0].model_dump(mode="json") == {key: second[key] for key in Task.model_fields}
    assert client.get(f'/api/v1/tasks/{first["task_id"]}').json()["history"]


def test_stale_snapshot_returns_conflict_without_mutating(client):
    create_task(client, "first")
    response = client.get("/api/v1/tasks/snapshot?expected_revision=0")
    assert response.status_code == 409
    assert response.json()["code"] == "stale_input_revision"
    assert response.json()["details"] == {"expected_revision": 0, "current_revision": 1}
    assert client.get("/api/v1/tasks/snapshot").json()["input_revision"] == 1


@pytest.mark.parametrize("value", ["-1", "true", "secret", "1.5"])
def test_invalid_expected_revision_has_safe_error(client, value):
    response = client.get("/api/v1/tasks/snapshot", params={"expected_revision": value})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error" and "secret" not in response.text


def test_missing_database_fails_without_recreation(client):
    path = client.app.state.database.path
    path.unlink()
    response = client.get("/api/v1/tasks/snapshot")
    assert response.status_code == 503 and response.json()["code"] == "database_unavailable"
    assert str(path) not in response.text and not path.exists()


def test_unavailable_query_service_is_not_an_empty_success(client):
    client.app.state.task_query_service = None
    response = client.get("/api/v1/tasks/snapshot")
    assert response.status_code == 503 and response.json()["code"] == "task_query_unavailable"
