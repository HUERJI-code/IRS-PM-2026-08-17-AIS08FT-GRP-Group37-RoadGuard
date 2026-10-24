# Evidence limits for assistant answers and changes

document_id: `rg-kb-assistant`; document_version: `9`; owner: `A`.

<a id="assistant-plan-facts"></a>
## Dynamic route facts

classification: `confirmed_project_fact`. citation_id: `rg-kb-assistant#assistant-plan-facts`.

B's planning persistence and query services are implemented. C implements ChromaDB/E5 retrieval, optional GPT grounded summaries with separately verified source selections, and confirmed crew-change orchestration. Real GPT connectivity and targeted cases have been exercised; broad semantic reliability remains unverified. The following constraints still govern the integrated service. Route answers must bind to B's saved plan_id and input_revision, using the corresponding crew_routes, stop order, unassigned entries, metrics, matrix_provider and stale information. Comparisons require two explicit saved plans plus evidence from the same recalculation and matching task/matrix/settings checks; time-saving comparisons also need the same assigned task set. A's static knowledge explains scope/labels/rules but cannot supply current crew assignments, arrival times or total travel minutes.

Without a persisted plan or relevant facts, return insufficient_data and identify missing plans/fields. Do not invent routes from images, task ordering, model answers or fixtures. Illustrative straight lines are not road geometry; simulated matrices are not Google measurements. Display stale plans and failures explicitly without replacing them with fictional new results.

Sources: [context-agents](../../docs/PROJECT_BASELINE.md), [context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md), [src-project-config](../../config/project.example.json), [src-routing-service](../roadguard/routing/service.py), [src-plan-comparison](../../frontend/src/planning/comparison.ts), [src-assistant-page](../../frontend/src/pages/AssistantPage.tsx).

Implementation sources: [src-assistant-query](../roadguard/assistant/query_service.py).

<a id="assistant-confirmation"></a>
## Crew adjustments require confirmation

classification: `confirmed_project_fact`. citation_id: `rg-kb-assistant#assistant-confirmation`.

The implemented dispatcher changes are crew availability, moving an assigned active task to another available crew, and cancelling an active assigned or unassigned task. Each uses a structured preview tied to a saved plan and input revision, then explicit confirmation. Discarding a preview makes no business change; confirming a cancel_task action instead cancels the task and retains its history. Task movement checks travel plus service plus required depot-return time against the configured shift, retaining every other assigned task. Infeasible changes are rejected.

Confirmed movement stores a persistent task-to-crew constraint. Greedy and GA respect it on later recalculation, including after new tasks arrive. If that crew is unavailable or the route cannot fit, the task is explicitly unassigned instead of silently moved elsewhere. Confirmation validates current input, task and configuration versions in one transaction. Cancellation reuses A's task service; availability reuses B's crew service. Recalculation is a separate explicit action and can fail without undoing a confirmed change. New tasks still use inspection/review; arbitrary priority, duration, deadline and account edits are outside this interface. Static answers never execute changes or establish that a particular receipt succeeded.

Sources: [context-agents](../../docs/PROJECT_BASELINE.md), [context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md), [src-workflow-schema](../roadguard/schemas/workflow.py), [src-crew-schema](../roadguard/crews/schemas.py), [src-crew-service](../roadguard/crews/service.py), [src-routing-service](../roadguard/routing/service.py).

Implementation sources: [src-assistant-change](../roadguard/assistant/change_service.py).

Task sources: [src-task-change-service](../roadguard/assistant/task_change_service.py), [src-task-change-models](../roadguard/assistant/task_change_models.py), [src-workflow-service](../roadguard/inspections/service.py), [src-routing-evaluation](../roadguard/routing/evaluation.py).

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

Standalone questions identifying the assistant model read the server's configured model name directly, without retrieval or a provider call. This identifies configuration, not a verified provider execution or the YOLO detector. Clearly unrelated questions receive friendly scope guidance with examples. These server responses have no fabricated citations or knowledge-package hash. Mixed or ambiguous project questions continue through the evidence path; malformed provider evidence is still rejected. Routing uses bounded English and Chinese phrase matching, not unrestricted intent understanding.

Sources: [context-agents](../../docs/PROJECT_BASELINE.md), [context-scope](../../../Miscellaneous/PROJECT_SCOPE.md), [src-label-schema](../../model/label_schema.json), [src-demo-rules](../../config/demo_rules.example.json), [src-vision-evaluation](../../experiments/vision/single_damage_summary.json), [src-routing-results](../../experiments/routing/results/README.md), [src-ga-evaluation](../../experiments/routing/results/ga-evaluation-v1/summary.json).

Implementation sources: [src-assistant-query](../roadguard/assistant/query_service.py), [src-assistant-intents](../roadguard/assistant/intents.py).
