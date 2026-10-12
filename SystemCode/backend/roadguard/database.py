"""SQLite infrastructure shared by future A/B/C domain services."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator

from roadguard.errors import StaleRevisionError


SCHEMA_VERSION = 1


class DatabaseStateError(RuntimeError):
    """The infrastructure database is missing or incompatible."""


def _validate_revision(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("Input revision must be a non-negative integer.")


def read_revision(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT schema_version, input_revision FROM infra_metadata WHERE singleton_id = 1"
    ).fetchone()
    if row is None or row[0] != SCHEMA_VERSION:
        raise DatabaseStateError("Infrastructure schema is not initialized or is incompatible.")
    if type(row[1]) is not int or row[1] < 0:
        raise DatabaseStateError("Stored input revision is invalid.")
    return row[1]


def assert_revision(connection: sqlite3.Connection, expected_revision: int) -> int:
    _validate_revision(expected_revision)
    current = read_revision(connection)
    if expected_revision != current:
        raise StaleRevisionError(expected_revision, current)
    return current


def increment_revision(connection: sqlite3.Connection, expected_revision: int | None = None) -> int:
    """Increment inside the domain mutation transaction; never commit independently."""
    if not connection.in_transaction:
        raise RuntimeError("Revision changes require a caller-owned transaction.")
    current = read_revision(connection) if expected_revision is None else assert_revision(connection, expected_revision)
    cursor = connection.execute(
        "UPDATE infra_metadata SET input_revision = input_revision + 1 "
        "WHERE singleton_id = 1 AND input_revision = ?",
        (current,),
    )
    if cursor.rowcount != 1:
        raise StaleRevisionError(current, read_revision(connection))
    return read_revision(connection)


class Database:
    def __init__(self, path: Path, busy_timeout_ms: int = 5000) -> None:
        self.path = Path(path)
        self.busy_timeout_ms = busy_timeout_ms

    def _open(self, *, read_only: bool = False) -> sqlite3.Connection:
        # Read-only URI prevents a health/read request recreating a deleted DB.
        target = self.path.resolve().as_uri() + "?mode=ro" if read_only else str(self.path)
        connection = sqlite3.connect(
            target,
            timeout=self.busy_timeout_ms / 1000,
            isolation_level=None,
            uri=read_only,
        )
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout_ms)}")
            if read_only:
                connection.execute("PRAGMA query_only = ON")
            return connection
        except BaseException:
            connection.close()
            raise

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """A per-operation, read-only consistent snapshot, closed on exit."""
        connection = self._open(read_only=True)
        try:
            connection.execute("BEGIN")
            yield connection
        finally:
            if connection.in_transaction:
                connection.rollback()
            connection.close()

    @contextmanager
    def transaction(self, expected_revision: int | None = None) -> Iterator[sqlite3.Connection]:
        """Serialize writers; check stale inputs before the caller mutates data."""
        connection = self._open()
        try:
            connection.execute("BEGIN IMMEDIATE")
            if expected_revision is not None:
                assert_revision(connection, expected_revision)
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        """Idempotent infrastructure migration entrypoint, called by lifespan."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS infra_metadata ("
                "singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1), "
                "schema_version INTEGER NOT NULL, "
                "input_revision INTEGER NOT NULL CHECK (input_revision >= 0))"
            )
            connection.execute(
                "INSERT OR IGNORE INTO infra_metadata (singleton_id, schema_version, input_revision) "
                "VALUES (1, ?, 0)",
                (SCHEMA_VERSION,),
            )
            read_revision(connection)
