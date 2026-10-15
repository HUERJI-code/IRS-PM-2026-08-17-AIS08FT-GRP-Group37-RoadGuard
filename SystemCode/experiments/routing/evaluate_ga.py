"""Evaluate the GA beyond "better than Greedy": ablation and gap to a best-known solution.

Methods compared on the same input and the same saved travel matrix:
  greedy      deterministic baseline (1 run)
  ga_pure     experiment GA, no Greedy in the initial population (seeds)
  ga_seeded   online GA, initial population contains the Greedy solution (seeds)
  long runs   a much larger GA budget (pure and seeded alternating) used only to find a
              best-known solution (BKS); the BKS is the best key over every run here.

The gap to the BKS is reported only when a run schedules exactly as many tasks per priority
as the BKS; a run that schedules fewer tasks is counted as a coverage shortfall instead,
because an objective gap between plans covering different tasks is not meaningful.
The BKS is not proven optimal.

Scenarios reuse matrices saved by run_experiments.py (no Google request): node order and the
recorded SHA-256 are checked before use.

Usage (repository root):
    python SystemCode/experiments/routing/evaluate_ga.py --output-dir SystemCode/experiments/routing/results/ga-evaluation-v1
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_experiments import ROOT, git_state, sha256_bytes  # noqa: E402

from roadguard.config import load_settings  # noqa: E402
from roadguard.routing import build_planning_input, default_crews, depot_from_project, load_routing_config  # noqa: E402
from roadguard.routing.evaluation import Evaluation, RoutingProblem  # noqa: E402
from roadguard.routing.ga import GeneticPlanner  # noqa: E402
from roadguard.routing.greedy import greedy_routes  # noqa: E402
from roadguard.routing.matrix import node_ids  # noqa: E402
from roadguard.routing.models import ShiftLimit, TravelMatrix  # noqa: E402
from roadguard.routing.settings import DEFAULT_ROUTING_CONFIG  # noqa: E402
from roadguard.schemas.task_query import TaskSnapshot  # noqa: E402


RESULTS = ROOT / "SystemCode/experiments/routing/results"
FIXTURES = ROOT / "SystemCode/contracts/planning"
# Matrix source per provider: the B6 run whose summary recorded the matrix hash.
MATRIX_RUNS = {"simulated": "simulated-shift480-v1", "google_routes": "google-shift480-v1"}
SHIFTS = ("limited", "unlimited")
LONG_RUN = {"population_size": 150, "max_generations": 1000, "patience_generations": 300}
RAW_FIELDS = ("provider", "shift", "task_count", "method", "seed", "unassigned_p1", "unassigned_p2",
              "unassigned_p3", "objective", "total_travel_minutes", "makespan_minutes",
              "workload_std_minutes", "priority_weighted_completion_minutes", "runtime_ms",
              "generations_run")


def load_matrix(provider: str, count: int, planning_input) -> tuple[TravelMatrix, str]:
    run = RESULTS / MATRIX_RUNS[provider]
    raw = (run / f"matrix_{count}.json").read_text(encoding="utf-8")
    matrix = TravelMatrix.model_validate_json(raw)
    recorded = json.loads((run / "summary.json").read_text(encoding="utf-8"))["scenarios"][str(count)]
    digest = sha256_bytes(json.dumps(matrix.duration_minutes).encode())
    if digest != recorded["matrix_sha256"]:
        raise ValueError(f"{run.name}/matrix_{count}.json does not match its recorded hash")
    if matrix.node_ids != node_ids(planning_input):
        raise ValueError(f"{run.name}/matrix_{count}.json node order differs from tasks_{count}.json")
    return matrix, digest


def row(provider, shift, count, method, seed, evaluation: Evaluation, runtime_ms, generations) -> dict:
    p1, p2, p3 = evaluation.skipped_by_priority
    return {"provider": provider, "shift": shift, "task_count": count, "method": method, "seed": seed,
            "unassigned_p1": p1, "unassigned_p2": p2, "unassigned_p3": p3,
            "objective": evaluation.objective, "total_travel_minutes": evaluation.total_travel,
            "makespan_minutes": evaluation.makespan, "workload_std_minutes": evaluation.workload_std,
            "priority_weighted_completion_minutes": evaluation.priority_completion,
            "runtime_ms": runtime_ms, "generations_run": generations}


def timed_ga(problem, parameters, seed):
    started = time.perf_counter()
    result = GeneticPlanner(problem, parameters, seed).run()
    return result, (time.perf_counter() - started) * 1000


def key_of(r: dict) -> tuple:
    return (r["unassigned_p1"], r["unassigned_p2"], r["unassigned_p3"], r["objective"])


def method_summary(rows: list[dict], bks: dict, greedy: dict) -> dict:
    same_cover = [r for r in rows if key_of(r)[:3] == key_of(bks)[:3]]
    gaps = [100 * (r["objective"] - bks["objective"]) / bks["objective"] for r in same_cover]
    vs_greedy = [key_of(r) < key_of(greedy) for r in rows]
    summary = {
        "runs": len(rows),
        "fewer_tasks_than_bks": sum(1 for r in rows if key_of(r)[:3] > key_of(bks)[:3]),
        "better_than_greedy": sum(vs_greedy),
        "equal_to_greedy": sum(1 for r in rows if key_of(r) == key_of(greedy)),
        "worse_than_greedy": sum(1 for r in rows if key_of(r) > key_of(greedy)),
        "reached_bks": sum(1 for r in rows if key_of(r) == key_of(bks)),
        "runtime_ms_mean": statistics.fmean(r["runtime_ms"] for r in rows),
    }
    if gaps:
        summary["gap_to_bks_percent"] = {"mean": statistics.fmean(gaps), "max": max(gaps), "min": min(gaps),
                                         "runs": len(gaps)}
    return summary


def evaluate(output_dir: Path, *, task_counts=(10, 15, 20), providers=("simulated", "google_routes"),
             shifts=SHIFTS, seeds=None, long_seeds=None, ga_overrides=None, long_overrides=None) -> dict:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing evaluation output: {output_dir}")
    config = load_routing_config(environ={})
    pure = config.ga.model_copy(update={**(ga_overrides or {}), "seed_with_greedy": False})
    seeded = pure.model_copy(update={"seed_with_greedy": True})
    long_pure = pure.model_copy(update=long_overrides or LONG_RUN)
    long_seeded = long_pure.model_copy(update={"seed_with_greedy": True})
    seeds = list(seeds if seeds is not None else config.experiment["ga_seeds"])
    long_seeds = list(long_seeds if long_seeds is not None else range(101, 121))
    project = load_settings().project
    crews, depot = default_crews(project), depot_from_project(project)

    raw_rows, scenarios, best_known = [], {}, {}
    for provider in providers:
        for shift in shifts:
            settings = config.settings if shift == "limited" else config.settings.model_copy(
                update={"shift_limit": ShiftLimit(mode="unlimited")})
            for count in task_counts:
                snapshot = TaskSnapshot.model_validate_json((FIXTURES / f"tasks_{count}.json").read_bytes())
                planning_input = build_planning_input(snapshot, crews, depot, settings,
                                                      config.experiment["planning_start_at"])
                matrix, digest = load_matrix(provider, count, planning_input)
                problem = RoutingProblem(planning_input, matrix)
                rows = []
                started = time.perf_counter()
                greedy_eval = problem.evaluate(greedy_routes(problem))
                rows.append(row(provider, shift, count, "greedy", None, greedy_eval,
                                (time.perf_counter() - started) * 1000, None))
                best = (greedy_eval.key, greedy_eval, "greedy", None)
                for method, parameters, method_seeds in (("ga_pure", pure, seeds), ("ga_seeded", seeded, seeds),
                                                         ("long_run", None, long_seeds)):
                    for index, seed in enumerate(method_seeds):
                        if parameters is None:  # alternate pure and seeded long runs
                            parameters_used = long_seeded if index % 2 else long_pure
                        else:
                            parameters_used = parameters
                        result, runtime = timed_ga(problem, parameters_used, seed)
                        rows.append(row(provider, shift, count, method, seed, result.best, runtime,
                                        result.generations_run))
                        if result.best.key < best[0]:
                            best = (result.best.key, result.best, method, seed)
                raw_rows.extend(rows)
                name = f"{provider}/{shift}/{count}"
                _, bks_eval, bks_method, bks_seed = best
                bks = row(provider, shift, count, bks_method, bks_seed, bks_eval, 0.0, None)
                greedy_row = rows[0]
                best_known[name] = {
                    "found_by": bks_method, "seed": bks_seed,
                    "unassigned_p1_p2_p3": list(bks_eval.skipped_by_priority),
                    "objective": bks_eval.objective,
                    "routes_task_ids": [[problem.tasks[i].task_id for i in route] for route in bks_eval.routes],
                }
                scenarios[name] = {
                    "matrix_run": MATRIX_RUNS[provider], "matrix_sha256": digest,
                    "bks_objective": bks_eval.objective,
                    "bks_unassigned_p1_p2_p3": list(bks_eval.skipped_by_priority),
                    "greedy": {"unassigned_p1_p2_p3": list(greedy_eval.skipped_by_priority),
                               "objective": greedy_eval.objective,
                               "gap_to_bks_percent": (100 * (greedy_eval.objective - bks_eval.objective)
                                                      / bks_eval.objective
                                                      if greedy_eval.key[:3] == bks_eval.key[:3] else None)},
                    **{method: method_summary([r for r in rows if r["method"] == method], bks, greedy_row)
                       for method in ("ga_pure", "ga_seeded")},
                    "ga_seeded_improvement_over_greedy_percent": statistics.fmean(
                        100 * (greedy_eval.objective - r["objective"]) / greedy_eval.objective
                        for r in rows if r["method"] == "ga_seeded"),
                }

    config_bytes = Path(DEFAULT_ROUTING_CONFIG).read_bytes()
    metadata = {
        "experiment": "GA evaluation: ablation (greedy / ga_pure / ga_seeded) and gap to best-known solution",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "task_counts": list(task_counts), "providers": list(providers), "shifts": list(shifts),
        "ga_seeds": seeds, "long_run_seeds": long_seeds,
        "ga_parameters": pure.model_dump(mode="json"),
        "long_run_parameters": long_pure.model_dump(mode="json"),
        "long_run_note": "even indices run pure, odd indices run seeded with Greedy",
        "routing_config_sha256": sha256_bytes(config_bytes),
        "routing_config": json.loads(config_bytes),
        "matrix_runs": MATRIX_RUNS,
        "code": git_state(),
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "processor": platform.processor() or None},
        "limitations": [
            "The best-known solution is the best key found here, not a proven optimum.",
            "One fixed synthetic task set; matrices reused from B6 (simulated and one Google snapshot).",
            "Shift, return-to-depot and objective weights are B demo assumptions pending A confirmation.",
        ],
        "is_demo": True,
    }
    output_dir.mkdir(parents=True)
    with (output_dir / "raw_runs.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(raw_rows)
    for name, payload in (("summary.json", {"scenarios": scenarios, "is_demo": True}),
                          ("best_known.json", best_known), ("run_metadata.json", metadata)):
        (output_dir / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {"scenarios": scenarios}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, required=True, help="new directory for this run")
    args = parser.parse_args()
    summary = evaluate(args.output_dir)
    for name, s in summary["scenarios"].items():
        pure, seeded = s["ga_pure"], s["ga_seeded"]
        gap = lambda m: f"{m['gap_to_bks_percent']['mean']:.2f}%" if "gap_to_bks_percent" in m else "n/a"  # noqa: E731
        greedy_gap = "n/a" if s["greedy"]["gap_to_bks_percent"] is None else f"{s['greedy']['gap_to_bks_percent']:.2f}%"
        print(f"{name:28s} greedy gap {greedy_gap:>7s} | pure gap {gap(pure):>7s} fewer-tasks {pure['fewer_tasks_than_bks']}"
              f" | seeded gap {gap(seeded):>7s} fewer-tasks {seeded['fewer_tasks_than_bks']}"
              f" improves-greedy {seeded['better_than_greedy']}/{seeded['runs']}")


if __name__ == "__main__":
    main()
