"""Summary behavior and bounded factual guards; no external model calls."""
import pytest

from roadguard.assistant.answering import compose_answer
from roadguard.assistant.query_models import EvidenceSelection, ModelSelection
from roadguard.errors import AppError


def selection(quote, answer, citation='rg-kb-demo-rules#demo-rule-table'):
    return ModelSelection(supported=True, answer=answer, selections=[
        EvidenceSelection(citation_id=citation, quote=quote),
    ])


@pytest.mark.parametrize('question, expected', [
    ('\u6df1\u5751\u6d1e\u9700\u8981\u4fee\u591a\u4e45？', 'Deep pothole has priority P1'),
    ('How long does a deep pothole take?', 'Deep pothole has priority P1'),
])
def test_rule_values_come_from_verified_row_even_when_draft_is_wrong(question, expected):
    result = compose_answer(question, 'knowledge', selection(
        '| pothole_deep | high | P1 | 240 |', 'A shallow pothole takes 999 minutes at P3.'))
    assert expected in result and '240' in result
    assert '999' not in result and 'P3' not in result and '|' not in result


def test_comparison_keeps_both_types_and_project_qualifier():
    result = compose_answer('Compare ordinary and wide longitudinal cracks.', 'knowledge', selection(
        '| longitudinal_crack | low | P3 | 60 |\n| longitudinal_crack_wide | medium | P2 | 120 |', 'ignored'))
    assert 'Longitudinal crack has priority P3' in result
    assert 'Wide longitudinal crack has priority P2' in result
    assert '60 minutes' in result and '120 minutes' in result
    assert 'project assumptions' in result


def test_rule_renderer_reads_actual_selected_duration_instead_of_hardcoding_defaults():
    result = compose_answer('pothole', 'knowledge', selection('| pothole | medium | P2 | 125 |', 'ignored'))
    assert '125 minutes' in result


@pytest.mark.parametrize('scope', ['knowledge', 'plan'])
def test_supported_summary_is_used_without_copying_raw_source(scope):
    answer = 'The saved plan assigns 2 tasks, with 98.8 minutes of simulated travel.'
    result = compose_answer('Summarize the plan.', scope, selection(
        'Assigned tasks: 2\nTravel minutes: 98.8\nMatrix source: simulated', answer, 'plan-test#metrics'))
    assert result == answer


@pytest.mark.parametrize('answer', [
    'Travel takes 999 minutes.', 'There are seven crews.',
    'Travel takes 999minutes.', 'Travel takes 999\u5206\u949f.',
    'Use priority P1.', 'Assigned to crew-02.', 'Use plan-abcdef.', '',
    '\u4f18\u5148\u7ea7P1。', '\u7531crew-02\u8d1f\u8d23。',
])
def test_unselected_numbers_priorities_and_identifiers_are_rejected(answer):
    with pytest.raises(AppError) as error:
        compose_answer('Summary', 'plan', selection(
            'Travel: 98.8 minutes. There are four crews. Priority P2; crew-01.', answer, 'plan-test#metrics'))
    assert error.value.code == 'assistant_invalid_response'


def test_current_rules_do_not_override_frozen_plan_facts():
    evidence = selection('| pothole | medium | P2 | 120 |', 'The saved service time is 45 minutes.')
    evidence.selections.append(EvidenceSelection(citation_id='plan-test#metrics', quote='Saved service minutes: 45'))
    result = compose_answer('What is the saved service time?', 'plan', evidence)
    assert result == 'The saved service time is 45 minutes.'
