"""Server-owned verbatim evidence units; the model selects IDs, never writes quotes."""
from dataclasses import dataclass
import re
import unicodedata

from roadguard.errors import AppError
from .query_models import EvidenceSelection, ModelSelection

LABEL_TABLES = {'rg-kb-demo-rules#demo-rule-table', 'rg-kb-labels#label-table'}
# Language aliases identify classes only. Rule values always come from verified sources.
LABEL_ALIASES = {
    'longitudinal_crack': (r'longitudinal[ _-]+cracks?', r'\u7eb5(?:\u5411)?\u88c2\u7f1d'),
    'longitudinal_crack_wide': (r'(?:wide[ _-]+longitudinal[ _-]+cracks?|longitudinal[ _-]+cracks?[ _-]+wide)', r'\u5bbd\u7eb5(?:\u5411)?\u88c2\u7f1d'),
    'transverse_crack': (r'transverse[ _-]+cracks?', r'\u6a2a(?:\u5411)?\u88c2\u7f1d'),
    'transverse_crack_wide': (r'(?:wide[ _-]+transverse[ _-]+cracks?|transverse[ _-]+cracks?[ _-]+wide)', r'\u5bbd\u6a2a(?:\u5411)?\u88c2\u7f1d'),
    'alligator_crack': (r'alligator[ _-]+cracks?', r'\u9f9f\u88c2'),
    'alligator_crack_sunken': (r'(?:sunken[ _-]+alligator[ _-]+cracks?|alligator[ _-]+cracks?[ _-]+sunken)', r'(?:\u4e0b\u9677|\u6c89\u9677)(?:\u7684)?\u9f9f\u88c2'),
    'pothole': (r'potholes?', r'\u5751\u6d1e'),
    'pothole_deep': (r'(?:deep[ _-]+potholes?|potholes?[ _-]+deep)', r'\u6df1(?:\u7684)?\u5751\u6d1e'),
}


def requested_labels(question: str) -> set[str]:
    """Longest non-overlapping aliases keep deep/sunken/wide distinct from base labels.

    This is a bounded terminology guard, not a general natural-language classifier.
    Unknown paraphrases still rely on the model's relevance/insufficiency decision.
    """
    text = unicodedata.normalize('NFKC', question).lower()
    matches = []
    for label, aliases in LABEL_ALIASES.items():
        for alias in aliases:
            pattern = alias if r'\u' in alias else rf'(?<![a-z0-9_]){alias}(?![a-z0-9_])'
            matches.extend((m.start(), m.end(), label) for m in re.finditer(pattern, text))
    accepted = []
    for match in sorted(matches, key=lambda m: (-(m[1] - m[0]), m[0])):
        if not any(match[0] < end and start < match[1] for start, end, _ in accepted):
            accepted.append(match)
    return {label for _, _, label in accepted}


def invalid_evidence():
    return AppError('assistant_invalid_response', 'The model returned unverifiable evidence.', 502)


@dataclass(frozen=True)
class EvidenceUnit:
    evidence_id: str
    citation_id: str
    kind: str
    classification: str
    quote: str
    context_quotes: tuple[str, ...] = ()
    label_key: str | None = None

    def selections(self) -> list[EvidenceSelection]:
        return [EvidenceSelection(citation_id=self.citation_id, quote=q)
                for q in (*self.context_quotes, self.quote)]

    def model_data(self) -> dict:
        return dict(evidence_id=self.evidence_id, citation_id=self.citation_id,
                    kind=self.kind, classification=self.classification,
                    label_key=self.label_key, content=self.quote,
                    required_context=list(self.context_quotes))


def build_catalogue(question: str, sources: list[dict]) -> list[EvidenceUnit]:
    labels = requested_labels(question)
    units = []

    def add(source, quote, context=(), label=None):
        if not quote.strip() or len(quote) > 2400 or any(len(q) > 2400 for q in context):
            raise AppError('assistant_context_too_large', 'An evidence unit exceeds the bounded size.', 422)
        units.append(EvidenceUnit(f'e{len(units) + 1}', source['citation_id'], source['kind'],
                                  source['classification'], quote, context, label))

    for source in sources:
        content = source['content']
        if source['citation_id'] in LABEL_TABLES:
            # The two canonical tables have one label_key column. Fail closed if
            # their reviewed shape changes; never infer values from column offsets.
            lines = list(re.finditer(r'^\|[^\n]+\|[ \t]*$', content, flags=re.M))
            if len(lines) < 3:
                raise invalid_evidence()
            header = [c.strip() for c in lines[0].group().strip().strip('|').split('|')]
            if header.count('label_key') != 1:
                raise invalid_evidence()
            column = header.index('label_key')
            rows = []
            for line in lines[2:]:
                cells = [c.strip() for c in line.group().strip().strip('|').split('|')]
                if len(cells) != len(header) or cells[column] not in LABEL_ALIASES:
                    raise invalid_evidence()
                rows.append((cells[column], line))
            if len(rows) != len(LABEL_ALIASES) or {label for label, _ in rows} != set(LABEL_ALIASES):
                raise invalid_evidence()
            if not labels:
                # A general table question may require all eight rows.
                add(source, content)
            else:
                context = content[:rows[0][1].start()].rstrip()
                for label, line in rows:
                    if label in labels:
                        add(source, line.group(), (context,), label)
            continue
        # Keep paragraphs intact. Long saved-plan projections can span many
        # stops: retain every line in bounded contiguous units, without cutting
        # a field value or silently omitting the remaining route facts.
        for paragraph in re.split(r'\n[ \t]*\n+', content):
            paragraph = paragraph.strip()
            if paragraph and not re.fullmatch(r'#{1,6} [^\n]+', paragraph):
                block = ''
                for line in paragraph.splitlines(keepends=True):
                    if block and len(block + line) > 2400:
                        add(source, block.rstrip())
                        block = ''
                    block += line
                if block:
                    add(source, block.rstrip())
    return units


def resolve_ids(ids: list[str], catalogue: list[EvidenceUnit]) -> ModelSelection:
    by_id = {unit.evidence_id: unit for unit in catalogue}
    if len(ids) != len(set(ids)) or any(item not in by_id for item in ids):
        raise invalid_evidence()
    selections = []
    seen = set()
    for evidence_id in ids:
        for selection in by_id[evidence_id].selections():
            key = (selection.citation_id, selection.quote)
            if key not in seen:
                seen.add(key)
                selections.append(selection)
    return ModelSelection(supported=bool(ids), selections=selections)


def validate_selection(question: str, sources: list[dict], selection: ModelSelection) -> bool:
    """Check catalogue membership as well as coverage of explicitly named table rows."""
    catalogue = build_catalogue(question, sources)
    allowed = {(item.citation_id, item.quote) for unit in catalogue for item in unit.selections()}
    selected = {(item.citation_id, item.quote) for item in selection.selections}
    if not selected <= allowed:
        raise invalid_evidence()
    for unit in catalogue:
        if (unit.citation_id, unit.quote) in selected:
            if any((unit.citation_id, context) not in selected for context in unit.context_quotes):
                raise invalid_evidence()
    labels = requested_labels(question)
    for citation in LABEL_TABLES & {item.citation_id for item in selection.selections}:
        covered = {unit.label_key for unit in catalogue
                   if unit.citation_id == citation and (citation, unit.quote) in selected}
        if labels and not labels <= covered:
            return False
    return True
