"""Export current backend contracts and isolated, synthetic read-only fixtures.
Run from the frontend with the backend CI dependencies installed. No live DB/API used.
"""
from pathlib import Path
import hashlib
import io
import json
import sys
import tempfile

FRONTEND = Path(__file__).resolve().parents[1]
ROOT = FRONTEND.parents[1]
sys.path.insert(0, str(ROOT / 'SystemCode/backend'))
from fastapi.testclient import TestClient
from PIL import Image
from roadguard.config import load_settings
from roadguard.main import create_app


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


with tempfile.TemporaryDirectory(prefix='roadguard-contract-') as temp:
    settings = load_settings({
        'ROADGUARD_DB_PATH': str(Path(temp) / 'fixture.sqlite3'),
        'ROADGUARD_VISION_MANIFEST_PATH': 'disabled',
        'ROADGUARD_TRAVEL_MATRIX_PROVIDER': 'simulated',
    })
    app = create_app(settings)
    spec = app.openapi()
    if '--check' in sys.argv:
        assert spec == json.loads((FRONTEND / 'src/api/generated/openapi.json').read_text()), 'Backend OpenAPI drift: regenerate contracts and inspect changes.'
        print('Current backend OpenAPI matches the checked-in frontend snapshot.')
        sys.exit(0)
    dump(FRONTEND / 'src/api/generated/openapi.json', spec)
    with TestClient(app) as client:
        def get(path):
            response = client.get('/api/v1' + path)
            response.raise_for_status()
            return response.json()

        empty = {p: get(p) for p in ['/health', '/inspections', '/tasks', '/tasks/snapshot', '/crews', '/demo/scenarios']}
        picture = io.BytesIO()
        Image.new('RGB', (640, 480), '#eef2e8').save(picture, 'PNG')
        image_path = FRONTEND / 'public/mock/inspection.png'
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(picture.getvalue())
        for index, scenario in enumerate(['high_confidence', 'low_confidence', 'no_detection']):
            response = client.post('/api/v1/inspections', headers={'Idempotency-Key': f'fixture_{index}'},
                files={'image': ('synthetic.png', picture.getvalue(), 'image/png')},
                data={'metadata': json.dumps({'mode': 'demo', 'scenario_id': scenario,
                    'latitude': 1.3405, 'longitude': 103.706, 'road_type': 'public_motor_road'})})
            response.raise_for_status()
        normal = {p: get(p) for p in ['/health', '/inspections', '/tasks', '/tasks/snapshot', '/crews', '/demo/scenarios']}
        response = client.post('/api/v1/route-plans/recalculate', json={
            'expected_revision': normal['/health']['input_revision'], 'planning_start_at': '2026-10-15T01:00:00Z'})
        response.raise_for_status()
        for plan in response.json()['plans']:
            saved = get('/route-plans/' + plan['plan_id'])
            normal['/route-plans/' + plan['plan_id']] = saved
            normal['/route-plans/latest?algorithm=' + plan['algorithm']] = saved
        for item in normal['/inspections']['items']:
            normal['/inspections/' + item['inspection_id']] = item
        for item in normal['/tasks']['items']:
            normal['/tasks/' + item['task_id']] = item
        dump(FRONTEND / 'src/api/mock/fixtures.json', {'normal': normal, 'empty': empty})
        dump(FRONTEND / 'src/api/generated/provenance.json', {
            'kind': 'synthetic_backend_generated', 'business_data': False,
            'openapi_sha256': hashlib.sha256((FRONTEND / 'src/api/generated/openapi.json').read_bytes()).hexdigest(),
            'source': 'roadguard.main.create_app; isolated temporary SQLite; demo detector; simulated matrix',
            'notes': 'Read-only snapshots. Random IDs, timestamps and algorithm runtime change on regeneration. Blank image is synthetic, not road evidence.',
        })
print('Exported OpenAPI and real-schema synthetic snapshots without using the project database.')
