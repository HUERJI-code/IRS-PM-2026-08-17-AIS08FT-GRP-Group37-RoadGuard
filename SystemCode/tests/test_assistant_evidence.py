"""Regression coverage for wrong table rows and model-reconstructed quotations."""
import json

import pytest

from roadguard.assistant import provider
from roadguard.assistant.content import clean_text
from roadguard.assistant.evidence import (
    build_catalogue, requested_labels, resolve_ids, validate_selection,
)
from roadguard.assistant.knowledge import load_package
from roadguard.errors import AppError

RULES = 'rg-kb-demo-rules#demo-rule-table'


@pytest.fixture
def sources():
    package = load_package()
    return [dict(citation_id=c.citation_id, kind='knowledge', classification=c.classification,
                 content=clean_text(c.text)) for c in package.chunks
            if c.citation_id in {RULES, 'rg-kb-labels#label-table'}]


@pytest.mark.parametrize('question,label', [
    ('longitudinal_crack', 'longitudinal_crack'),
    ('Wide longitudinal cracks', 'longitudinal_crack_wide'),
    ('transverse crack', 'transverse_crack'),
    ('transverse_crack_wide', 'transverse_crack_wide'),
    ('alligator crack', 'alligator_crack'),
    ('Sunken alligator cracks', 'alligator_crack_sunken'),
    ('ordinary pothole', 'pothole'),
    ('How long to repair deep potholes?', 'pothole_deep'),
    ('\u7eb5\u5411\u88c2\u7f1d', 'longitudinal_crack'),
    ('\u5bbd\u7eb5\u88c2\u7f1d', 'longitudinal_crack_wide'),
    ('\u6a2a\u5411\u88c2\u7f1d', 'transverse_crack'),
    ('\u5bbd\u6a2a\u88c2\u7f1d', 'transverse_crack_wide'),
    ('\u9f9f\u88c2', 'alligator_crack'),
    ('\u4e0b\u9677\u9f9f\u88c2', 'alligator_crack_sunken'),
    ('\u666e\u901a\u5751\u6d1e', 'pothole'),
    ('\u6df1\u5751\u6d1e\u9700\u8981\u5b89\u6392\u591a\u5c11\u7ef4\u4fee\u65f6\u95f4\uff1f\u4f18\u5148\u7ea7\u662f\u4ec0\u4e48\uff1f', 'pothole_deep'),
])
def test_exact_label_row_available_without_sibling_classes(question, label, sources):
    assert requested_labels(question) == {label}
    catalogue = build_catalogue(question, sources)
    assert {unit.label_key for unit in catalogue} == {label}
    unit = next(unit for unit in catalogue if unit.citation_id == RULES)
    result = resolve_ids([unit.evidence_id], catalogue)
    assert validate_selection(question, sources, result)
    assert len(result.selections) == 2
    assert f'| {label} |' in result.selections[-1].quote
    assert 'demo-rules-v2' in result.selections[0].quote
    assert 'Demo service_minutes' in result.selections[0].quote
    assert 'must not direct real repairs' in result.selections[0].quote
    original = next(s['content'] for s in sources if s['citation_id'] == RULES)
    assert all(item.quote in original for item in result.selections)


def test_comparison_retains_both_rows_and_rejects_partial_answer(sources):
    question = 'Compare ordinary pothole and deep pothole priority and repair minutes.'
    assert requested_labels(question) == {'pothole', 'pothole_deep'}
    catalogue = build_catalogue(question, sources)
    rows = [u for u in catalogue if u.citation_id == RULES]
    result = resolve_ids([u.evidence_id for u in rows], catalogue)
    assert len(result.selections) == 3  # One context plus two independent rows.
    assert validate_selection(question, sources, result)
    assert not validate_selection(question, sources, resolve_ids([rows[0].evidence_id], catalogue))


@pytest.mark.parametrize('kind', ['wrong_type', 'spliced', 'header_and_row', 'missing_context'])
def test_even_real_wrong_rows_and_manufactured_quotes_are_rejected(sources, kind):
    question = 'deep pothole repair time'
    catalogue = build_catalogue(question, sources)
    unit = next(u for u in catalogue if u.citation_id == RULES)
    result = resolve_ids([unit.evidence_id], catalogue)
    if kind == 'wrong_type':
        # Same P1 / 240 values, different class: source substring alone is insufficient.
        result.selections[-1].quote = '| alligator_crack_sunken | high | P1 | 240 |'
    elif kind == 'spliced':
        result.selections[-1].quote = result.selections[0].quote + '\n\n' + unit.quote
    elif kind == 'header_and_row':
        result.selections[-1].quote = '| label_key | Demo severity | Demo priority | Demo service_minutes |\n' + unit.quote
    else:
        result.selections = result.selections[-1:]
    with pytest.raises(AppError) as error:
        validate_selection(question, sources, result)
    assert error.value.code == 'assistant_invalid_response'


def test_generic_table_question_keeps_all_eight_rows(sources):
    catalogue = build_catalogue('List every configured repair rule.', sources)
    unit = next(u for u in catalogue if u.citation_id == RULES)
    assert '| pothole_deep | high | P1 | 240 |' in unit.quote
    assert '| longitudinal_crack | low | P3 | 60 |' in unit.quote
    assert validate_selection('List every configured repair rule.', sources,
                              resolve_ids([unit.evidence_id], catalogue))


@pytest.mark.parametrize('ids', [['forged'], ['e1', 'e1']])
def test_unknown_and_duplicate_ids_fail_closed(ids, sources):
    with pytest.raises(AppError):
        resolve_ids(ids, build_catalogue('deep pothole', sources))


def test_adapter_only_accepts_ids_and_restores_exact_quotes(monkeypatch, sources):
    question = 'deep pothole repair time'
    captured = []

    class Response:
        def __init__(self, raw): self.raw = raw
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return self.raw

    class Opener:
        def open(self, request, timeout):
            body = json.loads(request.data)
            captured.append(body)
            data = json.loads(body['input'][0]['content'])
            row = next(u for u in data['evidence'] if u['citation_id'] == RULES)
            assert row['label_key'] == 'pothole_deep'
            assert 'alligator_crack_sunken' not in json.dumps(data['evidence'])
            ids_schema = body['text']['format']['schema']['properties']['evidence_ids']
            assert row['evidence_id'] in ids_schema['items']['enum']
            output = {'supported': True, 'evidence_ids': [row['evidence_id']],
                      'answer': 'Deep potholes have priority P1 and an estimated repair time of 240 minutes.'}
            envelope = {'status': 'completed', 'output': [{'type': 'message', 'role': 'assistant',
                'content': [{'type': 'output_text', 'text': json.dumps(output)}]}]}
            return Response(json.dumps(envelope).encode())

    monkeypatch.setattr(provider, 'build_opener', lambda *args: Opener())
    monkeypatch.setattr(provider, 'BUDGET', provider.CallBudget())
    result = provider.select_evidence(provider.ModelConfig(True, 'fixture', 'fixture-model'),
                                      'dispatcher', question, 'knowledge', sources)
    assert len(captured) == 1
    assert result.selections[-1].quote == '| pothole_deep | high | P1 | 240 |'
    assert validate_selection(question, sources, result)


def test_long_saved_route_preserves_all_lines_in_bounded_contiguous_units():
    lines = ['Crew: crew-01'] + [f'Stop {i}: task-{i:032d}; service_minutes=120; arrival={i*130}' for i in range(1, 51)]
    content = '\n'.join(lines)
    source = dict(citation_id='plan:fixture#crew-crew-01', kind='saved_plan',
                  classification='saved_demo_plan', content=content)
    units = build_catalogue('What is the saved crew route?', [source])
    assert len(units) > 1
    assert all(len(u.quote) <= 2400 and u.quote in content for u in units)
    assert '\n'.join(u.quote for u in units) == content


@pytest.mark.parametrize('text', ['pothole_deeper', 'notpothole', 'longitudinal_crack_width'])
def test_partial_english_tokens_do_not_select_a_label(text):
    assert requested_labels(text) == set()
