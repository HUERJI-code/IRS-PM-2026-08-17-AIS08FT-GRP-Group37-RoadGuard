"""Create review test evidence with the real backend in a disposable demo DB."""
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

with tempfile.TemporaryDirectory(prefix='roadguard-review-') as temp:
    settings = load_settings({'ROADGUARD_DB_PATH': str(Path(temp) / 'review.sqlite3'), 'ROADGUARD_VISION_MANIFEST_PATH': 'disabled'})
    picture = io.BytesIO()
    Image.new('RGB', (640, 480), '#eef2e8').save(picture, 'PNG')
    fixtures = {}
    with TestClient(create_app(settings)) as client:
        for action in ('confirm', 'correct', 'dismiss'):
            upload = client.post('/api/v1/inspections', headers={'Idempotency-Key': 'upload_' + action}, files={'image': ('synthetic.png', picture.getvalue(), 'image/png')}, data={'metadata': json.dumps({'mode': 'demo', 'scenario_id': 'low_confidence', 'latitude': 1.3405, 'longitude': 103.706, 'road_type': 'public_motor_road'})})
            upload.raise_for_status()
            id = upload.json()['inspection_id']
            before = client.get('/api/v1/inspections/' + id).json()
            request = {'request_id': 'review_' + action, 'expected_version': before['record_version'], 'action': action, 'note': 'Synthetic review test.'}
            if action != 'dismiss':
                request['detection_id'] = before['detections'][0]['detection_id']
            if action == 'correct':
                request['damage_label'] = 'pothole_deep'
            response = client.post('/api/v1/inspections/' + id + '/review', json=request)
            response.raise_for_status()
            replay = client.post('/api/v1/inspections/' + id + '/review', json=request)
            replay.raise_for_status()
            assert replay.json()['replayed'] is True
            fixtures[action] = {'before': before, 'request': request, 'response': response.json(), 'replay': replay.json()}
    (FRONTEND / 'src/test/review-fixtures.json').write_text(json.dumps(fixtures, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Generated confirm/correct/dismiss and replay fixtures in an isolated temporary DB.')
