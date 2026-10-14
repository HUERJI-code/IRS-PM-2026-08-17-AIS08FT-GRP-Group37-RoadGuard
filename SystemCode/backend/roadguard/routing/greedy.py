"""
Rule: the available crew that becomes free earliest picks next. It takes the
highest-priority task it can still feasibly serve (P1 before P2 before P3), breaking
ties by the shortest travel time from its current position and then by snapshot order.
A crew that can take no remaining task stops. Leftover tasks are reported with reasons.
"""

from .evaluation import Evaluation, RoutingProblem

PRIORITY_RANK = {"P1": 0, "P2": 1, "P3": 2}


def greedy_routes(problem: RoutingProblem) -> list[list[int]]:
    crew_count = len(problem.available_crews)
    routes: list[list[int]] = [[] for _ in range(crew_count)]
    elapsed = [0.0] * crew_count
    position: list[int | None] = [None] * crew_count
    open_crews = set(range(crew_count))
    remaining = list(problem.schedulable)
    while remaining and open_crews:
        # Earliest-free crew; crew order breaks ties deterministically.
        crew = min(open_crews, key=lambda c: (elapsed[c], c))
        candidates = [task for task in remaining if problem.fits(elapsed[crew], position[crew], task)[0]]
        if not candidates:
            open_crews.discard(crew)
            continue
        task = min(candidates, key=lambda t: (
            PRIORITY_RANK[problem.tasks[t].priority], problem.leg(position[crew], t), t))
        elapsed[crew] += problem.leg(position[crew], task) + problem.service[task]
        position[crew] = task
        routes[crew].append(task)
        remaining.remove(task)
    if remaining:
        # Keep leftovers visible: append to the first crew so the shared evaluator assigns
        # each one its exact infeasibility reason instead of silently dropping it.
        if crew_count:
            routes[0].extend(remaining)
    return routes


def solve_greedy(problem: RoutingProblem) -> Evaluation:
    return problem.evaluate(greedy_routes(problem))
