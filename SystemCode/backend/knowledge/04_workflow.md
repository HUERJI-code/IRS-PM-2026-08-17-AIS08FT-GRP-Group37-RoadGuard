# Inspection, review and task records

document_id: `rg-kb-workflow`; document_version: `9`; owner: `A`.

<a id="workflow-evidence"></a>
## Records and manual review

classification: `confirmed_project_fact`. citation_id: `rg-kb-workflow#workflow-evidence`.

Current HTTP inspection-record contract is `a-workflow-v5`. POST /inspections succeeds with only inspection_id, status, detection and task_id. Detection contains only label, confidence, bbox_xyxy, image_width and image_height; it is null for no detections. GET /inspections/{id} returns full inspection details described below; GET /tasks/{id} returns task details. Obtain detection_id and record_version from inspection details before review. Upload replay returns HTTP 200 and creation returns 201; responses no longer contain replayed/input_revision. Obtain planning revisions from task snapshots. Uploads explicitly choose demo mode/scenario or real mode without a scenario. Images are decoded, EXIF-normalized and stripped of metadata before saving as RGB PNG. Demo detections are synthetic; real inference reads image pixels using an explicitly configured local model verified by hash and eight labels, with Detection.is_demo=false. Business rules remain demo assumptions, so Inspection/Task.is_demo=true. InspectionRecord retains raw detections, mode, model version/weights hash, location, decision process and review_history. TaskRecord retains tasks and mutation history. Clients strictly parsing old records must update schemas; old a-dto-v1 DTOs with extra=forbid cannot directly accept full records.

Real records with primary-suggestion policy also save primary_suggestion: one detection ID for display/review, policy version, threshold, ranking score and competing-object hints. The database retains every raw detection. HTTP InspectionResponse returns at most one box: accepted selected_detection_id first, otherwise the primary suggestion, or the highest-confidence box for older records without a suggestion. Competing IDs may refer to internally retained evidence. Ranking scores are not correctness probabilities and do not control automatic acceptance. Older records have null for this field and are not inferred again; restart, retry and review retain the original upload suggestion.

No detections is saved as no_detection without a task; this does not establish road safety. In demo mode, any low-confidence detection saves pending_review; only when all pass does the demo policy select one candidate and automatically create a task. Real mode uses user-confirmed single-primary-auto-v1: primary raw confidence >= configured confidence_threshold (default 0.60) automatically creates one task and saves accepted; lower confidence yields pending_review. auto_acceptance freezes policy_version and confidence_threshold; Task.history.actor_source=system_confidence_policy and empty review_history indicate no manual review. Ambiguity is advisory and does not override routing. The threshold is not a calibrated correctness probability; older inspections get neither retroactive tasks nor inference. Only pending_review supports new confirm/correct/dismiss actions: confirm selects an existing detection_id, correct also supplies a canonical damage_label, and dismiss selects no detection. Confirmation does not change original confidence to 1.0; correction does not overwrite the original model label; review decisions are retained separately. Since login permissions were integrated on 2026-10-18, new manual reviews and task mutations record actor_source=authenticated_user, with actual account/request/crew information in auth_audit. Older user_declared_unverified records retain their meaning. Authentication is not an engineering accreditation signature.

Sources: [src-workflow-service](../roadguard/inspections/service.py), [src-workflow-schema](../roadguard/schemas/workflow.py), [src-images-code](../roadguard/images.py), [context-workflow-guide](../../../Miscellaneous/INSPECTION_REVIEW_TASK_WORKFLOW.md).

<a id="workflow-task-state"></a>
## Task states and editable fields

classification: `confirmed_project_fact`. citation_id: `rg-kb-workflow#workflow-task-state`.

Only active tasks participate in new planning reads. completed/cancelled tasks retain history without physical deletion or reactivation. Active tasks may be completed/cancelled, have damage_label corrected, or have latitude/longitude/road_type corrected together. The server recalculates severity, priority, minutes and recommendation from the inspection's frozen rules after label correction. Locations are validated again while preserving original inspection locations. Arbitrary priority/service_minutes/due_at, empty changes and explicit null are rejected.

Task creation or actual correction/completion/cancellation changes planning input. Pending review, no detection and dismissal do not change active-task input. B must read active tasks and shared input_revision from one snapshot; pages with different revisions cannot form one planning input. Four-crew allocation, Greedy/GA planning and saved plan queries are implemented in B's PlanningService/RouteQueryService. After an HTTP upload automatically creates a task, or an HTTP confirm/correct review creates one, the backend attempts GA and Greedy recalculation after committing the task. It uses the latest consistent task/crew snapshot and the existing shared matrix/evaluator, retaining confirmed crew constraints. The HTTP response waits for this attempt. The compact upload JSON remains unchanged; X-RoadGuard-Replanning reports completed, failed or not_needed. Completion means both plans were saved, not that every task is assignable. Failure preserves the accepted task and old plans; dispatchers can retry from Four-crew routes. Corrections to existing tasks, completion, cancellation, crew availability and assistant task adjustments still require explicit recalculation. A task record or planning_input_changed alone is not proof of a successful new plan. Saved plans are marked stale after actual input changes. Crew completion is limited to the account's current latest-GA assignment and checked transactionally.

Sources: [src-workflow-service](../roadguard/inspections/service.py), [src-workflow-schema](../roadguard/schemas/workflow.py), [context-workflow-guide](../../../Miscellaneous/INSPECTION_REVIEW_TASK_WORKFLOW.md), [context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md), [src-routing-service](../roadguard/routing/service.py), [src-auth-access](../roadguard/auth/access.py).

Automatic planning sources: [src-automatic-planning](../roadguard/routing/automatic.py), [src-workflow-api](../roadguard/api/workflow.py).

<a id="workflow-versions"></a>
## Versions and safe retries

classification: `confirmed_project_fact`. citation_id: `rg-kb-workflow#workflow-versions`.

record_version is optimistic concurrency for one resource; review/mutation requests include expected_version. input_revision versions shared planning input and increments once in the same database transaction for actual task changes. Idempotency-Key prevents duplicate uploads; request_id prevents duplicate review/mutation on the corresponding resource. Identical requests replay safely; changed content or a stale new operation conflicts. Replay returns current resources/current input revision, not cached old state. Retries and changes without business-value differences neither increment revisions nor duplicate tasks.

planning_input_changed only indicates that this request actually changed shared input; replayed indicates safe replay. Neither means route calculation succeeded. An accepted active-task replay can recover missing/stale plans; both latest plans already at the current revision skip a redundant run. Automatic calls are serialized within one app process and retry revision conflicts at most three attempts with fresh input. There is no durable background queue or startup retry: interruption after task commit can require a safe accepted-request replay or manual recalculation. Pending review, no detection and dismissal trigger no planning. C must handle errors/conflicts by code/status and reread resources; old plans or demo responses cannot be displayed as new real results.

Sources: [src-workflow-service](../roadguard/inspections/service.py), [src-workflow-schema](../roadguard/schemas/workflow.py), [context-workflow-guide](../../../Miscellaneous/INSPECTION_REVIEW_TASK_WORKFLOW.md).

Automatic planning sources: [src-automatic-planning](../roadguard/routing/automatic.py), [src-workflow-api](../roadguard/api/workflow.py).

<a id="workflow-account-roles"></a>
## Account roles and cross-role workflow

classification: `confirmed_project_fact`. citation_id: `rg-kb-workflow#workflow-account-roles`.

Inspectors upload and read only their own inspections. Crew accounts are bound to one crew and can read its latest GA assignment and authorized task images, then complete eligible assigned tasks. Dispatchers review inspections and manage tasks, crews, planning, comparisons and the assistant. Headers and URL parameters cannot expand an account's permissions.

The workflow is inspector upload, automatic or dispatcher acceptance, automatic planning after task creation, crew completion and explicit dispatcher replanning after other input changes or a failed automatic attempt. The latest saved GA plan drives the crew workspace; there is no separate publish-plan step. Interfaces deny access by default, use HttpOnly session cookies and require CSRF for POST/PATCH, including read-only retrieval POSTs. Accounts are local database records, not shared through Git, and have no default password.

Sources: [src-account-roles](../../../Miscellaneous/ACCOUNT_ROLES.md), [src-auth-permissions](../roadguard/auth/dependencies.py).

Automatic planning sources: [src-automatic-planning](../roadguard/routing/automatic.py), [src-workflow-api](../roadguard/api/workflow.py).
