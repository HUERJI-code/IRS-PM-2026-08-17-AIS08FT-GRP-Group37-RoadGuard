"""C-13 cross-role HTTP acceptance. Synthetic inputs; never calls external services."""
from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
from pathlib import Path
import uuid

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from roadguard.assistant import provider
from roadguard.assistant.change_service import ChangeService
from roadguard.assistant.query_models import ModelSelection
from roadguard.auth import service as auth_module
from roadguard.auth.service import hash_password
from roadguard.config import load_settings
from roadguard.errors import AppError
from roadguard.main import create_app

BASE = '/api/v1'
CHANGE = BASE + '/assistant/change-requests'
PASSWORD = 'synthetic-c13-local-only'
QUESTIONS = [
    ('q01', '四队分别负责什么任务？', 'crews'),
    ('q02', 'crew-01 的访问顺序是什么？', 'crew'),
    ('q03', '为什么从 NUS-ISS 出发？', 'depot'),
    ('q04', 'crew-01 的任务预计何时到达和完成？', 'crew'),
    ('q05', '有哪些未分配任务及原因？', 'unassigned'),
    ('q06', '哪个队最忙？请列出四队工作分钟供核对。', 'crews'),
    ('q07', 'GA 与 Greedy 哪项更好？', 'unsupported'),
    ('q08', '为什么这个方案已经过期？', 'stale'),
    ('q09', '当前矩阵是否来自 Google？', 'summary'),
    ('q10', '没有期限时能否判断延误？', 'metrics'),
]
CHANGES = [
    ('a01','停用 crew-02','disable'), ('a02','启用 crew-02','enable'),
    ('a03','停用 crew-02','cancel'), ('a04','停用 crew-02','replay'),
    ('a05','停用 crew-02','concurrent'), ('a06','停用 crew-02','task_changed'),
    ('a07','停用 crew-02','crew_changed'), ('a08','启用 crew-02','noop'),
    ('a09','停用第二队','ambiguous'), ('a10','封闭道路并直接提高任务优先级','unsupported'),
    ('a11','停用 crew-02','failure_recovery'),
]


def emit(case, data):
    """Opt-in, sanitized evidence; fixture credentials/cookies never exported."""
    output = os.environ.get('ROADGUARD_ACCEPTANCE_OUTPUT')
    if output:
        path = Path(output); path.mkdir(parents=True, exist_ok=True)
        (path / f'{case}.json').write_text(json.dumps({
            'case_id':case, 'passed':True, 'is_synthetic':True,
            'real_model_called':False, 'real_travel_provider_called':False, **data},
            ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


@pytest.fixture(scope='module')
def password_hash():
    return hash_password(PASSWORD)


@pytest.fixture
def client(tmp_path, monkeypatch, password_hash):
    monkeypatch.setattr(auth_module, 'hash_password', lambda value: password_hash)
    monkeypatch.setattr(provider, 'config_from_env', lambda: provider.ModelConfig(False, '', ''))
    def forbidden(*args, **kwargs):
        raise AssertionError('External model calls forbidden in C-13')
    monkeypatch.setattr(provider, 'build_opener', forbidden)
    settings = load_settings({'ROADGUARD_DB_PATH':str(tmp_path/'db.sqlite3'),
        'ROADGUARD_UPLOAD_PATH':str(tmp_path/'images'), 'ROADGUARD_VISION_MANIFEST_PATH':'disabled',
        'ROADGUARD_TRAVEL_MATRIX_PROVIDER':'simulated'})
    with TestClient(create_app(settings), raise_server_exceptions=False) as c:
        for name, role, crew in [('i','inspector',None),('i2','inspector',None),('d','dispatcher',None)]+[
                (f'c{n}','crew',f'crew-0{n}') for n in range(1,5)]:
            c.app.state.auth_service.create_user(name,name,role,crew,PASSWORD)
        yield c


def login(c, user):
    c.cookies.clear(); c.headers.pop('X-CSRF-Token', None)
    r=c.post(BASE+'/auth/login',json={'username':user,'password':PASSWORD})
    assert r.status_code == 200, r.text
    c.headers['X-CSRF-Token']=r.json()['csrf_token']
    return r.json()['user']['user_id']


def upload(c, scenario='high_confidence'):
    image=io.BytesIO(); Image.new('RGB',(80,60),'gray').save(image,'PNG')
    r=c.post(BASE+'/inspections',headers={'Idempotency-Key':uuid.uuid4().hex},
        files={'image':('synthetic.png',image.getvalue(),'image/png')},
        data={'metadata':json.dumps({'mode':'demo','scenario_id':scenario,
            'latitude':1.332,'longitude':103.676,'road_type':'public_motor_road'})})
    assert r.status_code == 201, r.text
    return r.json()


def get(c, path):
    r=c.get(BASE+path); assert r.status_code == 200, r.text
    return r.json()


def revision(c):
    return get(c,'/health')['input_revision']


def plan(c):
    r=c.post(BASE+'/route-plans/recalculate',json={'expected_revision':revision(c)})
    assert r.status_code == 200, r.text
    result=r.json()
    return get(c,'/route-plans/'+next(p['plan_id'] for p in result['plans'] if p['algorithm']=='ga'))


def preview(c, instruction, pid):
    return c.post(CHANGE,json={'request_id':uuid.uuid4().hex,'based_on_plan_id':pid,'instruction':instruction})


def confirm(c, record):
    return c.post(CHANGE+'/'+record['change_id']+'/confirm',json={'expected_version':record['record_version']})


def patch_crew(c, available):
    roster=get(c,'/crews')
    crew=next(x for x in roster['crews'] if x['crew_id']=='crew-02')
    r=c.patch(BASE+'/crews/crew-02',json={'request_id':uuid.uuid4().hex,
        'expected_version':crew['record_version'],'available':available})
    assert r.status_code == 200, r.text


@pytest.mark.parametrize('case,question,kind', QUESTIONS, ids=[q[0] for q in QUESTIONS])
def test_route_questions_with_explicit_provider_double(client, monkeypatch, case, question, kind):
    c=client; login(c,'i'); upload(c); upload(c)
    login(c,'d'); saved=plan(c)
    request={'question':question,'scope':'plan','plan_id':saved['plan_id']}
    if kind=='stale':
        patch_crew(c,False)
    calls=[]
    def select(config, user, text, scope, sources):
        calls.append(text)
        if kind=='unsupported':
            return ModelSelection(supported=False,selections=[])
        suffixes={'crew':['#crew-crew-01'],'crews':[f'#crew-crew-0{n}' for n in range(1,5)],
            'summary':['#summary'],'metrics':['#metrics'],'unassigned':['#unassigned'],
            'depot':['#summary','#depot-crews']}[kind]
        selected=[next(s for s in sources if s['citation_id'].endswith(suffix)) for suffix in suffixes]
        return ModelSelection(supported=True,selections=[{'citation_id':s['citation_id'],'quote':s['content']} for s in selected])
    monkeypatch.setattr(provider,'select_evidence',select)
    with c.app.state.database.connect() as db: before=list(db.iterdump())
    r=c.post(BASE+'/assistant/query',json=request)
    assert r.status_code == 200, r.text
    actual=r.json(); expected='stale_plan' if kind=='stale' else 'insufficient_data' if kind=='unsupported' else 'supported'
    assert actual['status']==expected and not actual['business_changes_applied']
    assert len(calls)==(0 if kind=='stale' else 1)
    assert actual['plan']['plan_id']==saved['plan_id'] and actual['plan']['input_revision']==saved['input_revision']
    for selected in actual['selections']:
        source=next(s for s in actual['sources'] if s['citation_id']==selected['citation_id'])
        assert selected['quote'] in source['content'] and source['sha256'] and source['version']
    with c.app.state.database.connect() as db: assert list(db.iterdump())==before
    emit(case,{'input':request,'expected_status':expected,'actual':actual,
        'evaluation':'Contract and supplied-evidence validation only; deterministic provider double. Not GPT semantic accuracy.',
        'provider_double_calls':len(calls)})


@pytest.mark.parametrize('case,instruction,kind', CHANGES, ids=[a[0] for a in CHANGES])
def test_adjustment_acceptance(client, monkeypatch, case, instruction, kind):
    c=client; actor=login(c,'d')
    if kind=='enable': patch_crew(c,False)
    saved=plan(c); before=get(c,'/crews')
    response=preview(c,instruction,saved['plan_id'])
    if kind in {'ambiguous','unsupported'}:
        assert response.status_code==422 and response.json()['code']=='unsupported_change'
        assert get(c,'/crews')==before
        emit(case,{'input':instruction,'plan_id':saved['plan_id'],'expected':'422; no crew mutation','actual':response.json()})
        return
    assert response.status_code==200, response.text
    record=response.json(); assert get(c,'/crews')==before
    if kind=='cancel':
        result=c.post(CHANGE+'/'+record['change_id']+'/cancel',json={'expected_version':1}).json()
        assert result['status']=='cancelled' and get(c,'/crews')==before
    elif kind in {'task_changed','crew_changed'}:
        if kind=='task_changed': login(c,'i'); upload(c); login(c,'d')
        else: patch_crew(c,False)
        changed=get(c,'/crews'); result=confirm(c,record).json()
        assert result['status']=='failed' and result['error_code']=='stale_input_revision'
        assert get(c,'/crews')==changed
    elif kind=='concurrent':
        state=c.app.state
        service=ChangeService(state.database,state.crew_service,state.route_query_service,state.planning_service)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:service.confirm(record['change_id'],actor,1),range(2)))
        assert results[0]==results[1] and revision(c)==before['input_revision']+1
        result=results[0].model_dump(mode='json')
    else:
        result=confirm(c,record).json(); assert result['status']=='confirmed'
        assert revision(c)==before['input_revision']+(0 if kind=='noop' else 1)
        assert result['replan_status']=='not_requested'
        if kind=='replay': assert confirm(c,record).json()==result
        if kind=='failure_recovery':
            original=c.app.state.planning_service._travel_matrix
            def fail(*args,**kwargs): raise AppError('travel_matrix_unavailable','Synthetic failure',503)
            monkeypatch.setattr(c.app.state.planning_service,'_travel_matrix',fail)
            url=CHANGE+'/'+record['change_id']+'/replan'
            failed=c.post(url,json={'attempt_id':'first'}).json()
            assert failed['status']=='confirmed' and failed['replan_status']=='failed'
            assert get(c,'/crews')['crews'][1]['available'] is False
            monkeypatch.setattr(c.app.state.planning_service,'_travel_matrix',original)
            assert c.post(url,json={'attempt_id':'first'}).json()==failed
            result=c.post(url,json={'attempt_id':'recovery'}).json()
            assert result['replan_status']=='succeeded' and len(result['result']['plans'])==2
            # A fresh application instance recovers the receipt from the same database.
            # No process kill is claimed here; interrupted-execution fencing is tested separately.
            with TestClient(create_app(c.app.state.settings), raise_server_exceptions=False) as restarted:
                login(restarted,'d')
                recovered=get(restarted,'/assistant/change-requests/'+record['change_id'])
                assert recovered==result
                assert restarted.post(url,json={'attempt_id':'after-restart'}).json()==result
    emit(case,{'input':instruction,'plan_id':saved['plan_id'],'input_revision':saved['input_revision'],
        'expected':kind,'actual':result,'crew_state_after':get(c,'/crews')})


def test_complete_multi_role_workflow(client):
    c=client; login(c,'i')
    empty=upload(c,'no_detection'); pending=upload(c,'low_confidence'); accepted=upload(c)
    assert empty['task_id'] is None and pending['task_id'] is None and accepted['task_id']
    assert revision(c)==1
    login(c,'i2')
    assert c.get(BASE+'/inspections/'+pending['inspection_id']).status_code==404
    assert c.get(BASE+'/tasks').status_code==403
    login(c,'d'); detail=get(c,'/inspections/'+pending['inspection_id'])
    body={'request_id':'review-c13','expected_version':detail['record_version'],'action':'confirm',
          'detection_id':detail['detections'][0]['detection_id']}
    reviewed=c.post(BASE+'/inspections/'+pending['inspection_id']+'/review',json=body)
    assert reviewed.status_code==200, reviewed.text
    assert revision(c)==2
    assert c.post(BASE+'/inspections/'+pending['inspection_id']+'/review',json=body).json()['replayed']
    saved=plan(c)
    stops=[s for r in saved['crew_routes'] for s in r['stops']]
    assert len(stops)==len({s['task_id'] for s in stops})==2
    crew=next(r for r in saved['crew_routes'] if r['stops']); task_id=crew['stops'][0]['task_id']
    other='c2' if crew['crew_id']!='crew-02' else 'c1'
    login(c,other); assert c.get(BASE+'/tasks/'+task_id).status_code==404
    login(c,'c'+crew['crew_id'][-1]); workspace=get(c,'/crew/workspace')
    assert [r['crew_id'] for r in workspace['plan']['crew_routes']]==[crew['crew_id']]
    task=get(c,'/tasks/'+task_id)
    complete={'request_id':'finish-c13','expected_version':task['record_version'],'status':'completed'}
    done=c.patch(BASE+'/tasks/'+task_id,json=complete)
    assert done.status_code==200 and done.json()['task']['status']=='completed'
    assert c.patch(BASE+'/tasks/'+task_id,json=complete).json()['replayed']
    assert revision(c)==3
    login(c,'d'); assert get(c,'/route-plans/'+saved['plan_id'])['is_stale']
    fresh=plan(c)
    assert task_id not in [s['task_id'] for r in fresh['crew_routes'] for s in r['stops']]
    assert fresh['metrics']['assigned_task_count']==1
    query=c.post(BASE+'/assistant/query',json={'question':'当前行程来源是什么？','scope':'plan','plan_id':fresh['plan_id']})
    assert query.status_code==503 and query.json()['code']=='assistant_not_configured'
    record=preview(c,'停用 crew-02',fresh['plan_id']).json()
    assert confirm(c,record).json()['status']=='confirmed'
    result=c.post(CHANGE+'/'+record['change_id']+'/replan',json={'attempt_id':'final'}).json()
    assert result['replan_status']=='succeeded'
    login(c,'c2'); disabled=get(c,'/crew/workspace')
    assert disabled['crew']['available'] is False and disabled['tasks']==[]
    emit('workflow',{'expected':'upload/review/plan/own-crew completion/stale/replan/change/replan',
        'actual':{'initial_input_revision':saved['input_revision'],'after_completion_revision':fresh['input_revision'],
                  'final_input_revision':result['result']['input_revision'],'disabled_crew':'crew-02',
                  'remaining_task_count':result['result']['task_count'],'assistant_unconfigured_http':query.status_code}})
