"""Authorization within caller-owned transactions, including crew reassignment races."""

import time
from uuid import uuid4

from roadguard.errors import AppError
from roadguard.routing.service import RouteQueryService
from .models import Account


def denied():
    raise AppError("forbidden", "This account cannot perform that action.", 403)


def not_accessible():
    raise AppError("not_found", "The requested resource was not found.", 404)


def latest_ga(connection):
    row = connection.execute("SELECT plan_id,plan_json,algorithm,input_revision FROM route_plans WHERE algorithm='ga' "
                             "ORDER BY created_at DESC,rowid DESC LIMIT 1").fetchone()
    return RouteQueryService._load(connection, row) if row else None


def active_actor(connection, actor: Account):
    row = connection.execute("SELECT role,crew_id FROM auth_users WHERE user_id=? AND enabled=1", (actor.user_id,)).fetchone()
    if not row or row[0] != actor.role or row[1] != actor.crew_id:
        raise AppError("authentication_required", "Sign in to continue.", 401)


def affinity_matches(connection, task_id: str, crew_id: str) -> bool:
    """A confirmed dispatcher constraint takes effect before explicit replanning."""
    row = connection.execute("SELECT crew_id FROM task_crew_constraints WHERE task_id=?", (task_id,)).fetchone()
    return row is None or row[0] == crew_id


def check_task(connection, actor: Account, task_id: str, *, writing: bool = False, replay: bool = False):
    active_actor(connection, actor)
    if actor.role == "dispatcher":
        return None
    if actor.role != "crew":
        denied()
    plan = latest_ga(connection)
    route = next((r for r in plan.crew_routes if r.crew_id == actor.crew_id), None) if plan else None
    assigned = (route is not None and any(stop.task_id == task_id for stop in route.stops)
                and affinity_matches(connection, task_id, actor.crew_id))
    receipt = connection.execute("SELECT 1 FROM auth_audit WHERE resource_id=? AND crew_id=? AND action='task.completed'",
                                 (task_id, actor.crew_id)).fetchone()
    if not assigned and not (receipt and (not writing or replay)):
        not_accessible()
    if writing and not replay:
        row = connection.execute("SELECT available FROM crews WHERE crew_id=?", (actor.crew_id,)).fetchone()
        if not route or not route.available or (row and not row[0]):
            denied()
    return plan.plan_id if assigned else None


def check_inspection(connection, actor: Account, inspection_id: str):
    active_actor(connection, actor)
    if actor.role == "dispatcher":
        return
    if actor.role == "inspector":
        if connection.execute("SELECT 1 FROM inspection_owners WHERE inspection_id=? AND user_id=?", (inspection_id, actor.user_id)).fetchone():
            return
        not_accessible()
    row = connection.execute("SELECT task_id FROM tasks WHERE inspection_id=?", (inspection_id,)).fetchone()
    if not row:
        not_accessible()
    check_task(connection, actor, row[0])


def audit(connection, actor: Account, action: str, resource_id: str, request_id: str, plan_id: str | None = None):
    connection.execute("INSERT INTO auth_audit VALUES (?,?,?,?,?,?,?,?)", (
        uuid4().hex, actor.user_id, action, resource_id, request_id, actor.crew_id, plan_id, int(time.time())))
