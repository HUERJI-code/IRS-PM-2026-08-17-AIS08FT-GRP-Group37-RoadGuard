"""Crew availability: persisted planning input that shares A's input_revision."""

from datetime import datetime, timezone
from functools import wraps
import hashlib
import json
import sqlite3

from roadguard.database import Database, DatabaseStateError, increment_revision, read_revision
from roadguard.errors import AppError
from roadguard.routing.models import Crew

from .schemas import CrewList, CrewMutation, CrewPatch, CrewRecord


def _db_operation(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except (sqlite3.Error, DatabaseStateError):
            raise AppError("database_unavailable", "The crew database is unavailable.", 503) from None
    return wrapped


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_record(row) -> CrewRecord:
    if row[2] not in (0, 1):
        raise DatabaseStateError("Stored crew availability is invalid.")
    return CrewRecord(crew_id=row[0], name=row[1], available=bool(row[2]), depot_id=row[3],
                      record_version=row[4], updated_at=row[5])


class CrewService:
    """Configured crew IDs are the roster; the crews table stores only changed state.

    A crew without a row has its configured default: available, record_version 1 and
    updated_at null. Startup therefore needs no write lock, and the first PATCH inserts
    the row. Rows for crews no longer in the configuration are ignored.
    """

    def __init__(self, database: Database, crew_ids: list[str], depot_id: str) -> None:
        if not crew_ids or len(set(crew_ids)) != len(crew_ids):
            raise ValueError("configured crew IDs must be non-empty and unique")
        self.database = database
        self.crew_ids = list(crew_ids)
        self.depot_id = depot_id

    def _default(self, crew_id: str) -> CrewRecord:
        return CrewRecord(crew_id=crew_id, name=f"Crew {crew_id.rsplit('-', 1)[-1]}", available=True,
                          depot_id=self.depot_id, record_version=1, updated_at=None)

    def read_records(self, connection: sqlite3.Connection) -> list[CrewRecord]:
        """Read inside the caller's transaction so crews share the task snapshot revision."""
        rows = {row[0]: _row_to_record(row) for row in connection.execute(
            "SELECT crew_id,name,available,depot_id,record_version,updated_at FROM crews")}
        return [rows.get(crew_id) or self._default(crew_id) for crew_id in self.crew_ids]

    def read_planning_crews(self, connection: sqlite3.Connection) -> list[Crew]:
        return [Crew(crew_id=r.crew_id, name=r.name, available=r.available, depot_id=r.depot_id)
                for r in self.read_records(connection)]

    @_db_operation
    def list(self) -> CrewList:
        with self.database.connect() as connection:
            revision = read_revision(connection)
            return CrewList(crews=self.read_records(connection), input_revision=revision)

    def _get(self, connection: sqlite3.Connection, crew_id: str) -> CrewRecord:
        if crew_id not in self.crew_ids:
            raise AppError("not_found", "The requested resource was not found.", 404)
        return next(r for r in self.read_records(connection) if r.crew_id == crew_id)

    @_db_operation
    def update(self, crew_id: str, payload: CrewPatch) -> CrewMutation:
        with self.database.transaction() as connection:
            return self.update_in_transaction(connection, crew_id, payload)

    def update_in_transaction(self, connection: sqlite3.Connection, crew_id: str, payload: CrewPatch) -> CrewMutation:
        """Use the caller's transaction for atomic C confirmation; never commit here."""
        if not connection.in_transaction:
            raise RuntimeError("Crew changes require a caller-owned transaction.")
        payload = CrewPatch.model_validate(payload.model_dump())
        scope = "crew:" + crew_id
        fingerprint = hashlib.sha256(json.dumps(payload.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
        # Same idempotency table and semantics as A's task mutations.
        stored = connection.execute("SELECT payload_hash FROM operation_keys WHERE scope=? AND request_key=?",
                                    (scope, payload.request_id)).fetchone()
        if stored is not None:
            if stored[0] != fingerprint:
                raise AppError("idempotency_conflict", "The request key was already used for different input.", 409)
            return CrewMutation(crew=self._get(connection, crew_id), input_revision=read_revision(connection),
                                planning_input_changed=False, replayed=True)
        crew = self._get(connection, crew_id)
        if crew.record_version != payload.expected_version:
            raise AppError("stale_record_version", "The crew has changed. Reload it before retrying.", 409)
        changed = crew.available != payload.available
        if changed:
            # Availability and the shared revision change in one transaction.
            connection.execute(
                "INSERT INTO crews VALUES (?,?,?,?,?,?) ON CONFLICT(crew_id) DO UPDATE SET "
                "available=excluded.available, record_version=excluded.record_version, "
                "updated_at=excluded.updated_at",
                (crew.crew_id, crew.name, int(payload.available), crew.depot_id, crew.record_version + 1,
                 _now().isoformat()))
            increment_revision(connection)
        connection.execute("INSERT INTO operation_keys VALUES (?,?,?,?,?)",
                           (scope, payload.request_id, fingerprint, crew_id, _now().isoformat()))
        return CrewMutation(crew=self._get(connection, crew_id), input_revision=read_revision(connection),
                            planning_input_changed=changed, replayed=False)
