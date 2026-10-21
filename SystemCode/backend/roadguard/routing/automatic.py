"""Best-effort planning after committed task acceptance; no durable job queue."""

import logging
from threading import Lock
from typing import Literal

from roadguard.database import read_revision
from roadguard.errors import AppError
from .service import PlanningService, RecalculateRequest

logger = logging.getLogger(__name__)
Outcome = Literal["completed", "failed", "not_needed"]


class AutomaticPlanningCoordinator:
    """Serialize automatic attempts per app process and retry revision races only."""

    def __init__(self, planning: PlanningService) -> None:
        self.planning = planning
        self._lock = Lock()

    def after_acceptance(self, task_id: str | None) -> Outcome:
        if task_id is None:
            return "not_needed"
        try:
            with self._lock:
                for attempt in range(3):
                    with self.planning.database.connect() as connection:
                        task = connection.execute("SELECT status FROM tasks WHERE task_id=?", (task_id,)).fetchone()
                        if task is None or task[0] != "active":
                            return "not_needed"
                        revision = read_revision(connection)
                        latest = [connection.execute(
                            "SELECT input_revision FROM route_plans WHERE algorithm=? "
                            "ORDER BY created_at DESC, rowid DESC LIMIT 1", (algorithm,)).fetchone()
                            for algorithm in ("ga", "greedy")]
                        if all(row is not None and row[0] == revision for row in latest):
                            return "not_needed"
                    # The snapshot transaction is closed before matrix/GA work begins.
                    try:
                        self.planning.recalculate(RecalculateRequest(expected_revision=revision))
                        return "completed"
                    except AppError as exc:
                        if exc.code == "stale_input_revision" and attempt < 2:
                            continue
                        break
        except Exception:
            # Never log exception text, provider payloads, or user input.
            logger.warning("automatic_planning_failed")
            return "failed"
        logger.warning("automatic_planning_failed")
        return "failed"
