"""Readable answers backed by verified selections; rule values are never generated."""
from decimal import Decimal
import re

from .evidence import invalid_evidence
from .query_models import ModelSelection

RULE_CITATION = 'rg-kb-demo-rules#demo-rule-table'
LABEL_NAMES = {
    'longitudinal_crack': 'Longitudinal crack',
    'longitudinal_crack_wide': 'Wide longitudinal crack',
    'transverse_crack': 'Transverse crack',
    'transverse_crack_wide': 'Wide transverse crack',
    'alligator_crack': 'Alligator crack',
    'alligator_crack_sunken': 'Sunken alligator crack',
    'pothole': 'Pothole',
    'pothole_deep': 'Deep pothole',
}
SEVERITIES = {'low', 'medium', 'high'}
NUMBER = re.compile(r'(?<![\w.])[-+]?\d+(?:\.\d+)?%?(?![\w.])')
NUMBER_WORDS = dict(zip(
    ('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'),
    map(str, range(11)),
))


def numerical_literals(text: str) -> set[str]:
    normalized = re.sub(r'\b(?:' + '|'.join(NUMBER_WORDS) + r')\b',
                        lambda m: NUMBER_WORDS[m.group().lower()], text, flags=re.I)
    # Chinese units touch the number; ASCII boundaries prevent swallowing them.
    normalized = re.sub(r'[\u3400-\u9fff]', ' ', normalized)
    # Accept adjacent English units as numeric claims too (for example 999minutes).
    normalized = re.sub(r'(?<=\d)(?=(?:milliseconds?|minutes?|hours?|tasks?|crews?)\b)',
                        ' ', normalized, flags=re.I)
    return {str(Decimal(token.rstrip('%')).normalize()) + ('%' if token.endswith('%') else '')
            for token in NUMBER.findall(normalized)}


def rule_answer(question: str, selection: ModelSelection) -> str | None:
    """Render the selected canonical rows, including context, without trusting a draft."""
    rows = []
    seen = set()
    for item in selection.selections:
        if item.citation_id != RULE_CITATION:
            continue
        for line in item.quote.splitlines():
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if len(cells) != 4 or cells[0] not in LABEL_NAMES or cells[0] in seen:
                continue
            label, severity, priority, minutes = cells
            if severity not in SEVERITIES or priority not in {'P1', 'P2', 'P3'} or not minutes.isdigit():
                raise invalid_evidence()
            seen.add(label)
            rows.append((label, severity, priority, minutes))
    if not rows:
        return None
    lines = [f'{LABEL_NAMES[label]} has priority {priority}, an estimated repair time of '
             f'{minutes} minutes and {severity} severity.' for label, severity, priority, minutes in rows]
    lines.append('These estimates follow the current project rules and are project assumptions.')
    return '\n\n'.join(lines)


def compose_answer(question: str, scope: str, selection: ModelSelection) -> str:
    # Static rule questions get deterministic wording. A plan question may ask
    # about saved facts instead; current rule defaults must not replace them.
    if scope == 'knowledge':
        rules = rule_answer(question, selection)
        if rules is not None:
            return rules
    answer = selection.answer.strip()
    if not answer:
        raise invalid_evidence()
    selected_text = '\n'.join(item.quote for item in selection.selections)
    if not numerical_literals(answer) <= numerical_literals(selected_text):
        raise invalid_evidence()
    for token in (r'P[123]', r'(?:crew-\d+|task-[a-f0-9]+|plan-[a-f0-9]+)'):
        # Chinese prose need not add spaces around an ASCII business identifier.
        pattern = r'(?<![A-Za-z0-9_])' + token + r'(?![A-Za-z0-9_])'
        if not set(re.findall(pattern, answer)) <= set(re.findall(pattern, selected_text)):
            raise invalid_evidence()
    return answer
