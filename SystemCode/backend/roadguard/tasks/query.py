"""Read one complete persisted task snapshot without lifecycle side effects."""

from pathlib import Path
import sqlite3

from roadguard.database import Database, DatabaseStateError, read_revision
from roadguard.errors import AppError, StaleRevisionError
from roadguard.schemas.task import Task
from roadguard.schemas.task_query import TaskSnapshot
from roadguard.schemas.workflow import TaskRecord


class TaskQueryService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def snapshot(self, expected_revision: int | None = None, *,
                 connection: sqlite3.Connection | None = None) -> TaskSnapshot:
        """Read all active tasks, or participate in the caller's shared transaction.

        Supplied connections are never begun, committed, rolled back or closed here.
        B can read its crew rows before/after this call in the same transaction.
        """
        if expected_revision is not None and (type(expected_revision) is not int or expected_revision < 0):
            raise AppError("validation_error", "Expected input revision must be a non-negative integer.", 422)
        try:
            if connection is not None:
                if not isinstance(connection, sqlite3.Connection) or not connection.in_transaction:
                    raise AppError("validation_error", "An active shared database transaction is required.", 422)
                return self._snapshot(connection, expected_revision)
            with self.database.connect() as owned_connection:
                return self._snapshot(owned_connection, expected_revision)
        except (sqlite3.Error, DatabaseStateError, OSError, ValueError, TypeError):
            raise AppError("database_unavailable", "The persisted task snapshot is unavailable.", 503) from None

    def _snapshot(self, connection: sqlite3.Connection, expected_revision: int | None) -> TaskSnapshot:
        # The first read establishes SQLite's snapshot before any task/crew reads.
        revision = read_revision(connection)
        main = next((row for row in connection.execute("PRAGMA database_list") if row[1] == "main"), None)
        if main is None or not main[2] or Path(main[2]).resolve() != self.database.path.resolve():
            raise AppError("validation_error", "The connection must belong to the shared database.", 422)
        if expected_revision is not None and expected_revision != revision:
            raise StaleRevisionError(expected_revision, revision)
        # Validate all persisted task rows before filtering. A corrupt status column
        # must not silently hide a task or yield a partial valid planning input.
        rows = connection.execute(
            "SELECT task_id,inspection_id,status,record_version,created_at,record_json "
            "FROM tasks ORDER BY created_at,task_id"
        ).fetchall()
        tasks = []
        for row in rows:
            record = TaskRecord.model_validate_json(row[5])
            if (record.task_id, record.inspection_id, record.status, record.record_version,
                    record.created_at.isoformat()) != tuple(row[:5]):
                raise DatabaseStateError("Stored task columns do not match the record.")
            if record.status == "active":
                fields = record.model_dump(mode="python", include=set(Task.model_fields))
                tasks.append(Task.model_validate(fields))
        return TaskSnapshot(source="persisted_workflow", input_revision=revision,
                            tasks=tasks, total=len(tasks), is_demo=True)
