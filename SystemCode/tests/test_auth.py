"""Real cookie authentication and cross-role/object access; no auth dependency overrides."""
import io
import json
import time
from dataclasses import replace

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from roadguard.auth import service as auth_module
from roadguard.auth.service import digest, hash_password, verify_password
from roadguard.config import load_settings
from roadguard.database import Database, read_revision
from roadguard.main import create_app

PASSWORD = 'isolated-test-password-2026'
POINTS = [(1.332, 103.676), (1.332, 103.688), (1.346, 103.694), (1.3405, 103.706), (1.34, 103.72)]


@pytest.fixture(scope='module')
def encoded():
    return hash_password(PASSWORD)


@pytest.fixture
def client(tmp_path, monkeypatch, encoded):
    # Reuse a real scrypt hash to avoid hashing six identical fixture passwords per test.
    monkeypatch.setattr(auth_module, 'hash_password', lambda password: encoded)
    settings = load_settings({'ROADGUARD_DB_PATH': str(tmp_path/'auth.sqlite3'),
                              'ROADGUARD_UPLOAD_PATH': str(tmp_path/'uploads'),
                              'ROADGUARD_VISION_MANIFEST_PATH': 'disabled',
                              'ROADGUARD_TRAVEL_MATRIX_PROVIDER': 'simulated'})
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        for username, role, crew in [('a','inspector',None), ('a2','inspector',None),
                                    ('b','crew','crew-02'), ('b1','crew','crew-01'), ('c','dispatcher',None)]:
            client.app.state.auth_service.create_user(username, username.upper(), role, crew, PASSWORD)
        yield client


def login(client, username):
    response = client.post('/api/v1/auth/login', json={'username': username, 'password': PASSWORD})
    assert response.status_code == 200, response.text
    client.headers['X-CSRF-Token'] = response.json()['csrf_token']
    return response.json()


def upload(client, key='photo', index=0):
    image=io.BytesIO(); Image.new('RGB',(80,40),'gray').save(image,'PNG')
    latitude, longitude = POINTS[index]
    return client.post('/api/v1/inspections', headers={'Idempotency-Key': key},
        files={'image':('photo.png',image.getvalue(),'image/png')}, data={'metadata':json.dumps({
            'mode':'demo','scenario_id':'high_confidence','latitude':latitude,'longitude':longitude,'road_type':'public_motor_road'})})


def seed_plan(client):
    login(client, 'a')
    for i in range(5):
        assert upload(client, f'photo-{i}', i).status_code == 201
    login(client, 'c')
    response=client.post('/api/v1/route-plans/recalculate',json={'expected_revision':5})
    assert response.status_code == 200, response.text
    plan=next(p for p in response.json()['plans'] if p['algorithm']=='ga')
    return client.get(f"/api/v1/route-plans/{plan['plan_id']}").json()


def test_anonymous_and_forged_role_cannot_access_business_data(client):
    assert client.get('/api/v1/health').status_code==200
    for path in ['/tasks','inspections','crews','crew/workspace','route-plans/latest']:
        assert client.get('/api/v1/'+path.lstrip('/')).status_code==401
    response=client.post('/api/v1/auth/login',json={'username':'a','password':PASSWORD,'role':'dispatcher'})
    assert response.status_code==422
    response=client.post('/api/v1/auth/login',json={'username':'a','password':'incorrect'})
    assert response.status_code==401 and PASSWORD not in response.text
    session=login(client,'A')
    assert session['user']['role']=='inspector'
    assert client.get('/api/v1/tasks',headers={'X-Role':'dispatcher'}).status_code==403
    assert 'password' not in session['user']


def test_inspector_owns_uploads_and_idempotency_is_per_account(client):
    a=login(client,'a'); first=upload(client).json(); iid=first['inspection_id']
    assert upload(client).status_code==200
    assert client.get(f'/api/v1/inspections/{iid}').status_code==200
    assert client.get(f'/api/v1/inspections/{iid}/image').status_code==200
    assert client.get('/api/v1/tasks/'+first['task_id']).status_code==403
    assert client.post(f'/api/v1/inspections/{iid}/review',json={}).status_code==403
    login(client,'a2')
    for suffix in ['', '/image']:
        assert client.get(f'/api/v1/inspections/{iid}{suffix}').status_code==404
    second=upload(client)
    assert second.status_code==201 and second.json()['inspection_id']!=iid
    with client.app.state.database.connect() as conn:
        assert conn.execute('SELECT user_id FROM inspection_owners WHERE inspection_id=?',(iid,)).fetchone()[0]==a['user']['user_id']


def test_dispatcher_manages_records_but_cannot_upload_or_use_crew_workspace(client):
    login(client,'a'); created=upload(client).json()
    login(client,'c')
    for path in ['/inspections','/tasks','/tasks/snapshot','/crews',f"/inspections/{created['inspection_id']}"]:
        assert client.get('/api/v1'+path).status_code==200
    assert upload(client,'not-authorized').status_code==403
    assert client.get('/api/v1/crew/workspace').status_code==403


def test_crew_only_reads_own_route_and_can_complete_own_task(client):
    plan=seed_plan(client)
    login(client,'b')
    response=client.get('/api/v1/crew/workspace?crew=crew-01&algorithm=greedy')
    assert response.status_code==200, response.text
    workspace=response.json()
    assert workspace['crew']['crew_id']=='crew-02'
    assert [r['crew_id'] for r in workspace['plan']['crew_routes']]==['crew-02']
    assert 'metrics' not in workspace['plan'] and 'matrix' not in workspace['plan']
    own=workspace['tasks'][0]; task_id=own['task_id']
    other=next(stop['task_id'] for r in plan['crew_routes'] if r['crew_id']!='crew-02' for stop in r['stops'])
    for path in ['/crews','/tasks','/tasks/snapshot','/inspections','/route-plans/latest']:
        assert client.get('/api/v1'+path).status_code==403
    assert client.get('/api/v1/tasks/'+other).status_code==404
    assert client.get('/api/v1/tasks/'+task_id).status_code==200
    assert client.get('/api/v1/inspections/'+own['inspection_id']+'/image').status_code==200
    payload={'request_id':'done','expected_version':1,'status':'completed'}
    assert client.patch('/api/v1/tasks/'+other,json=payload).status_code==404
    assert client.patch('/api/v1/tasks/'+task_id,json={**payload,'status':'cancelled'}).status_code==403
    assert client.patch('/api/v1/tasks/'+task_id,json={**payload,'damage_label':'pothole_deep'}).status_code==403
    result=client.patch('/api/v1/tasks/'+task_id,json=payload)
    assert result.status_code==200, result.text
    assert result.json()['task']['status']=='completed' and result.json()['input_revision']==6
    assert result.json()['task']['history'][-1]['actor_source']=='authenticated_user'
    assert client.patch('/api/v1/tasks/'+task_id,json=payload).json()['replayed']
    with client.app.state.database.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM auth_audit WHERE action='task.completed'").fetchone()[0]==1
    # The original account can retry a committed completion after replanning excludes it.
    login(client,'c')
    assert client.post('/api/v1/route-plans/recalculate',json={'expected_revision':6}).status_code==200
    login(client,'b')
    assert client.patch('/api/v1/tasks/'+task_id,json=payload).json()['replayed']
    assert client.get('/api/v1/tasks/'+task_id).status_code==200
    login(client,'b1')
    assert client.get('/api/v1/tasks/'+task_id).status_code==404


def test_reassignment_and_disabled_crew_are_checked_at_write_time(client):
    seed_plan(client); login(client,'b')
    task=client.get('/api/v1/crew/workspace').json()['tasks'][0]
    payload={'request_id':'stale-assignment','expected_version':1,'status':'completed'}
    login(client,'c')
    assert client.patch('/api/v1/crews/crew-02',json={'request_id':'disable','expected_version':1,'available':False}).status_code==200
    login(client,'b')
    assert client.patch('/api/v1/tasks/'+task['task_id'],json=payload).status_code==403
    login(client,'c')
    assert client.post('/api/v1/route-plans/recalculate',json={'expected_revision':6}).status_code==200
    login(client,'b')
    assert client.get('/api/v1/tasks/'+task['task_id']).status_code==404
    assert client.get('/api/v1/inspections/'+task['inspection_id']+'/image').status_code==404
    assert client.patch('/api/v1/tasks/'+task['task_id'],json=payload).status_code==404
    assert client.get('/api/v1/health').json()['input_revision']==6


def test_cookie_csrf_origin_logout_and_expiry(client):
    result=client.post('/api/v1/auth/login',json={'username':'a','password':PASSWORD})
    cookie=result.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie
    assert 'no-store' in result.headers['cache-control']
    token=client.cookies.get('roadguard_session')
    assert client.post('/api/v1/auth/logout').status_code==403
    client.headers['X-CSRF-Token']=result.json()['csrf_token']
    assert client.post('/api/v1/auth/logout',headers={'Origin':'https://attacker.example'}).status_code==403
    with client.app.state.database.connect() as conn:
        stored=conn.execute('SELECT token_hash FROM auth_sessions').fetchone()[0]
        assert stored==digest(token) and stored!=token
    assert client.post('/api/v1/auth/logout').status_code==200
    assert client.get('/api/v1/auth/session').status_code==401
    client.cookies.set('roadguard_session',token)
    assert client.get('/api/v1/auth/session').status_code==401
    client.cookies.clear(); login(client,'a')
    with client.app.state.database.transaction() as conn:
        conn.execute('UPDATE auth_sessions SET expires_at=?',(int(time.time())-1,))
    assert client.get('/api/v1/auth/session').status_code==401


def test_password_reset_disable_and_login_throttling(client):
    session=login(client,'a')
    client.app.state.auth_service.set_password('a', PASSWORD)
    assert client.get('/api/v1/auth/session').status_code==401
    login(client,'a')
    with client.app.state.database.transaction() as conn:
        conn.execute('UPDATE auth_users SET enabled=0 WHERE user_id=?',(session['user']['user_id'],))
    assert client.get('/api/v1/auth/session').status_code==401
    # Pre-fill persistent counter to test the boundary without ten costly password verifications.
    with client.app.state.database.transaction() as conn:
        conn.execute('INSERT INTO auth_login_limits VALUES (?,?,?)',('account:'+digest('unknown'),int(time.time()),10))
    assert client.post('/api/v1/auth/login',json={'username':'unknown','password':'anything'}).status_code==429


def test_no_plan_and_database_failure_are_not_faked_as_valid_data(client):
    login(client,'b')
    body=client.get('/api/v1/crew/workspace').json()
    assert body['plan'] is None and body['tasks']==[] and body['crew']['crew_id']=='crew-02'
    with client.app.state.database.transaction() as conn:
        conn.execute('DROP TABLE auth_sessions')
    response=client.get('/api/v1/crew/workspace')
    assert response.status_code==503 and response.json()['code']=='database_unavailable'


def test_v3_migration_preserves_business_data_without_granting_old_uploads(client):
    login(client,'a'); created=upload(client).json()
    database=client.app.state.database
    with database.transaction() as conn:
        before=tuple(conn.execute('SELECT record_json FROM inspections').fetchone())
        for table in ['inspection_owners','auth_audit','auth_sessions','auth_login_limits','auth_users']:
            conn.execute('DROP TABLE '+table)
        conn.execute('UPDATE infra_metadata SET schema_version=3')
    database.initialize()
    with database.connect() as conn:
        assert read_revision(conn)==1
        assert tuple(conn.execute('SELECT record_json FROM inspections').fetchone())==before
        assert conn.execute('SELECT COUNT(*) FROM inspection_owners').fetchone()[0]==0
    client.app.state.auth_service.create_user('a','Inspector','inspector',None,PASSWORD)
    login(client,'a')
    assert client.get('/api/v1/inspections/'+created['inspection_id']).status_code==404


def test_password_hash_uses_unique_salt_and_constant_format():
    one=hash_password(PASSWORD); two=hash_password(PASSWORD)
    assert one!=two and verify_password(PASSWORD,one) and not verify_password('incorrect',one)
    assert not verify_password(PASSWORD,'invalid')
    with pytest.raises(ValueError): hash_password('short')
