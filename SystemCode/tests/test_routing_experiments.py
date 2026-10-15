"""B-3: the experiment runner records every run with provenance and refuses overwrite."""

import csv
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "routing_experiments", ROOT / "SystemCode/experiments/routing/run_experiments.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
FAST = {"population_size": 12, "max_generations": 10, "patience_generations": 5}


def test_runner_writes_raw_runs_summary_and_metadata(tmp_path):
    output = tmp_path / "run"
    summary = RUNNER.run_experiments(output, task_counts=(10, 15), seeds=[1, 2], ga_overrides=FAST)
    with (output / "raw_runs.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [(r["task_count"], r["algorithm"], r["seed"]) for r in rows] == [
        ("10", "greedy", ""), ("10", "ga", "1"), ("10", "ga", "2"),
        ("15", "greedy", ""), ("15", "ga", "1"), ("15", "ga", "2")]
    assert all(int(r["assigned_task_count"]) + int(r["unassigned_task_count"]) == int(r["task_count"]) for r in rows)
    scenario = summary["scenarios"]["10"]
    assert scenario["ga_seed_count"] == 2 and scenario["matrix_is_simulated"] is True
    assert (scenario["ga_better_than_greedy_seeds"] + scenario["ga_equal_to_greedy_seeds"]
            + scenario["ga_worse_than_greedy_seeds"]) == 2
    metadata = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["ga_parameters"]["population_size"] == 12 and metadata["is_demo"] is True
    assert metadata["routing_config"]["return_to_depot"] is True
    with (output / "ga_convergence.csv").open(encoding="utf-8") as handle:
        convergence = list(csv.DictReader(handle))
    assert {(r["task_count"], r["seed"]) for r in convergence} == {("10", "1"), ("10", "2"), ("15", "1"), ("15", "2")}


def test_same_seeds_reproduce_identical_metrics(tmp_path):
    first = RUNNER.run_experiments(tmp_path / "a", task_counts=(10,), seeds=[4], ga_overrides=FAST)
    second = RUNNER.run_experiments(tmp_path / "b", task_counts=(10,), seeds=[4], ga_overrides=FAST)
    for summary in (first, second):
        summary["scenarios"]["10"]["ga"].pop("algorithm_runtime_ms")
        summary["scenarios"]["10"]["greedy"].pop("algorithm_runtime_ms")
    assert first == second


def test_runner_refuses_to_overwrite_existing_output(tmp_path):
    with pytest.raises(FileExistsError):
        RUNNER.run_experiments(tmp_path, task_counts=(10,), seeds=[1], ga_overrides=FAST)


def test_matrices_are_saved_and_match_recorded_hashes(tmp_path):
    output = tmp_path / "run"
    summary = RUNNER.run_experiments(output, task_counts=(10,), seeds=[1], ga_overrides=FAST)
    scenario = summary["scenarios"]["10"]
    saved = json.loads((output / scenario["matrix_file"]).read_text(encoding="utf-8"))
    assert RUNNER.sha256_bytes(json.dumps(saved["duration_minutes"]).encode()) == scenario["matrix_sha256"]
    assert saved["is_simulated"] is True and len(saved["node_ids"]) == 11
    assert scenario["matrix_source"] == "computed" and scenario["unreachable_pairs"] == 0
    with (output / "raw_runs.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    # No fixture task has due_at, so lateness stays empty instead of an invented zero.
    assert all(r["tasks_with_due_at"] == "0" and r["total_lateness_minutes"] == "" for r in rows)


def google_provider(fake):
    from roadguard.routing.google_matrix import GoogleRoutesMatrixProvider
    config = RUNNER.load_routing_config()
    return GoogleRoutesMatrixProvider(config.google_routes, transport=fake,
                                      environ={config.google_routes.api_key_env: "test-key"})


def test_google_mode_fetches_once_and_slices_prefix_scenarios(tmp_path):
    from test_routing_google_matrix import FakeGoogle
    fake = FakeGoogle()
    output = tmp_path / "google"
    summary = RUNNER.run_experiments(output, task_counts=(10, 20), seeds=[1], ga_overrides=FAST,
                                     matrix_provider="google_routes", google=google_provider(fake))
    assert len(fake.calls) == 1 and len(fake.calls[0]["body"]["origins"]) == 21
    assert summary["scenarios"]["20"]["matrix_source"] == "fetched"
    assert summary["scenarios"]["10"]["matrix_source"] == "sliced_from_20"
    assert summary["scenarios"]["10"]["matrix_is_simulated"] is False
    # The slice equals what a direct 10-task request would return.
    direct_fake = FakeGoogle()
    direct = RUNNER.scenario_matrices(
        {10: RUNNER.build_planning_input(
            RUNNER.TaskSnapshot.model_validate_json((RUNNER.FIXTURES / "tasks_10.json").read_bytes()),
            RUNNER.default_crews(RUNNER.load_settings().project),
            RUNNER.depot_from_project(RUNNER.load_settings().project),
            RUNNER.load_routing_config().settings, "2026-10-15T01:00:00Z")},
        RUNNER.load_routing_config(), "google_routes", None, google_provider(direct_fake))[10][0]
    saved = json.loads((output / "matrix_10.json").read_text(encoding="utf-8"))
    assert saved["duration_minutes"] == direct.duration_minutes and saved["node_ids"] == direct.node_ids
    metadata = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["matrix_provider"] == "google_routes" and "test-key" not in json.dumps(metadata)


def test_google_failure_writes_no_output(tmp_path):
    from roadguard.routing.google_matrix import TravelMatrixError
    from test_routing_google_matrix import FakeGoogle
    output = tmp_path / "failed"
    with pytest.raises(TravelMatrixError):
        RUNNER.run_experiments(output, task_counts=(10,), seeds=[1], ga_overrides=FAST,
                               matrix_provider="google_routes", google=google_provider(FakeGoogle(mutate=lambda e: e[1:])))
    assert not output.exists()


def test_unlimited_shift_variant_routes_every_task_and_records_override(tmp_path):
    output = tmp_path / "unlimited"
    summary = RUNNER.run_experiments(output, task_counts=(20,), seeds=[1], ga_overrides=FAST, unlimited_shift=True)
    assert summary["scenarios"]["20"]["greedy"]["unassigned_task_count"] == 0
    assert summary["scenarios"]["20"]["ga"]["unassigned_task_count"]["max"] == 0
    metadata = json.loads((output / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["settings_overrides"] == {"shift_limit": {"mode": "unlimited", "minutes": None}}
    # The recorded config file itself is untouched; the override is listed separately.
    assert metadata["routing_config"]["shift_limit"] == {"mode": "limited", "minutes": 480.0}
