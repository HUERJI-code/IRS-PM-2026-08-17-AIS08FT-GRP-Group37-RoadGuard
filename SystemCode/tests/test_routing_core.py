"""B-1: routing models, simulated matrix, shared evaluator and Greedy baseline."""

from datetime import timedelta
import json
from pathlib import Path

from pydantic import ValidationError
import pytest

from roadguard.config import load_settings
from roadguard.routing import (
    RoutingProblem, TravelMatrix, build_planning_input, default_crews, depot_from_project,
    load_routing_config, plan_routes, simulated_travel_matrix,
)
from roadguard.routing.matrix import haversine_km
from roadguard.routing.models import ShiftLimit
from roadguard.schemas.task_query import TaskSnapshot


ROOT = Path(__file__).resolve().parents[2]
PLANNING = ROOT / "SystemCode/contracts/planning"
START = "2026-10-15T01:00:00Z"
CONFIG = load_routing_config()
PROJECT = load_settings().project


def snapshot(name="tasks_20.json", count=None):
    snap = TaskSnapshot.model_validate_json((PLANNING / name).read_text(encoding="utf-8"))
    if count is not None:
        snap = snap.model_copy(update={"tasks": snap.tasks[:count], "total": count})
    return snap


def make_input(count=None, *, name="tasks_20.json", unavailable=frozenset(), **settings_update):
    settings = CONFIG.settings.model_copy(update=settings_update)
    return build_planning_input(snapshot(name, count), default_crews(PROJECT, unavailable),
                                depot_from_project(PROJECT), settings, START)


def matrix_for(planning_input):
    return simulated_travel_matrix(planning_input, CONFIG.simulated_matrix)


def with_cells(matrix, cells):
    rows = [row[:] for row in matrix.duration_minutes]
    for (i, j), value in cells.items():
        rows[i][j] = value
    return matrix.model_copy(update={"duration_minutes": rows})


def greedy(planning_input, matrix=None):
    return plan_routes(planning_input, matrix or matrix_for(planning_input), "greedy")[0]


def assigned_ids(plan):
    return [stop.task_id for route in plan.crew_routes for stop in route.stops]


def test_example_config_is_explicit_demo_with_chosen_policies():
    settings = CONFIG.settings
    assert settings.is_demo is True and settings.config_version == "b-routing-demo-v1"
    assert settings.return_to_depot is True
    assert settings.shift_limit == ShiftLimit(mode="limited", minutes=480.0)
    assert CONFIG.ga.seed_with_greedy is False
    # Online recalculation starts GA from Greedy; experiments above stay unseeded.
    assert CONFIG.planning_service.seed_with_greedy is True
    assert PROJECT["planning"]["return_to_depot"] is None   # A's project config stays undecided


def test_duplicate_config_keys_are_rejected(tmp_path):
    text = (ROOT / "SystemCode/config/routing.example.json").read_text(encoding="utf-8")
    path = tmp_path / "routing.json"
    path.write_text(text.replace('"is_demo": true,', '"is_demo": true, "is_demo": true,', 1), encoding="utf-8")
    with pytest.raises(ValueError):
        load_routing_config(path)


def test_shift_limit_requires_consistent_mode():
    with pytest.raises(ValidationError):
        ShiftLimit(mode="limited")
    with pytest.raises(ValidationError):
        ShiftLimit(mode="unlimited", minutes=480.0)


def test_simulated_matrix_orders_depot_first_and_is_labelled():
    planning_input = make_input(3)
    matrix = matrix_for(planning_input)
    assert matrix.node_ids == ["depot-nus-iss"] + [t.task_id for t in planning_input.tasks]
    assert matrix.is_simulated and matrix.provider == "simulated_haversine_v1"
    task = planning_input.tasks[0]
    expected = haversine_km(1.292149, 103.776551, task.latitude, task.longitude) * 1.3 * 2.0
    assert matrix.duration_minutes[0][1] == pytest.approx(expected, abs=0.05)
    assert matrix.duration_minutes[0][1] > 0   # depot outside Jurong is a real journey


def test_matrix_rejects_bad_shape_diagonal_and_negative_values():
    matrix = matrix_for(make_input(2))
    with pytest.raises(ValidationError):
        TravelMatrix.model_validate(with_cells(matrix, {(1, 1): 5.0}).model_dump())
    with pytest.raises(ValidationError):
        TravelMatrix.model_validate({**matrix.model_dump(), "duration_minutes": [[0.0, -1.0, 2.0], [1.0, 0.0, 1.0], [1.0, 1.0, 0.0]]})
    with pytest.raises(ValidationError):
        TravelMatrix.model_validate({**matrix.model_dump(), "duration_minutes": [[0.0, 1.0], [1.0, 0.0]]})


def test_problem_rejects_matrix_with_other_node_order():
    planning_input = make_input(3)
    matrix = matrix_for(planning_input)
    swapped = matrix.model_copy(update={"node_ids": [matrix.node_ids[0], matrix.node_ids[2], matrix.node_ids[1], matrix.node_ids[3]]})
    with pytest.raises(ValueError):
        RoutingProblem(planning_input, swapped)


def test_empty_task_list_keeps_all_four_crews_visible_and_idle():
    plan = greedy(make_input(name="tasks_empty.json"))
    assert [r.crew_id for r in plan.crew_routes] == ["crew-01", "crew-02", "crew-03", "crew-04"]
    assert all(r.status == "idle" and r.stops == [] for r in plan.crew_routes)
    assert plan.unassigned_tasks == [] and plan.metrics.makespan_minutes == 0
    assert plan.metrics.priority_weighted_completion_minutes is None


def test_single_task_counts_depot_legs_both_ways():
    planning_input = make_input(1)
    matrix = matrix_for(planning_input)
    plan = greedy(planning_input, matrix)
    route = next(r for r in plan.crew_routes if r.stops)
    out, back = matrix.duration_minutes[0][1], matrix.duration_minutes[1][0]
    stop = route.stops[0]
    assert stop.travel_minutes_from_previous == out and stop.arrival_minute == out
    assert route.return_travel_minutes == back
    assert route.travel_minutes == pytest.approx(out + back)
    assert route.total_work_minutes == pytest.approx(out + back + stop.service_minutes)
    assert plan.metrics.makespan_minutes == pytest.approx(route.end_minute)


def test_no_return_policy_ends_at_last_task():
    plan = greedy(make_input(1, return_to_depot=False))
    route = next(r for r in plan.crew_routes if r.stops)
    assert route.return_travel_minutes is None
    assert route.end_minute == pytest.approx(route.stops[-1].completion_minute)


def test_fewer_tasks_than_crews_leaves_idle_crews_visible():
    plan = greedy(make_input(2))
    statuses = [r.status for r in plan.crew_routes]
    assert statuses.count("assigned") == 2 and statuses.count("idle") == 2
    # idle available crews count as zero workload in the balance metric
    assert plan.metrics.workload_std_minutes > 0


def test_unavailable_crew_gets_no_tasks_and_stays_visible():
    plan = greedy(make_input(unavailable=frozenset({"crew-02"})))
    crew2 = plan.crew_routes[1]
    assert crew2.crew_id == "crew-02" and crew2.status == "unavailable" and crew2.stops == []
    # Three crews cannot fit four 240-minute P1 jobs plus travel into 480-minute shifts.
    assert_exact_cover(plan, snapshot().tasks, all_p1_fit=False)
    assert plan.metrics.unassigned_by_priority["P1"] == 1


def test_all_crews_unavailable_reports_every_task():
    planning_input = make_input(5, unavailable=frozenset({"crew-01", "crew-02", "crew-03", "crew-04"}))
    plan = greedy(planning_input)
    assert assigned_ids(plan) == []
    assert {u.reason for u in plan.unassigned_tasks} == {"no_available_crew"}
    assert len(plan.unassigned_tasks) == 5


def test_unknown_service_minutes_is_unassigned_not_zero():
    plan = greedy(make_input(name="tasks_unknown_service.json"))
    assert [(u.task_id, u.reason) for u in plan.unassigned_tasks] == [
        (snapshot("tasks_unknown_service.json").tasks[0].task_id, "unknown_service_minutes")]
    assert plan.metrics.total_service_minutes == 0


def test_unreachable_legs_are_reported_never_zero_minutes():
    planning_input = make_input(3)
    matrix = matrix_for(planning_input)
    plan = greedy(planning_input, with_cells(matrix, {(0, 1): None, (2, 0): None}))
    reasons = {u.task_id: u.reason for u in plan.unassigned_tasks}
    tasks = planning_input.tasks
    assert reasons == {tasks[0].task_id: "unreachable_from_depot", tasks[1].task_id: "unreachable_to_depot"}
    assert assigned_ids(plan) == [tasks[2].task_id]


def test_unreachable_between_tasks_is_skipped_by_shared_evaluator():
    planning_input = make_input(2)
    problem = RoutingProblem(planning_input, with_cells(matrix_for(planning_input), {(1, 2): None}))
    evaluation = problem.evaluate([[0, 1], [], [], []])
    assert evaluation.routes[0] == (0,) and evaluation.skipped == ((1, "no_feasible_route_position"),)
    # Greedy routes around the gap by giving the task to another crew.
    plan = greedy(planning_input, problem.matrix)
    assert plan.unassigned_tasks == [] and len(assigned_ids(plan)) == 2


def test_shift_limit_marks_tasks_that_do_not_fit():
    planning_input = make_input(20, shift_limit=ShiftLimit(mode="limited", minutes=480.0))
    plan = greedy(planning_input)
    assert all(r.total_work_minutes <= 480.0 for r in plan.crew_routes)
    assert plan.unassigned_tasks and {u.reason for u in plan.unassigned_tasks} == {"exceeds_shift_limit"}
    assert len(assigned_ids(plan)) + len(plan.unassigned_tasks) == 20


def test_task_longer_than_shift_is_prefiltered():
    planning_input = make_input(1, shift_limit=ShiftLimit(mode="limited", minutes=30.0))
    plan = greedy(planning_input)
    assert [u.reason for u in plan.unassigned_tasks] == ["exceeds_shift_limit"]


def test_greedy_is_deterministic_and_dispatches_p1_first():
    planning_input = make_input(10)
    first, second = greedy(planning_input), greedy(planning_input)
    assert first.crew_routes == second.crew_routes
    priorities = {t.task_id: t.priority for t in planning_input.tasks}
    first_stops = [priorities[r.stops[0].task_id] for r in first.crew_routes if r.stops]
    assert "P1" in first_stops


def assert_exact_cover(plan, tasks, limit=480.0, *, all_p1_fit=True):
    """Every task once (route or unassigned); 480-minute shifts hold; P1 kept when capacity allows."""
    listed = assigned_ids(plan) + [u.task_id for u in plan.unassigned_tasks]
    assert sorted(listed) == sorted(t.task_id for t in tasks)
    assert all(r.total_work_minutes <= limit for r in plan.crew_routes)
    assert {u.reason for u in plan.unassigned_tasks} <= {"exceeds_shift_limit"}
    if all_p1_fit:
        assert plan.metrics.unassigned_by_priority["P1"] == 0
    assert sum(plan.metrics.unassigned_by_priority.values()) == len(plan.unassigned_tasks)


@pytest.mark.parametrize("count", [10, 15, 20])
def test_greedy_covers_every_fixture_task_exactly_once(count):
    planning_input = make_input(count)
    plan = greedy(planning_input)
    assert_exact_cover(plan, planning_input.tasks)
    if count == 10:
        assert plan.unassigned_tasks == []
    assert plan.is_demo and plan.matrix_is_simulated and plan.random_seed is None
    assert plan.metrics.tasks_with_due_at == 0 and plan.metrics.total_lateness_minutes is None
    total_travel = sum(r.travel_minutes for r in plan.crew_routes)
    assert plan.metrics.total_travel_minutes == pytest.approx(total_travel)
    assert plan.metrics.makespan_minutes == pytest.approx(max(r.end_minute for r in plan.crew_routes))
    json.loads(plan.model_dump_json())   # serializable wire format


def test_lateness_uses_known_due_at_only():
    planning_input = make_input(2)
    start = planning_input.planning_start_at
    tasks = [planning_input.tasks[0].model_copy(update={"due_at": start + timedelta(minutes=1)}),
             planning_input.tasks[1]]
    planning_input = planning_input.model_copy(update={"tasks": tasks})
    plan = greedy(planning_input)
    assert plan.metrics.tasks_with_due_at == 1 and plan.metrics.late_task_count == 1
    stop = next(s for r in plan.crew_routes for s in r.stops if s.task_id == tasks[0].task_id)
    assert plan.metrics.total_lateness_minutes == pytest.approx(stop.completion_minute - 1)


def test_greedy_rejects_seed_and_plan_rejects_duplicates():
    planning_input = make_input(3)
    with pytest.raises(ValueError):
        plan_routes(planning_input, matrix_for(planning_input), "greedy", random_seed=1)
    plan = greedy(planning_input)
    data = plan.model_dump()
    data["unassigned_tasks"] = [{"task_id": plan.crew_routes[0].stops[0].task_id, "reason": "exceeds_shift_limit"}]
    with pytest.raises(ValidationError):
        type(plan).model_validate(data)


def test_planning_input_rejects_non_active_or_duplicate_tasks():
    planning_input = make_input(2)
    with pytest.raises(ValidationError):
        type(planning_input).model_validate({**planning_input.model_dump(), "tasks": [planning_input.tasks[0].model_dump()] * 2})
    done = planning_input.tasks[0].model_copy(update={"status": "completed"}).model_dump()
    with pytest.raises(ValidationError):
        type(planning_input).model_validate({**planning_input.model_dump(), "tasks": [done]})


def test_unlimited_shift_assigns_every_reachable_task():
    planning_input = make_input(20, shift_limit=ShiftLimit(mode="unlimited"))
    plan = greedy(planning_input)
    assert plan.unassigned_tasks == [] and len(assigned_ids(plan)) == 20
    assert max(r.total_work_minutes for r in plan.crew_routes) > 480.0


def test_objective_key_never_trades_a_p1_for_shorter_tasks():
    """Dropping one long P1 to fit two P3 tasks must rank worse, whatever the cost."""
    planning_input = make_input(20)
    problem = RoutingProblem(planning_input, matrix_for(planning_input))
    p1 = next(i for i, t in enumerate(planning_input.tasks) if t.priority == "P1")
    p3s = [i for i, t in enumerate(planning_input.tasks) if t.priority == "P3"][:2]
    keep_p1 = problem.evaluate([[p1], [], [], []])
    tiny = problem.limit
    problem.limit = 0.0    # force every task to be skipped for the comparison sample
    drop_all = problem.evaluate([[p1, *p3s], [], [], []])
    problem.limit = tiny
    assert drop_all.skipped_by_priority == (1, 0, 2)
    assert keep_p1.key < drop_all.key
    assert (0, 0, 2, 10_000.0) < (1, 0, 0, 0.0)
