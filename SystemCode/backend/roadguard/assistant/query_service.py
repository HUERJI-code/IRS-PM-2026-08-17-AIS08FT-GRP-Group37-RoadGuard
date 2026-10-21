"""Validate selected evidence before composing a read-only grounded summary."""
import hashlib

from roadguard.errors import AppError
from roadguard.routing.models import RoutePlan
from roadguard.routing.service import RouteQueryService
from .knowledge import load_package
from .models import KnowledgeSearchRequest
from .retrieval import search
from .content import clean_text
from .evidence import validate_selection
from .answering import compose_answer
from .query_models import AssistantQuery, AssistantAnswer, AnswerSource, PlanEvidenceSummary
from . import provider
from .intents import classify_intent, SCOPE_GUIDANCE

WARNINGS = [
    'Answers use verified sources; rule values come from original evidence. Source validation does not guarantee every semantic judgment.',
    'Demo rules, simulated travel and pending decisions are not real engineering conclusions.',
    'This endpoint does not change crews, replan or write business records. Without a comparison plan, improvement cannot be inferred.',
]
DECLINES = {
    'insufficient_data': 'I could not find enough verified RoadGuard evidence to answer this question. ' + SCOPE_GUIDANCE,
    'rule_version_unavailable': 'The knowledge package does not contain the requested rule version. Current rules cannot replace older rules.',
    'stale_plan': 'Task or crew inputs have changed and the selected plan is stale. Review the Routes page and replan.',
    'model_refused': 'The model returned no usable evidence selection. No answer was generated.',
}


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def readable_facts(data, indent=''):
    """Deterministic labels and values; no model-generated numerical prose."""
    lines = []
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f'{indent}{key}: ')
            lines.append(readable_facts(value, indent + '  '))
        elif isinstance(value, list):
            lines.append(f'{indent}{key}: ' + ('None' if not value else ''))
            for item in value:
                lines.append(readable_facts(item, indent + '  '))
        else:
            rendered = 'Not provided (unknown)' if value is None else ('Yes' if value else 'No') if isinstance(value, bool) else str(value)
            lines.append(f'{indent}{key}: {rendered}')
    return '\n'.join(lines)


def plan_sources(plan: RoutePlan) -> list[AnswerSource]:
    """Whitelisted projection: no images, coordinates, account data or arbitrary parameters."""
    prefix = f'plan:{plan.plan_id}'
    sections = {
        'summary': ('Plan and provenance', {
            'Plan ID': plan.plan_id, 'Algorithm': plan.algorithm, 'Input revision': plan.input_revision,
            'Common start UTC': plan.planning_start_at.isoformat(), 'Demo plan': plan.is_demo,
            'Travel source': plan.matrix_provider, 'Simulated travel': plan.matrix_is_simulated,
            'Notes': 'Saved plan facts, not live vehicle status; individual task rule snapshots are not included.',
        }),
        'metrics': ('Plan metrics', {
            'Assigned task count': plan.metrics.assigned_task_count,
            'Unassigned task count': plan.metrics.unassigned_task_count,
            'Total travel minutes': plan.metrics.total_travel_minutes,
            'Total service minutes': plan.metrics.total_service_minutes,
            'Makespan minute offset': plan.metrics.makespan_minutes,
            'Workload standard deviation minutes': plan.metrics.workload_std_minutes,
            'Tasks with deadlines': plan.metrics.tasks_with_due_at,
            'Total lateness minutes': plan.metrics.total_lateness_minutes,
            'Algorithm runtime milliseconds': plan.metrics.algorithm_runtime_ms,
            'Notes': 'null means unknown, not zero. Lateness cannot be calculated without deadlines. Algorithm runtime is distinct from travel or repair duration.',
        }),
        'settings': ('Saved demo constraints', {
            'Configuration version': plan.settings.config_version, 'Demo configuration': plan.settings.is_demo,
            'Return to depot': plan.settings.return_to_depot, 'Shift': plan.settings.shift_limit.model_dump(),
            'Objective version': plan.settings.objective_version, 'Objective weights': plan.settings.weights.model_dump(),
            'Notes': 'These are saved demo settings for this plan, not approval for real operations.',
        }),
        'unassigned': ('Unassigned tasks', {
            'Unassigned': [item.model_dump() for item in plan.unassigned_tasks],
            'Notes': 'reason is returned by the routing service and is not inferred by the assistant.',
        }),
    }
    for route in plan.crew_routes:
        sections[f'crew-{route.crew_id}'] = (f'{route.crew_id} Visit order', {
            'Crew': route.crew_id, 'Available': route.available, 'Status': route.status,
            'Ordered stops': [
                {'Sequence': s.sequence, 'Task ID': s.task_id, 'Priority': s.priority,
                 'Travel minutes from previous stop': s.travel_minutes_from_previous, 'Arrival minute offset': s.arrival_minute,
                 'Service minutes': s.service_minutes, 'Completion minute offset': s.completion_minute}
                for s in route.stops],
            'Total travel minutes': route.travel_minutes, 'Return travel minutes': route.return_travel_minutes,
            'Total work minutes': route.total_work_minutes,
            'Notes': 'Times are offsets from the common start. This is a saved simulated maintenance schedule without real road geometry.',
        })
    output = []
    for key, (title, data) in sections.items():
        content = readable_facts(data)
        output.append(AnswerSource(citation_id=f'{prefix}#{key}', kind='saved_plan',
                                  title=title, classification='saved_demo_plan',
                                  content=content, version=str(plan.input_revision),
                                  sha256=digest(content), provenance=[]))
    return output


def answer_query(payload: AssistantQuery, user_id: str, queries: RouteQueryService) -> AssistantAnswer:
    intent = classify_intent(payload.question)
    if intent in {'model_info', 'out_of_scope'}:
        model = (provider.config_from_env().model or None) if intent == 'model_info' else None
        answer = (f'The server is configured to use {model}. This reports configuration; no model was called for this answer.'
                  if model else 'No assistant model name is configured on this server. No model was called for this answer.')
        return AssistantAnswer(
            status=intent, supported=intent == 'model_info',
            answer=answer if intent == 'model_info' else SCOPE_GUIDANCE,
            selections=[], sources=[], package_version=None, manifest_sha256=None,
            plan=None, model=model, model_called=False,
            answer_mode='server_configuration' if intent == 'model_info' else 'scope_guidance',
            warnings=[])
    package = load_package()
    plan = queries.get(payload.plan_id) if payload.plan_id else None
    summary = PlanEvidenceSummary(
        **plan.model_dump(include={'plan_id', 'input_revision', 'algorithm', 'matrix_provider',
                                  'matrix_is_simulated', 'is_demo', 'is_stale'})) if plan else None
    common = dict(package_version=package.package_version, manifest_sha256=package.manifest_sha256,
                  plan=summary, model=None, model_called=False, warnings=WARNINGS)

    def decline(status):
        return AssistantAnswer(status=status, supported=False, answer=DECLINES[status],
                               selections=[], sources=[], **common)

    if payload.rule_version and payload.rule_version != package.versions['rule_version']:
        return decline('rule_version_unavailable')
    if plan and plan.is_stale:
        return decline('stale_plan')
    result = search(package, KnowledgeSearchRequest(query=payload.question, limit=8,
                                                   rule_version=payload.rule_version))
    if not result.hits and plan is None:
        return decline('insufficient_data')
    # Use retrieved parent sections only; unrelated sibling sections inflate context.
    selected = result.hits
    sources = [AnswerSource(citation_id=c.citation_id, kind='knowledge', title=c.title,
                            classification=c.classification, content=clean_text(c.text),
                            version=c.document_version, sha256=c.document_sha256,
                            provenance=c.sources) for c in selected]
    if plan:
        sources.extend(plan_sources(plan))
    config = provider.config_from_env()
    evidence = [{'citation_id': s.citation_id, 'kind': s.kind, 'classification': s.classification,
                 'content': s.content} for s in sources]
    selection = provider.select_evidence(config, user_id, payload.question, payload.scope, evidence)
    common.update(model=config.model, model_called=True)
    # Recheck after network latency. Never attach a new state to old model output.
    if load_package().manifest_sha256 != package.manifest_sha256:
        raise AppError('knowledge_unavailable', 'Knowledge changed during the query.', 503)
    if plan:
        latest = queries.get(plan.plan_id)
        if latest.is_stale:
            common['plan'] = summary.model_copy(update={'is_stale': True})
            return decline('stale_plan')
        if latest != plan:
            raise AppError('assistant_evidence_changed', 'Saved evidence changed during the query.', 409)
    if selection is None:
        return decline('model_refused')
    if not selection.supported:
        return decline('insufficient_data')
    by_id = {s.citation_id: s for s in sources}
    seen = set()
    for item in selection.selections:
        source = by_id.get(item.citation_id)
        if (not source or not item.quote.strip() or item.quote not in source.content
                or (item.citation_id, item.quote) in seen):
            raise provider.invalid_response()
        seen.add((item.citation_id, item.quote))
    if not validate_selection(payload.question, evidence, selection):
        return decline('insufficient_data')
    if plan and not any(by_id[s.citation_id].kind == 'saved_plan' for s in selection.selections):
        return decline('insufficient_data')
    used = {item.citation_id for item in selection.selections}
    answer = compose_answer(payload.question, payload.scope, selection)
    return AssistantAnswer(status='supported', supported=True, answer=answer,
                           selections=selection.selections, sources=[s for s in sources if s.citation_id in used],
                           **common)
