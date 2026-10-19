"""RoadGuard Google matrix smoke test: create 3 demo tasks -> recalculate -> print travel sources and leg durations.

Usage (start the backend with google_routes, then run from the repository root in another window):
    python SystemCode/experiments/routing/google_smoke.py [--base http://127.0.0.1:8000]
Requests only (3+1)^2 = 16 Google elements; repeated runs in the same backend process use the cache without additional charges.
"""

import argparse
import io
import json
import sys
import uuid

import httpx
from PIL import Image

POINTS = [(1.332, 103.676), (1.346, 103.694), (1.3405, 103.706)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    base = parser.parse_args().base.rstrip("/") + "/api/v1"
    client = httpx.Client(timeout=120)

    stream = io.BytesIO()
    Image.new("RGB", (80, 40), "gray").save(stream, format="PNG")
    run = uuid.uuid4().hex[:8]
    for index, (lat, lon) in enumerate(POINTS):
        response = client.post(f"{base}/inspections", headers={"Idempotency-Key": f"smoke-{run}-{index}"},
                               files={"image": ("smoke.png", stream.getvalue(), "image/png")},
                               data={"metadata": json.dumps({
                                   "mode": "demo", "scenario_id": "high_confidence", "latitude": lat,
                                   "longitude": lon, "road_type": "public_motor_road"})})
        if response.status_code != 201:
            print("Task creation failed:", response.status_code, response.text)
            return 1
        print("Created task", response.json()["task_id"])

    revision = client.get(f"{base}/health").json()["input_revision"]
    response = client.post(f"{base}/route-plans/recalculate", json={"expected_revision": revision})
    if response.status_code != 200:
        print("Recalculation failed:", response.status_code, json.dumps(response.json(), ensure_ascii=False, indent=2))
        return 1
    result = response.json()
    print(f"\nMatrix source: {result['matrix_provider']}  Simulated: {result['matrix_is_simulated']}  "
          f"Generated at: {result['matrix_generated_at']}  Task count: {result['task_count']}")
    for summary in result["plans"]:
        plan = client.get(f"{base}/route-plans/{summary['plan_id']}").json()
        print(f"\n[{plan['algorithm']}] Makespan {plan['metrics']['makespan_minutes']} minutes, "
              f"Total travel {plan['metrics']['total_travel_minutes']} minutes, Unassigned {len(plan['unassigned_tasks'])}")
        for route in plan["crew_routes"]:
            legs = " -> ".join(f"{s['task_id'][-6:]}({s['travel_minutes_from_previous']}min)" for s in route["stops"])
            back = route["return_travel_minutes"]
            print(f"  {route['crew_id']} {route['status']:<11} Depot -> {legs or 'none'}"
                  + (f" -> Depot({back}min)" if route["stops"] and back is not None else ""))
    if result["matrix_is_simulated"]:
        print("\nNote: this run used a simulated matrix; ROADGUARD_TRAVEL_MATRIX_PROVIDER=google_routes was not set in the backend window.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
