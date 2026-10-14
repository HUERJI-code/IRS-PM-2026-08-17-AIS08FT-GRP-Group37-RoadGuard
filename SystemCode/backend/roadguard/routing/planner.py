"""Stateless planning entry: one input + one matrix -> a validated RoutePlan.

Persistence, crew mutations and recalculation triggers belong to later services; this
module never reads or writes the database.
"""

import time
import uuid
from typing import Literal

from .evaluation import RoutingProblem
from .ga import GAResult, solve_ga
from .greedy import solve_greedy
from .models import PlanningInput, RoutePlan, TravelMatrix
from .settings import GAParameters


def plan_routes(planning_input: PlanningInput, matrix: TravelMatrix, algorithm: Literal["ga", "greedy"], *,
                ga_parameters: GAParameters | None = None, random_seed: int | None = None,
                plan_id: str | None = None) -> tuple[RoutePlan, GAResult | None]:
    problem = RoutingProblem(planning_input, matrix)
    ga_result = None
    started = time.perf_counter()
    if algorithm == "greedy":
        if random_seed is not None or ga_parameters is not None:
            raise ValueError("greedy is deterministic and takes no seed or GA parameters")
        evaluation = solve_greedy(problem)
        parameters: dict = {"rule": "earliest_free_crew_highest_priority_then_nearest"}
    elif algorithm == "ga":
        if ga_parameters is None or type(random_seed) is not int:
            raise ValueError("GA requires explicit parameters and an integer random seed")
        ga_result = solve_ga(problem, ga_parameters, random_seed)
        evaluation = ga_result.best
        parameters = {**ga_parameters.model_dump(mode="json"),
                      "generations_run": ga_result.generations_run,
                      "unique_evaluations": ga_result.unique_evaluations}
    else:
        raise ValueError("algorithm must be 'ga' or 'greedy'")
    runtime_ms = (time.perf_counter() - started) * 1000
    crew_routes, unassigned, metrics = problem.build_routes_and_metrics(evaluation, runtime_ms)
    plan = RoutePlan(
        plan_id=plan_id or f"plan-{uuid.uuid4().hex}",
        input_revision=planning_input.input_revision,
        task_source=planning_input.task_source,
        algorithm=algorithm,
        planning_start_at=planning_input.planning_start_at,
        depot=planning_input.depot,
        crew_routes=crew_routes,
        unassigned_tasks=unassigned,
        metrics=metrics,
        matrix_provider=matrix.provider,
        matrix_is_simulated=matrix.is_simulated,
        settings=planning_input.settings,
        random_seed=random_seed,
        algorithm_parameters=parameters,
    )
    check_plan_covers_input(plan, planning_input)
    return plan, ga_result


def check_plan_covers_input(plan: RoutePlan, planning_input: PlanningInput) -> None:
    """Every input task appears exactly once, either in one route or as unassigned."""
    listed = [stop.task_id for route in plan.crew_routes for stop in route.stops]
    listed += [item.task_id for item in plan.unassigned_tasks]
    if sorted(listed) != sorted(task.task_id for task in planning_input.tasks):
        raise AssertionError("route plan does not cover every input task exactly once")
    if [route.crew_id for route in plan.crew_routes] != [crew.crew_id for crew in planning_input.crews]:
        raise AssertionError("route plan must list every configured crew in input order")
