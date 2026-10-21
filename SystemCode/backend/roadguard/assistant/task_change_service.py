"""Owner-scoped, transactional manual dispatch intents; no business writes in preview."""
from datetime import timedelta
import hashlib
import json
import uuid

from roadguard.auth.access import active_actor
from roadguard.database import DatabaseStateError, assert_revision, increment_revision
from roadguard.errors import AppError
from roadguard.routing.evaluation import RoutingProblem
from roadguard.routing.settings import build_planning_input
from roadguard.schemas.workflow import TaskPatch
from .change_service import ChangeService, now, safe_db
from .task_change_models import TaskChangeRecord, TaskChangeList


class TaskChangeService(ChangeService):
    def __init__(self, database, crews, queries, planning, workflow):
        super().__init__(database, crews, queries, planning)
        self.workflow = workflow

    def _config_fingerprint(self):
        configuration = self.planning.config.model_dump_json() + self.planning.depot.model_dump_json()
        return hashlib.sha256(configuration.encode()).hexdigest()

    def _read(self, connection, change_id, actor_id):
        row = connection.execute("SELECT change_id,actor_id,client_key,record_json FROM assistant_task_changes WHERE change_id=? AND actor_id=?", (change_id, actor_id)).fetchone()
        if row is None:
            raise AppError("not_found", "The task change was not found.", 404)
        record = TaskChangeRecord.model_validate_json(row[3])
        if (record.change_id, record.actor_id, record.client_key) != tuple(row[:3]):
            raise DatabaseStateError("Stored task change columns mismatch.")
        return record

    def _event(self, connection, record, action, details=None):
        connection.execute("INSERT INTO assistant_task_change_events VALUES (?,?,?,?,?,?)", (uuid.uuid4().hex, record.change_id, record.actor_id, action, now().isoformat(), json.dumps(details or {}, sort_keys=True)))

    def _save(self, connection, record, action, details=None):
        record.record_version += 1
        connection.execute("UPDATE assistant_task_changes SET record_json=? WHERE change_id=? AND actor_id=?", (record.model_dump_json(), record.change_id, record.actor_id))
        self._event(connection, record, action, details)
        return record

    @safe_db
    def list(self, actor_id):
        with self.database.connect() as connection:
            rows = connection.execute("SELECT change_id FROM assistant_task_changes WHERE actor_id=? ORDER BY rowid DESC LIMIT 20", (actor_id,)).fetchall()
            return TaskChangeList(items=[self._view(self._read(connection, r[0], actor_id)) for r in rows])

    def _replay(self, connection, payload, actor_id, fingerprint):
        row = connection.execute("SELECT change_id,payload_hash FROM assistant_task_changes WHERE actor_id=? AND client_key=?", (actor_id, payload.request_id)).fetchone()
        if row:
            if row[1] != fingerprint:
                raise AppError("idempotency_conflict", "The preview key was used for different input.", 409)
            return self._view(self._read(connection, row[0], actor_id))

    @safe_db
    def preview(self, payload, actor_id):
        fingerprint = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
        config_fingerprint = self._config_fingerprint()
        with self.database.connect() as connection:
            replay = self._replay(connection, payload, actor_id, fingerprint)
            if replay:
                return replay
            plan = self.queries.get(payload.based_on_plan_id, connection=connection)
            assert_revision(connection, plan.input_revision)
            task = self.workflow._task(connection, payload.task_id)
            if task.status != "active":
                raise AppError("invalid_state", "Only active tasks can be changed.", 409)
            source = next((r.crew_id for r in plan.crew_routes if any(s.task_id == task.task_id for s in r.stops)), None)
            if source is None and (payload.action == "reassign" or not any(t.task_id == task.task_id for t in plan.unassigned_tasks)):
                raise AppError("task_not_assigned", "The task is not assigned in this saved plan.", 409)
            crews = self.crews.read_planning_crews(connection)
            if payload.action == "reassign":
                target = next((c for c in crews if c.crew_id == payload.target_crew_id), None)
                if target is None or not target.available or target.crew_id == source:
                    raise AppError("invalid_target_crew", "Choose another available crew.", 422)
            snapshot = self.planning.tasks.snapshot(plan.input_revision, connection=connection)
            constraints = dict(connection.execute("SELECT task_id,crew_id FROM task_crew_constraints"))
        # Matrix/provider work runs without a database writer lock. Revision is checked again below.
        inputs = build_planning_input(snapshot, crews, self.planning.depot, self.planning.config.settings, plan.planning_start_at)
        if inputs.settings != plan.settings:
            raise AppError("stale_planning_settings", "Recalculate with current settings before changing tasks.", 409)
        if payload.action == "reassign":
            constraints[task.task_id] = payload.target_crew_id
        else:
            constraints.pop(task.task_id, None)
        inputs = inputs.model_copy(update={"task_crew_constraints": constraints})
        matrix = self.planning._travel_matrix(inputs)
        problem = RoutingProblem(inputs, matrix)
        index = {t.task_id: i for i, t in enumerate(inputs.tasks)}
        by_crew = {route.crew_id: route for route in plan.crew_routes}
        sequences = [[index[stop.task_id] for stop in by_crew[crew].stops
                      if stop.task_id != task.task_id] for crew in problem.available_crews]
        required = {index[s.task_id] for r in plan.crew_routes for s in r.stops if s.task_id != task.task_id}
        if payload.action == "reassign":
            required.add(index[task.task_id])
        if required.intersection(problem.prefiltered):
            raise AppError("task_change_infeasible", "An affected route contains a task with unreachable travel or insufficient shift capacity.", 409, {"shift_limit_minutes": problem.limit, "return_to_depot": inputs.settings.return_to_depot})
        candidates = []
        if payload.action == "reassign":
            slot = problem.available_crews.index(payload.target_crew_id)
            for position in range(len(sequences[slot])+1):
                route = [r[:] for r in sequences]
                route[slot].insert(position, index[task.task_id])
                candidates.append(problem.evaluate(route))
        else:
            candidates.append(problem.evaluate(sequences))
        feasible = [e for e in candidates if set(e.completion) == required and not e.skipped]
        if not feasible:
            raise AppError("task_change_infeasible", "The changed routes cannot retain all assigned tasks within the configured travel, service and depot-return limits.", 409, {"shift_limit_minutes": problem.limit, "return_to_depot": inputs.settings.return_to_depot})
        best = min(feasible, key=lambda e: e.key)
        after, _, _ = problem.build_routes_and_metrics(best, 0.0)
        created = now()
        record = TaskChangeRecord(
            change_id="task-change-" + uuid.uuid4().hex, actor_id=actor_id,
            client_key=payload.request_id, based_on_plan_id=plan.plan_id,
            input_revision=plan.input_revision, action=payload.action, task_id=task.task_id,
            task_record_version=task.record_version, planning_config_fingerprint=config_fingerprint,
            source_crew_id=source, target_crew_id=payload.target_crew_id, status="pending",
            record_version=1, created_at=created, expires_at=created + timedelta(minutes=15),
            before_routes=plan.crew_routes, after_routes=after, shift_limit_minutes=problem.limit,
            return_to_depot=inputs.settings.return_to_depot)
        with self.database.transaction(expected_revision=plan.input_revision) as connection:
            if config_fingerprint != self._config_fingerprint():
                raise AppError("stale_planning_settings", "Planning settings changed during preview.", 409)
            replay = self._replay(connection, payload, actor_id, fingerprint)
            if replay:
                return replay
            connection.execute("INSERT INTO assistant_task_changes VALUES (?,?,?,?,?)", (record.change_id, actor_id, payload.request_id, fingerprint, record.model_dump_json()))
            self._event(connection, record, "previewed")
        return record

    @safe_db
    def confirm(self, change_id, actor, expected_version):
        actor_id = actor.user_id
        with self.database.transaction() as connection:
            active_actor(connection, actor)
            record = self._read(connection, change_id, actor_id)
            if record.status == "confirmed":
                return record
            if record.status != "pending" or record.expires_at <= now():
                raise AppError("change_not_pending", "This preview has closed or expired.", 409)
            if record.record_version != expected_version:
                raise AppError("stale_record_version", "Reload the preview before confirming.", 409)
            assert_revision(connection, record.input_revision)
            if record.planning_config_fingerprint != self._config_fingerprint():
                raise AppError("stale_planning_settings", "Planning configuration changed; create a new preview.", 409)
            task = self.workflow._task(connection, record.task_id)
            if task.status != "active" or task.record_version != record.task_record_version:
                raise AppError("stale_record_version", "The task changed since preview.", 409)
            if record.action == "reassign":
                crew = next((c for c in self.crews.read_planning_crews(connection) if c.crew_id == record.target_crew_id), None)
                if crew is None or not crew.available:
                    raise AppError("invalid_target_crew", "The selected crew is unavailable.", 409)
                connection.execute(
                    "INSERT INTO task_crew_constraints VALUES (?,?,?) ON CONFLICT(task_id) "
                    "DO UPDATE SET crew_id=excluded.crew_id,change_id=excluded.change_id",
                    (task.task_id, record.target_crew_id, record.change_id))
                record.applied_revision = increment_revision(connection)
            else:
                patch = TaskPatch(request_id=record.change_id, expected_version=task.record_version,
                                  status="cancelled")
                result = self.workflow.update_task(task.task_id, patch, actor=actor, connection=connection)
                connection.execute("DELETE FROM task_crew_constraints WHERE task_id=?", (task.task_id,))
                record.applied_revision = result.input_revision
            record.status = "confirmed"
            return self._save(connection, record, "confirmed", {"input_revision": record.applied_revision})
