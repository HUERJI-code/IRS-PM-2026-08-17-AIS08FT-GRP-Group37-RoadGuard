"""Reproduce synthetic task handoff JSON; never read or initialize a database."""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIRECTORY = Path(__file__).resolve().parent
BACKEND_ROOT = REPOSITORY_ROOT / "SystemCode/backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from roadguard.errors import AppError
from roadguard.geography import JurongScope
from roadguard.rules import load_rule_policy
from roadguard.schemas import Task
from roadguard.schemas.task_query import TaskSnapshot


SOURCE_PATHS = (
    "SystemCode/config/project.example.json",
    "SystemCode/config/demo_rules.example.json",
    "SystemCode/model/label_schema.json",
    "Miscellaneous/geography/jurong-boundary-mp2025.geojson",
    "Miscellaneous/geography/nus-iss-depot.geojson",
)
TASK_COUNTS = (10, 15, 20)
GRID_STEP_DEGREES = 0.002
FIXED_START_AT = datetime(2026, 10, 12, 2, tzinfo=timezone.utc)


def _read_json(path: str) -> dict:
    return json.loads((REPOSITORY_ROOT / path).read_text(encoding="utf-8"))


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _vertices(coordinates):
    if len(coordinates) == 2 and all(type(value) in (int, float) for value in coordinates):
        yield tuple(coordinates)
    else:
        for child in coordinates:
            yield from _vertices(child)


def _locations(boundary: dict, scope: JurongScope) -> list[tuple[float, float]]:
    """Evenly sample a fixed grid in the polygon union, without road-network claims."""
    vertices = [point for feature in boundary["features"] for point in _vertices(feature["geometry"]["coordinates"])]
    longitudes, latitudes = zip(*vertices)
    scale = round(1 / GRID_STEP_DEGREES)
    candidates = []
    # Longitude-first order and evenly spaced ranks spread the cases across the union.
    for x in range(math.ceil(min(longitudes) * scale), math.floor(max(longitudes) * scale) + 1):
        for y in range(math.ceil(min(latitudes) * scale), math.floor(max(latitudes) * scale) + 1):
            longitude, latitude = round(x / scale, 6), round(y / scale, 6)
            try:
                scope.validate(latitude, longitude, "public_motor_road")
            except AppError as error:
                if error.code != "outside_service_area":
                    raise
            else:
                candidates.append((latitude, longitude))
    count = max(TASK_COUNTS)
    if len(candidates) < count:
        raise ValueError("The frozen scope does not contain enough synthetic grid points.")
    # Integer ranks avoid floating-point rounding differences between runtimes.
    return [candidates[index * (len(candidates) - 1) // (count - 1)] for index in range(count)]


def _snapshot(tasks: list[Task]) -> dict:
    return TaskSnapshot(
        contract_version="a-task-query-v1", source="synthetic_fixture",
        input_revision=0, tasks=tasks, total=len(tasks), is_demo=True,
    ).model_dump(mode="json")


def build_artifacts() -> dict[str, bytes]:
    """Build every declared artifact in memory; independent of cwd and runtime env."""
    project = _read_json(SOURCE_PATHS[0])
    labels = _read_json(SOURCE_PATHS[2])
    boundary = _read_json(SOURCE_PATHS[3])
    policy = load_rule_policy(REPOSITORY_ROOT / SOURCE_PATHS[1])
    scope = JurongScope(REPOSITORY_ROOT / SOURCE_PATHS[3])
    ordered_labels = [item["label_key"] for item in sorted(labels["classes"], key=lambda item: item["class_id"])]
    tasks = []
    for index, (latitude, longitude) in enumerate(_locations(boundary, scope), start=1):
        label = ordered_labels[(index - 1) % len(ordered_labels)]
        rule = policy.rules[label]
        tasks.append(Task(
            task_id=f"fixture-task-{index:03d}", inspection_id=f"fixture-inspection-{index:03d}",
            latitude=latitude, longitude=longitude, damage_label=label,
            severity=rule.severity, priority=rule.priority, service_minutes=rule.service_minutes,
            created_at=FIXED_START_AT + timedelta(minutes=index - 1), due_at=None,
            status="active", rule_version=policy.rule_version, is_demo=True,
        ))
    snapshots = {f"tasks_{count:02d}.json": _snapshot(tasks[:count]) for count in TASK_COUNTS}
    snapshots["tasks_empty.json"] = _snapshot([])
    # This standalone contract edge intentionally represents missing duration; it
    # is not an output of the current complete demo rule mapping or a sized set.
    unknown = Task.model_validate(tasks[0].model_dump() | {
        "task_id": "fixture-unknown-service-001", "inspection_id": "fixture-unknown-inspection-001",
        "service_minutes": None,
    })
    snapshots["tasks_unknown_service.json"] = _snapshot([unknown])
    artifacts = {name: _json_bytes(snapshot) for name, snapshot in snapshots.items()}
    depot, planning = project["scenario"]["depot"], project["planning"]
    manifest = {
        "fixture_version": "planning-synthetic-v1",
        "contract_version": "a-task-query-v1", "source": "synthetic_fixture", "is_demo": True,
        "input_revision": 0,
        "revision_meaning": "Fixed fixture marker only; never a live database revision or mutation count.",
        "source_files": [
            {"path": path, "sha256": hashlib.sha256((REPOSITORY_ROOT / path).read_bytes()).hexdigest()}
            for path in SOURCE_PATHS
        ],
        "scope_version": scope.scope_version,
        "depot_version": depot["depot_version"],
        "label_schema_version": labels["schema_version"], "rule_version": policy.rule_version,
        "coordinate_construction": {
            "method": "longitude-first grid inside frozen polygon union; twenty evenly spaced integer ranks",
            "grid_step_degrees": GRID_STEP_DEGREES,
            "polygon_containment_checked": True,
            "road_permission_verified": False,
            "is_field_site_data": False,
            "road_declaration_for_containment_check": "public_motor_road",
            "limitations": "Synthetic points may lie off roads or on excluded roads. Not road-validated experiment inputs.",
        },
        "configured_context": {
            "default_crew_count": planning["default_crew_count"], "crew_ids": list(planning["crew_ids"]),
            "depot_id": depot["depot_id"], "depot_name": depot["name"],
            "depot_latitude": depot["latitude"], "depot_longitude": depot["longitude"],
            "depot_allowed_outside_task_service_area": depot["allowed_outside_task_service_area"],
            "driving_access_status": depot["driving_access_status"],
            "shift_minutes": None, "return_to_depot": planning["return_to_depot"],
            "constraint_parameters_status": planning["constraint_parameters_status"],
        },
        "due_at_policy": "All deadlines are null; no lateness metric is defined.",
        "prefix_relationship": "tasks_10.json is the first ten tasks of tasks_15.json, which is the first fifteen of tasks_20.json.",
        "unknown_service_edge": {
            "file": "tasks_unknown_service.json", "override": {"service_minutes": None},
            "meaning": f"Explicit missing-duration contract edge; other rule fields derive from {policy.rule_version}. Not the output of its current duration mapping.",
        },
        "usage": "Offline development fixtures only. Never seed app databases, replace failed live queries, or claim field experiments.",
        "generator": "SystemCode/contracts/planning/generate.py",
        "snapshots": {
            name: {"total": snapshots[name]["total"], "sha256": hashlib.sha256(content).hexdigest()}
            for name, content in artifacts.items()
        },
    }
    artifacts["manifest.json"] = _json_bytes(manifest)
    return artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare existing files without writing anything.")
    arguments = parser.parse_args()
    artifacts = build_artifacts()
    if arguments.check:
        changed = [name for name, content in artifacts.items()
                   if not (OUTPUT_DIRECTORY / name).is_file() or (OUTPUT_DIRECTORY / name).read_bytes() != content]
        if changed:
            print("Planning fixtures require regeneration: " + ", ".join(changed))
            return 1
        print("All planning fixture bytes match their sources.")
        return 0
    for name, content in artifacts.items():
        (OUTPUT_DIRECTORY / name).write_bytes(content)
    print(f"Wrote {len(artifacts)} declared planning fixture files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
