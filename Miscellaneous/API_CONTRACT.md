# A shared data and demo API contract

Version: `a-dto-v1`; date: 2026-10-12; maintainer: A. This is the sole maintenance point for implemented A shared DTO contracts. Allocation sections 6/7 retain responsibilities/future designs and link here for implemented fields. B/C owners propose their later objects; this file does not freeze them implicitly. Executable [schemas](../SystemCode/backend/roadguard/schemas/), fixed [contracts](../SystemCode/contracts/README.md). Changes update DTOs, examples, necessary tests and caller-impact notes together.

The initial freeze covers representation/minimum consistency, not all M0. Single-box/0.60 routing was confirmed later; on 2026-10-14 course rules `demo-rules-v2` fixed P3/P2/P1=60/120/240 minutes; see [baseline](BUSINESS_RULES_BASELINE.md). Deadlines, shifts/return and optimization constraints remain pending, not engineering standards. Historical fixtures retain original versions and do not replace runtime configuration. Imports: `from roadguard.schemas import Detection, Inspection, Task, ErrorResponse, HealthResponse, PlanningRevision`, plus structured DecisionTrace.

Step 5 adds `a-demo-v1`, preserving DTO fields and adding RuleCandidate/RuleAssessment and `/demo`. [Demo mappings](DEMO_DETECTION_AND_RULES.md) do not establish approval of formal thresholds/durations/priorities.

Step 6 adds `a-workflow-v1` upload/inspection/review/task interfaces and new request/record models; [workflow/examples](INSPECTION_REVIEW_TASK_WORKFLOW.md). Original DTO fixtures remain compatible. Live business records are explicitly demo; caller road declarations are not eligibility verification.

Step 7 adds `a-task-query-v1`, consistent active snapshots for B/C; [handoff](BC_HANDOFF.md) includes inputs/knowledge/HTTP examples. Task/TaskRecord fields unchanged; B's complete PlanningInput is not frozen.

Step 8 extends inspections to `a-workflow-v2`: explicit local mode=real, weight hash/manifest version, null demo_scenario_id for real. Old demo data loads, but strict legacy clients update schemas. Real Detection is_demo=false; business rules/Inspection/Task/snapshot remain true. Current v5 auto-creates one task at confirmed raw-primary 0.60, below review; no calibrated-accuracy claim. [Real API](REAL_VISION_API.md) covers requests/config/errors; a-dto-v1/a-task-query-v1 fields unchanged.

## General representation

- snake_case JSON; nonempty string IDs/versions trimmed; whitespace-only invalid. Reject unknown fields to catch typos.
- JSON numbers only, never strings/booleans; class IDs/dimensions/revisions reject fractions; finite floats. is_demo requires explicit boolean.
- WGS84 latitude [-90,90], longitude [-180,180]. DTO validates numbers; Step 6 additionally covers frozen JE/JW polygons and checks declarations, without assuming every interior point is a road.
- Timestamps require ISO 8601 strings/aware Python datetime; reject naive times/Unix numbers; normalize UTC. Frontend Asia/Singapore; durations minutes.
- Nullable business fields below remain required, with null unknown. ErrorResponse.details may omit/default null; HealthResponse.api_version defaults v1. [], null and zero differ.
- Validate on construction/parsing. DTOs are snapshots, not mutable business entities. Direct assignments/list mutations/unvalidated model_copy(update=...) need not preserve invariants; producers revalidate changed dictionaries with model_validate or model_validate_json. Services own state changes.

## Frozen objects

| Object | Fields/constraints |
| --- | --- |
| Detection | detection_id; integer class_id 0–7; central label_key matching ID; confidence [0,1]; four original-pixel bbox_xyxy [left,top,right,bottom]; positive integer image_width/image_height; model_version; is_demo |
| Inspection | inspection_id; nonempty image_url (relative allowed, existence not guaranteed); nullable annotated_image_url; coordinates; Detection list detections; nullable selected_detection_id; status; nullable task_id; DecisionTrace list decision_trace; is_demo |
| DecisionTrace | Nonempty stable code/message; nullable rule_version before rule execution; is_demo. Ordered decision steps, [] if none. code not yet a business enum; message alone cannot determine status |
| Task | task_id; inspection_id; coordinates; central damage_label; severity low/medium/high; priority P1/P2/P3; positive service_minutes or null; created_at; nullable due_at; status active/completed/cancelled; rule_version; is_demo |
| PlanningRevision | Nonnegative integer input_revision; shared DB/services own task/crew change semantics; DTO never increments |
| HealthResponse | status/database ok; api_version v1; nonnegative input_revision. App/DB check only, not model/Google/GPT readiness |
| ErrorResponse | Nonempty code/message; nullable JSON object/array details with finite JSON/string keys. Only sanitized counts/field IDs/metadata, no passwords/credentials/raw input/stacks/SQL/internal paths/exception strings. DTO cannot detect secrets in prose |

Sole labels: [label_schema.json](../SystemCode/model/label_schema.json), loaded relative to Python source and validated as exactly eight distinct IDs 0–7. Retain in deployments; no duplicate class table. Boxes require 0≤left<right≤image_width, 0≤top<bottom≤image_height, including right/bottom image edges. Not normalized YOLO xywh.

low/medium/high are DTO vocabulary, not engineering severity derived from wide/sunken/deep. Task has no arbitrary-priority request or label→priority/service_minutes/due_at implementation. Unknown duration null, not zero. DTOs do not alter queues/create tasks from status.

Inspection IDs unique; selected ID, if present, belongs to its detections. no_detection has no detections/selection/task; all other statuses have detections. pending_review/rejected have no task and may omit selection; accepted requires both. Demo detections/traces require inspection is_demo=true, retaining step provenance. DTO checks within a snapshot; Step 6 services/DB enforce cross-object links, deduplication, transitions and transactions.

## Route implementation and errors

Current implementation: GET /api/v1/health, stateless demo below, a-workflow-v5 uploads/query/images/review and task queries/patches. Crew/planning/assistant remain for B/C. OpenAPI shows registered routes only, never fixtures as live success.

### a-demo-v1: detection/rule previews

Shared types import from roadguard.schemas, defined in [assessment.py](../SystemCode/backend/roadguard/schemas/assessment.py); HTTP wrappers in [demo.py](../SystemCode/backend/roadguard/api/demo.py).

| Object | Fields/constraints |
| --- | --- |
| RuleCandidate | detection_id, central damage_label, severity low/medium/high, priority P1/P2/P3, positive/null service_minutes, nonempty repair_recommendation/rule_version, is_demo:true. No task_id/location/time; not Task |
| RuleAssessment | status no_detection/pending_review/ready_for_task, detections, nullable selected_detection_id/candidate, nonempty decision_trace, rule_version, is_demo:true |
| DemoAssessmentRequest | Only nonempty scenario_id ≤64 chars; no extra fields/images/threshold overrides/business settings |
| DemoAssessmentResponse | is_demo:true, scenario_id, model_version, dimensions, actual confidence_threshold, nested assessment |
| DemoScenarioCatalogue | is_demo:true, model_version, dimensions, scenarios with scenario_id/description |

RuleAssessment IDs unique, image dimensions consistent; no_detection empty, others nonempty. Only ready_for_task has a candidate linked to selected detection/label/rule version; other candidate/selection null. All traces explicitly demo and same version. Real detections evaluated under demo rules retain real source while assessment/candidate remain demo.

GET /api/v1/demo/scenarios returns catalogue; POST /api/v1/demo/assessments takes request, returns 200 response, e.g. {"scenario_id":"high_confidence"}. No persistence/revision increments/queue records, including retries. Candidates have no deadlines/lateness. Step 6 creates tasks with geography/review/storage/idempotency checks.

### a-workflow-v5: persisted business interfaces, original requests retained

[schemas/workflow.py](../SystemCode/backend/roadguard/schemas/workflow.py), [api/workflow.py](../SystemCode/backend/roadguard/api/workflow.py); [Step 6](INSPECTION_REVIEW_TASK_WORKFLOW.md) and schemas define fields/operations.

| Type | Additions over base DTO |
| --- | --- |
| UploadMetadata | Required mode=real/demo, strict coordinates, road_type=public_motor_road; scenario_id required for demo, forbidden for real; JSON inside multipart metadata string |
| InspectionResponse (HTTP)/InspectionRecord (internal) | Adds created_at/updated_at/record_version/mode/demo_scenario_id/model_version/dimensions/scope_version/road_type/road_type_source/review_history; requires is_demo=true |
| TaskRecord | Adds updated_at/record_version/repair_recommendation/history; is_demo=true |
| ReviewRequest | request_id/expected_version/action; confirm/correct select detection_id, correct also damage_label; dismiss forbids both; optional note |
| TaskPatch | request_id/expected_version and at least one change; completed/cancelled, damage_label, or full location/road; no direct priority/duration/deadline |
| InspectionUploadResponse | Only inspection_id/status/nullable detection/nullable task_id; detection only label/confidence/bbox_xyxy/dimensions |
| InspectionMutationResponse | inspection/nullable task/input_revision/planning_input_changed/replayed |
| TaskMutation | task/input_revision/planning_input_changed/replayed |
| InspectionListResponse / TaskList | items/total/limit/offset; TaskList adds same-snapshot input_revision |

Base extra=forbid rejects record additions. HTTP clients use InspectionResponse, internal InspectionRecord retains all boxes; task clients use TaskRecord. Raw labels/confidence remain; review_history/Task.history express correction. Original review identities are unverified, not credentials. Only transactional task creation updates planning revision; /demo never writes.

2026-10-13 a-workflow-v3 added nullable primary_suggestion, defined in [primary.py](../SystemCode/backend/roadguard/schemas/primary.py): policy_version/strategy/threshold/nullable detection_id/nullable ranking_score/ambiguous/competing_detection_ids. v3 initially display/review only; v4 routes by raw primary confidence. DB retains raw detections, HTTP at most one box. Missing legacy field loads null; strict v2 clients accept new fields. See [release guide](MODEL_RELEASE_AND_BACKEND.md) for defaults/install/examples/caller impacts. SQLite v2/snapshot unchanged. v4 adds nullable auto_acceptance(policy_version/confidence_threshold) and TaskHistory.actor_source system_confidence_policy; old records not rerouted. v5 reduces uploads to four fields; GET details separately. Review/task responses unchanged; replay 200/new 201. [Field reference](INSPECTION_RESPONSE_FIELDS.md).

### a-task-query-v1: consistent active snapshots

GET /api/v1/tasks/snapshot → TaskSnapshot; optional nonnegative expected_revision, mismatch 409 stale_input_revision. Register before /tasks/{task_id}.

[task_query.py](../SystemCode/backend/roadguard/schemas/task_query.py), import `from roadguard.schemas import TaskSnapshot`. contract_version a-task-query-v1; source persisted_workflow/synthetic_fixture; nonnegative input_revision; exact original Task fields; total=list length; is_demo=true. All active/demo with unique task_id/inspection_id. Real detection acceptance/review may create demo-business tasks, not production rules.

Live persisted_workflow reads all, validates storage then projects active; created_at/task_id order without pagination/truncation. Corrupt tasks fail entire query 503, never partial success. Empty 200 valid. No writes/revision change; unknown duration/deadline null.

`from roadguard.tasks import TaskQueryService`, snapshot(expected_revision=None, *, connection=None). Default manages read transaction; caller connection must already transact on same DB, caller owns commit/rollback/close. Same snapshot tasks/revision. B reads crews on same connection and rechecks revision when saving. Separate HTTP crew queries have no matching-revision guarantee.

synthetic_fixture revisions are offline contexts, not current DB. Knowledge has separate versions; explanations match saved rule_version.

### b-crew-v1 / b-recalculation-v1 / b-route-plan-v1-draft: crews/plans (B)

Implemented by B on 2026-10-14; structures in [routing guide](../SystemCode/backend/roadguard/routing/README.md). Default matrix explicitly simulated; B-5 on 2026-10-15 adds optional Google Routes, configuration-selected/off by default. matrix_provider/matrix_is_simulated distinguish sources. 480-minute shifts, return and weights remain B's demo assumptions pending A confirmation.

| Endpoint | Request | Success | Main errors |
| --- | --- | --- | --- |
| GET /crews | None | CrewList with all configured/unavailable crews, input_revision | 503 |
| PATCH /crews/{crew_id} | request_id/expected_version/available | CrewMutation crew/revision/changed/replayed | 404,409 stale_record_version/idempotency_conflict,422 |
| POST /route-plans/recalculate | Required expected_revision, optional planning_start_at | Both same-input/matrix plan IDs/summaries, matrix_provider/matrix_is_simulated/matrix_generated_at (B-5 additive fields) | 409 stale_input_revision,422,503 database_unavailable/travel_matrix_unavailable |
| GET /route-plans/latest?algorithm=ga\|greedy | Algorithm | RoutePlan; is_stale computed at read | 404 route_plan_not_found |
| GET /route-plans/{plan_id} | plan- plus 32 hex digits | Saved plan, including historical | 404 route_plan_not_found,422 |

- Actual availability changes increment shared revision in same transaction; replay never repeats. Crew updates do not auto-recalculate: caller invokes recalculate with returned revision.
- Changes during computation prevent saving either plan, returning 409. Saving does not increment input revision.
- Online GA starts from Greedy (planning_service.seed_with_greedy=true, recorded in algorithm_parameters.seed_with_greedy) and is no worse under lexicographic unassigned P1/P2/P3 counts then objective. No field changes.
- Google failures (missing key, HTTP/network, incomplete response/element errors) return 503 travel_matrix_unavailable with provider/reason and optional http_status; neither plan saved, **no simulated fallback**. Google no-route pairs are null/unreachable, never zero.
- No plan is 404, not valid empty plan. All crews returned, unavailable or idle as appropriate; unassigned reasons retained. geometry=null permits only labeled schematic lines.

### Shared errors

Executable [errors.py](../SystemCode/backend/roadguard/errors.py)/[health.py](../SystemCode/backend/roadguard/api/health.py); use code, not message matching. Update table with implementation:

| code | HTTP | Meaning |
| --- | --- | --- |
| validation_error | 422 | FastAPI validation; details error_count only, no raw input |
| not_found | 404 | Path/inspection/task absent |
| method_not_allowed | 405 | Method unsupported; Allow retained |
| stale_input_revision | 409 | Shared DB/snapshot/planning rejects stale; expected_revision/current_revision details |
| database_unavailable | 503 | DB unavailable/invalid state/unparseable persisted data |
| internal_error | 500 | Safe unhandled-error text, no raw exception |
| http_error | Corresponding status | Safe generic other HTTPException |
| demo_scenario_not_found | 404 | Unknown case without echo |
| demo_unavailable | 503 | Service unavailable, no success fixture fallback |
| invalid_detections | 422 | Internal rule input invalid; demo HTTP cannot submit detections |
| outside_service_area | 422 | Outside frozen JE/JW; no task exception for NUS-ISS |
| unsupported_road_type | 422 | Non-public motor declaration; HTTP may first give validation_error |
| service_area_unavailable | 503 | Frozen geometry unreadable/invalid; startup fails |
| unsupported_upload_type | 415 | Required multipart not used |
| unsupported_image_type | 415 | Recognized format not JPEG/PNG |
| invalid_image | 422 | Empty/corrupt/animated/undecodable |
| image_too_large | 413 | Bytes/body/pixels exceed limit |
| image_not_found | 404 | File absent |
| image_storage_unavailable | 503 | Read/write failure/unsafe path |
| image_already_exists | 409 | Generated target exists; no overwrite |
| idempotency_conflict | 409 | Same key/different content |
| stale_record_version | 409 | Inspection/task revision changed |
| invalid_state | 409 | Closed inspection/terminal task |
| invalid_detection_selection | 422 | Detection not in inspection |
| workflow_unavailable | 503 | Workflow not ready |
| task_query_unavailable | 503 | Snapshot unavailable, not empty success |
| route_plan_not_found | 404 | ID absent/no saved algorithm plan, not valid empty |
| travel_matrix_unavailable | 503 | Configured Google matrix unusable; provider/reason missing_api_key/too_many_nodes/http_error/timeout/network_error/invalid_response/element_error, optional http_status; no save/fallback |

Error fixture uses validation_error/422; its details.is_demo is fixture metadata, not required in real errors. Services explicitly raise/document later errors; fixtures do not establish implemented logic.

## Caller effects and acceptance

B honors null duration/deadline/is_demo rather than guessing from label; PlanningRevision represents shared input. C displays status/selection/trace/provenance without inferring severity/threshold. Use marked contracts/examples directly for frontend mocks, never as real success during failure.

SystemCode/tests/test_contracts.py verifies DTO fixtures. Step 6 test_workflow/test_workflow_api/test_geography/test_images cover persistence/HTTP/geography/uploads/regression. Training/real detection/routes/full end-to-end acceptance remain incomplete in this historical baseline.

## Account-permission increment (2026-10-18)

HTTP examples now require login/X-CSRF-Token on writes. Inspectors upload/read own; dispatchers review/manage; crews read/complete own tasks. Four fields, single box and 0.60 unchanged. [Account roles](ACCOUNT_ROLES.md) covers matrix/sessions/Swagger.

## Assistant retrieval, evidence answers and crew changes (2026-10-21)

The dispatcher-only assistant uses the existing session, role and CSRF checks:

- `POST /api/v1/assistant/knowledge/search` returns versioned static passages, stable citations and source integrity metadata; it does not generate answers or read business plans. Rule-version mismatch returns empty hits; inconsistent knowledge returns `503 knowledge_unavailable`.
- `GET /api/v1/assistant/status` exposes non-secret configuration status. `POST /api/v1/assistant/query` accepts question, scope and optional plan_id/rule_version. Plan questions require an explicit saved plan loaded through B's query service. `c-assistant-query-v1` returns verified evidence extracts and provenance without business changes. Real GPT connectivity and semantic quality remain unverified.
- `/api/v1/assistant/change-requests` provides preview/history and per-request confirm/cancel/replan operations under `c-assistant-change-v1`. Preview does not change planning input. Confirmation and recalculation are separate explicit actions; history supports uncertain-outcome recovery. This flow does not call GPT.

Schema v5 adds persistent assistant change requests and audit records while retaining v4 accounts, sessions, ownership, crews and plans. No new dependency or model weight is required. The assistant guide defines limits, concurrency, idempotency, failure handling and server-only provider configuration.

See [assistant contracts](../SystemCode/backend/roadguard/assistant/README.md).
