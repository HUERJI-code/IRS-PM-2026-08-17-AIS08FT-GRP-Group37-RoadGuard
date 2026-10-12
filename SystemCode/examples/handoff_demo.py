"""Exercise A's real HTTP contracts and optionally export responses for B/C.

Run only against an isolated development server. This explicitly creates demo
inspections, completes/cancels their tasks, and retains their audit history.
"""

import argparse
import io
import json
from pathlib import Path
import sys
from uuid import uuid4

import httpx
from PIL import Image

BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from roadguard.schemas import InspectionMutation, TaskMutation, TaskSnapshot


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def run_demo(client: httpx.Client) -> dict:
    """Use public HTTP only; compatible with httpx.Client and TestClient."""
    responses = {}
    prefix = "handoff-" + uuid4().hex
    image = io.BytesIO()
    Image.new("RGB", (240, 120), "gray").save(image, format="PNG")

    def request(name, method, path, status=200, **kwargs):
        response = client.request(method, "/api/v1" + path, **kwargs)
        require(response.status_code == status, f"{name}: expected HTTP {status}, got {response.status_code}")
        responses[name] = response.json()
        return responses[name]

    def upload(name, scenario):
        data = request(name, "POST", "/inspections", 201,
                       headers={"Idempotency-Key": prefix + "-" + name},
                       files={"image": ("synthetic.png", image.getvalue(), "image/png")},
                       data={"metadata": json.dumps({"mode": "demo", "scenario_id": scenario,
                             "latitude": 1.34, "longitude": 103.72, "road_type": "public_motor_road"})})
        return InspectionMutation.model_validate(data)

    initial = TaskSnapshot.model_validate(request("initial_snapshot", "GET", "/tasks/snapshot"))
    revision = initial.input_revision
    high = upload("auto_accepted", "high_confidence")
    require(high.task is not None and high.input_revision == revision + 1, "Auto acceptance did not create a task")
    low = upload("pending_review", "low_confidence")
    require(low.task is None and low.inspection.status == "pending_review", "Low confidence bypassed review")
    review_payload = {"request_id": prefix + "-review", "expected_version": low.inspection.record_version,
                      "action": "correct", "detection_id": low.inspection.detections[0].detection_id,
                      "damage_label": "pothole_deep"}
    review_path = f"/inspections/{low.inspection.inspection_id}/review"
    corrected = InspectionMutation.model_validate(request("corrected_review", "POST", review_path, json=review_payload))
    require(corrected.task is not None and corrected.task.priority == "P1", "Corrected rule mapping was not applied")
    require(corrected.inspection.detections == low.inspection.detections, "Original evidence changed during review")
    replay = InspectionMutation.model_validate(request("replayed_review", "POST", review_path, json=review_payload))
    require(replay.replayed and not replay.planning_input_changed and replay.input_revision == revision + 2,
            "Repeated review changed planning input")

    empty = upload("no_detection", "no_detection")
    require(empty.task is None and empty.inspection.status == "no_detection", "No detection created a task")
    rejected = upload("pending_dismissal", "low_confidence")
    dismissed = InspectionMutation.model_validate(request("dismissed_review", "POST",
        f"/inspections/{rejected.inspection.inspection_id}/review", json={
            "request_id": prefix + "-dismiss", "expected_version": 1, "action": "dismiss",
            "note": "Synthetic handoff case; caller identity is unverified.",
        }))
    require(dismissed.task is None and dismissed.inspection.status == "rejected", "Dismissal created a task")

    active = TaskSnapshot.model_validate(request("active_snapshot", "GET", "/tasks/snapshot",
                                                 params={"expected_revision": revision + 2}))
    require(active.total == initial.total + 2, "Snapshot did not contain both new tasks")
    stale = request("stale_snapshot", "GET", "/tasks/snapshot", 409,
                    params={"expected_revision": revision})
    require(stale["code"] == "stale_input_revision", "Stale input was accepted")

    for name, task, target_status in (("completed_task", high.task, "completed"),
                                     ("cancelled_task", corrected.task, "cancelled")):
        result = TaskMutation.model_validate(request(name, "PATCH", f"/tasks/{task.task_id}", json={
            "request_id": prefix + "-" + name, "expected_version": task.record_version, "status": target_status,
        }))
        require(result.task.status == target_status and result.planning_input_changed, "Task transition failed")
    final = TaskSnapshot.model_validate(request("final_snapshot", "GET", "/tasks/snapshot"))
    require(final.input_revision == revision + 4 and final.tasks == initial.tasks,
            "Final queue or revision differs; use an isolated server with no concurrent writers")
    return {"is_demo": True, "contract_version": "a-task-query-v1", "baseline_revision": revision,
            "final_revision": final.input_revision, "source": "actual_http_responses",
            "note": "Synthetic PNG and detections; coordinates are not road-verified. Four inspection records remain.",
            "responses": responses}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--confirm-demo-writes", action="store_true",
                        help="Create four demo inspections and retain their audit history on the target server")
    parser.add_argument("--output", type=Path, help="Optional new JSON file containing actual responses; never overwritten")
    args = parser.parse_args()
    if not args.confirm_demo_writes:
        parser.error("Use an isolated development server and pass --confirm-demo-writes explicitly.")
    if args.output is not None and (args.output.exists() or not args.output.parent.is_dir()):
        parser.error("--output must be a new file in an existing directory.")
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=30, trust_env=False) as client:
        result = run_demo(client)
    if args.output is not None:
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    print(json.dumps({"result": "passed", "response_cases": len(result["responses"]),
                      "baseline_revision": result["baseline_revision"], "final_revision": result["final_revision"]}))


if __name__ == "__main__":
    main()
