"""SQLite infrastructure shared by future A/B/C domain services."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator

from roadguard.errors import StaleRevisionError


SCHEMA_VERSION = 3

# B-owned routing tables (v3). Crew availability is planning input; plans are outputs and
# never change input_revision. A integrates them through this single migration entrypoint.
ROUTING_TABLES = {
    "crews": ("CREATE TABLE crews (crew_id TEXT PRIMARY KEY, name TEXT NOT NULL, "
              "available INTEGER NOT NULL CHECK(available IN (0,1)), depot_id TEXT NOT NULL, "
              "record_version INTEGER NOT NULL CHECK(record_version>=1), updated_at TEXT NOT NULL)",
              ("crew_id", "name", "available", "depot_id", "record_version", "updated_at")),
    "route_plans": ("CREATE TABLE route_plans (plan_id TEXT PRIMARY KEY, "
                    "algorithm TEXT NOT NULL CHECK(algorithm IN ('ga','greedy')), "
                    "input_revision INTEGER NOT NULL CHECK(input_revision>=0), created_at TEXT NOT NULL, "
                    "plan_json TEXT NOT NULL)",
                    ("plan_id", "algorithm", "input_revision", "created_at", "plan_json")),
}


def _validate_routing_schema(connection: sqlite3.Connection) -> None:
    for table, (_, columns) in ROUTING_TABLES.items():
        info = connection.execute(f"PRAGMA table_info({table})").fetchall()
        if tuple(row[1] for row in info) != columns:
            raise DatabaseStateError("Routing schema is missing or incompatible.")
        if tuple(row[1] for row in info if row[5]) != (columns[0],):
            raise DatabaseStateError("Routing schema primary keys are incompatible.")


def _create_routing_tables(connection: sqlite3.Connection) -> None:
    for statement, _ in ROUTING_TABLES.values():
        connection.execute(statement)
    connection.execute("CREATE INDEX route_plans_algorithm_created ON route_plans(algorithm,created_at,plan_id)")


def _validate_workflow_schema(connection: sqlite3.Connection) -> None:
    expected = {
        "inspections": ("inspection_id", "status", "record_version", "created_at", "record_json", "policy_json"),
        "tasks": ("task_id", "inspection_id", "status", "record_version", "created_at", "record_json"),
        "operation_keys": ("scope", "request_key", "payload_hash", "resource_id", "created_at"),
    }
    for table, columns in expected.items():
        info = connection.execute(f"PRAGMA table_info({table})").fetchall()
        if tuple(row[1] for row in info) != columns:
            raise DatabaseStateError("Workflow schema is missing or incompatible.")
        if any(row[2] != ("INTEGER" if row[1] == "record_version" else "TEXT") for row in info):
            raise DatabaseStateError("Workflow schema column types are incompatible.")
        primary = tuple(row[1] for row in sorted(info, key=lambda row: row[5]) if row[5])
        if primary != (("scope", "request_key") if table == "operation_keys" else (columns[0],)):
            raise DatabaseStateError("Workflow schema primary keys are incompatible.")
    foreign_keys = connection.execute("PRAGMA foreign_key_list(tasks)").fetchall()
    if not any((row[2], row[3], row[4]) == ("inspections", "inspection_id", "inspection_id") for row in foreign_keys):
        raise DatabaseStateError("Workflow task foreign key is missing.")
    unique_indexes = [row[1] for row in connection.execute("PRAGMA index_list(tasks)") if row[2]]
    if not any(tuple(row[0] for row in connection.execute("SELECT name FROM pragma_index_info(?) ORDER BY seqno", (index,))) == ("inspection_id",)
               for index in unique_indexes):
        raise DatabaseStateError("Workflow task uniqueness constraint is missing.")


class DatabaseStateError(RuntimeError):
    """The infrastructure database is missing or incompatible."""


def _schema_version(connection: sqlite3.Connection) -> int:
    columns = connection.execute("PRAGMA table_info(infra_metadata)").fetchall()
    if tuple(row[1] for row in columns) != ("singleton_id", "schema_version", "input_revision"):
        raise DatabaseStateError("Infrastructure metadata schema is incompatible.")
    row = connection.execute("SELECT schema_version, input_revision FROM infra_metadata WHERE singleton_id=1").fetchone()
    if (row is None or row[0] not in {1, 2, SCHEMA_VERSION} or type(row[1]) is not int or row[1] < 0
            or connection.execute("SELECT COUNT(*) FROM infra_metadata").fetchone()[0] != 1):
        raise DatabaseStateError("Infrastructure schema is incompatible.")
    return row[0]


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

    def _open(self, *, read_only: bool = False, create: bool = False) -> sqlite3.Connection:
        # Only explicit initialization may create files. Reads and normal writes
        # must fail if the persistent DB disappeared, not recreate revision zero.
        mode = "ro" if read_only else ("rwc" if create else "rw")
        target = self.path.resolve().as_uri() + "?mode=" + mode
        connection = sqlite3.connect(
            target,
            timeout=self.busy_timeout_ms / 1000,
            isolation_level=None,
            uri=True,
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
        with self._write_transaction(expected_revision) as connection:
            yield connection

    @contextmanager
    def _write_transaction(self, expected_revision: int | None = None, *, create: bool = False) -> Iterator[sqlite3.Connection]:
        connection = self._open(create=create)
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
        if self.path.exists():
            # A restart only validates the current schema. BEGIN IMMEDIATE plus
            # COMMIT would needlessly compete with database viewers, even when
            # no rows changed. Release this snapshot before any migration.
            with self.connect() as connection:
                metadata_exists = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='infra_metadata'"
                ).fetchone()
                if metadata_exists and _schema_version(connection) == SCHEMA_VERSION:
                    _validate_workflow_schema(connection)
                    _validate_routing_schema(connection)
                    read_revision(connection)
                    return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._write_transaction(create=True) as connection:
            # Recheck under the write lock: another initializer may have migrated
            # the database since the read-only preflight completed.
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            workflow_tables = {"inspections", "tasks", "operation_keys"}
            if "infra_metadata" not in tables:
                # An empty DB is new. Existing business/unknown tables without the
                # singleton mean lost metadata, never permission to reset revision.
                if any(not table.startswith("sqlite_") for table in tables):
                    raise DatabaseStateError("Existing database is missing infrastructure metadata.")
                connection.execute(
                    "CREATE TABLE infra_metadata ("
                    "singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1), "
                    "schema_version INTEGER NOT NULL, "
                    "input_revision INTEGER NOT NULL CHECK (input_revision >= 0))"
                )
                connection.execute("INSERT INTO infra_metadata VALUES (1,1,0)")
            version = _schema_version(connection)
            if version == SCHEMA_VERSION:
                _validate_workflow_schema(connection)
                _validate_routing_schema(connection)
                read_revision(connection)
                return
            if tables & set(ROUTING_TABLES):
                raise DatabaseStateError("Pre-v3 database has unexpected routing tables.")
            if version == 2:
                # v2 -> v3 keeps every inspection/task/key row and the input revision.
                _validate_workflow_schema(connection)
                _create_routing_tables(connection)
                connection.execute("UPDATE infra_metadata SET schema_version=? WHERE singleton_id=1", (SCHEMA_VERSION,))
                read_revision(connection)
                return
            if tables & workflow_tables:
                raise DatabaseStateError("Version 1 database has incompatible partial workflow tables.")
            # Only v1 migrations create domain tables; missing v2 tables are corruption.
            connection.execute(
                "CREATE TABLE IF NOT EXISTS inspections (inspection_id TEXT PRIMARY KEY, "
                "status TEXT NOT NULL CHECK(status IN ('no_detection','pending_review','accepted','rejected')), "
                "record_version INTEGER NOT NULL CHECK(record_version>=1), created_at TEXT NOT NULL, "
                "record_json TEXT NOT NULL, policy_json TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS tasks (task_id TEXT PRIMARY KEY, "
                "inspection_id TEXT NOT NULL UNIQUE REFERENCES inspections(inspection_id), "
                "status TEXT NOT NULL CHECK(status IN ('active','completed','cancelled')), "
                "record_version INTEGER NOT NULL CHECK(record_version>=1), created_at TEXT NOT NULL, record_json TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS operation_keys (scope TEXT NOT NULL, request_key TEXT NOT NULL, "
                "payload_hash TEXT NOT NULL, resource_id TEXT NOT NULL, created_at TEXT NOT NULL, "
                "PRIMARY KEY(scope,request_key))"
            )
            connection.execute("CREATE INDEX IF NOT EXISTS inspections_status_created ON inspections(status,created_at,inspection_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS tasks_status_created ON tasks(status,created_at,task_id)")
            _validate_workflow_schema(connection)
            _create_routing_tables(connection)
            connection.execute("UPDATE infra_metadata SET schema_version=? WHERE singleton_id=1", (SCHEMA_VERSION,))
            read_revision(connection)
