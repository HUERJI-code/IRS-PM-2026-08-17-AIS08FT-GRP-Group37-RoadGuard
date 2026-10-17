"""Create task test evidence with the real backend in a disposable demo DB."""
from pathlib import Path
import io
import json
import sys
import tempfile

FRONTEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND.parents[1] / 'SystemCode/backend'))
from fastapi.testclient import TestClient
from PIL import Image
from roadguard.config import load_settings
from roadguard.main import create_app

with tempfile.TemporaryDirectory(prefix='roadguard-task-') as temp:
    settings = load_settings({'ROADGUARD_DB_PATH': str(Path(temp) / 'tasks.sqlite3'), 'ROADGUARD_UPLOAD_PATH': str(Path(temp) / 'uploads'), 'ROADGUARD_VISION_MANIFEST_PATH': 'disabled'})
    picture = io.BytesIO()
    Image.new('RGB', (640, 480), '#eef2e8').save(picture, 'PNG')
    fixtures = {}
    with TestClient(create_app(settings)) as client:
        for action in ('completed', 'cancelled', 'label', 'location', 'noop'):
            upload = client.post('/api/v1/inspections', headers={'Idempotency-Key': 'upload_' + action}, files={'image': ('synthetic.png', picture.getvalue(), 'image/png')}, data={'metadata': json.dumps({'mode': 'demo', 'scenario_id': 'high_confidence', 'latitude': 1.3405, 'longitude': 103.706, 'road_type': 'public_motor_road'})})
            upload.raise_for_status()
            id = upload.json()['task_id']
            url = '/api/v1/tasks/' + id
            before = client.get(url).json()
            request = {'request_id': 'task_' + action, 'expected_version': before['record_version']}
            if action in ('completed', 'cancelled'):
                request['status'] = action
            elif action in ('label', 'noop'):
                request['damage_label'] = 'pothole_deep' if action == 'label' else before['damage_label']
            else:
                request.update(latitude=1.3406, longitude=103.706, road_type='public_motor_road')
            stale = client.patch(url, json={**request, 'expected_version': 999})
            assert stale.status_code == 409
            response = client.patch(url, json=request)
            response.raise_for_status()
            replay = client.patch(url, json=request)
            replay.raise_for_status()
            assert replay.json()['replayed'] is True
            assert replay.json()['task']['history'] == response.json()['task']['history']
            assert response.json()['planning_input_changed'] is (action != 'noop')
            if action in ('completed', 'cancelled'):
                reopen = client.patch(url, json={'request_id': 'second_' + action, 'expected_version': response.json()['task']['record_version'], 'damage_label': 'pothole'})
                assert reopen.status_code == 409
                assert not any(t['task_id'] == id for t in client.get('/api/v1/tasks/snapshot').json()['tasks'])
            fixtures[action] = {'before': before, 'request': request, 'response': response.json(), 'replay': replay.json()}
    (FRONTEND / 'src/test/task-fixtures.json').write_text(json.dumps(fixtures, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Generated task mutation fixtures; verified conflicts, replay, no-op and terminal exclusion in disposable DB.')
