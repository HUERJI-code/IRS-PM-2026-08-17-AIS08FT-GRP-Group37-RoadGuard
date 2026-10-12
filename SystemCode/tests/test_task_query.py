"""TaskQueryService reads complete, validated snapshots and never owns caller life cycles."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import sqlite3
from threading import Event

from pydantic import ValidationError
import pytest

from roadguard.database import Database, increment_revision
from roadguard.errors import AppError, StaleRevisionError
from roadguard.schemas.task import Task
from roadguard.schemas.task_query import TaskSnapshot
from roadguard.schemas.workflow import TaskAuditValues, TaskHistoryEntry, TaskRecord
from roadguard.tasks import TaskQueryService


START = datetime(2026, 10, 12, 8, tzinfo=timezone.utc)


def record(index=1, status="active", *, minutes=45, created_at=None):
    data = dict(
        task_id=f"{index:032x}", inspection_id=f"{index + 100000:032x}", latitude=1.3405, longitude=103.706,
        damage_label="pothole", severity="medium", priority="P2", service_minutes=minutes,
        created_at=created_at or START + timedelta(seconds=index), due_at=None, status=status,
        rule_version="demo-rules-v1", is_demo=True,
    )
    audit = TaskAuditValues.model_validate({key: data[key] for key in TaskAuditValues.model_fields})
    return TaskRecord(**data, updated_at=data["created_at"], record_version=1,
                      repair_recommendation="Test-owned demo recommendation.", history=[TaskHistoryEntry(
                          request_id=f"seed-{index}", action="created", recorded_at=data["created_at"],
                          changed_fields=list(TaskAuditValues.model_fields), before=None, after=audit,
                          actor_source="system_demo_rules",
                      )])


def insert(connection, item):
    # Only task storage is under test; minimal parent rows satisfy the real FK.
    connection.execute("INSERT INTO inspections VALUES (?,?,?,?,?,?)", (
        item.inspection_id, "accepted", 1, item.created_at.isoformat(), "{}", "{}",
    ))
    connection.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?)", (
        item.task_id, item.inspection_id, item.status, item.record_version, item.created_at.isoformat(), item.model_dump_json(),
    ))


@pytest.fixture
def database(tmp_path):
    result = Database(tmp_path / "tasks.sqlite3")
    result.initialize()
    return result


@pytest.fixture
def query(database):
    return TaskQueryService(database)


def seed(database, records):
    with database.transaction() as connection:
        for item in records:
            insert(connection, item)
            increment_revision(connection)


def test_empty_snapshot_is_read_only_and_has_explicit_provenance(query, database):
    before = hashlib.sha256(database.path.read_bytes()).hexdigest()
    result = query.snapshot(expected_revision=0)
    assert result.model_dump() == {
        "contract_version": "a-task-query-v1", "source": "persisted_workflow", "input_revision": 0,
        "tasks": [], "total": 0, "is_demo": True,
    }
    assert hashlib.sha256(database.path.read_bytes()).hexdigest() == before


def test_active_only_exact_original_task_fields_and_nullable_values(query, database):
    active = record(1, minutes=None)
    seed(database, [active, record(2, "completed"), record(3, "cancelled")])
    result = query.snapshot(expected_revision=3)
    assert result.total == 1 and result.input_revision == 3
    task = result.tasks[0]
    assert type(task) is Task
    assert set(task.model_dump()) == set(Task.model_fields)
    assert task.task_id == active.task_id and task.service_minutes is None and task.due_at is None
    assert "history" not in task.model_dump() and "record_version" not in task.model_dump()
    assert task.status == "active" and task.is_demo is True


def test_complete_snapshot_never_applies_http_list_limit(query, database):
    seed(database, [record(index) for index in range(1, 126)])
    result = query.snapshot()
    assert result.total == len(result.tasks) == result.input_revision == 125
    assert result.tasks[-1].task_id == f"{125:032x}"


def test_order_is_created_at_then_id_independent_of_insert_order(query, database):
    seed(database, [record(3, created_at=START), record(2, created_at=START), record(1, created_at=START - timedelta(seconds=1))])
    assert [item.task_id for item in query.snapshot().tasks] == [f"{index:032x}" for index in (1, 2, 3)]


def test_stale_expected_revision_raises_shared_conflict_without_task_read(query, database):
    seed(database, [record()])
    with database.connect() as connection:
        statements = []
        connection.set_trace_callback(statements.append)
        with pytest.raises(StaleRevisionError) as error:
            query.snapshot(expected_revision=0, connection=connection)
        assert error.value.status_code == 409
        assert error.value.details == {"expected_revision": 0, "current_revision": 1}
        assert not any("FROM tasks" in statement for statement in statements)
        assert connection.in_transaction


@pytest.mark.parametrize("value", [-1, True, False, 1.0, "1", [], {}])
def test_expected_revision_requires_strict_nonnegative_integer(query, value):
    with pytest.raises(AppError) as error:
        query.snapshot(expected_revision=value)
    assert error.value.code == "validation_error" and error.value.status_code == 422


def test_missing_database_fails_without_recreation(query, database):
    database.path.unlink()
    with pytest.raises(AppError) as error:
        query.snapshot()
    assert error.value.code == "database_unavailable" and error.value.status_code == 503
    assert not database.path.exists()


@pytest.mark.parametrize("damage", ["bad_json", "wrong_id", "wrong_status", "wrong_version", "wrong_inspection", "wrong_created", "nondemo"])
def test_corrupt_rows_fail_whole_snapshot_without_partial_subset(query, database, damage):
    seed(database, [record(1), record(2)])
    with database.transaction() as connection:
        if damage == "bad_json":
            connection.execute("UPDATE tasks SET record_json='private-raw-secret' WHERE task_id=?", (record(2).task_id,))
        elif damage == "wrong_id":
            connection.execute("UPDATE tasks SET task_id=? WHERE task_id=?", ("bad-normalized-id", record(2).task_id))
        elif damage == "wrong_status":
            connection.execute("UPDATE tasks SET status='completed' WHERE task_id=?", (record(2).task_id,))
        elif damage == "wrong_version":
            connection.execute("UPDATE tasks SET record_version=2 WHERE task_id=?", (record(2).task_id,))
        elif damage == "wrong_inspection":
            connection.execute("INSERT INTO inspections VALUES (?,?,?,?,?,?)", ("f" * 32, "accepted", 1, START.isoformat(), "{}", "{}"))
            connection.execute("UPDATE tasks SET inspection_id=? WHERE task_id=?", ("f" * 32, record(2).task_id))
        elif damage == "wrong_created":
            connection.execute("UPDATE tasks SET created_at='private-raw-secret' WHERE task_id=?", (record(2).task_id,))
        else:
            import json
            data = record(2).model_dump(mode="json")
            data["is_demo"] = False
            connection.execute("UPDATE tasks SET record_json=? WHERE task_id=?", (json.dumps(data), record(2).task_id))
    with pytest.raises(AppError) as error:
        query.snapshot()
    assert error.value.code == "database_unavailable" and error.value.status_code == 503
    assert "private-raw-secret" not in str(error.value)


def test_corrupt_metadata_or_missing_table_returns_safe_503(query, database):
    with database.transaction() as connection:
        connection.execute("DROP TABLE tasks")
    with pytest.raises(AppError) as error:
        query.snapshot()
    assert error.value.status_code == 503


def test_caller_connection_stays_open_and_active_without_lifecycle_calls(query, database, monkeypatch):
    seed(database, [record()])
    with database.connect() as connection:
        statements = []
        connection.set_trace_callback(statements.append)
        def forbidden():
            raise AssertionError("Query attempted to acquire another connection")
        monkeypatch.setattr(database, "connect", forbidden)
        result = query.snapshot(connection=connection)
        assert result.total == 1 and connection.in_transaction
        assert connection.execute("SELECT input_revision FROM infra_metadata").fetchone()[0] == 1
        assert statements[0].startswith("SELECT schema_version, input_revision")
        assert all(statement.startswith(("SELECT", "PRAGMA")) for statement in statements)


def test_caller_write_transaction_remains_uncommitted_and_is_rolled_back_by_caller(query, database):
    with pytest.raises(RuntimeError):
        with database.transaction() as connection:
            insert(connection, record())
            increment_revision(connection)
            result = query.snapshot(connection=connection)
            assert result.total == 1 and result.input_revision == 1 and connection.in_transaction
            raise RuntimeError("Caller elects to roll back its own transaction")
    assert query.snapshot().total == 0 and query.snapshot().input_revision == 0


def test_inactive_or_wrong_database_caller_connection_is_rejected(query, database, tmp_path):
    with sqlite3.connect(database.path, isolation_level=None) as connection:
        with pytest.raises(AppError) as error:
            query.snapshot(connection=connection)
        assert error.value.status_code == 422
        assert not connection.in_transaction
    other = Database(tmp_path / "other.sqlite3")
    other.initialize()
    with other.connect() as connection:
        with pytest.raises(AppError) as error:
            query.snapshot(connection=connection)
        assert error.value.status_code == 422 and connection.in_transaction


def test_wal_concurrent_writer_cannot_mix_revision_and_tasks(query, database, monkeypatch):
    # WAL lets a writer commit while the reader holds its old snapshot. This
    # test would return revision 1 plus two tasks if query split its reads.
    with sqlite3.connect(database.path, isolation_level=None) as connection:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    seed(database, [record(1)])
    snapshot_established, writer_committed = Event(), Event()
    import roadguard.tasks.query as module
    original_read_revision = module.read_revision
    def gated_read_revision(connection):
        revision = original_read_revision(connection)
        snapshot_established.set()
        assert writer_committed.wait(timeout=10)
        return revision
    monkeypatch.setattr(module, "read_revision", gated_read_revision)
    def writer():
        assert snapshot_established.wait(timeout=10)
        seed(database, [record(2)])
        writer_committed.set()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(writer)
        result = query.snapshot()
        future.result(timeout=10)
    assert result.input_revision == 1 and result.total == 1 and result.tasks[0].task_id == record(1).task_id
    monkeypatch.setattr(module, "read_revision", original_read_revision)
    assert query.snapshot().input_revision == 2 and query.snapshot().total == 2


@pytest.mark.parametrize("change", ["total", "duplicate_task", "duplicate_inspection", "terminal", "nondemo", "bad_source", "bad_contract"])
def test_snapshot_contract_consistency(change):
    task = Task.model_validate(record().model_dump(include=set(Task.model_fields)))
    data = dict(source="synthetic_fixture", input_revision=0, tasks=[task.model_dump()], total=1, is_demo=True)
    if change == "total":
        data["total"] = 2
    elif change.startswith("duplicate"):
        duplicate = dict(data["tasks"][0])
        if change == "duplicate_inspection":
            duplicate["task_id"] = "different-task"
        data["tasks"].append(duplicate)
        data["total"] = 2
    elif change == "terminal":
        data["tasks"][0]["status"] = "completed"
    elif change == "nondemo":
        data["tasks"][0]["is_demo"] = False
    elif change == "bad_source":
        data["source"] = "live_planner"
    else:
        data["contract_version"] = "different-contract"
    with pytest.raises(ValidationError):
        TaskSnapshot.model_validate(data)


@pytest.mark.parametrize("is_demo", [False, 1, "true"])
def test_snapshot_requires_strict_demo_flag(is_demo):
    with pytest.raises(ValidationError):
        TaskSnapshot(source="synthetic_fixture", input_revision=0, tasks=[], total=0, is_demo=is_demo)
