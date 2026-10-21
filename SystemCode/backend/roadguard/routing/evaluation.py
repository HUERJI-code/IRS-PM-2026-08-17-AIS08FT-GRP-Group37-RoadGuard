"""One shared schedule evaluator, so Greedy and GA obey identical constraints and metrics.

Model (demo assumptions from routing config): every available crew leaves the shared
depot at planning_start_at (minute 0), drives and services tasks back to back with no
waiting, and drives back to the depot when return_to_depot is true. A crew's total work
is travel (including the depot legs) plus service.
"""

from dataclasses import dataclass, field
import math
import statistics

from .models import (
    CrewRoute, PlanMetrics, PlanningInput, Stop, TravelMatrix, UnassignedReason, UnassignedTask,
)
from .matrix import node_ids


@dataclass(frozen=True)
class Evaluation:
    """Decoded schedule for one candidate; routes hold task indices per available crew."""

    routes: tuple[tuple[int, ...], ...]
    skipped: tuple[tuple[int, UnassignedReason], ...]
    crew_travel: tuple[float, ...]
    crew_return: tuple[float | None, ...]
    crew_service: tuple[float, ...]
    arrival: dict[int, float] = field(compare=False)
    completion: dict[int, float] = field(compare=False)
    makespan: float
    total_travel: float
    workload_std: float | None
    priority_completion: float | None
    objective: float
    skipped_by_priority: tuple[int, int, int]   # skipped P1, P2, P3 counts

    @property
    def unassigned_count(self) -> int:
        return len(self.skipped)

    @property
    def key(self) -> tuple[int, int, int, float]:
        # Lexicographic: never drop a more urgent task to fit more short ones, and never
        # drop tasks to improve cost. A plain count would let long P1 jobs be sacrificed.
        return (*self.skipped_by_priority, self.objective)


class RoutingProblem:
    """Index-based view of a PlanningInput and its TravelMatrix for fast evaluation."""

    def __init__(self, planning_input: PlanningInput, matrix: TravelMatrix) -> None:
        expected = node_ids(planning_input)
        if matrix.node_ids != expected:
            raise ValueError("matrix node order must be the depot followed by tasks in input order")
        self.input = planning_input
        self.matrix = matrix
        self.settings = planning_input.settings
        self.tasks = planning_input.tasks
        self.duration = matrix.duration_minutes   # node 0 = depot, node i+1 = task i
        self.available_crews = [crew.crew_id for crew in planning_input.crews if crew.available]
        self.limit = self.settings.shift_limit.minutes
        self.priority_weight = [self.settings.priority_weights[task.priority] for task in self.tasks]
        self.service = [task.service_minutes for task in self.tasks]
        self.prefiltered: dict[int, UnassignedReason] = {}
        for index, task in enumerate(self.tasks):
            reason = self._prefilter_reason(index)
            if reason and reason != "assigned_crew_unavailable" and task.task_id in planning_input.task_crew_constraints:
                reason = "assigned_crew_infeasible"
            if reason is not None:
                self.prefiltered[index] = reason
        self.schedulable = [i for i in range(len(self.tasks)) if i not in self.prefiltered]

    def _prefilter_reason(self, index: int) -> UnassignedReason | None:
        """Tasks that no crew could ever serve, identical for every algorithm."""
        locked = self.input.task_crew_constraints.get(self.tasks[index].task_id)
        if locked and locked not in self.available_crews:
            return "assigned_crew_unavailable"
        node = index + 1
        if self.service[index] is None:
            return "unknown_service_minutes"
        if self.duration[0][node] is None:
            return "unreachable_from_depot"
        back = self.duration[node][0]
        if self.settings.return_to_depot and back is None:
            return "unreachable_to_depot"
        if not self.available_crews:
            return "no_available_crew"
        if self.limit is not None:
            solo = self.duration[0][node] + self.service[index] + (back if self.settings.return_to_depot else 0)
            if solo > self.limit:
                return "exceeds_shift_limit"
        return None

    def leg(self, from_task: int | None, to_task: int | None) -> float | None:
        """Travel minutes between task indices; None denotes the depot."""
        return self.duration[0 if from_task is None else from_task + 1][0 if to_task is None else to_task + 1]

    def fits(self, elapsed: float, previous: int | None, task: int) -> tuple[bool, UnassignedReason | None]:
        """Can a crew at `previous` after `elapsed` minutes still take `task`?"""
        travel = self.leg(previous, task)
        if travel is None:
            return False, "no_feasible_route_position"
        if self.limit is not None:
            back = self.leg(task, None) if self.settings.return_to_depot else 0.0
            if elapsed + travel + self.service[task] + back > self.limit:
                return False, "exceeds_shift_limit"
        return True, None

    def evaluate(self, routes: list[list[int]] | tuple[tuple[int, ...], ...]) -> Evaluation:
        """Decode crew orders; infeasible stops are skipped and reported, never hidden."""
        if len(routes) != len(self.available_crews):
            raise ValueError("one route per available crew is required")
        # Normalize every candidate ownership before evaluation, including GA mutations.
        normalized = [[] for _ in self.available_crews]
        for slot, route in enumerate(routes):
            for task in route:
                locked = self.input.task_crew_constraints.get(self.tasks[task].task_id)
                normalized[self.available_crews.index(locked) if locked else slot].append(task)
        routes = normalized
        kept_routes, skipped = [], []
        travel_totals, return_legs, service_totals, arrival, completion = [], [], [], {}, {}
        for route in routes:
            elapsed, travel_sum, service_sum, previous, kept = 0.0, 0.0, 0.0, None, []
            for task in route:
                ok, reason = self.fits(elapsed, previous, task)
                if not ok:
                    skipped.append((task, "assigned_crew_infeasible" if self.tasks[task].task_id in self.input.task_crew_constraints else reason))
                    continue
                travel = self.leg(previous, task)
                arrival[task] = elapsed + travel
                elapsed = arrival[task] + self.service[task]
                travel_sum += travel
                service_sum += self.service[task]
                completion[task] = elapsed
                kept.append(task)
                previous = task
            back = None
            if self.settings.return_to_depot and kept:
                back = self.leg(previous, None)   # prefilter guarantees reachability
                travel_sum += back
            kept_routes.append(tuple(kept))
            travel_totals.append(travel_sum)
            return_legs.append(back)
            service_totals.append(service_sum)
        work = [t + s for t, s in zip(travel_totals, service_totals)]
        makespan = max(work, default=0.0)
        total_travel = math.fsum(travel_totals)  # order independent: GA and Greedy report equal sums
        workload_std = statistics.pstdev(work) if work else None
        weight_sum = sum(self.priority_weight[t] for t in completion)
        priority_completion = (sum(self.priority_weight[t] * c for t, c in completion.items()) / weight_sum
                               if weight_sum else None)
        weights = self.settings.weights
        objective = (weights.makespan_minutes * makespan
                     + weights.total_travel_minutes * total_travel
                     + weights.workload_std_minutes * (workload_std or 0.0)
                     + weights.priority_weighted_completion_minutes * (priority_completion or 0.0))
        return Evaluation(
            routes=tuple(kept_routes), skipped=tuple(skipped), crew_travel=tuple(travel_totals),
            crew_return=tuple(return_legs), crew_service=tuple(service_totals), arrival=arrival, completion=completion,
            makespan=makespan, total_travel=total_travel, workload_std=workload_std,
            priority_completion=priority_completion, objective=objective,
            skipped_by_priority=tuple(
                sum(1 for task, _ in skipped if self.tasks[task].priority == p) for p in ("P1", "P2", "P3")),
        )

    def build_routes_and_metrics(self, evaluation: Evaluation, runtime_ms: float
                                 ) -> tuple[list[CrewRoute], list[UnassignedTask], PlanMetrics]:
        """Expand an evaluation into the wire format, listing all configured crews."""
        by_crew = dict(zip(self.available_crews, range(len(self.available_crews))))
        crew_routes = []
        for crew in self.input.crews:
            slot = by_crew.get(crew.crew_id)
            if slot is None:
                crew_routes.append(CrewRoute(
                    crew_id=crew.crew_id, available=False, status="unavailable", stops=[],
                    travel_minutes=0.0, return_travel_minutes=None, service_minutes=0.0,
                    total_work_minutes=0.0, end_minute=0.0))
                continue
            stops, previous = [], None
            for sequence, task_index in enumerate(evaluation.routes[slot], start=1):
                task = self.tasks[task_index]
                completed = evaluation.completion[task_index]
                stops.append(Stop(
                    sequence=sequence, task_id=task.task_id, damage_label=task.damage_label,
                    locked_crew_id=self.input.task_crew_constraints.get(task.task_id), latitude=task.latitude,
                    longitude=task.longitude, priority=task.priority,
                    travel_minutes_from_previous=self.leg(previous, task_index),
                    arrival_minute=evaluation.arrival[task_index],
                    service_minutes=task.service_minutes, completion_minute=completed))
                previous = task_index
            total = evaluation.crew_travel[slot] + evaluation.crew_service[slot]
            crew_routes.append(CrewRoute(
                shift_remaining_minutes=max(0.0, self.limit-total) if self.limit is not None else None,
                crew_id=crew.crew_id, available=True, status="assigned" if stops else "idle",
                stops=stops, travel_minutes=evaluation.crew_travel[slot],
                return_travel_minutes=evaluation.crew_return[slot],
                service_minutes=evaluation.crew_service[slot], total_work_minutes=total, end_minute=total))
        unassigned = sorted(
            [*self.prefiltered.items(), *evaluation.skipped], key=lambda item: item[0])
        unassigned_tasks = [UnassignedTask(task_id=self.tasks[i].task_id, reason=r) for i, r in unassigned]
        metrics = PlanMetrics(
            assigned_task_count=len(evaluation.completion),
            unassigned_task_count=len(unassigned_tasks),
            unassigned_by_priority={p: sum(1 for i, _ in unassigned if self.tasks[i].priority == p)
                                    for p in ("P1", "P2", "P3")},
            total_travel_minutes=evaluation.total_travel,
            total_service_minutes=sum(evaluation.crew_service),
            makespan_minutes=evaluation.makespan,
            workload_std_minutes=evaluation.workload_std,
            priority_weighted_completion_minutes=evaluation.priority_completion,
            **self._lateness(evaluation),
            objective_value=evaluation.objective,
            algorithm_runtime_ms=runtime_ms,
        )
        return crew_routes, unassigned_tasks, metrics

    def _lateness(self, evaluation: Evaluation) -> dict[str, float | int | None]:
        """Lateness only for tasks with a known due_at; none known means no lateness metric."""
        start = self.input.planning_start_at
        due = {i: t.due_at for i, t in enumerate(self.tasks) if t.due_at is not None}
        if not due:
            return {"tasks_with_due_at": 0, "total_lateness_minutes": None, "late_task_count": None}
        lateness = [max(0.0, evaluation.completion[i] - (d - start).total_seconds() / 60)
                    for i, d in due.items() if i in evaluation.completion]
        return {"tasks_with_due_at": len(due), "total_lateness_minutes": math.fsum(lateness),
                "late_task_count": sum(1 for value in lateness if value > 0)}
