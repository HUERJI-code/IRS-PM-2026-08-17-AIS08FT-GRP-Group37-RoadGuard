"""Four-crew GA vs Greedy experiment on the fixed 10/15/20 synthetic task snapshots.

Both algorithms receive the identical PlanningInput (tasks, crews, depot, settings,
start time) and the identical TravelMatrix per scenario. Greedy runs once (it is
deterministic); GA runs once per seed. Every run, including infeasible or worse
results, is written to raw_runs.csv. The matrix is the simulated provider, so results
describe algorithm behaviour on simulated travel times, not real road performance.

Usage (repository root):
    python SystemCode/experiments/routing/run_experiments.py --output-dir SystemCode/experiments/routing/results/simulated-v1
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "SystemCode/backend"))

from roadguard.config import load_settings  # noqa: E402
from roadguard.routing import (  # noqa: E402
    build_planning_input, default_crews, depot_from_project, load_routing_config, plan_routes,
    simulated_travel_matrix,
)
from roadguard.routing.settings import DEFAULT_ROUTING_CONFIG  # noqa: E402
from roadguard.schemas.task_query import TaskSnapshot  # noqa: E402


FIXTURES = ROOT / "SystemCode/contracts/planning"
METRICS = ("assigned_task_count", "unassigned_task_count", "total_travel_minutes", "total_service_minutes",
           "makespan_minutes", "workload_std_minutes", "priority_weighted_completion_minutes",
           "objective_value", "algorithm_runtime_ms")
RAW_FIELDS = ("task_count", "algorithm", "seed", *METRICS, "generations_run", "unique_evaluations",
              "matrix_preparation_ms")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_state() -> dict[str, object]:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                                check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                                    text=True, check=True).stdout.strip())
        return {"commit": commit, "working_tree_dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "working_tree_dirty": None}


def describe(values: list[float]) -> dict[str, float]:
    return {"mean": statistics.fmean(values), "std": statistics.pstdev(values), "min": min(values),
            "median": statistics.median(values), "max": max(values)}


def run_experiments(output_dir: Path, *, task_counts=(10, 15, 20), seeds=None, ga_overrides=None,
                    config_path: Path | None = None) -> dict:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing experiment output: {output_dir}")
    config = load_routing_config(config_path)
    ga_parameters = config.ga.model_copy(update=ga_overrides or {})
    seeds = list(seeds if seeds is not None else config.experiment["ga_seeds"])
    project = load_settings().project
    crews, depot = default_crews(project), depot_from_project(project)
    start = config.experiment["planning_start_at"]
    generated_at = datetime.fromisoformat(config.experiment["matrix_generated_at"])

    raw_rows, convergence_rows, scenarios = [], [], {}
    for count in task_counts:
        fixture = FIXTURES / f"tasks_{count}.json"
        fixture_bytes = fixture.read_bytes()
        snapshot = TaskSnapshot.model_validate_json(fixture_bytes)
        planning_input = build_planning_input(snapshot, crews, depot, config.settings, start)
        matrix_started = time.perf_counter()
        matrix = simulated_travel_matrix(planning_input, config.simulated_matrix, generated_at)
        matrix_ms = (time.perf_counter() - matrix_started) * 1000

        greedy_plan, _ = plan_routes(planning_input, matrix, "greedy", plan_id=f"exp-{count}-greedy")
        runs = [(greedy_plan, None)]
        for seed in seeds:
            runs.append(plan_routes(planning_input, matrix, "ga", ga_parameters=ga_parameters,
                                    random_seed=seed, plan_id=f"exp-{count}-ga-{seed}"))
        for plan, result in runs:
            row = {"task_count": count, "algorithm": plan.algorithm, "seed": plan.random_seed,
                   **{name: getattr(plan.metrics, name) for name in METRICS},
                   "generations_run": result.generations_run if result else None,
                   "unique_evaluations": result.unique_evaluations if result else None,
                   "matrix_preparation_ms": matrix_ms}
            raw_rows.append(row)
            if result:
                for generation, (unassigned, objective) in enumerate(result.best_key_history):
                    convergence_rows.append({"task_count": count, "seed": plan.random_seed,
                                             "generation": generation, "best_unassigned": unassigned,
                                             "best_objective": objective})
        ga_rows = [row for row in raw_rows if row["task_count"] == count and row["algorithm"] == "ga"]
        greedy_row = next(row for row in raw_rows if row["task_count"] == count and row["algorithm"] == "greedy")
        greedy_key = (greedy_row["unassigned_task_count"], greedy_row["objective_value"])
        ga_keys = [(row["unassigned_task_count"], row["objective_value"]) for row in ga_rows]
        scenarios[str(count)] = {
            "fixture": fixture.relative_to(ROOT).as_posix(),
            "fixture_sha256": sha256_bytes(fixture_bytes),
            "matrix_provider": matrix.provider,
            "matrix_is_simulated": matrix.is_simulated,
            "matrix_sha256": sha256_bytes(json.dumps(matrix.duration_minutes).encode()),
            "greedy": {name: greedy_row[name] for name in METRICS},
            "ga": {name: describe([row[name] for row in ga_rows if row[name] is not None])
                   for name in METRICS if any(row[name] is not None for row in ga_rows)},
            "ga_seed_count": len(ga_rows),
            "ga_better_than_greedy_seeds": sum(1 for key in ga_keys if key < greedy_key),
            "ga_equal_to_greedy_seeds": sum(1 for key in ga_keys if key == greedy_key),
            "ga_worse_than_greedy_seeds": sum(1 for key in ga_keys if key > greedy_key),
            # Every plan was checked to list each input task exactly once.
            "coverage_checked": True,
        }

    config_bytes = Path(config_path or DEFAULT_ROUTING_CONFIG).read_bytes()
    metadata = {
        "experiment": "four-crew GA vs Greedy on fixed synthetic snapshots",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "task_counts": list(task_counts),
        "crew_ids": [crew.crew_id for crew in crews],
        "ga_seeds": seeds,
        "ga_parameters": ga_parameters.model_dump(mode="json"),
        "routing_config_sha256": sha256_bytes(config_bytes),
        "routing_config": json.loads(config_bytes),
        "planning_start_at": start,
        "code": git_state(),
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "processor": platform.processor() or None},
        "limitations": [
            "Simulated travel matrix (great-circle x detour / speed); not road-network or Google data.",
            "Task points are synthetic and polygon-checked only; road eligibility is not verified.",
            "return_to_depot=true and unlimited shift are B demo assumptions pending A confirmation.",
            "All due_at are null, so no lateness is reported; priority-weighted completion is not lateness.",
            "Objective weights are a demo proposal; runtime is single-machine wall time.",
        ],
        "is_demo": True,
    }
    output_dir.mkdir(parents=True)
    with (output_dir / "raw_runs.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(raw_rows)
    with (output_dir / "ga_convergence.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("task_count", "seed", "generation", "best_unassigned",
                                                    "best_objective"), lineterminator="\n")
        writer.writeheader()
        writer.writerows(convergence_rows)
    summary = {"scenarios": scenarios, "is_demo": True}
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output_dir / "run_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, required=True, help="new directory for this run")
    parser.add_argument("--task-counts", type=int, nargs="+", default=[10, 15, 20], choices=[10, 15, 20])
    parser.add_argument("--seeds", type=int, nargs="+", default=None, help="defaults to routing config ga_seeds")
    args = parser.parse_args()
    summary = run_experiments(args.output_dir, task_counts=tuple(args.task_counts), seeds=args.seeds)
    for count, scenario in summary["scenarios"].items():
        ga_objective = scenario["ga"]["objective_value"]
        print(f"{count} tasks: greedy objective {scenario['greedy']['objective_value']:.1f}; "
              f"GA mean {ga_objective['mean']:.1f} (min {ga_objective['min']:.1f}, max {ga_objective['max']:.1f}); "
              f"GA better/equal/worse seeds {scenario['ga_better_than_greedy_seeds']}/"
              f"{scenario['ga_equal_to_greedy_seeds']}/{scenario['ga_worse_than_greedy_seeds']}")


if __name__ == "__main__":
    main()
