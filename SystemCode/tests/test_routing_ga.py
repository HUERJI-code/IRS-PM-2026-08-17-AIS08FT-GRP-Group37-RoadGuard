"""B-2: GA legality, reproducibility and parity of constraints with Greedy."""

import pytest

from roadguard.routing import RoutingProblem, plan_routes
from roadguard.routing.ga import GeneticPlanner
from roadguard.routing.greedy import solve_greedy
from roadguard.routing.models import ShiftLimit

from test_routing_core import CONFIG, assert_exact_cover, assigned_ids, make_input, matrix_for, with_cells


FAST = CONFIG.ga.model_copy(update={"population_size": 20, "max_generations": 40, "patience_generations": 15})


def ga(planning_input, seed=7, parameters=FAST, matrix=None):
    return plan_routes(planning_input, matrix or matrix_for(planning_input), "ga",
                       ga_parameters=parameters, random_seed=seed)


def test_same_seed_reproduces_the_same_plan():
    planning_input = make_input(15)
    first, first_result = ga(planning_input, seed=3)
    second, second_result = ga(planning_input, seed=3)
    assert first.crew_routes == second.crew_routes
    assert first_result.best_key_history == second_result.best_key_history
    assert first.random_seed == 3 and first.algorithm_parameters["generations_run"] >= 1


@pytest.mark.parametrize("count", [10, 15, 20])
def test_ga_covers_every_fixture_task_exactly_once(count):
    planning_input = make_input(count)
    plan, _ = ga(planning_input)
    assert_exact_cover(plan, planning_input.tasks)
    assert [r.crew_id for r in plan.crew_routes] == ["crew-01", "crew-02", "crew-03", "crew-04"]


def test_best_key_never_gets_worse_with_elitism():
    _, result = ga(make_input(20), seed=11)
    history = result.best_key_history
    assert all(later <= earlier for earlier, later in zip(history, history[1:]))


def test_ga_seeded_with_greedy_is_never_worse_than_greedy():
    planning_input = make_input(20)
    problem = RoutingProblem(planning_input, matrix_for(planning_input))
    seeded = FAST.model_copy(update={"seed_with_greedy": True})
    plan, result = ga(planning_input, parameters=seeded)
    assert result.best.key <= solve_greedy(problem).key


def test_ga_never_assigns_unavailable_crews():
    plan, _ = ga(make_input(12, unavailable=frozenset({"crew-01", "crew-04"})))
    assert plan.crew_routes[0].status == plan.crew_routes[3].status == "unavailable"
    assert plan.crew_routes[0].stops == plan.crew_routes[3].stops == []
    assert len(assigned_ids(plan)) + len(plan.unassigned_tasks) == 12


def test_ga_handles_empty_tasks_and_all_crews_unavailable():
    empty, result = ga(make_input(name="tasks_empty.json"))
    assert result.generations_run == 0 and all(r.status == "idle" for r in empty.crew_routes)
    none_available, _ = ga(make_input(4, unavailable=frozenset({"crew-01", "crew-02", "crew-03", "crew-04"})))
    assert {u.reason for u in none_available.unassigned_tasks} == {"no_available_crew"}


def test_ga_and_greedy_share_prefilter_and_shift_constraints():
    planning_input = make_input(20, shift_limit=ShiftLimit(mode="limited", minutes=480.0))
    matrix = with_cells(matrix_for(planning_input), {(0, 3): None})
    greedy_plan, _ = plan_routes(planning_input, matrix, "greedy")
    ga_plan, _ = ga(planning_input, matrix=matrix)
    for plan in (greedy_plan, ga_plan):
        reasons = {u.task_id: u.reason for u in plan.unassigned_tasks}
        assert reasons[planning_input.tasks[2].task_id] == "unreachable_from_depot"
        assert all(r.total_work_minutes <= 480.0 for r in plan.crew_routes)
        assert len(assigned_ids(plan)) + len(plan.unassigned_tasks) == 20


def test_operators_preserve_a_valid_permutation_and_available_owners():
    planning_input = make_input(10, unavailable=frozenset({"crew-03"}))
    planner = GeneticPlanner(RoutingProblem(planning_input, matrix_for(planning_input)), FAST, seed=5)
    population = [planner.random_chromosome() for _ in range(10)]
    for _ in range(200):
        child = planner.mutate(planner.crossover(*planner.random.sample(population, 2)))
        order, owner = child
        assert sorted(order) == planner.tasks
        assert all(0 <= owner[t] < planner.crew_count == 3 for t in order)


def test_ga_requires_seed_and_parameters():
    planning_input = make_input(3)
    with pytest.raises(ValueError):
        plan_routes(planning_input, matrix_for(planning_input), "ga", ga_parameters=FAST)
    with pytest.raises(ValueError):
        plan_routes(planning_input, matrix_for(planning_input), "ga", random_seed=1)


@pytest.mark.parametrize("count", [15, 20])
def test_ga_with_default_parameters_keeps_every_p1_under_shift_limit(count):
    """Regression: a plain unassigned count once let GA drop all long P1 jobs."""
    planning_input = make_input(count)
    for seed in (1, 2):
        plan, _ = ga(planning_input, seed=seed, parameters=CONFIG.ga)
        assert_exact_cover(plan, planning_input.tasks)
