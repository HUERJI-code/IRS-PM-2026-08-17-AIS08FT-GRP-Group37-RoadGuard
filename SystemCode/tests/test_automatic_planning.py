"""Committed acceptance triggers real shared GA/Greedy planning and safe recovery."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from roadguard.errors import AppError, StaleRevisionError
from test_workflow_api import client, settings, png, upload
from test_single_box_workflow import TwoDetections
from test_real_vision import metadata
import json


def plans(client):
    return [client.get(f"/api/v1/route-plans/latest?algorithm={a}").json() for a in ("ga", "greedy")]


def count(client):
    with client.app.state.database.connect() as c:
        return c.execute("SELECT COUNT(*) FROM route_plans").fetchone()[0]


def assert_current(client, task_ids):
    revision = client.get('/api/v1/tasks/snapshot').json()['input_revision']
    for plan in plans(client):
        assert plan['input_revision'] == revision and not plan['is_stale']
        assigned = [s['task_id'] for r in plan['crew_routes'] for s in r['stops']]
        unassigned = [t['task_id'] for t in plan['unassigned_tasks']]
        assert sorted(assigned + unassigned) == sorted(task_ids)


@pytest.mark.parametrize('real', [False, True])
def test_high_confidence_both_algorithms_and_replay(client, png, real):
    if real:
        client.app.state.workflow_service.real_detector = TwoDetections(.6)
        def send():
            return client.post('/api/v1/inspections', headers={'Idempotency-Key': 'high'},
                files={'image': ('x.png', png, 'image/png')},
                data={'metadata': json.dumps(metadata().model_dump(exclude_none=True))})
    else:
        def send():
            return upload(client, png, 'high_confidence', key='high')
    response = send()
    assert response.status_code == 201, response.text
    assert response.headers['X-RoadGuard-Replanning'] == 'completed'
    assert set(response.json()) == {'inspection_id', 'status', 'detection', 'task_id'}
    assert_current(client, [response.json()['task_id']])
    assert send().headers['X-RoadGuard-Replanning'] == 'not_needed'
    assert count(client) == 2


@pytest.mark.parametrize('action', ['confirm', 'correct'])
def test_review_plans_and_replay(client, png, action):
    created = upload(client, png).json()
    inspection = client.get(f"/api/v1/inspections/{created['inspection_id']}").json()
    payload = dict(request_id='review', expected_version=1, action=action,
                   detection_id=inspection['detections'][0]['detection_id'])
    if action == 'correct':
        payload['damage_label'] = 'pothole_deep'
    url = f"/api/v1/inspections/{created['inspection_id']}/review"
    accepted = client.post(url, json=payload)
    assert accepted.status_code == 200, accepted.text
    assert accepted.headers['X-RoadGuard-Replanning'] == 'completed'
    assert_current(client, [accepted.json()['task']['task_id']])
    assert client.post(url, json=payload).headers['X-RoadGuard-Replanning'] == 'not_needed'
    assert count(client) == 2


@pytest.mark.parametrize('failure', [AppError('travel_matrix_unavailable', 'SECRET', 503), RuntimeError('SECRET')])
def test_failure_keeps_task_and_replay_recovers(client, png, monkeypatch, caplog, failure):
    service = client.app.state.planning_service
    original = service.recalculate
    def fail(*args):
        raise failure
    monkeypatch.setattr(service, 'recalculate', fail)
    response = upload(client, png, 'high_confidence')
    assert response.status_code == 201 and response.headers['X-RoadGuard-Replanning'] == 'failed'
    assert client.get('/api/v1/tasks/snapshot').json()['total'] == 1 and count(client) == 0
    assert 'SECRET' not in caplog.text and 'automatic_planning_failed' in caplog.text
    monkeypatch.setattr(service, 'recalculate', original)
    recovered = upload(client, png, 'high_confidence')
    assert recovered.status_code == 200 and recovered.headers['X-RoadGuard-Replanning'] == 'completed'
    assert count(client) == 2


@pytest.mark.parametrize('stale_count,expected', [(2, 'completed'), (3, 'failed')])
def test_stale_conflicts_bounded_and_fresh_revision(client, png, monkeypatch, stale_count, expected):
    service = client.app.state.planning_service
    original = service.recalculate
    revisions = []
    def racing(payload):
        revisions.append(payload.expected_revision)
        if len(revisions) <= stale_count:
            with service.database.transaction() as c:
                c.execute('UPDATE infra_metadata SET input_revision=input_revision+1')
            raise StaleRevisionError(payload.expected_revision, payload.expected_revision + 1)
        return original(payload)
    monkeypatch.setattr(service, 'recalculate', racing)
    response = upload(client, png, 'high_confidence')
    assert response.headers['X-RoadGuard-Replanning'] == expected
    assert revisions == [1, 2, 3]
    assert count(client) == (2 if expected == 'completed' else 0)


def test_pending_no_detection_dismissal_no_plans(client, png):
    assert upload(client, png, 'no_detection', key='none').headers['X-RoadGuard-Replanning'] == 'not_needed'
    pending = upload(client, png).json()
    response = client.post(f"/api/v1/inspections/{pending['inspection_id']}/review",
        json={'request_id': 'dismiss', 'expected_version': 1, 'action': 'dismiss'})
    assert response.status_code == 200, response.text
    assert response.headers['X-RoadGuard-Replanning'] == 'not_needed' and count(client) == 0


def test_concurrent_acceptances_retry_after_committed_change(client, png, monkeypatch):
    service = client.app.state.planning_service
    original = service.recalculate
    entered, release = Event(), Event()
    calls = []
    def paused(payload):
        calls.append(payload.expected_revision)
        if len(calls) == 1:
            entered.set()
            assert release.wait(10)
        return original(payload)
    monkeypatch.setattr(service, 'recalculate', paused)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(upload, client, png, 'high_confidence', 'one')
        assert entered.wait(10)
        second = executor.submit(upload, client, png, 'high_confidence', 'two')
        # Observe committed second task while the first planning call is paused.
        import time
        deadline = time.monotonic() + 10
        while client.get('/api/v1/tasks/snapshot').json()['total'] != 2:
            assert time.monotonic() < deadline
            time.sleep(.01)
        release.set()
        responses = [first.result(), second.result()]
    assert all(r.status_code == 201 for r in responses)
    assert calls == [1, 2] and count(client) == 2
    assert_current(client, [r.json()['task_id'] for r in responses])


def test_replay_repairs_missing_algorithm_and_retains_persistent_crew_lock(client, png):
    first = upload(client, png, 'high_confidence', key='one').json()
    task_id = first['task_id']
    plan = plans(client)[0]
    source = next(route['crew_id'] for route in plan['crew_routes'] if any(stop['task_id'] == task_id for stop in route['stops']))
    target = 'crew-04' if source != 'crew-04' else 'crew-03'
    base = '/api/v1/assistant/task-changes'
    preview = client.post(base + '/preview', json={'request_id': 'lock', 'based_on_plan_id': plan['plan_id'],
        'action': 'reassign', 'task_id': task_id, 'target_crew_id': target})
    assert preview.status_code == 200, preview.text
    record = preview.json()
    confirmed = client.post(base + '/' + record['change_id'] + '/confirm', json={'expected_version': record['record_version']})
    assert confirmed.status_code == 200, confirmed.text
    with client.app.state.database.transaction() as c:
        c.execute("DELETE FROM route_plans WHERE algorithm='greedy'")
    missing = count(client)
    repaired = upload(client, png, 'high_confidence', key='one')
    assert repaired.headers['X-RoadGuard-Replanning'] == 'completed' and count(client) == missing + 2
    second = upload(client, png, 'high_confidence', key='two')
    assert second.headers['X-RoadGuard-Replanning'] == 'completed'
    for plan in plans(client):
        matching = [(route['crew_id'], stop) for route in plan['crew_routes']
                    for stop in route['stops'] if stop['task_id'] == task_id]
        assert len(matching) == 1 and matching[0][0] == target
        assert matching[0][1]['locked_crew_id'] == target
    with client.app.state.database.connect() as c:
        assert tuple(c.execute('SELECT task_id,crew_id FROM task_crew_constraints').fetchone()) == (task_id, target)


def test_nonstale_conflict_is_not_retried(client, png, monkeypatch):
    calls = []
    def fail(payload):
        calls.append(payload.expected_revision)
        raise AppError('other_conflict', 'safe', 409)
    monkeypatch.setattr(client.app.state.planning_service, 'recalculate', fail)
    assert upload(client, png, 'high_confidence').headers['X-RoadGuard-Replanning'] == 'failed'
    assert calls == [1] and count(client) == 0

def test_review_failure_retains_accepted_version_and_replay_recovers(client, png, monkeypatch):
    pending = upload(client, png).json()
    record = client.get(f"/api/v1/inspections/{pending['inspection_id']}").json()
    payload = dict(request_id='review-fail', expected_version=1, action='confirm',
                   detection_id=record['detections'][0]['detection_id'])
    url = f"/api/v1/inspections/{pending['inspection_id']}/review"
    service = client.app.state.planning_service
    original = service.recalculate
    def fail(payload):
        raise RuntimeError('secret')
    monkeypatch.setattr(service, 'recalculate', fail)
    accepted = client.post(url, json=payload)
    assert accepted.status_code == 200 and accepted.headers['X-RoadGuard-Replanning'] == 'failed'
    data = accepted.json()
    assert data['inspection']['status'] == 'accepted' and data['inspection']['record_version'] == 2
    assert data['task']['record_version'] == 1 and count(client) == 0
    monkeypatch.setattr(service, 'recalculate', original)
    replay = client.post(url, json=payload)
    assert replay.status_code == 200 and replay.headers['X-RoadGuard-Replanning'] == 'completed'
    assert replay.json()['inspection'] == data['inspection'] and replay.json()['task'] == data['task']
    assert_current(client, [data['task']['task_id']])


def test_completed_task_replay_does_not_replan(client, png):
    created = upload(client, png, 'high_confidence').json()
    response = client.patch('/api/v1/tasks/' + created['task_id'], json={
        'request_id': 'complete', 'expected_version': 1, 'status': 'completed'})
    assert response.status_code == 200, response.text
    assert count(client) == 2
    replay = upload(client, png, 'high_confidence')
    assert replay.status_code == 200 and replay.headers['X-RoadGuard-Replanning'] == 'not_needed'
    assert count(client) == 2 and all(p['is_stale'] for p in plans(client))


def test_failed_new_task_retains_previous_stale_plans(client, png, monkeypatch):
    upload(client, png, 'high_confidence', key='first')
    previous = [p['plan_id'] for p in plans(client)]
    def fail(payload):
        raise AppError('travel_matrix_unavailable', 'safe', 503)
    monkeypatch.setattr(client.app.state.planning_service, 'recalculate', fail)
    created = upload(client, png, 'high_confidence', key='second')
    assert created.status_code == 201 and created.headers['X-RoadGuard-Replanning'] == 'failed'
    assert client.get('/api/v1/tasks/snapshot').json()['total'] == 2
    assert count(client) == 2 and [p['plan_id'] for p in plans(client)] == previous
    assert all(p['is_stale'] for p in plans(client))
