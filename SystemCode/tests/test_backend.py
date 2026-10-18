"""Executable checks for the shared foundation, independent of future domains."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import sqlite3

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from roadguard.config import ConfigurationError, REPOSITORY_ROOT, Settings, load_settings
from roadguard.database import Database, DatabaseStateError, increment_revision, read_revision
from roadguard.errors import AppError, StaleRevisionError
from auth_test_support import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return load_settings({"ROADGUARD_DB_PATH": str(tmp_path / "data" / "roadguard.sqlite3")})


@pytest.fixture
def database(settings: Settings) -> Database:
    result = Database(settings.database_path)
    result.initialize()
    return result


def test_configuration_is_repository_relative_and_deeply_immutable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = load_settings({"ROADGUARD_DB_PATH": "SystemCode/backend/data/test.sqlite3"})
    assert settings.config_path == REPOSITORY_ROOT / "SystemCode/config/project.example.json"
    assert settings.database_path == REPOSITORY_ROOT / "SystemCode/backend/data/test.sqlite3"
    assert settings.project["planning"]["return_to_depot"] is None
    assert settings.project["planning"]["crew_ids"] == ("crew-01", "crew-02", "crew-03", "crew-04")
    with pytest.raises(TypeError):
        settings.project["planning"]["return_to_depot"] = True
    with pytest.raises(FrozenInstanceError):
        settings.database_busy_timeout_ms = 1
    assert not settings.database_path.exists()


@pytest.mark.parametrize("content", [
    "{malformed secret-token",
    "[]",
    '{}',
    '{"project_name":"RoadGuard","scenario":[],"planning":{}}',
    '{"project_name":"RoadGuard","project_name":"duplicate","scenario":{},"planning":{}}',
    '{"project_name":"RoadGuard","scenario":{"value":NaN},"planning":{}}',
    '{"project_name":"RoadGuard","scenario":{"value":1e999},"planning":{}}',
])
def test_invalid_config_fails_without_echoing_input(tmp_path, content):
    config_path = tmp_path / "secret-token.json"
    config_path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigurationError) as error:
        load_settings({"ROADGUARD_CONFIG_PATH": str(config_path)})
    assert "secret-token" not in str(error.value)
    assert str(config_path) not in str(error.value)


def test_missing_config_and_empty_paths_fail(tmp_path):
    with pytest.raises(ConfigurationError):
        load_settings({"ROADGUARD_CONFIG_PATH": str(tmp_path / "missing.json")})
    with pytest.raises(ConfigurationError):
        load_settings({"ROADGUARD_DB_PATH": " "})


def test_factory_defers_config_loading_and_initialization(settings, monkeypatch):
    import roadguard.main as main

    def invalid_config():
        raise ConfigurationError("Invalid configuration.")

    monkeypatch.setattr(main, "load_settings", invalid_config)
    app = main.create_app()
    assert not settings.database_path.exists()
    with pytest.raises(ConfigurationError), TestClient(app):
        pass
    app = main.create_app(settings)
    assert not settings.database_path.exists()
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200
    assert settings.database_path.exists()
    assert app.state.database is None


def test_health_and_implemented_openapi(settings):
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "database": "ok", "api_version": "v1", "input_revision": 0}
        openapi = client.get("/openapi.json").json()
        assert set(openapi["paths"]) == {
            "/api/v1/auth/login", "/api/v1/auth/session", "/api/v1/auth/logout", "/api/v1/crew/workspace",
            "/api/v1/health", "/api/v1/demo/scenarios", "/api/v1/demo/assessments",
            "/api/v1/inspections", "/api/v1/inspections/{inspection_id}",
            "/api/v1/inspections/{inspection_id}/image", "/api/v1/inspections/{inspection_id}/review",
            "/api/v1/tasks", "/api/v1/tasks/{task_id}", "/api/v1/tasks/snapshot",
            "/api/v1/crews", "/api/v1/crews/{crew_id}", "/api/v1/route-plans/recalculate",
            "/api/v1/route-plans/latest", "/api/v1/route-plans/{plan_id}",
        }
        health_schema = openapi["paths"]["/api/v1/health"]["get"]
        assert health_schema["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/HealthResponse")
        assert health_schema["responses"]["503"]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorResponse")
        with client.app.state.database.transaction() as connection:
            increment_revision(connection)
        assert client.get("/api/v1/health").json()["input_revision"] == 1


@pytest.mark.parametrize("failure", ["missing_table", "deleted_database", "bad_revision", "incompatible_schema"])
def test_health_database_failure_returns_safe_503(settings, failure):
    with TestClient(create_app(settings)) as client:
        if failure == "deleted_database":
            settings.database_path.unlink()
        else:
            with client.app.state.database.transaction() as connection:
                if failure == "missing_table":
                    connection.execute("DROP TABLE infra_metadata")
                elif failure == "bad_revision":
                    connection.execute("UPDATE infra_metadata SET input_revision = 'secret-token'")
                else:
                    connection.execute("UPDATE infra_metadata SET schema_version = 999")
        response = client.get("/api/v1/health?token=secret-token")
        assert response.status_code == 503
        assert response.json() == {
            "code": "database_unavailable",
            "message": "The infrastructure database is unavailable.",
            "details": None,
        }
        assert "secret-token" not in response.text
        assert str(settings.database_path) not in response.text
        if failure == "deleted_database":
            assert not settings.database_path.exists()


def test_http_errors_have_one_safe_envelope(settings):
    with TestClient(create_app(settings)) as client:
        missing = client.get("/secret-token?api_key=secret-token")
        assert missing.status_code == 404
        assert missing.json()["code"] == "not_found"
        assert "secret-token" not in missing.text
        wrong_method = client.post("/api/v1/health")
        assert wrong_method.status_code == 405
        assert wrong_method.json()["code"] == "method_not_allowed"
        assert "GET" in wrong_method.headers["allow"]


def test_validation_app_http_and_unhandled_errors_are_sanitized(settings):
    app = create_app(settings)

    @app.get("/test/validate")
    def validate(count: int):
        return {"count": count}

    @app.get("/test/domain")
    def domain():
        raise AppError("example_conflict", "The operation conflicts with current state.", 409)

    @app.get("/test/http")
    def http_error():
        raise HTTPException(400, detail="secret-token")

    @app.get("/test/crash")
    def crash():
        raise RuntimeError("secret-token; local-path; traceback")

    with TestClient(app, raise_server_exceptions=False) as client:
        validation = client.get("/test/validate?count=secret-token")
        assert validation.status_code == 422
        assert validation.json() == {
            "code": "validation_error", "message": "Request validation failed.", "details": {"error_count": 1},
        }
        assert client.get("/test/domain").json()["code"] == "example_conflict"
        http_response = client.get("/test/http")
        assert http_response.status_code == 400
        assert http_response.json()["code"] == "http_error"
        internal = client.get("/test/crash?api_key=secret-token")
        assert internal.status_code == 500
        assert internal.json() == {
            "code": "internal_error", "message": "An unexpected server error occurred.", "details": None,
        }
        for response in (validation, http_response, internal):
            assert "secret-token" not in response.text
            assert "traceback" not in response.text


def test_database_initialization_is_idempotent_and_revision_persists(database):
    with database.transaction(expected_revision=0) as connection:
        assert increment_revision(connection, expected_revision=0) == 1
    database.initialize()
    reopened = Database(database.path)
    reopened.initialize()
    with reopened.connect() as connection:
        assert read_revision(connection) == 1
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")} == {
            "infra_metadata", "inspections", "tasks", "operation_keys", "crews", "route_plans",
            "auth_users", "auth_sessions", "auth_login_limits", "inspection_owners", "auth_audit",
        }
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("UPDATE infra_metadata SET input_revision = 2")
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


@pytest.mark.parametrize("external_transaction", ["reader", "writer"])
def test_restart_current_database_while_external_transaction_is_open(settings, database, external_transaction):
    # A database viewer can keep a read transaction open after fetching a table.
    # A current-schema startup only needs a snapshot, not a write lock/commit.
    external = sqlite3.connect(database.path, isolation_level=None)
    try:
        assert external.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        external.execute("BEGIN" if external_transaction == "reader" else "BEGIN IMMEDIATE")
        assert external.execute("SELECT input_revision FROM infra_metadata").fetchone()[0] == 0
        if external_transaction == "writer":
            external.execute("UPDATE infra_metadata SET input_revision=42")
        with TestClient(create_app(replace(settings, database_busy_timeout_ms=100))) as client:
            response = client.get("/api/v1/health")
            assert response.status_code == 200
            assert response.json()["input_revision"] == 0
        assert external.in_transaction
    finally:
        external.rollback()
        external.close()
    with database.connect() as connection:
        assert read_revision(connection) == 0


def test_migration_still_requires_lock_and_rolls_back_before_retry(tmp_path):
    database = Database(tmp_path / "legacy.sqlite3", busy_timeout_ms=100)
    with sqlite3.connect(database.path) as connection:
        connection.execute("CREATE TABLE infra_metadata(singleton_id INTEGER PRIMARY KEY, schema_version INTEGER, input_revision INTEGER)")
        connection.execute("INSERT INTO infra_metadata VALUES (1,1,7)")
    reader = sqlite3.connect(database.path, isolation_level=None)
    try:
        reader.execute("BEGIN")
        assert tuple(reader.execute("SELECT * FROM infra_metadata").fetchone()) == (1, 1, 7)
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            database.initialize()
        assert tuple(reader.execute("SELECT * FROM infra_metadata").fetchone()) == (1, 1, 7)
        assert {row[0] for row in reader.execute("SELECT name FROM sqlite_master WHERE type='table'")} == {"infra_metadata"}
    finally:
        reader.rollback()
        reader.close()
    database.initialize()
    with database.connect() as connection:
        assert read_revision(connection) == 7


def test_mutation_and_revision_share_commit_and_rollback(database):
    with database.transaction() as connection:
        # A test-owned table illustrates a future domain migration, not a shipped schema.
        connection.execute("CREATE TABLE test_domain (id INTEGER PRIMARY KEY, value TEXT)")
    with pytest.raises(RuntimeError):
        with database.transaction(expected_revision=0) as connection:
            connection.execute("INSERT INTO test_domain VALUES (1, 'rolled_back')")
            increment_revision(connection)
            raise RuntimeError("Simulated domain failure")
    with database.connect() as connection:
        assert read_revision(connection) == 0
        assert connection.execute("SELECT count(*) FROM test_domain").fetchone()[0] == 0
    with database.transaction(expected_revision=0) as connection:
        connection.execute("INSERT INTO test_domain VALUES (2, 'committed')")
        assert increment_revision(connection) == 1
    with database.connect() as connection:
        assert read_revision(connection) == 1
        assert connection.execute("SELECT value FROM test_domain").fetchone()[0] == "committed"


def test_stale_revision_rejects_before_write_and_increment(database):
    with database.transaction() as connection:
        assert increment_revision(connection) == 1
    entered = False
    with pytest.raises(StaleRevisionError) as error:
        with database.transaction(expected_revision=0):
            entered = True
    assert not entered
    assert error.value.status_code == 409
    assert error.value.details == {"expected_revision": 0, "current_revision": 1}
    with pytest.raises(StaleRevisionError):
        with database.transaction() as connection:
            increment_revision(connection, expected_revision=0)
    with database.connect() as connection:
        assert read_revision(connection) == 1


def test_concurrent_stale_writers_have_one_winner(database):
    def mutate():
        try:
            with database.transaction(expected_revision=0) as connection:
                return increment_revision(connection, expected_revision=0)
        except StaleRevisionError:
            return "stale"

    with ThreadPoolExecutor(max_workers=4) as executor:
        outcomes = list(executor.map(lambda _: mutate(), range(4)))
    assert outcomes.count(1) == 1
    assert outcomes.count("stale") == 3
    with database.connect() as connection:
        assert read_revision(connection) == 1


def test_concurrent_increment_has_no_lost_updates(database):
    def mutate(_):
        with database.transaction() as connection:
            return increment_revision(connection)

    with ThreadPoolExecutor(max_workers=4) as executor:
        revisions = list(executor.map(mutate, range(12)))
    assert sorted(revisions) == list(range(1, 13))


def test_revision_requires_transaction_and_valid_expected_value(database):
    with sqlite3.connect(database.path, isolation_level=None) as connection:
        with pytest.raises(RuntimeError):
            increment_revision(connection)
    for invalid in (-1, True, 1.5):
        with pytest.raises(ValueError), database.transaction(expected_revision=invalid):
            pass


def test_initializer_refuses_incompatible_schema_without_reset(database):
    with database.transaction() as connection:
        connection.execute("UPDATE infra_metadata SET schema_version = 999, input_revision = 7")
    with pytest.raises(DatabaseStateError):
        database.initialize()
    with database.connect() as connection:
        row = connection.execute("SELECT schema_version, input_revision FROM infra_metadata").fetchone()
        assert tuple(row) == (999, 7)
