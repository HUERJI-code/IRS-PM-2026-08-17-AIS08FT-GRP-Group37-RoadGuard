# Evidence limits for assistant answers and changes

document_id: `rg-kb-assistant`; document_version: `3`; owner: `A`.

<a id="assistant-plan-facts"></a>
## Dynamic route facts

classification: `confirmed_project_fact`. citation_id: `rg-kb-assistant#assistant-plan-facts`.

These are recorded integration requirements pending B/C implementation, not assistant/planning features supplied by this package. Route answers must bind to B's saved plan_id and input_revision, using the corresponding crew_routes, stop order, unassigned entries, metrics, matrix_provider and stale information. Comparisons require two explicit saved plans. A's static knowledge explains scope/labels/rules but cannot supply current crew assignments, arrival times or total travel minutes.

Without a persisted plan or relevant facts, return insufficient_data and identify missing plans/fields. Do not invent routes from images, task ordering, model answers or fixtures. Illustrative straight lines are not road geometry; simulated matrices are not Google measurements. Display stale plans and failures explicitly without replacing them with fictional new results.

Sources: [context-agents](../../../AGENTS.md), [context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md), [src-project-config](../../config/project.example.json).

<a id="assistant-confirmation"></a>
## Crew adjustments require confirmation

classification: `confirmed_project_fact`. citation_id: `rg-kb-assistant#assistant-confirmation`.

The first assistant change scope is crew availability only: structured preview, then explicit user confirmation, then B's CrewService/planning service checks the previous input revision, executes and recalculates. Cancellation, stale requests and repeated confirmation need explicit outcomes. Neither the assistant nor C directly writes task/crew/plan tables or creates another scheduling algorithm. New tasks use A's inspection/review workflow; natural language cannot freely specify priority, deadlines or service durations. These are future integration policies; current text cannot claim successful crew deactivation, recalculation or confirmation calls.

Sources: [context-agents](../../../AGENTS.md), [context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md), [src-workflow-schema](../roadguard/schemas/workflow.py).

<a id="assistant-rule-versions"></a>
## Rule versions in runtime records

classification: `confirmed_project_fact`. citation_id: `rg-kb-assistant#assistant-rule-versions`.

This package pins demo-rules-v2, but runtime configuration or frozen older inspection snapshots may use demo-rules-v1 or another version. C must first check task/inspection rule_version, then explain using that record's decision_trace, review/task history and matching rule evidence. It must not silently substitute the latest static table to infer the original decision. Explain only with sufficient matching saved evidence; otherwise return insufficient_data and request the corresponding record/version. A version mismatch does not establish a bad record or authorize business-data changes.

Sources: [src-demo-rules](../../config/demo_rules.example.json), [src-workflow-service](../roadguard/inspections/service.py), [src-workflow-schema](../roadguard/schemas/workflow.py).

<a id="assistant-evidence-limits"></a>
## Unsupported conclusions

classification: `confirmed_project_fact`. citation_id: `rg-kb-assistant#assistant-evidence-limits`.

This package contains no real training metrics, actual road permissions, runtime plans, algorithm-comparison results or measured service times. Health does not establish model/Google/GPT readiness; fixed confidence does not prove detection accuracy; demo rules do not prove engineering severity. GA superiority over Greedy requires records using the same tasks, matrix and constraints across multiple random seeds. Do not invent lateness minutes without deadlines or monetary savings without a cost model.

Answers must preserve both support and limitations: static project explanations may be supported, while specific numbers/conclusions requiring missing dynamic evidence must be insufficient_data. Cite relevant stable sections and versions; do not add facts absent from sources.

Sources: [context-agents](../../../AGENTS.md), [context-scope](../../../Miscellaneous/PROJECT_SCOPE.md), [src-label-schema](../../model/label_schema.json), [src-demo-rules](../../config/demo_rules.example.json).
