> Archive: retains the 2026-10-15 planning baseline/open work. Steps 1–9 are now implemented; README, VALIDATION.md and COMPARISON_GUIDE.md define actual validation. Steps 10–14 remain pending.

# RoadGuard · C step 1: API and field mapping

Baseline: main `f8a2cf37de91c09d86ec14e6cbd6045e83e421f8`, 2026-10-15. A/B entries were checked against code; C entries were unfrozen proposals, not callable APIs. All backend paths use `/api/v1`; P1–P6 refer to PAGE_FLOW.md.

## 1. Seventeen implemented endpoints

| ID/owner | Method/path (prefix omitted) | Page purpose | Request | Success/notes |
|---|---|---|---|---|
| H01 A | GET /health | Shared connection | None | status, database, api_version, input_revision; not model/external readiness |
| A01 A | GET /demo/scenarios | P1 scenarios | None | is_demo, model_version, image_width/height, scenarios[scenario_id,description] |
| A02 A | POST /inspections | P1 upload | multipart image + metadata JSON string; Idempotency-Key | New 201/replay 200; inspection_id,status,detection,task_id only |
| A03 A | GET /inspections | P2 queue/P1 history | status=all default; limit=50 default (1–100); offset=0 | items:InspectionResponse[],total,limit,offset; no input_revision |
| A04 A | GET /inspections/{inspection_id} | P1/P2 details/P3 rules | 32 lowercase hexadecimal ID | InspectionResponse including detection_id/record_version for review |
| A05 A | GET /inspections/{inspection_id}/image | P1/P2 image | Inspection ID | image/png, no-store; normalised orientation/dimensions |
| A06 A | POST /inspections/{inspection_id}/review | P2 review | ReviewRequest below | inspection,nullable task,input_revision,planning_input_changed,replayed |
| A07 A | GET /tasks | P3 list | status active default; active/completed/cancelled/all; same pagination | items:TaskRecord[],total,limit,offset,input_revision |
| A08 A | GET /tasks/snapshot | Consistent full active input | Optional expected_revision ≥0 | contract_version=a-task-query-v1,source=persisted_workflow,tasks:Task[],total,input_revision,is_demo; not TaskRecord[] |
| A09 A | GET /tasks/{task_id} | P1 linked task/P3 detail | 32 lowercase hexadecimal ID | TaskRecord |
| A10 A | PATCH /tasks/{task_id} | P3 edit/complete/cancel | TaskPatch below | task,input_revision,planning_input_changed,replayed |
| A11 A | POST /demo/assessments | Optional stateless development preview | scenario_id | is_demo,scenario_id,model_version,image_width/height,confidence_threshold,assessment; no saved inspection/task |
| B01 B | GET /crews | P4 crew control | None | contract_version=b-crew-v1,crews:CrewRecord[],input_revision |
| B02 B | PATCH /crews/{crew_id} | P4/future assistant internal service | request_id,expected_version ≥1,available:boolean | b-crew-v1,crew,input_revision,planning_input_changed,replayed; no automatic recalculation |
| B03 B | POST /route-plans/recalculate | P4 planning/P5 pairing | expected_revision ≥0; optional timezone-aware planning_start_at | Synchronous 200 RecalculationResult; no job/polling/request_id |
| B04 B | GET /route-plans/latest | P4 latest | Required algorithm=ga/greedy | RoutePlan; missing 404 route_plan_not_found |
| B05 B | GET /route-plans/{plan_id} | P4/P5/P6 specified plan | plan- plus 32 lowercase hexadecimal characters | RoutePlan; old plans readable, is_stale uses current revision |

## 2. Writes and revisions

| DTO | Fields | Constraints |
|---|---|---|
| UploadMetadata | mode,latitude,longitude,road_type; demo also scenario_id | real/demo; public_motor_road only; real omits scenario_id |
| ReviewRequest | request_id,expected_version,action; optional detection_id,damage_label,note | confirm/correct require detection_id; correct requires damage_label, confirm forbids it; dismiss forbids both; note ≤500 |
| TaskPatch | request_id,expected_version; status,damage_label or complete location | At least one non-null edit; status completed/cancelled; latitude/longitude/road_type together; no free priority/duration/deadline |
| CrewPatch | request_id,expected_version,available | Availability only; no-op does not increment input revision |
| RecalculateRequest | expected_revision; optional planning_start_at | Revision checked during read/save; change causes 409 without saving either plan |

request_id/Idempotency-Key allow 1–64 ASCII letters/digits/underscore/hyphen. They identify logical operations, not authentication. expected_version is record-specific; expected_revision is global planning input. Numbers/booleans remain typed, JSON snake_case, IDs strings; do not add invented fields. Supported writes reuse original key/payload after uncertain outcomes; content changes/conflict resolution create new actions/keys. Replay may return current resource state and does not imply a new write. planning_input_changed explicitly identifies a change. B03 has no idempotency guarantee; duplicates can generate plans/reuse external services.

## 3. UI fields and sources

| UI field/purpose | Source | Display/limitations |
|---|---|---|
| Inspection status/task | A02/A04.status/task_id | accepted/pending_review/no_detection/rejected; nullable task |
| Upload box | A02.detection.label/confidence/bbox_xyxy/image_width/image_height | Nullable; no detection_id, so not enough to review directly |
| Review ID/version | A04.detections[].detection_id,record_version | At most one box; other primary_suggestion IDs are not selectable boxes |
| Image | A04.image_url/A05 | annotated_image_url nullable; do not assume annotated image |
| Inference/business provenance | A04.mode/model_version/model_weights_sha256/model_manifest_version/is_demo | Separate mode/business flags; confidence is not accuracy |
| Auto-acceptance/review | A04.auto_acceptance/review_history/selected_detection_id | Current real primary threshold can create a task; follow backend status rather than frontend routing |
| Label/severity/priority | A09.damage_label/severity/priority | Backend rules only |
| Duration/deadline | A09.service_minutes/due_at | Null differs from zero; minutes; absent deadline is not lateness |
| Recommendation/history | A09.repair_recommendation/history/created_at/updated_at | Task.history is not the complete detection decision chain |
| Rule chain/version | A04.decision_trace/A09.rule_version | Explain frozen history, never overwrite using latest rules |
| Crew name/status | B01.crews[].crew_id/name/available/depot_id/record_version/updated_at | Initial updated_at nullable; no depot coordinates/shift in CrewRecord |
| Depot coordinates | B05.depot.depot_id/latitude/longitude | Without plan, use versioned static geography, not an invented API |
| Route status | B05.crew_routes[].available/status | assigned/idle/unavailable; separate from current B01 availability |
| Stop order/location | B05.crew_routes[].stops[].sequence/task_id/latitude/longitude/priority | Follow saved order/coordinates, not current-task replacements |
| Arrival/completion | stops[].arrival_minute/completion_minute + planning_start_at | UTC start plus minutes; Asia/Singapore display |
| Travel/work | stops[].travel_minutes_from_previous/service_minutes; crew_routes[].travel_minutes/return_travel_minutes/service_minutes/total_work_minutes/end_minute | Nullable return; avoid double-counting it |
| Geometry | crew_routes[].geometry/geometry_note | Currently null; schematic only |
| Unassigned | B05.unassigned_tasks[].task_id/reason | Preserve every task/reason |
| Constraints/source | B05.settings/task_source/matrix_provider/matrix_is_simulated/is_demo | Separate demo durations/simulated travel; no approved-policy claims |
| Plan/freshness | B05.plan_id/input_revision/algorithm/is_stale | Can change after read; writes still require backend checks |
| Same-run/matrix time | B03.plans[]/matrix_generated_at | B05 lacks matrix_generated_at/batch_id; retain response context |
| Comparison metrics | B05.metrics | Saved values, not model-generated numbers |
| Boundaries/labels | Miscellaneous/geography, SystemCode/model/label_schema.json | No existing HTTP config API; D03 delivery open at planning |

TaskRecord extends Task’s task_id,inspection_id,latitude,longitude,damage_label,severity,priority,service_minutes,created_at,due_at,status,rule_version,is_demo with updated_at,record_version,repair_recommendation,history.

RecalculationResult contains contract_version=b-recalculation-v1,status=completed,input_revision,planning_start_at,task_count,matrix_provider,matrix_is_simulated,matrix_generated_at,plans. Each plan summary has algorithm,plan_id,assigned_task_count,unassigned_task_count,objective_value, without complete stops; read B05.

| Metric | Meaning/unit |
|---|---|
| assigned_task_count/unassigned_task_count/unassigned_by_priority | Assigned/unassigned counts, P1/P2/P3 groups |
| total_travel_minutes/total_service_minutes | Total travel/repair minutes |
| makespan_minutes | Overall finish offset in minutes |
| workload_std_minutes | Workload standard deviation in minutes, nullable |
| priority_weighted_completion_minutes | Weighted completion minutes, nullable |
| tasks_with_due_at/total_lateness_minutes/late_task_count | Deadline count/lateness minutes/late-task count; latter two nullable |
| objective_value | Interpret with settings.objective_version/weights |
| algorithm_runtime_ms | Algorithm milliseconds, not end-to-end wait |

| Unassigned reason | UI meaning |
|---|---|
| unknown_service_minutes | Unknown repair duration |
| unreachable_from_depot | Unreachable from depot |
| unreachable_to_depot | Cannot return under current policy |
| no_available_crew | No available crew |
| exceeds_shift_limit | Exceeds shift limit |
| no_feasible_route_position | No feasible insertion position |

## 4. Normal, empty and failure examples

Illustrative examples only, not live responses/full mocks; IDs cannot be queried. Complete schema-based mocks were planned for step 3.

Pending upload, four fields:

```json
{"inspection_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","status":"pending_review","detection":{"label":"pothole","confidence":0.55,"bbox_xyxy":[10,20,100,120],"image_width":640,"image_height":480},"task_id":null}
```

No detection:

```json
{"inspection_id":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","status":"no_detection","detection":null,"task_id":null}
```

Empty tasks (illustrative revision):

```json
{"items":[],"total":0,"limit":50,"offset":0,"input_revision":0}
```

Review confirmation (replace detection_id from details):

```json
{"request_id":"review_demo_001","expected_version":1,"action":"confirm","detection_id":"from_inspection_detail"}
```

Crew save/recalculation are separate requests, with illustrative revisions:

```json
{"request_id":"crew_demo_001","expected_version":1,"available":false}
```

```json
{"expected_revision":8,"planning_start_at":"2026-10-15T01:00:00Z"}
```

Error shape (message illustrative; decisions use code):

```json
{"code":"stale_input_revision","message":"Planning inputs changed.","details":{}}
```

| Area | Normal | Empty/not applicable | Failure |
|---|---|---|---|
| Upload | accepted→task; pending_review→review | no_detection/null | detector_unavailable 503/inference_failed 502, never switch demo |
| Review | inspection/task/new revision | items=[] | stale_record_version 409 reread; invalid_state 409 processed |
| Tasks | Populated items | Empty/null duration | not_found 404/outside_service_area 422; retain input |
| Crews | Four records/saved availability | Idle differs from missing | stale_record_version/idempotency_conflict 409 |
| Routes | Read both after B03 | Missing 404; valid zero-task plan still crews | stale_input_revision 409/travel_matrix_unavailable 503; retain old plans |
| Comparison | B03 pair | Null metrics/missing evidence | No invented differences if one read fails |
| Assistant | Proposed cited answer/preview | Proposed supported=false/clarification | Unimplemented API, never treat 404 as empty answer |

Other existing errors: validation_error, unsupported_upload_type, unsupported_image_type, invalid_image, image_too_large, image_not_found, image_storage_unavailable, invalid_detection_selection, workflow_unavailable, task_query_unavailable, database_unavailable. details can supplement guidance; never match natural-language message strings.

## 5. Four proposed assistant endpoints (unimplemented/unfrozen)

These fields must not enter “existing API types”. Paths come from allocation; C proposes details for A/B review.

| ID | Path | Proposed request | Proposed response |
|---|---|---|---|
| C01 | POST /assistant/query | question,plan_id; optional compare_plan_id | plan_id,nullable compare_plan_id,answer,supported,sources[] |
| C02 | POST /assistant/change-requests | client_request_id,text,based_on_plan_id | ChangeRequest, no business write |
| C03 | POST /assistant/change-requests/{id}/confirm | confirmation_id,expected_request_version | ChangeRequest; atomically check crew/global versions, save/replan |
| C04 | POST /assistant/change-requests/{id}/cancel | cancellation_id,expected_request_version | ChangeRequest; pending/unexecuted only |

Proposed Explanation.sources is a tagged union. Plan sources contain plan_id/field_path referencing actual saved values. Knowledge sources contain document_id,section_id,package_version,document_version,nullable rule_version,excerpt; frontend shows locatable citations rather than arbitrary generated URLs. Unsupported answers set supported=false and explain scope; missing plans return resource errors, not invented facts.

Proposed ChangeRequest: request_id (server resource),request_version,based_on_plan_id,input_revision,type=crew_availability,params={crew_id,available},before={available,crew_record_version},status,created_at,expires_at,business_update_status,recalculation_status,nullable result_plan_id (prefer GA),nullable result_plan_ids (ga/greedy),nullable error. client_request_id and confirmation/cancellation operation IDs are separate from resource IDs.

Proposed lifecycle: pending→executing→confirmed; pending→cancelled/expired; executing→failed. Failure explicitly reports whether business save succeeded rather than implying rollback. Duplicate executing confirmation queries existing execution, never repeats crew save/planning. Cancel after confirmation conflicts. Server transaction state transitions resolve concurrent confirm/cancel.

Proposed error semantics, not registered/current code: change_request_expired,change_request_conflict,unsupported_change,ambiguous_change,assistant_unavailable. Reuse stale_input_revision where appropriate; A registers final codes/status/details.

Required order: read/check state/expiry and idempotently claim execution; inside B’s business transaction check preview input_revision and crew record_version, then save (C never writes B tables); call planning with new revision; persist stage/result IDs/errors so retries return the result; if crew saved but planning failed, show partial success and retry planning only.

The four routes lack independent reload/status reading. Propose read-only GET change-request status as an additional endpoint outside the four, or freeze another durable recovery protocol. Reload must not call confirm just to obtain status. B03 also lacks execution idempotency; frontend alone cannot guarantee this lifecycle.

## 6. Static evidence

Repository root at planning: groupwork1. Relative sources: AGENTS.md (ownership/units/assistant scope); Miscellaneous/TEAM_WORK_ALLOCATION.md (six pages/four paths, corrected against code); backend roadguard/main.py, api/health.py, api/demo.py, api/workflow.py (mounts/A); schemas/workflow.py,task.py,task_query.py,detection.py (fields); crews/api.py,schemas.py,service.py (contracts/transactions); routing/api.py,models.py,service.py (contracts/synchronous same-run persistence); vision/real.py (failure codes); knowledge/manifest.json and acceptance_cases.json (versions/outdated text).

This reviewed static contracts/design completeness only. No services/models/paid APIs ran and no business data changed.
