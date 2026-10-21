"""Compose an answer only from validated quotations, using B's query service."""
import hashlib
import re

from roadguard.errors import AppError
from roadguard.routing.models import RoutePlan
from roadguard.routing.service import RouteQueryService
from .knowledge import load_package
from .models import KnowledgeSearchRequest
from .retrieval import search
from .query_models import AssistantQuery, AssistantAnswer, AnswerSource, PlanEvidenceSummary
from . import provider

WARNINGS = [
    '回答由模型选择的原文证据组成；引用校验不等于语义充分性或工程专家审批。',
    '演示规则、模拟行程与待定事项不能视为真实工程结论。',
    '本接口不调整队伍、不重算、不写业务记录；未提供比较方案，不能推导优化提升。',
]
DECLINES = {
    'insufficient_data': '现有证据不足以完整回答，请补充具体方案或缩小问题范围。',
    'rule_version_unavailable': '知识包不包含所请求的规则版本，不能用当前规则替代旧规则。',
    'stale_plan': '任务或队伍输入已变化，指定方案已过期。请在路线页核对并重新规划。',
    'model_refused': '模型未返回可用的证据选择，本次没有生成回答。',
}


def clean_text(text):
    return re.sub(
        r'^(?:classification|Sources|Implementation sources|\u6765\u6e90)\s*[:\uff1a].*$',
        '', text, flags=re.M,
    ).strip()


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def readable_facts(data, indent=''):
    """Deterministic labels and values; no model-generated numerical prose."""
    lines = []
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f'{indent}{key}：')
            lines.append(readable_facts(value, indent + '  '))
        elif isinstance(value, list):
            lines.append(f'{indent}{key}：' + ('无' if not value else ''))
            for item in value:
                lines.append(readable_facts(item, indent + '  '))
        else:
            rendered = '未提供（未知）' if value is None else ('是' if value else '否') if isinstance(value, bool) else str(value)
            lines.append(f'{indent}{key}：{rendered}')
    return '\n'.join(lines)


def plan_sources(plan: RoutePlan) -> list[AnswerSource]:
    """Whitelisted projection: no images, coordinates, account data or arbitrary parameters."""
    prefix = f'plan:{plan.plan_id}'
    sections = {
        'summary': ('方案与来源', {
            '方案ID': plan.plan_id, '算法': plan.algorithm, '输入版本': plan.input_revision,
            '统一开始时间UTC': plan.planning_start_at.isoformat(), '演示方案': plan.is_demo,
            '行程来源': plan.matrix_provider, '模拟行程': plan.matrix_is_simulated,
            '说明': '保存方案事实，不是实时车辆状态；不包含单条任务的冻结规则证据。',
        }),
        'metrics': ('方案指标', {
            '已分配任务数': plan.metrics.assigned_task_count,
            '未分配任务数': plan.metrics.unassigned_task_count,
            '总行程分钟': plan.metrics.total_travel_minutes,
            '总维修分钟': plan.metrics.total_service_minutes,
            '最晚收工分钟偏移': plan.metrics.makespan_minutes,
            '工作量标准差分钟': plan.metrics.workload_std_minutes,
            '有期限任务数': plan.metrics.tasks_with_due_at,
            '总延误分钟': plan.metrics.total_lateness_minutes,
            '算法耗时毫秒': plan.metrics.algorithm_runtime_ms,
            '说明': 'null 表示未知，不能当作零；无期限不能计算延误；算法耗时不等于行程或维修时长。',
        }),
        'settings': ('保存的演示约束', {
            '配置版本': plan.settings.config_version, '演示配置': plan.settings.is_demo,
            '返基地': plan.settings.return_to_depot, '班次': plan.settings.shift_limit.model_dump(),
            '目标版本': plan.settings.objective_version, '目标权重': plan.settings.weights.model_dump(),
            '说明': '仅为该方案保存的演示设置，不能视为正式运营批准。',
        }),
        'unassigned': ('未分配任务', {
            '未分配': [item.model_dump() for item in plan.unassigned_tasks],
            '说明': 'reason 为 B 返回的原因，不由助手推测。',
        }),
    }
    for route in plan.crew_routes:
        sections[f'crew-{route.crew_id}'] = (f'{route.crew_id} 访问顺序', {
            '队伍': route.crew_id, '可用': route.available, '状态': route.status,
            '按顺序停靠': [
                {'顺序': s.sequence, '任务ID': s.task_id, '优先级': s.priority,
                 '上一站行程分钟': s.travel_minutes_from_previous, '到达分钟偏移': s.arrival_minute,
                 '维修分钟': s.service_minutes, '完成分钟偏移': s.completion_minute}
                for s in route.stops],
            '总行程分钟': route.travel_minutes, '返程分钟': route.return_travel_minutes,
            '总工作分钟': route.total_work_minutes,
            '说明': '时间相对统一开始时刻；仅为保存的模拟维修安排，没有真实道路几何。',
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
    # Include sibling sections of matched documents: the small package can supply
    # adjacent constraints missed by word overlap, without indexing mutable context.
    docs = {hit.document_id for hit in result.hits}
    selected = list(result.hits) + [c for c in package.chunks
                                   if c.document_id in docs and c.citation_id not in
                                   {h.citation_id for h in result.hits}]
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
    if plan and not any(by_id[s.citation_id].kind == 'saved_plan' for s in selection.selections):
        return decline('insufficient_data')
    used = {item.citation_id for item in selection.selections}
    answer = '\n\n'.join(f'[{item.citation_id}]\n{item.quote}' for item in selection.selections)
    return AssistantAnswer(status='supported', supported=True, answer=answer,
                           selections=selection.selections, sources=[s for s in sources if s.citation_id in used],
                           **common)
