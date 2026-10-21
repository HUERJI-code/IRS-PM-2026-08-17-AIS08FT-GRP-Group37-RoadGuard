"""Isolated real SQLite task dispatch, durable affinity, cancellation and safety tests."""
import uuid

import pytest
from fastapi.testclient import TestClient
from auth_test_support import create_app
from test_routing_api import create_task, revision, recalculate
from roadguard.config import load_settings
from roadguard.database import increment_revision

BASE = "/api/v1/assistant/task-changes"
@pytest.fixture
def client(tmp_path):
    settings = load_settings({"ROADGUARD_DB_PATH": str(tmp_path/"db.sqlite3"), "ROADGUARD_UPLOAD_PATH":str(tmp_path/"uploads"), "ROADGUARD_VISION_MANIFEST_PATH":"disabled"})
    with TestClient(create_app(settings)) as c:
        yield c

def body(client, task_index=0, action="reassign"):
    task = create_task(client, task_index)
    result = recalculate(client, revision(client)).json()
    plan = client.get("/api/v1/route-plans/"+result["plans"][0]["plan_id"]).json()
    source = next(r["crew_id"] for r in plan["crew_routes"] if any(s["task_id"]==task for s in r["stops"]))
    target = next(r["crew_id"] for r in plan["crew_routes"] if r["crew_id"]!=source)
    return {"request_id":uuid.uuid4().hex,"based_on_plan_id":plan["plan_id"],"action":action,"task_id":task, **({"target_crew_id":target} if action=="reassign" else {})}
def preview(client,payload):
    result=client.post(BASE+"/preview",json=payload)
    assert result.status_code==200,result.text
    return result.json()
def confirm(client,record):
    return client.post(BASE+"/"+record["change_id"]+"/confirm",json={"expected_version":record["record_version"]})

def test_move_preview_idempotency_later_tasks_and_unavailable_lock(client):
    payload=body(client); before=revision(client)
    record=preview(client,payload)
    assert revision(client)==before
    assert preview(client,payload)==record
    assert client.post(BASE+"/preview",json={**payload,"target_crew_id":"crew-04"}).status_code==409
    done=confirm(client,record)
    assert done.status_code==200,done.text
    assert revision(client)==before+1
    assert confirm(client,record).json()==done.json()
    create_task(client,1)
    result=recalculate(client,revision(client)).json()
    for summary in result["plans"]:
        plan=client.get("/api/v1/route-plans/"+summary["plan_id"]).json()
        route=next(r for r in plan["crew_routes"] if any(s["task_id"]==payload["task_id"] for s in r["stops"]))
        assert route["crew_id"]==payload["target_crew_id"]
        stop=next(s for s in route["stops"] if s["task_id"]==payload["task_id"])
        assert stop["locked_crew_id"]==route["crew_id"] and stop["damage_label"]
        assert route["shift_remaining_minutes"]==pytest.approx(480-route["total_work_minutes"])
    client.patch("/api/v1/crews/"+payload["target_crew_id"],json={"request_id":"unavailable","expected_version":1,"available":False})
    result=recalculate(client,revision(client)).json()
    for summary in result["plans"]:
        plan=client.get("/api/v1/route-plans/"+summary["plan_id"]).json()
        assert {"task_id":payload["task_id"],"reason":"assigned_crew_unavailable"} in plan["unassigned_tasks"]

def test_cancel_authoritative_history_and_exclusion(client):
    payload=body(client,action="cancel_task"); record=preview(client,payload)
    before=client.get("/api/v1/tasks/"+payload["task_id"]).json()
    result=confirm(client,record)
    assert result.status_code==200,result.text
    task=client.get("/api/v1/tasks/"+payload["task_id"]).json()
    assert task["status"]=="cancelled" and task["record_version"]==before["record_version"]+1
    assert len(task["history"])==len(before["history"])+1
    plans=recalculate(client,revision(client)).json()
    for summary in plans["plans"]:
        plan=client.get("/api/v1/route-plans/"+summary["plan_id"]).json()
        assert not any(s["task_id"]==payload["task_id"] for r in plan["crew_routes"] for s in r["stops"])
    assert confirm(client,record).json()==result.json()

def test_stale_forged_nonassigned_and_preview_cancel(client):
    payload=body(client); record=preview(client,payload)
    assert client.post(BASE+"/preview",json={**payload,"request_id":uuid.uuid4().hex,"task_id":"task-forged"}).status_code==404
    with client.app.state.database.transaction() as connection: increment_revision(connection)
    assert confirm(client,record).status_code==409
    assert client.post(BASE+"/preview",json={**payload,"request_id":uuid.uuid4().hex}).status_code==409
    response=client.post(BASE+"/"+record["change_id"]+"/cancel",json={"expected_version":1})
    assert response.json()["status"]=="cancelled"
    assert confirm(client,record).status_code==409

def test_travel_and_return_limit_reject_not_service_sum(client,monkeypatch):
    payload=body(client)
    planning=client.app.state.planning_service
    original=planning._travel_matrix
    def costly(inputs):
        matrix=original(inputs)
        # One 120-minute service fits alone, but 190 each way exceeds the 480-minute shift.
        durations=[[0.0 if i==j else 190.0 for j in range(len(matrix.node_ids))] for i in range(len(matrix.node_ids))]
        return matrix.model_copy(update={"duration_minutes":durations})
    monkeypatch.setattr(planning,"_travel_matrix",costly)
    response=client.post(BASE+"/preview",json=payload)
    assert response.status_code==409,response.text
    assert response.json()["code"]=="task_change_infeasible"

def test_confirm_rollback_and_replan_receipt(client,monkeypatch):
    payload=body(client); record=preview(client,payload); before=revision(client)
    from roadguard.assistant.task_change_service import TaskChangeService
    def failure(*args,**kwargs): raise RuntimeError("injected")
    with monkeypatch.context() as patch:
        patch.setattr(TaskChangeService,"_save",failure)
        with pytest.raises(RuntimeError): confirm(client,record)
    assert revision(client)==before
    with client.app.state.database.connect() as connection:
        assert connection.execute("SELECT count(*) FROM task_crew_constraints").fetchone()[0]==0
    assert confirm(client,record).status_code==200
    url=BASE+"/"+record["change_id"]+"/replan"
    result=client.post(url,json={"attempt_id":"first-attempt"})
    assert result.status_code==200,result.text
    assert result.json()["replan_status"]=="succeeded"
    assert client.post(url,json={"attempt_id":"first-attempt"}).json()==result.json()

def test_v5_migration_keeps_data_and_revision(client):
    payload=body(client); db=client.app.state.database
    with db.transaction() as connection:
        before=[tuple(r) for r in connection.execute("SELECT * FROM tasks")]
        rev=connection.execute("SELECT input_revision FROM infra_metadata").fetchone()[0]
        for table in ["task_crew_constraints","assistant_task_change_events","assistant_task_changes"]: connection.execute("DROP TABLE "+table)
        connection.execute("UPDATE infra_metadata SET schema_version=5")
    db.initialize(); db.initialize()
    with db.connect() as connection:
        assert before==[tuple(r) for r in connection.execute("SELECT * FROM tasks")]
        assert connection.execute("SELECT schema_version,input_revision FROM infra_metadata").fetchone()[:]==(6,rev)


def test_cancel_unassigned_task_and_reassign_rejected(client):
    task=create_task(client,0)
    for number in range(1,5):
        client.patch(f"/api/v1/crews/crew-{number:02}",json={"request_id":f"off-{number}","expected_version":1,"available":False})
    result=recalculate(client,revision(client)).json()
    payload={"request_id":"cancel-unassigned","based_on_plan_id":result["plans"][0]["plan_id"],"action":"cancel_task","task_id":task}
    record=preview(client,payload)
    assert record["source_crew_id"] is None
    moved=client.post(BASE+"/preview",json={**payload,"request_id":"move-unassigned","action":"reassign","target_crew_id":"crew-02"})
    assert moved.status_code==409 and moved.json()["code"]=="task_not_assigned"
    assert confirm(client,record).status_code==200
    assert client.get("/api/v1/tasks/"+task).json()["status"]=="cancelled"

def test_config_change_after_preview_rejected(client):
    payload=body(client); record=preview(client,payload)
    planning=client.app.state.planning_service
    planning.config=planning.config.model_copy(update={"travel_matrix_provider":"google_routes"})
    response=confirm(client,record)
    assert response.status_code==409 and response.json()["code"]=="stale_planning_settings"

def test_cancellation_rechecks_remaining_nonmetric_route(client,monkeypatch):
    for number in range(2,5):
        client.patch(f"/api/v1/crews/crew-{number:02}",json={"request_id":f"off-{number}","expected_version":1,"available":False})
    first=create_task(client,0); second=create_task(client,1)
    result=recalculate(client,revision(client)).json()
    plan=client.get("/api/v1/route-plans/"+result["plans"][0]["plan_id"]).json()
    route=next(r for r in plan["crew_routes"] if r["stops"])
    cancelled=route["stops"][0]["task_id"]; remaining=route["stops"][1]["task_id"]
    original=client.app.state.planning_service._travel_matrix
    def matrix(inputs):
        value=original(inputs); rows=[r[:] for r in value.duration_minutes]
        rows[0][value.node_ids.index(remaining)]=400.0
        return value.model_copy(update={"duration_minutes":rows})
    monkeypatch.setattr(client.app.state.planning_service,"_travel_matrix",matrix)
    response=client.post(BASE+"/preview",json={"request_id":"nonmetric-cancel","based_on_plan_id":plan["plan_id"],"action":"cancel_task","task_id":cancelled})
    assert response.status_code==409 and response.json()["code"]=="task_change_infeasible"
    assert client.get("/api/v1/tasks/"+cancelled).json()["status"]=="active"

def test_new_endpoints_auth_csrf_and_owner(client):
    from roadguard.auth.dependencies import current_user
    client.app.dependency_overrides.pop(current_user)
    assert client.get(BASE).status_code==401
    password="isolated-task-change-password"
    for username,role in [("dispatcher1","dispatcher"),("dispatcher2","dispatcher"),("inspector1","inspector")]:
        client.app.state.auth_service.create_user(username,username,role,None,password)
    def login(username):
        client.cookies.clear();client.headers.pop("X-CSRF-Token",None)
        result=client.post("/api/v1/auth/login",json={"username":username,"password":password})
        client.headers["X-CSRF-Token"]=result.json()["csrf_token"]
    login("inspector1")
    assert client.get(BASE).status_code==403
    # Create a task through the inspector identity; dispatcher then previews it.
    task=create_task(client,0)
    login("dispatcher1")
    result=recalculate(client,revision(client)).json()
    record=preview(client,{"request_id":"owned","based_on_plan_id":result["plans"][0]["plan_id"],"action":"reassign","task_id":task,"target_crew_id":"crew-02"})
    url=BASE+"/"+record["change_id"]
    assert client.post(url+"/confirm",json={"expected_version":1},headers={"X-CSRF-Token":"forged"}).status_code==403
    login("dispatcher2")
    assert client.get(url).status_code==404
    assert confirm(client,record).status_code==404
    assert client.get(BASE).json()["items"]==[]

def test_restart_retains_constraint_and_confirm_receipt(client):
    payload=body(client);record=preview(client,payload);done=confirm(client,record).json()
    with TestClient(create_app(client.app.state.settings)) as restarted:
        assert confirm(restarted,record).json()==done
        plans=recalculate(restarted,revision(restarted)).json()
        for summary in plans["plans"]:
            plan=restarted.get("/api/v1/route-plans/"+summary["plan_id"]).json()
            assert next(r["crew_id"] for r in plan["crew_routes"] if any(s["task_id"]==payload["task_id"] for s in r["stops"]))==payload["target_crew_id"]


@pytest.mark.parametrize("unreachable_return", [True,False])
def test_unreachable_return_and_unknown_service_rejected(client,monkeypatch,unreachable_return):
    payload=body(client)
    planning=client.app.state.planning_service
    if unreachable_return:
        original=planning._travel_matrix
        def matrix(inputs):
            value=original(inputs)
            rows=[row[:] for row in value.duration_minutes]
            rows[value.node_ids.index(payload["task_id"])][0]=None
            return value.model_copy(update={"duration_minutes":rows})
        monkeypatch.setattr(planning,"_travel_matrix",matrix)
    else:
        original=planning.tasks.snapshot
        def snapshot(*args,**kwargs):
            value=original(*args,**kwargs)
            return value.model_copy(update={"tasks":[t.model_copy(update={"service_minutes":None}) for t in value.tasks]})
        monkeypatch.setattr(planning.tasks,"snapshot",snapshot)
    response=client.post(BASE+"/preview",json=payload)
    assert response.status_code==409 and response.json()["code"]=="task_change_infeasible"

def test_later_infeasible_locked_task_is_explicitly_unassigned(client,monkeypatch):
    payload=body(client);record=preview(client,payload)
    assert confirm(client,record).status_code==200
    planning=client.app.state.planning_service
    original=planning._travel_matrix
    def matrix(inputs):
        value=original(inputs)
        rows=[[0.0 if i==j else 190.0 for j in range(len(value.node_ids))] for i in range(len(value.node_ids))]
        return value.model_copy(update={"duration_minutes":rows})
    monkeypatch.setattr(planning,"_travel_matrix",matrix)
    plans=recalculate(client,revision(client)).json()
    for summary in plans["plans"]:
        plan=client.get("/api/v1/route-plans/"+summary["plan_id"]).json()
        assert {"task_id":payload["task_id"],"reason":"assigned_crew_infeasible"} in plan["unassigned_tasks"]
        assert not any(s["task_id"]==payload["task_id"] for r in plan["crew_routes"] for s in r["stops"])

def test_input_changes_during_preview_saves_no_intent(client,monkeypatch):
    payload=body(client);planning=client.app.state.planning_service
    original=planning._travel_matrix
    def changing(inputs):
        result=original(inputs)
        with client.app.state.database.transaction() as connection: increment_revision(connection)
        return result
    monkeypatch.setattr(planning,"_travel_matrix",changing)
    response=client.post(BASE+"/preview",json=payload)
    assert response.status_code==409 and response.json()["code"]=="stale_input_revision"
    with client.app.state.database.connect() as connection:
        assert connection.execute("SELECT count(*) FROM assistant_task_changes").fetchone()[0]==0

def test_cancel_confirm_failure_rolls_back_task_history(client,monkeypatch):
    payload=body(client,action="cancel_task");record=preview(client,payload)
    before=client.get("/api/v1/tasks/"+payload["task_id"]).json();rev=revision(client)
    from roadguard.assistant.task_change_service import TaskChangeService
    def fail(*args,**kwargs): raise RuntimeError("injected audit failure")
    monkeypatch.setattr(TaskChangeService,"_save",fail)
    with pytest.raises(RuntimeError): confirm(client,record)
    assert revision(client)==rev
    assert client.get("/api/v1/tasks/"+payload["task_id"]).json()==before


def test_affinity_revokes_old_crew_immediately_and_new_crew_waits_for_plan(client):
    from roadguard.auth.dependencies import current_user
    from roadguard.auth.models import Account
    payload=body(client);record=preview(client,payload)
    task=client.get("/api/v1/tasks/"+payload["task_id"]).json()
    assert confirm(client,record).status_code==200
    dispatcher_override=client.app.dependency_overrides[current_user]
    actors={}
    with client.app.state.database.transaction() as connection:
        for number,crew in enumerate([record["source_crew_id"],record["target_crew_id"]], start=3):
            actor=Account(user_id=str(number)*32,username=f"crew{number}",display_name="Test crew",role="crew",crew_id=crew)
            actors[crew]=actor
            connection.execute("INSERT INTO auth_users VALUES (?,?,?,?,?,?,1,0)",(actor.user_id,actor.username,actor.display_name,"crew",crew,"not-a-login-hash"))
    def identity(actor):
        def selected(request):
            request.state.account=actor
            return actor
        # FastAPI must inject Request rather than treating it as a query parameter.
        from fastapi import Request
        selected.__annotations__["request"]=Request
        return selected
    old=actors[record["source_crew_id"]];new=actors[record["target_crew_id"]]
    client.app.dependency_overrides[current_user]=identity(old)
    patch={"request_id":"old-crew-done","expected_version":1,"status":"completed"}
    assert client.patch("/api/v1/tasks/"+task["task_id"],json=patch).status_code==404
    assert client.get("/api/v1/tasks/"+task["task_id"]).status_code==404
    assert client.get("/api/v1/inspections/"+task["inspection_id"]).status_code==404
    workspace=client.get("/api/v1/crew/workspace").json()
    assert workspace["plan"]["crew_routes"]==[] and workspace["tasks"]==[]
    client.app.dependency_overrides[current_user]=identity(new)
    assert client.patch("/api/v1/tasks/"+task["task_id"],json={**patch,"request_id":"new-crew-too-soon"}).status_code==404
    client.app.dependency_overrides[current_user]=dispatcher_override
    assert recalculate(client,revision(client)).status_code==200
    client.app.dependency_overrides[current_user]=identity(new)
    response=client.patch("/api/v1/tasks/"+task["task_id"],json={**patch,"request_id":"new-crew-done"})
    assert response.status_code==200,response.text
    assert response.json()["task"]["status"]=="completed"
