"""The approved course durations reach real-mode HTTP tasks without rewriting v1 history.

Detector outputs are injected: these are workflow checks, not model-quality results.
"""

from dataclasses import replace
import json

from fastapi.testclient import TestClient
import pytest

from roadguard.config import REPOSITORY_ROOT, load_settings
from roadguard.main import create_app
from roadguard.schemas.common import LABELS_BY_ID
from test_real_vision import FakeDetector, metadata, png


EXPECTED = [
    (0, "low", "P3", 60), (1, "medium", "P2", 120),
    (2, "low", "P3", 60), (3, "medium", "P2", 120),
    (4, "medium", "P2", 120), (5, "high", "P1", 240),
    (6, "medium", "P2", 120), (7, "high", "P1", 240),
]


class LabelDetector(FakeDetector):
    def __init__(self, class_id, confidence):
        super().__init__(confidence)
        self.class_id = class_id

    def detect(self, image):
        detection = super().detect(image)[0]
        return [detection.model_copy(update={"class_id": self.class_id, "label": LABELS_BY_ID[self.class_id]})]


def upload(client, key):
    return client.post(
        "/api/v1/inspections", headers={"Idempotency-Key": key},
        files={"image": ("synthetic.png", png(), "image/png")},
        data={"metadata": json.dumps(metadata().model_dump(exclude_none=True))},
    )


@pytest.mark.parametrize("class_id,severity,priority,minutes", EXPECTED)
@pytest.mark.parametrize("acceptance", ["automatic", "review_correction"])
def test_v2_eight_class_durations_reach_task_detail_and_snapshot(tmp_path, class_id, severity, priority, minutes, acceptance):
    settings = load_settings({"ROADGUARD_DB_PATH": str(tmp_path / "baseline.sqlite3"),
                              "ROADGUARD_VISION_MANIFEST_PATH": "disabled"})
    with TestClient(create_app(settings)) as client:
        detector = LabelDetector(class_id if acceptance == "automatic" else 6,
                                 .60 if acceptance == "automatic" else .599999)
        client.app.state.workflow_service.real_detector = detector
        response = upload(client, "baseline")
        assert response.status_code == 201, response.text
        summary = response.json()
        assert set(summary) == {"inspection_id", "status", "detection", "task_id"}
        detail_url = f'/api/v1/inspections/{summary["inspection_id"]}'
        inspection = client.get(detail_url).json()
        raw_detection = inspection["detections"][0]
        if acceptance == "review_correction":
            assert summary["status"] == "pending_review" and summary["task_id"] is None
            assert client.get("/api/v1/tasks/snapshot").json()["input_revision"] == 0
            review = client.post(detail_url + "/review", json={
                "request_id": "baseline-review", "expected_version": inspection["record_version"],
                "action": "correct", "detection_id": raw_detection["detection_id"],
                "damage_label": LABELS_BY_ID[class_id],
            })
            assert review.status_code == 200, review.text
            task_id = review.json()["task"]["task_id"]
        else:
            assert summary["status"] == "accepted" and summary["task_id"]
            assert inspection["auto_acceptance"]["confidence_threshold"] == .60
            task_id = summary["task_id"]
        task = client.get(f"/api/v1/tasks/{task_id}").json()
        assert (task["damage_label"], task["severity"], task["priority"], task["service_minutes"]) == (
            LABELS_BY_ID[class_id], severity, priority, minutes,
        )
        assert task["rule_version"] == "demo-rules-v2" and task["due_at"] is None and task["is_demo"]
        assert task["history"][0]["after"]["service_minutes"] == minutes
        assert task["history"][0]["actor_source"] == (
            "system_confidence_policy" if acceptance == "automatic" else "user_declared_unverified"
        )
        assert client.get(detail_url).json()["detections"] == [raw_detection]
        snapshot = client.get("/api/v1/tasks/snapshot").json()
        assert snapshot["total"] == 1 and snapshot["input_revision"] == 1
        assert snapshot["tasks"][0]["service_minutes"] == minutes
        replay = upload(client, "baseline")
        assert replay.status_code == 200 and replay.json()["task_id"] == task_id
        assert detector.calls == 1
        assert client.get("/api/v1/tasks/snapshot").json() == snapshot


def test_v1_records_retain_frozen_durations_after_v2_restart(tmp_path):
    settings = load_settings({"ROADGUARD_DB_PATH": str(tmp_path / "history.sqlite3"),
                              "ROADGUARD_VISION_MANIFEST_PATH": "disabled"})
    previous = replace(settings, demo_rules_path=REPOSITORY_ROOT / "SystemCode/config/rule_history/demo-rules-v1.json")
    with TestClient(create_app(previous)) as client:
        detector = LabelDetector(6, .60)
        client.app.state.workflow_service.real_detector = detector
        old = upload(client, "old-accepted").json()
        old_task = client.get(f'/api/v1/tasks/{old["task_id"]}').json()
        assert old_task["service_minutes"] == 45 and old_task["rule_version"] == "demo-rules-v1"
        detector.confidence = .42
        pending = upload(client, "old-pending").json()
        pending_url = f'/api/v1/inspections/{pending["inspection_id"]}'
        pending_detail = client.get(pending_url).json()
    with TestClient(create_app(settings)) as client:
        assert client.get(f'/api/v1/tasks/{old["task_id"]}').json() == old_task
        assert client.get(pending_url).json() == pending_detail
        # An old request replays before inference, even with real inference disabled.
        replay = upload(client, "old-accepted")
        assert replay.status_code == 200 and replay.json() == old
        reviewed = client.post(pending_url + "/review", json={
            "request_id": "old-review", "expected_version": 1, "action": "correct",
            "detection_id": pending_detail["detections"][0]["detection_id"], "damage_label": "pothole_deep",
        })
        assert reviewed.status_code == 200, reviewed.text
        assert reviewed.json()["task"]["service_minutes"] == 60
        assert reviewed.json()["task"]["rule_version"] == "demo-rules-v1"
        corrected = client.patch(f'/api/v1/tasks/{old["task_id"]}', json={
            "request_id": "old-correction", "expected_version": 1, "damage_label": "longitudinal_crack",
        })
        assert corrected.status_code == 200, corrected.text
        assert corrected.json()["task"]["service_minutes"] == 20
        assert corrected.json()["task"]["rule_version"] == "demo-rules-v1"
        client.app.state.workflow_service.real_detector = LabelDetector(6, .60)
        new = upload(client, "new-v2").json()
        new_task = client.get(f'/api/v1/tasks/{new["task_id"]}').json()
        assert new_task["service_minutes"] == 120 and new_task["rule_version"] == "demo-rules-v2"
        snapshot = client.get("/api/v1/tasks/snapshot").json()
        assert snapshot["total"] == 3 and snapshot["input_revision"] == 4
        assert {task["rule_version"] for task in snapshot["tasks"]} == {"demo-rules-v1", "demo-rules-v2"}
