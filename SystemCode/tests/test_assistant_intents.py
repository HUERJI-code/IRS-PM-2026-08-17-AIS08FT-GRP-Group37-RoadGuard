"""Local intent answers never require knowledge, saved plans or paid calls."""
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from roadguard.assistant import query_service
from roadguard.assistant.intents import classify_intent
from roadguard.assistant.query_models import AssistantQuery
from test_assistant_query import client, login, no_real_network, URL


@pytest.mark.parametrize('question', [
    'What model are you?', 'Which model are you using?', 'What is your model name?',
    '\u4f60\u662f\u4ec0\u4e48\u6a21\u578b\uff1f',
    '\u4f60\u7528\u7684\u662f\u4ec0\u4e48\u6a21\u578b\uff1f',
])
@pytest.mark.parametrize('configured', [True, False])
def test_identity_works_without_dependencies(client, monkeypatch, question, configured):
    login(client)
    monkeypatch.setenv('ROADGUARD_ASSISTANT_ENABLED', 'false')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    if not configured:
        monkeypatch.delenv('ROADGUARD_ASSISTANT_MODEL', raising=False)
    for name in ['load_package', 'search']:
        monkeypatch.setattr(query_service, name, Mock(side_effect=AssertionError(name)))
    monkeypatch.setattr(query_service.provider, 'select_evidence', Mock(side_effect=AssertionError('paid call')))
    with client.app.state.database.connect() as conn:
        before = list(conn.iterdump())
    # Even a syntactically valid but absent saved plan is unnecessary here.
    response = client.post(URL, json={'question': question, 'scope': 'plan', 'plan_id': 'plan-' + '0'*32})
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'model_info' and body['supported']
    assert body['contract_version'] == 'c-assistant-query-v3'
    assert body['answer_mode'] == 'server_configuration'
    assert body['model'] == ('fixture-model' if configured else None)
    assert not body['model_called'] and not body['business_changes_applied']
    assert body['sources'] == body['selections'] == []
    assert body['package_version'] is body['manifest_sha256'] is body['plan'] is None
    assert 'fixture-not-a-key' not in response.text
    with client.app.state.database.connect() as conn:
        assert list(conn.iterdump()) == before


@pytest.mark.parametrize('question', ['What is the weather?', 'Tell me a joke', '\u4eca\u5929\u5929\u6c14\u5982\u4f55'])
def test_explicit_unrelated_question_has_friendly_local_guidance(client, monkeypatch, question):
    login(client)
    monkeypatch.setattr(query_service, 'load_package', Mock(side_effect=AssertionError('knowledge')))
    monkeypatch.setattr(query_service.provider, 'config_from_env', Mock(side_effect=AssertionError('provider')))
    body = client.post(URL, json={'question': question, 'scope': 'knowledge'}).json()
    assert body['status'] == 'out_of_scope' and not body['supported']
    assert body['answer_mode'] == 'scope_guidance' and 'RoadGuard' in body['answer']
    assert not body['model_called'] and body['sources'] == body['selections'] == []


@pytest.mark.parametrize('question', [
    'What model are you and how do we repair deep potholes?',
    'Which model should we select for YOLO?', 'How do I repair potholes?',
    'Explain crew visit order and GA routing', 'What is Chroma?',
    'Does weather affect RoadGuard repair durations?',
    'Do routes change in bad weather?', 'How do repairs depend on weather?', 'xyzzyq987 qqqzz',
    '\u6df1\u5751\u6d1e\u7ef4\u4fee\u5de5\u65f6',
])
def test_project_and_ambiguous_questions_reach_existing_validation(monkeypatch, question):
    assert classify_intent(question) == 'grounded'
    marker = RuntimeError('existing knowledge validation reached')
    monkeypatch.setattr(query_service, 'load_package', Mock(side_effect=marker))
    with pytest.raises(RuntimeError, match='knowledge validation reached'):
        query_service.answer_query(AssistantQuery(question=question, scope='knowledge'), 'user', Mock())


def test_local_intents_keep_authentication_and_csrf(client):
    payload = {'question': 'What model are you?', 'scope': 'knowledge'}
    client.cookies.clear()
    assert client.post(URL, json=payload).status_code == 401
    for role in ['i', 'c']:
        login(client, role)
        assert client.post(URL, json=payload).status_code == 403
    login(client)
    assert client.post(URL, json=payload, headers={'X-CSRF-Token': 'wrong'}).status_code == 403
    assert client.post(URL, json={**payload, 'scope': 'plan', 'plan_id': 'forged'}).status_code == 422
    with pytest.raises(ValidationError):
        AssistantQuery(question='What model are you?', scope='plan')
