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
