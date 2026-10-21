# Saved plans, route explanations and comparisons

document_id: `rg-kb-plans`; document_version: `2`; owner: `A`.

<a id="plans-provenance"></a>
## Where dynamic answers obtain evidence

classification: `confirmed_project_fact`. citation_id: `rg-kb-plans#plans-provenance`.

Dispatcher APIs under `/api/v1` include POST /route-plans/recalculate, GET /route-plans/latest?algorithm=ga (or greedy), and GET /route-plans/{plan_id}. Recalculation requires expected_revision; planning_start_at is optional. It computes both algorithms on one input and one matrix, checks the revision again, and saves both plans together. A revision change during computation returns 409 stale_input_revision and saves neither.

Use the requested plan's plan_id, input_revision, algorithm, planning_start_at, crew_routes/stops, unassigned_tasks, metrics, matrix_provider, matrix_is_simulated, settings, random_seed, algorithm_parameters and is_stale. task_source distinguishes persisted_workflow from synthetic_fixture. A valid saved plan with zero tasks differs from a 404 route_plan_not_found. Static knowledge and synthetic fixtures cannot establish today's plan.

Routes expose shift_remaining_minutes (null for an unlimited shift); stops may expose damage_label and locked_crew_id. Older snapshots can lack optional stop metadata. Current nonstale plans can be enriched from matching active task/constraint records on read; historical stale plans must not inherit today's labels or locks. Display the selected plan ID and separate travel, service, return and total work rather than guessing capacity in the browser.

The recalculation response records matrix_generated_at, including the original fetch time for a cached Google matrix. This field is not currently in the saved RoutePlan model; retain the response as evidence if an answer needs matrix age or same-run provenance. Do not invent a persisted matrix ID/hash or timestamp.

Sources: [src-routing-api](../roadguard/routing/api.py), [src-routing-service](../roadguard/routing/service.py), [src-routing-models](../roadguard/routing/models.py), [src-auth-permissions](../roadguard/auth/dependencies.py).

<a id="plans-stale"></a>
## Input revisions, stale plans and completion

classification: `confirmed_project_fact`. citation_id: `rg-kb-plans#plans-stale`.

Actual task or crew-availability changes increment the shared input_revision. On read, a saved plan with another revision is marked is_stale=true. Such changes do not automatically recalculate. A new plan is available only after explicit successful recalculation; a mutation response's planning_input_changed is not a planning-success receipt. Saved historical plans remain accessible by ID.

The crew workspace uses the latest saved GA plan, without a separate publication step. It exposes only the signed-in crew's route. Completion checks current account, latest-GA assignment, crew availability and task revision/status in the write transaction. A stale plan flag alone does not prohibit completion of a still-valid assigned task. Reassignment can invalidate actions from an old page; refresh after conflicts. A committed completion may safely replay through its completion receipt after recalculation.

Sources: [src-routing-service](../roadguard/routing/service.py), [src-crew-service](../roadguard/crews/service.py), [src-auth-access](../roadguard/auth/access.py), [src-account-guide](../../../Miscellaneous/ACCOUNT_ROLES.md).

<a id="plans-unassigned"></a>
## Explain recorded unassigned reasons

classification: `confirmed_project_fact`. citation_id: `rg-kb-plans#plans-unassigned`.

Use the specific plan entry's reason, not a guessed explanation from task priority:

| Reason | Meaning within this planner |
| --- | --- |
| unknown_service_minutes | Required task duration is unknown; it cannot be assumed zero. |
| unreachable_from_depot | No usable depot-to-task matrix leg. |
| unreachable_to_depot | A required task-to-depot return is unreachable. |
| no_available_crew | No configured crew is currently available for planning. |
| exceeds_shift_limit | The task or attempted route cannot fit the configured shift including required return. |
| no_feasible_route_position | The evaluated placement cannot satisfy travel/route constraints. |
| assigned_crew_unavailable | A confirmed task-to-crew constraint points to an unavailable crew. |
| assigned_crew_infeasible | The task cannot fit a feasible route on its locked crew under this input. |

An unassigned reason describes this input and evaluated plan. It is not a mathematical proof that every possible permutation is infeasible. Do not claim a task was cancelled or completed merely because it is unassigned. Unknown or unreachable travel is not zero; changing a demo duration to force assignment is not authorized.

Sources: [src-routing-evaluation](../roadguard/routing/evaluation.py), [src-routing-models](../roadguard/routing/models.py).

<a id="plans-comparison"></a>
## When GA and Greedy percentages are meaningful

classification: `confirmed_project_fact`. citation_id: `rg-kb-plans#plans-comparison`.

The frontend requires both complete plans and evidence from the same recalculation response. Matching algorithm labels or two latest-plan responses alone does not establish that the matrix was shared. Check plan IDs, input revision, start time, settings, depot, crews/availability, task set, task source, matrix provider/simulation flag and counts against that response. Duplicate tasks or inconsistent totals invalidate comparison.

Check the assigned task IDs as well as assigned counts. Comparisons of time metrics for equivalent work require the same assigned set. If coverage differs, report unassigned P1/P2/P3 and explain the difference before interpreting the objective; do not advertise a time saving caused by omitting work. Historical before/after plans with changed inputs can describe an operational change but cannot isolate the algorithm's effect.

For a comparable nonzero Greedy baseline, the frontend displays signed change `(GA - Greedy) / Greedy * 100`; negative means a reduction. If phrased as improvement, explicitly use `(Greedy - GA) / Greedy * 100` for a lower-is-better metric. Null values or a zero baseline have no percentage. Label the metric and units: durations/objective in minutes, algorithm_runtime_ms in milliseconds. Algorithm runtime is not travel time or end-to-end API latency.

Sources: [src-plan-comparison](../../frontend/src/planning/comparison.ts), [src-routing-models](../roadguard/routing/models.py), [src-routing-service](../roadguard/routing/service.py), [src-routing-evaluation](../roadguard/routing/evaluation.py).
