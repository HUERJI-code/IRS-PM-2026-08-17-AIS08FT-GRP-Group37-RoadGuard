"""B-4: persisted crews, recalculation, plan queries, staleness and the v3 migration."""

import io
import json

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from roadguard.config import load_settings
from roadguard.database import Database, DatabaseStateError, read_revision
from auth_test_support import create_app
from roadguard.routing import service as routing_service


CREWS = ["crew-01", "crew-02", "crew-03", "crew-04"]
POINTS = [(1.332, 103.676), (1.332, 103.688), (1.346, 103.694), (1.3405, 103.706), (1.34, 103.72)]


@pytest.fixture
def settings(tmp_path):
    return load_settings({"ROADGUARD_DB_PATH": str(tmp_path / "routing.sqlite3")})


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client


def create_task(client, index):
    stream = io.BytesIO()
    Image.new("RGB", (80, 40), "gray").save(stream, format="PNG")
    latitude, longitude = POINTS[index]
    response = client.post("/api/v1/inspections", headers={"Idempotency-Key": f"task-{index}"},
                           files={"image": ("test.png", stream.getvalue(), "image/png")},
                           data={"metadata": json.dumps({"mode": "demo", "scenario_id": "high_confidence",
                                 "latitude": latitude, "longitude": longitude, "road_type": "public_motor_road"})})
    assert response.status_code == 201, response.text
    return response.json()["task_id"]


def revision(client):
    return client.get("/api/v1/health").json()["input_revision"]


def recalculate(client, expected):
    return client.post("/api/v1/route-plans/recalculate", json={"expected_revision": expected})


def patch_crew(client, crew_id, available, request_id, version):
    return client.patch(f"/api/v1/crews/{crew_id}", json={
        "request_id": request_id, "expected_version": version, "available": available})


def stops(plan):
    return [stop["task_id"] for route in plan["crew_routes"] for stop in route["stops"]]


def test_crews_default_to_configured_roster_without_writing(client, settings):
    body = client.get("/api/v1/crews").json()
    assert body["contract_version"] == "b-crew-v1" and body["input_revision"] == 0
    assert [c["crew_id"] for c in body["crews"]] == CREWS
    assert all(c["available"] and c["record_version"] == 1 and c["updated_at"] is None for c in body["crews"])
    assert {c["depot_id"] for c in body["crews"]} == {"depot-nus-iss"}
    with Database(settings.database_path).connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM crews").fetchone()[0] == 0


def test_crew_patch_versions_idempotency_and_conflicts(client):
    response = patch_crew(client, "crew-02", False, "disable-2", 1)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["crew"]["available"] is False and body["crew"]["record_version"] == 2
    assert body["planning_input_changed"] is True and body["replayed"] is False and body["input_revision"] == 1
    replay = patch_crew(client, "crew-02", False, "disable-2", 1).json()
    assert replay["replayed"] is True and replay["planning_input_changed"] is False and replay["input_revision"] == 1
    conflict = patch_crew(client, "crew-02", True, "disable-2", 1)
    assert conflict.status_code == 409 and conflict.json()["code"] == "idempotency_conflict"
    stale = patch_crew(client, "crew-02", True, "enable-2", 1)
    assert stale.status_code == 409 and stale.json()["code"] == "stale_record_version"
    unchanged = patch_crew(client, "crew-02", False, "noop-2", 2).json()
    assert unchanged["planning_input_changed"] is False and unchanged["input_revision"] == 1
    assert patch_crew(client, "crew-09", False, "x", 1).status_code == 404
    assert patch_crew(client, "Crew_01!", False, "x", 1).status_code == 422
    assert revision(client) == 1
    listed = {c["crew_id"]: c for c in client.get("/api/v1/crews").json()["crews"]}
    assert listed["crew-02"]["available"] is False and listed["crew-01"]["available"] is True


def test_no_plan_is_a_404_not_an_empty_plan(client):
    for path in ("/api/v1/route-plans/latest?algorithm=ga", f"/api/v1/route-plans/plan-{'0' * 32}"):
        response = client.get(path)
        assert response.status_code == 404 and response.json()["code"] == "route_plan_not_found"
    assert client.get("/api/v1/route-plans/latest?algorithm=best").status_code == 422
    assert client.get("/api/v1/route-plans/not-a-plan").status_code == 422


def test_recalculate_requires_current_revision(client):
    assert client.post("/api/v1/route-plans/recalculate", json={}).status_code == 422
    stale = recalculate(client, 5)
    assert stale.status_code == 409 and stale.json()["code"] == "stale_input_revision"
    assert client.get("/api/v1/route-plans/latest?algorithm=greedy").status_code == 404


def test_empty_queue_plans_keep_all_crews_visible(client):
    response = recalculate(client, 0)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["task_count"] == 0 and body["matrix_is_simulated"] is True and revision(client) == 0
    assert [p["algorithm"] for p in body["plans"]] == ["greedy", "ga"]
    plan = client.get("/api/v1/route-plans/latest?algorithm=ga").json()
    assert [r["status"] for r in plan["crew_routes"]] == ["idle"] * 4 and plan["is_stale"] is False


def test_full_flow_tasks_crew_change_staleness_and_history(client):
    tasks = [create_task(client, i) for i in range(4)]
    assert revision(client) == 4
    first = recalculate(client, 4).json()
    plan_ids = {p["algorithm"]: p["plan_id"] for p in first["plans"]}
    for algorithm in ("greedy", "ga"):
        latest = client.get(f"/api/v1/route-plans/latest?algorithm={algorithm}").json()
        assert latest["plan_id"] == plan_ids[algorithm] and latest["input_revision"] == 4
        assert sorted(stops(latest)) == sorted(tasks) and latest["is_stale"] is False
        assert latest["settings"]["shift_limit"] == {"mode": "limited", "minutes": 480.0}
        assert latest["matrix_is_simulated"] is True and latest["is_demo"] is True
    assert client.get(f"/api/v1/route-plans/{plan_ids['ga']}").json()["random_seed"] == 1

    # A crew change makes saved plans stale but never deletes them.
    patch_crew(client, "crew-01", False, "disable-1", 1)
    assert client.get("/api/v1/route-plans/latest?algorithm=ga").json()["is_stale"] is True
    assert recalculate(client, 4).status_code == 409

    # Completing a task removes it from the next plan.
    done = client.patch(f"/api/v1/tasks/{tasks[0]}", json={"request_id": "done", "expected_version": 1,
                                                             "status": "completed"})
    assert done.status_code == 200
    second = recalculate(client, revision(client)).json()
    new_ga = client.get("/api/v1/route-plans/latest?algorithm=ga").json()
    assert new_ga["plan_id"] != plan_ids["ga"] and new_ga["is_stale"] is False
    assert new_ga["crew_routes"][0]["status"] == "unavailable" and new_ga["crew_routes"][0]["stops"] == []
    assert sorted(stops(new_ga)) == sorted(tasks[1:]) and second["task_count"] == 3
    old = client.get(f"/api/v1/route-plans/{plan_ids['ga']}").json()
    assert old["is_stale"] is True and sorted(stops(old)) == sorted(tasks)


def test_inputs_changed_during_calculation_saves_nothing(client, monkeypatch):
    create_task(client, 0)
    original = routing_service.simulated_travel_matrix

    def matrix_while_crew_changes(*args, **kwargs):
        # Simulates another user disabling a crew after the snapshot was read.
        assert patch_crew(client, "crew-03", False, "race", 1).status_code == 200
        return original(*args, **kwargs)

    monkeypatch.setattr(routing_service, "simulated_travel_matrix", matrix_while_crew_changes)
    response = recalculate(client, 1)
    assert response.status_code == 409 and response.json()["code"] == "stale_input_revision"
    assert client.get("/api/v1/route-plans/latest?algorithm=ga").status_code == 404


def test_plans_and_crew_state_survive_restart(settings):
    with TestClient(create_app(settings)) as client:
        create_task(client, 0)
        patch_crew(client, "crew-04", False, "disable-4", 1)
        plan_id = recalculate(client, 2).json()["plans"][1]["plan_id"]
    with TestClient(create_app(settings)) as client:
        plan = client.get(f"/api/v1/route-plans/{plan_id}").json()
        assert plan["is_stale"] is False and plan["crew_routes"][3]["status"] == "unavailable"
        assert {c["crew_id"]: c["available"] for c in client.get("/api/v1/crews").json()["crews"]}["crew-04"] is False


def test_v2_database_migrates_to_v3_keeping_rows_and_revision(settings):
    with TestClient(create_app(settings)) as client:
        task_id = create_task(client, 0)
    database = Database(settings.database_path)
    with database.transaction() as connection:
        for table in ("assistant_change_events", "assistant_changes", "inspection_owners", "auth_audit", "auth_sessions", "auth_login_limits", "auth_users"):
            connection.execute(f"DROP TABLE {table}")
        connection.execute("DROP TABLE route_plans")
        connection.execute("DROP TABLE crews")
        connection.execute("UPDATE infra_metadata SET schema_version=2")
    database.initialize()
    with database.connect() as connection:
        assert connection.execute("SELECT schema_version FROM infra_metadata").fetchone()[0] == 5
        assert read_revision(connection) == 1
        assert connection.execute("SELECT COUNT(*) FROM tasks WHERE task_id=?", (task_id,)).fetchone()[0] == 1


def test_pre_v3_database_with_routing_table_is_refused(settings):
    with TestClient(create_app(settings)):
        pass
    database = Database(settings.database_path)
    with database.transaction() as connection:
        connection.execute("DROP TABLE crews")
        connection.execute("UPDATE infra_metadata SET schema_version=2")
    with pytest.raises(DatabaseStateError):
        database.initialize()


def test_missing_routing_table_in_v3_is_not_recreated(settings):
    with TestClient(create_app(settings)):
        pass
    database = Database(settings.database_path)
    with database.transaction() as connection:
        connection.execute("DROP TABLE route_plans")
    with pytest.raises(DatabaseStateError):
        database.initialize()


def test_openapi_registers_fixed_paths_before_plan_id(client):
    paths = list(client.get("/openapi.json").json()["paths"])
    assert paths.index("/api/v1/route-plans/latest") < paths.index("/api/v1/route-plans/{plan_id}")
    assert paths.index("/api/v1/route-plans/recalculate") < paths.index("/api/v1/route-plans/{plan_id}")


def test_online_ga_starts_from_greedy_and_is_never_worse(client):
    for index in range(5):
        create_task(client, index)
    plans = {p["algorithm"]: p["plan_id"] for p in recalculate(client, revision(client)).json()["plans"]}
    ga = client.get(f"/api/v1/route-plans/{plans['ga']}").json()
    greedy = client.get(f"/api/v1/route-plans/{plans['greedy']}").json()
    assert ga["algorithm_parameters"]["seed_with_greedy"] is True
    key = lambda plan: (*plan["metrics"]["unassigned_by_priority"].values(), plan["metrics"]["objective_value"])  # noqa: E731
    assert key(ga) <= key(greedy)
