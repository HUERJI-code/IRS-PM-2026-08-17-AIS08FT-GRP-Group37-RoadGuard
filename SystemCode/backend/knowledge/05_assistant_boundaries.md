# Evidence limits for assistant answers and changes

document_id: `rg-kb-assistant`; document_version: `6`; owner: `A`.

<a id="assistant-plan-facts"></a>
## Dynamic route facts

classification: `confirmed_project_fact`. citation_id: `rg-kb-assistant#assistant-plan-facts`.

B's planning persistence and query services are implemented. C implements lexical retrieval, opt-in GPT selection of verified evidence extracts and confirmed crew-change orchestration. Real GPT connectivity and semantic quality remain unverified. The following constraints still govern the integrated service. Route answers must bind to B's saved plan_id and input_revision, using the corresponding crew_routes, stop order, unassigned entries, metrics, matrix_provider and stale information. Comparisons require two explicit saved plans plus evidence from the same recalculation and matching task/matrix/settings checks; time-saving comparisons also need the same assigned task set. A's static knowledge explains scope/labels/rules but cannot supply current crew assignments, arrival times or total travel minutes.

Without a persisted plan or relevant facts, return insufficient_data and identify missing plans/fields. Do not invent routes from images, task ordering, model answers or fixtures. Illustrative straight lines are not road geometry; simulated matrices are not Google measurements. Display stale plans and failures explicitly without replacing them with fictional new results.

Sources: [context-agents](../../../AGENTS.md), [context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md), [src-project-config](../../config/project.example.json), [src-routing-service](../roadguard/routing/service.py), [src-plan-comparison](../../frontend/src/planning/comparison.ts), [src-assistant-page](../../frontend/src/pages/AssistantPage.tsx).

Implementation sources: [src-assistant-query](../roadguard/assistant/query_service.py).

<a id="assistant-confirmation"></a>
## Crew adjustments require confirmation

classification: `confirmed_project_fact`. citation_id: `rg-kb-assistant#assistant-confirmation`.

The first assistant change scope is crew availability only: structured preview, then explicit user confirmation, then the assistant validates input and crew versions inside a write transaction and calls the existing B services. CrewService PATCH checks expected_version and returns input_revision; it does not take expected_revision or automatically recalculate. PlanningService separately requires expected_revision. Cancellation, stale requests and repeated confirmation need explicit outcomes. Neither the assistant nor C directly writes task/crew/plan tables or creates another scheduling algorithm. New tasks use A's inspection/review workflow; natural language cannot freely specify priority, deadlines or service durations. The implemented workflow persists preview/confirm/cancel and explicit replan receipts. Static text alone cannot claim a specific crew change or calculation succeeded; read the authorized receipt and saved plans.

Sources: [context-agents](../../../AGENTS.md), [context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md), [src-workflow-schema](../roadguard/schemas/workflow.py), [src-crew-schema](../roadguard/crews/schemas.py), [src-crew-service](../roadguard/crews/service.py), [src-routing-service](../roadguard/routing/service.py).

Implementation sources: [src-assistant-change](../roadguard/assistant/change_service.py).

<a id="assistant-rule-versions"></a>
## Rule versions in runtime records

classification: `confirmed_project_fact`. citation_id: `rg-kb-assistant#assistant-rule-versions`.

This package pins demo-rules-v2, but runtime configuration or frozen older inspection snapshots may use demo-rules-v1 or another version. C must first check task/inspection rule_version, then explain using that record's decision_trace, review/task history and matching rule evidence. It must not silently substitute the latest static table to infer the original decision. Explain only with sufficient matching saved evidence; otherwise return insufficient_data and request the corresponding record/version. A version mismatch does not establish a bad record or authorize business-data changes.

Sources: [src-demo-rules](../../config/demo_rules.example.json), [src-workflow-service](../roadguard/inspections/service.py), [src-workflow-schema](../roadguard/schemas/workflow.py).

<a id="assistant-evidence-limits"></a>
## Unsupported conclusions

classification: `confirmed_project_fact`. citation_id: `rg-kb-assistant#assistant-evidence-limits`.

The evaluation document now summarizes committed historical model and GA experiments with pinned sources. The package still contains no current runtime plans, actual road permissions or measured service times. Historical results are not today's assignments or a guarantee of future performance. Health does not establish model/Google/GPT readiness; fixed confidence does not prove detection accuracy; demo rules do not prove engineering severity. GA superiority over Greedy requires records using the same tasks, matrix and constraints across multiple random seeds. Do not invent lateness minutes without deadlines or monetary savings without a cost model.

Answers must preserve both support and limitations: static project explanations may be supported, while specific numbers/conclusions requiring missing dynamic evidence must be insufficient_data. Cite relevant stable sections and versions; do not add facts absent from sources.

Sources: [context-agents](../../../AGENTS.md), [context-scope](../../../Miscellaneous/PROJECT_SCOPE.md), [src-label-schema](../../model/label_schema.json), [src-demo-rules](../../config/demo_rules.example.json), [src-vision-evaluation](../../experiments/vision/single_damage_summary.json), [src-routing-results](../../experiments/routing/results/README.md), [src-ga-evaluation](../../experiments/routing/results/ga-evaluation-v1/summary.json).
