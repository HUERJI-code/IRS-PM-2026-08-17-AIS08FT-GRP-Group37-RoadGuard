"""Diagnose why some pure-GA seeds schedule fewer tasks than Greedy in the tight-capacity case.

Case: results/google-shift480-v1, 15 tasks, 480-minute shift. Task service time sums to
exactly 4 x 480 minutes, so with travel at most 13 tasks fit. Uses the saved Google matrix
(no API call) and writes nothing; it only prints.

Usage (repository root):
    python SystemCode/experiments/routing/diagnose_tight_capacity.py
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "SystemCode/backend"))

from roadguard.config import load_settings  # noqa: E402
from roadguard.routing import build_planning_input, default_crews, depot_from_project, load_routing_config  # noqa: E402
from roadguard.routing.evaluation import RoutingProblem  # noqa: E402
from roadguard.routing.ga import GeneticPlanner  # noqa: E402
from roadguard.routing.greedy import greedy_routes  # noqa: E402
from roadguard.routing.models import TravelMatrix  # noqa: E402
from roadguard.schemas.task_query import TaskSnapshot  # noqa: E402

MATRIX = ROOT / "SystemCode/experiments/routing/results/google-shift480-v1/matrix_15.json"
SEEDS = range(1, 11)
BUDGET_VARIANTS = [
    ("patience 300, max 1000", {"patience_generations": 300, "max_generations": 1000}),
    ("population 120, patience 300, max 1000",
     {"population_size": 120, "patience_generations": 300, "max_generations": 1000}),
    ("mutation 0.6, patience 300, max 1000",
     {"mutation_rate": 0.6, "patience_generations": 300, "max_generations": 1000}),
]


def build_problem() -> tuple[RoutingProblem, object]:
    config = load_routing_config(environ={})
    project = load_settings().project
    snapshot = TaskSnapshot.model_validate_json(
        (ROOT / "SystemCode/contracts/planning/tasks_15.json").read_bytes())
    planning_input = build_planning_input(snapshot, default_crews(project), depot_from_project(project),
                                          config.settings, config.experiment["planning_start_at"])
    matrix = TravelMatrix.model_validate_json(MATRIX.read_text(encoding="utf-8"))
    return RoutingProblem(planning_input, matrix), config


def fits(problem: RoutingProblem, routes) -> bool:
    return not problem.evaluate(routes).skipped


def single_insertions(problem, routes, missing) -> int:
    return sum(1 for task in missing for c in range(len(routes)) for p in range(len(routes[c]) + 1)
               if fits(problem, [r[:p] + [task] + r[p:] if i == c else r for i, r in enumerate(routes)]))


def relocate_then_insert(problem, routes, missing):
    """First (moved task, from crew, to crew, inserted task, into crew) that schedules one more task."""
    for c1, route in enumerate(routes):
        for index, moved in enumerate(route):
            base = [r[:] for r in routes]
            base[c1].pop(index)
            for c2 in range(len(routes)):
                for p2 in range(len(base[c2]) + 1):
                    trial = [r[:] for r in base]
                    trial[c2].insert(p2, moved)
                    if not fits(problem, trial):
                        continue
                    for task in missing:
                        for c3 in range(len(routes)):
                            for p3 in range(len(trial[c3]) + 1):
                                candidate = [r[:] for r in trial]
                                candidate[c3].insert(p3, task)
                                if fits(problem, candidate):
                                    return moved, c1 + 1, c2 + 1, task, c3 + 1
    return None


def main() -> None:
    problem, config = build_problem()
    priority = [task.priority for task in problem.tasks]
    print(f"service total {sum(problem.service):.0f} min; capacity 4 x 480 = 1920 min")
    greedy = problem.evaluate(greedy_routes(problem))
    slack = [round(480 - greedy.crew_travel[i] - greedy.crew_service[i], 1) for i in range(4)]
    print(f"Greedy: unassigned P1/P2/P3 {greedy.key[:3]}, objective {greedy.objective:.1f}, crew slack {slack}")

    print("\nPure GA (experiment setting, seed_with_greedy=false):")
    for seed in SEEDS:
        result = GeneticPlanner(problem, config.ga, seed).run()
        best, history = result.best, result.best_key_history
        settled = next(g for g, key in enumerate(history) if key[:3] == history[-1][:3])
        line = (f"  seed {seed:2d}: unassigned {best.key[:3]}, objective {best.objective:.1f}, "
                f"coverage settled at generation {settled}, stopped at {result.generations_run}")
        if best.key[:3] > greedy.key[:3]:
            routes = [list(route) for route in best.routes]
            missing = [task for task, _ in best.skipped]
            slack = [round(480 - best.crew_travel[i] - best.crew_service[i], 1) for i in range(4)]
            line += (f"\n           FAIL slack {slack}; missing {[(t, priority[t]) for t in missing]}; "
                     f"single insertions that fit: {single_insertions(problem, routes, missing)}; "
                     f"relocate+insert: {relocate_then_insert(problem, routes, missing)}")
        print(line)

    print("\nLarger budgets / other parameters (pure GA): seeds still scheduling fewer tasks than Greedy")
    for label, update in BUDGET_VARIANTS:
        parameters = config.ga.model_copy(update=update)
        failing = [seed for seed in SEEDS
                   if GeneticPlanner(problem, parameters, seed).run().best.key[:3] > greedy.key[:3]]
        print(f"  {label:40s} {failing}")

    print("\nGA seeded with Greedy (online setting):")
    seeded = config.ga.model_copy(update={"seed_with_greedy": True})
    for seed in SEEDS:
        best = GeneticPlanner(problem, seeded, seed).run().best
        print(f"  seed {seed:2d}: unassigned {best.key[:3]}, objective {best.objective:.1f}")


if __name__ == "__main__":
    main()
