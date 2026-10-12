"""Exercise the real simulation routes and prove they cannot change the queue."""

from dataclasses import replace
import json

from fastapi.testclient import TestClient
import pytest

from roadguard.config import ConfigurationError, REPOSITORY_ROOT, load_settings
from roadguard.main import create_app


@pytest.fixture
def settings(tmp_path):
    return load_settings({"ROADGUARD_DB_PATH": str(tmp_path / "demo.sqlite3")})


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client


def test_scenario_catalogue_marks_synthetic_source(client):
    response = client.get("/api/v1/demo/scenarios")
    assert response.status_code == 200
    body = response.json()
    assert body["is_demo"] is True
    assert body["model_version"] == "demo-detector-v1"
    assert (body["image_width"], body["image_height"]) == (640, 480)
    assert {scenario["scenario_id"] for scenario in body["scenarios"]} == {
        "high_confidence", "low_confidence", "no_detection", "multiple_detections",
        "mixed_confidence", "threshold_boundary", "below_threshold",
    }


@pytest.mark.parametrize("scenario,status,priority", [
    ("high_confidence", "ready_for_task", "P2"),
    ("low_confidence", "pending_review", None),
    ("no_detection", "no_detection", None),
    ("multiple_detections", "ready_for_task", "P1"),
    ("mixed_confidence", "pending_review", None),
    ("threshold_boundary", "ready_for_task", "P2"),
    ("below_threshold", "pending_review", None),
])
def test_demo_flows_through_detector_and_rules(client, scenario, status, priority):
    response = client.post("/api/v1/demo/assessments", json={"scenario_id": scenario})
    assert response.status_code == 200
    body = response.json()
    assert body["is_demo"] is True
    assert body["confidence_threshold"] == 0.60
    assessment = body["assessment"]
    assert assessment["status"] == status
    assert assessment["rule_version"] == "demo-rules-v1"
    assert assessment["is_demo"] is True
    assert all(detection["is_demo"] for detection in assessment["detections"])
    assert assessment["decision_trace"]
    assert all(trace["rule_version"] == "demo-rules-v1" and trace["is_demo"] for trace in assessment["decision_trace"])
    if priority is None:
        assert assessment["candidate"] is None
        assert assessment["selected_detection_id"] is None
    else:
        candidate = assessment["candidate"]
        assert candidate["priority"] == priority
        assert candidate["detection_id"] == assessment["selected_detection_id"]
        assert candidate["is_demo"] is True
        assert "task_id" not in candidate


def test_repeated_previews_are_identical_and_never_create_records_or_revisions(client):
    before = client.get("/api/v1/health").json()["input_revision"]
    first = client.post("/api/v1/demo/assessments", json={"scenario_id": "high_confidence"}).json()
    second = client.post("/api/v1/demo/assessments", json={"scenario_id": "high_confidence"}).json()
    assert first == second
    assert client.get("/api/v1/health").json()["input_revision"] == before == 0
    with client.app.state.database.connect() as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables == {"infra_metadata"}
    assert client.get("/api/v1/tasks").status_code == 404


@pytest.mark.parametrize("payload", [
    {}, {"scenario_id": True}, {"scenario_id": 1}, {"scenario_id": " "},
    {"scenario_id": "x" * 65}, {"scenario_id": "high_confidence", "is_demo": False},
    {"scenario_id": "high_confidence", "confidence_threshold": 0},
])
def test_bad_requests_use_shared_422(client, payload):
    response = client.post("/api/v1/demo/assessments", json=payload)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_unknown_scenario_and_runtime_failure_never_fall_back_to_success(client, monkeypatch):
    response = client.post("/api/v1/demo/assessments", json={"scenario_id": "secret-input"})
    assert response.status_code == 404
    assert response.json()["code"] == "demo_scenario_not_found"
    assert "secret-input" not in response.text

    def failure(_):
        raise RuntimeError("private-path-and-secret")

    monkeypatch.setattr(client.app.state.demo_detector, "detect", failure)
    response = client.post("/api/v1/demo/assessments", json={"scenario_id": "high_confidence"})
    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert "private-path-and-secret" not in response.text
    assert client.get("/api/v1/health").json()["input_revision"] == 0


def test_unavailable_demo_returns_503(client):
    client.app.state.rule_service = None
    response = client.post("/api/v1/demo/assessments", json={"scenario_id": "high_confidence"})
    assert response.status_code == 503
    assert response.json()["code"] == "demo_unavailable"


def test_demo_error_openapi_matches_shared_envelope(client):
    schema = client.get("/openapi.json").json()
    responses = schema["paths"]["/api/v1/demo/assessments"]["post"]["responses"]
    for status in ("404", "422", "503"):
        assert responses[status]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorResponse")


def test_policy_override_is_loaded_at_startup_and_has_observable_effect(settings, tmp_path, monkeypatch):
    raw = json.loads(settings.demo_rules_path.read_text(encoding="utf-8"))
    raw["confidence_threshold"] = 0.99
    raw["rule_version"] = "demo-test-stricter-v1"
    override = tmp_path / "stricter.json"
    override.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    configured = load_settings({
        "ROADGUARD_DEMO_RULES_PATH": str(override), "ROADGUARD_DB_PATH": str(settings.database_path),
    })
    assert configured.config_path == REPOSITORY_ROOT / "SystemCode/config/project.example.json"
    with TestClient(create_app(configured)) as client:
        response = client.post("/api/v1/demo/assessments", json={"scenario_id": "high_confidence"})
        assert response.status_code == 200
        body = response.json()
        assert body["confidence_threshold"] == 0.99
        assert body["assessment"]["status"] == "pending_review"
        assert body["assessment"]["rule_version"] == "demo-test-stricter-v1"


def test_missing_policy_fails_before_database_creation(settings, tmp_path):
    invalid = replace(settings, demo_rules_path=tmp_path / "private-missing.json")
    with pytest.raises(ConfigurationError), TestClient(create_app(invalid)):
        pass
    assert not invalid.database_path.exists()


def test_relative_policy_path_and_empty_override(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = load_settings({"ROADGUARD_DEMO_RULES_PATH": "SystemCode/config/demo_rules.example.json"})
    assert settings.demo_rules_path == REPOSITORY_ROOT / "SystemCode/config/demo_rules.example.json"
    with pytest.raises(ConfigurationError):
        load_settings({"ROADGUARD_DEMO_RULES_PATH": " "})
