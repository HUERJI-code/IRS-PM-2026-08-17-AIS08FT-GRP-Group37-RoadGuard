"""Generate isolated demo crew/recalculation fixtures using the existing backend."""
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
# Explicit isolated fixture identities; production never installs this override.
sys.path.insert(0, str(FRONTEND.parents[1] / 'SystemCode/tests'))
from auth_test_support import create_app

with tempfile.TemporaryDirectory(prefix='roadguard-planning-') as temp:
    settings = load_settings({'ROADGUARD_DB_PATH': str(Path(temp)/'test.sqlite3'), 'ROADGUARD_UPLOAD_PATH': str(Path(temp)/'uploads'), 'ROADGUARD_VISION_MANIFEST_PATH': 'disabled', 'ROADGUARD_TRAVEL_MATRIX_PROVIDER': 'simulated'})
    with TestClient(create_app(settings)) as client:
        def get(path):
            response=client.get('/api/v1'+path); response.raise_for_status(); return response.json()
        def calc(revision):
            response=client.post('/api/v1/route-plans/recalculate',json={'expected_revision':revision,'planning_start_at':'2026-10-16T01:00:00Z'});response.raise_for_status();return response.json()
        picture=io.BytesIO();Image.new('RGB',(640,480),'#eef2e8').save(picture,'PNG')
        upload=client.post('/api/v1/inspections',headers={'Idempotency-Key':'planning_fixture'},files={'image':('synthetic.png',picture.getvalue(),'image/png')},data={'metadata':json.dumps({'mode':'demo','scenario_id':'high_confidence','latitude':1.3405,'longitude':103.706,'road_type':'public_motor_road'})});upload.raise_for_status()
        crews=get('/crews');snapshot=get('/tasks/snapshot');old_calc=calc(snapshot['input_revision'])
        request={'request_id':'disable_first','expected_version':crews['crews'][0]['record_version'],'available':False}
        url='/api/v1/crews/'+crews['crews'][0]['crew_id']
        response=client.patch(url,json=request);response.raise_for_status();mutation=response.json()
        replay=client.patch(url,json=request);replay.raise_for_status();assert replay.json()['replayed']
        assert replay.json()['input_revision']==mutation['input_revision']
        assert client.patch(url,json={**request,'request_id':'stale'}).status_code==409
        assert client.post('/api/v1/route-plans/recalculate',json={'expected_revision':snapshot['input_revision']}).status_code==409
        stale={p['algorithm']:get('/route-plans/'+p['plan_id']) for p in old_calc['plans']};assert all(p['is_stale'] for p in stale.values())
        after_crews=get('/crews');after_snapshot=get('/tasks/snapshot');calculation=calc(mutation['input_revision'])
        plans={p['algorithm']:get('/route-plans/'+p['plan_id']) for p in calculation['plans']}
        assert all(any(r['crew_id']==mutation['crew']['crew_id'] and r['status']=='unavailable' and not r['stops'] for r in p['crew_routes']) for p in plans.values())
        for crew in after_crews['crews'][1:]:
            result=client.patch('/api/v1/crews/'+crew['crew_id'],json={'request_id':'disable_'+crew['crew_id'],'expected_version':crew['record_version'],'available':False});result.raise_for_status()
        all_off=calc(get('/crews')['input_revision']);all_off_plans={p['algorithm']:get('/route-plans/'+p['plan_id']) for p in all_off['plans']}
        assert all(p['unassigned_tasks'][0]['reason']=='no_available_crew' for p in all_off_plans.values())
        fixtures={'crews':crews,'snapshot':snapshot,'mutation':mutation,'replay':replay.json(),'after_crews':after_crews,'after_snapshot':after_snapshot,'stale':stale,'calculation':calculation,'plans':plans,'all_off':all_off,'all_off_plans':all_off_plans}
        (FRONTEND/'src/test/planning-fixtures.json').write_text(json.dumps(fixtures,ensure_ascii=False,indent=2)+'\n')
print('Verified isolated crew versions, replay, stale plans, paired recalculation and all-crews-off unassigned tasks.')
