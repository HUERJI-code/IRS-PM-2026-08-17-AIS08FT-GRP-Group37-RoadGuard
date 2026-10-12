"""Offline task handoff provenance, exact DTO shape and deterministic reproduction."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from roadguard.geography import JurongScope
from roadguard.rules import load_rule_policy
from roadguard.schemas import Task
from roadguard.schemas.task_query import TaskSnapshot


ROOT = Path(__file__).resolve().parents[2]
PLANNING = ROOT / "SystemCode/contracts/planning"
SPEC = importlib.util.spec_from_file_location("planning_fixture_generator", PLANNING / "generate.py")
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)
NAMES = ("tasks_10.json", "tasks_15.json", "tasks_20.json", "tasks_empty.json", "tasks_unknown_service.json")


def source_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def artifacts():
    return GENERATOR.build_artifacts()


@pytest.mark.parametrize("name", NAMES)
def test_checked_in_snapshot_has_exact_old_tasks_and_valid_handoff_envelope(name):
    raw = source_json(PLANNING / name)
    snapshot = TaskSnapshot.model_validate(raw)
    assert snapshot.contract_version == "a-task-query-v1"
    assert snapshot.source == "synthetic_fixture" and snapshot.input_revision == 0 and snapshot.is_demo
    assert snapshot.total == len(snapshot.tasks)
    assert len({item.task_id for item in snapshot.tasks}) == snapshot.total
    assert len({item.inspection_id for item in snapshot.tasks}) == snapshot.total
    for item, payload in zip(snapshot.tasks, raw["tasks"]):
        assert set(payload) == set(Task.model_fields)
        assert Task.model_validate(payload) == item
        assert item.status == "active" and item.is_demo and item.due_at is None
        assert item.created_at.utcoffset().total_seconds() == 0


def test_sized_sets_are_prefixes_with_matching_fixed_task_data():
    ten, fifteen, twenty = (source_json(PLANNING / f"tasks_{count:02d}.json") for count in (10, 15, 20))
    assert [ten["total"], fifteen["total"], twenty["total"]] == [10, 15, 20]
    assert ten["tasks"] == fifteen["tasks"][:10] == twenty["tasks"][:10]
    assert fifteen["tasks"] == twenty["tasks"][:15]
    assert source_json(PLANNING / "tasks_empty.json")["tasks"] == []
    assert len({(task["latitude"], task["longitude"]) for task in twenty["tasks"]}) == 20


def test_each_location_is_inside_scope_and_rule_values_derive_from_shared_sources():
    scope = JurongScope()
    policy = load_rule_policy(ROOT / "SystemCode/config/demo_rules.example.json")
    labels = source_json(ROOT / "SystemCode/model/label_schema.json")
    ordered_labels = [item["label_key"] for item in sorted(labels["classes"], key=lambda item: item["class_id"])]
    tasks = TaskSnapshot.model_validate(source_json(PLANNING / "tasks_20.json")).tasks
    assert set(task.damage_label for task in tasks) == set(ordered_labels)
    for index, task in enumerate(tasks):
        scope.validate(task.latitude, task.longitude, "public_motor_road")
        assert task.damage_label == ordered_labels[index % len(ordered_labels)]
        rule = policy.rules[task.damage_label]
        assert (task.severity, task.priority, task.service_minutes, task.rule_version) == (
            rule.severity, rule.priority, rule.service_minutes, policy.rule_version,
        )


def test_unknown_service_is_explicit_separate_contract_edge():
    snapshot = TaskSnapshot.model_validate(source_json(PLANNING / "tasks_unknown_service.json"))
    assert snapshot.total == 1 and snapshot.tasks[0].service_minutes is None
    task = snapshot.tasks[0]
    JurongScope().validate(task.latitude, task.longitude, "public_motor_road")
    policy = load_rule_policy(ROOT / "SystemCode/config/demo_rules.example.json")
    rule = policy.rules[task.damage_label]
    assert (task.severity, task.priority, task.rule_version) == (rule.severity, rule.priority, policy.rule_version)
    normal_ids = {item["task_id"] for item in source_json(PLANNING / "tasks_20.json")["tasks"]}
    assert snapshot.tasks[0].task_id not in normal_ids
    manifest = source_json(PLANNING / "manifest.json")
    assert manifest["unknown_service_edge"]["override"] == {"service_minutes": None}
    assert "Not the output" in manifest["unknown_service_edge"]["meaning"]


def test_manifest_hashes_versions_and_unverified_context_match_shared_sources():
    manifest = source_json(PLANNING / "manifest.json")
    project = source_json(ROOT / "SystemCode/config/project.example.json")
    labels = source_json(ROOT / "SystemCode/model/label_schema.json")
    rules = source_json(ROOT / "SystemCode/config/demo_rules.example.json")
    depot = source_json(ROOT / "Miscellaneous/geography/nus-iss-depot.geojson")["features"][0]
    assert {entry["path"] for entry in manifest["source_files"]} == set(GENERATOR.SOURCE_PATHS)
    for entry in manifest["source_files"]:
        assert entry["sha256"] == hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest()
    assert manifest["contract_version"] == "a-task-query-v1" and manifest["is_demo"]
    assert manifest["source"] == "synthetic_fixture" and manifest["input_revision"] == 0
    assert manifest["scope_version"] == project["scenario"]["study_boundary"]["scope_version"]
    assert manifest["depot_version"] == project["scenario"]["depot"]["depot_version"]
    assert manifest["label_schema_version"] == labels["schema_version"]
    assert manifest["rule_version"] == rules["rule_version"]
    context = manifest["configured_context"]
    assert context["default_crew_count"] == project["planning"]["default_crew_count"] == 4
    assert context["crew_ids"] == project["planning"]["crew_ids"]
    assert (context["depot_latitude"], context["depot_longitude"]) == (
        project["scenario"]["depot"]["latitude"], project["scenario"]["depot"]["longitude"],
    )
    assert depot["geometry"]["coordinates"] == [context["depot_longitude"], context["depot_latitude"]]
    assert depot["properties"]["depot_version"] == manifest["depot_version"]
    assert context["depot_allowed_outside_task_service_area"] is True
    assert context["shift_minutes"] is None and context["return_to_depot"] is None
    coordinates = manifest["coordinate_construction"]
    assert coordinates["polygon_containment_checked"] is True
    assert coordinates["road_permission_verified"] is coordinates["is_field_site_data"] is False
    for name, entry in manifest["snapshots"].items():
        assert entry["sha256"] == hashlib.sha256((PLANNING / name).read_bytes()).hexdigest()
        assert entry["total"] == source_json(PLANNING / name)["total"]


def test_generated_bytes_are_repeatable_and_match_every_declared_file(artifacts):
    assert artifacts == GENERATOR.build_artifacts()
    assert set(artifacts) == set(NAMES) | {"manifest.json"}
    for name, content in artifacts.items():
        assert (PLANNING / name).read_bytes() == content
        assert content.endswith(b"\n") and b"\r\n" not in content


def test_in_memory_generation_is_cwd_independent_and_never_creates_database(tmp_path, monkeypatch, artifacts):
    nonexistent_db = tmp_path / "must-not-be-created.sqlite3"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ROADGUARD_DB_PATH", str(nonexistent_db))
    monkeypatch.setenv("ROADGUARD_CONFIG_PATH", str(tmp_path / "runtime-config-not-used.json"))
    assert GENERATOR.build_artifacts() == artifacts
    assert not nonexistent_db.exists()
    assert list(tmp_path.iterdir()) == []


def test_cli_check_uses_script_paths_and_does_not_rewrite_checkout(tmp_path):
    before = {path.name: path.read_bytes() for path in PLANNING.iterdir() if path.is_file()}
    result = subprocess.run([sys.executable, str(PLANNING / "generate.py"), "--check"],
                            cwd=tmp_path, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "match their sources" in result.stdout
    assert before == {path.name: path.read_bytes() for path in PLANNING.iterdir() if path.is_file()}
    assert list(tmp_path.iterdir()) == []
