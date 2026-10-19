# Single-box responses, 60% automatic tasks and field reference

Date: 2026-10-13; owner: A; contract a-workflow-v5; API 0.8.0.

## Current behavior

Rules became `demo-rules-v2` on 2026-10-14, with new-inspection P3/P2/P1 durations 60/120/240 minutes. Fields are unchanged; old records and historical acceptance examples retain their versions/durations. See the [baseline](BUSINESS_RULES_BASELINE.md).

As confirmed by the initiator, real uploads first choose one primary box under the existing policy, then compare its **raw confidence**:

| Condition | Status | task | Planning input |
| --- | --- | --- | --- |
| Primary confidence ≥0.60, inclusive | accepted | One active task automatically | input_revision +1 |
| Nonempty, primary <0.60 | pending_review | null; confirm/correct/dismiss | Unchanged |
| No detection | no_detection | null | Unchanged |

Upload returns only inspection_id/status/detection/task_id; detection is one object or null. Detail/list/review detections remain arrays with at most one element, or []. All endpoints/replays project the same box: selected_detection_id for accepted records, otherwise primary suggestion, otherwise highest-confidence legacy evidence. Full raw boxes remain only in database InspectionRecord.

Default `area_quarter` ranking is confidence × fourth root of box area/image area. Acceptance compares confidence, not ranking_score; competitors/ambiguous do not override the confirmed gate. Do not force YOLO max_det=1 and lose evidence before ranking. Legacy manifests without primary policy use highest confidence.

0.60 is confidence_threshold in [demo_rules.example.json](../SystemCode/config/demo_rules.example.json); version/restart after changes. Released inference filtering remains 0.20, so typically 0.20–0.60 awaits review; no new “discard below 0.30” rule. The business gate is not an accuracy guarantee; duration/severity/priority remain demo assumptions.

Weights/checkpoints/raw data are unchanged; no training started. Existing inspections are not re-inferred or retroactively tasked; old keys replay old records. Use a new key to test new rules.

## Swagger upload

Restart, open `/docs`, select POST /api/v1/inspections and Try it out:

- idempotency-key: `single-box-test-001`, new key for each new test.
- image: JPEG/PNG, maximum 8 MiB/20 million pixels.
- metadata: JSON below, without scenario_id.

```json
{
  "mode": "real",
  "latitude": 1.3405,
  "longitude": 103.706,
  "road_type": "public_motor_road"
}
```

Coordinates test the in-Jurong workflow, not photo provenance. New success 201; same content/key replay 200; same key/different content 409.

## Four upload fields

| Field | Meaning |
| --- | --- |
| inspection_id | Inspection ID for details |
| status | accepted; pending_review; no_detection; old replay may be rejected |
| detection | One object or null; only label/confidence/bbox_xyxy/image_width/image_height |
| task_id | Linked automatically or manually accepted task; null if absent |

[Current example](../SystemCode/contracts/workflow/real-upload-example.json). Detection's five fields are English class key, raw confidence, original-image pixel box, width and height, without model/audit metadata.

GET /api/v1/inspections/{inspection_id} returns inspection fields directly at JSON top level without an inspection wrapper. GET /api/v1/tasks/{task_id} returns full task. Obtain detection_id/record_version before review.

Both upload success bodies contain only these four fields, without replayed/input_revision. GET /api/v1/tasks/snapshot supplies planning revision; errors remain code/message/details.

## Review-response top level

This full wrapper applies to review; upload uses the compact format above.

| Field | Meaning |
| --- | --- |
| inspection | Images/detection/location/decisions/history |
| task | Linked task or null; retains linked history after completion/cancellation |
| input_revision | Global planning revision after task creation/actual change/completion/cancellation, not count |
| planning_input_changed | Actual input change; false on replay; not route recalculation completion |
| replayed | Reused idempotent result, without inference/duplicate task |

## Inspection details (also review inspection)

| Field | Meaning |
| --- | --- |
| inspection_id | Unique ID |
| image_url | EXIF-normalized original-size RGB PNG without metadata; relative to backend root |
| annotated_image_url | Annotated image, currently null; Swagger draws no boxes; frontend may draw bbox_xyxy |
| latitude | Submitted WGS84 latitude |
| longitude | Submitted WGS84 longitude |
| detections | User-facing array, 0 or 1; below |
| selected_detection_id | Accepted task-creation detection, usually null pending review |
| status | no_detection/pending_review/accepted/rejected; accepted is not repair completion |
| task_id | Linked task or null |
| decision_trace | Decision/rule explanations for display/audit |
| is_demo | Currently true: simulated business context/durations, not necessarily synthetic model input |
| created_at | UTC ISO 8601; Z means UTC |
| updated_at | Latest inspection update |
| record_version | Inspection concurrency version used as review expected_version |
| mode | real pixel inference or demo synthetic case |
| demo_scenario_id | Demo case, null for real |
| model_version | Detector version |
| model_weights_sha256 | Actual weight digest; null for demo |
| model_manifest_version | Manifest format, roadguard-model-v1 for real; not epoch count |
| primary_suggestion | Initial primary-ranking snapshot; may be null for legacy/no policy |
| auto_acceptance | Automatic-policy snapshot; null for low-confidence/manual/legacy |
| image_width | Normalized original pixel width |
| image_height | Normalized original pixel height |
| scope_version | Jurong boundary version for validation |
| road_type | Currently public_motor_road |
| road_type_source | user_declared, not automatically verified |
| review_history | Manual history; [] for automatic task creation |

## detections[0]

| Field | Meaning |
| --- | --- |
| detection_id | Unique detection ID for review |
| class_id | RDD2022ES ID 0–7 |
| label | Corresponding English key |
| confidence | Raw 0–1; 0.60=60%, not measured correctness |
| bbox_xyxy | [top-left x, top-left y, bottom-right x, bottom-right y] in normalized-original pixels, not normalized 0–1 |
| image_width | Original pixel width |
| image_height | Original pixel height |
| model_version | Producing model |
| is_demo | false for real, true for synthetic |

Classes: 0 longitudinal_crack (longitudinal crack); 1 longitudinal_crack_wide (wide longitudinal crack); 2 transverse_crack (transverse crack); 3 transverse_crack_wide (wide transverse crack); 4 alligator_crack; 5 alligator_crack_sunken (sunken alligator cracking); 6 pothole; 7 pothole_deep (deep pothole). Width/depth are training-label meanings, not engineering measurements.

## primary_suggestion and auto_acceptance

| Path | Meaning |
| --- | --- |
| primary_suggestion.policy_version | single-damage-v1 currently |
| primary_suggestion.strategy | Ranking, default area_quarter |
| primary_suggestion.threshold | Candidate filter, default 0.20; not automatic-task 0.60 |
| primary_suggestion.detection_id | Initial suggestion or null; may differ after manual alternative selection |
| primary_suggestion.ranking_score | Primary ranking or null; not confidence/correctness probability |
| primary_suggestion.ambiguous | Similar-score different class/disjoint region; warning does not block passing primary |
| primary_suggestion.competing_detection_ids | Primary/competitor IDs, possibly internal-only evidence without additional boxes; [] without ambiguity |
| auto_acceptance.policy_version | single-primary-auto-v1 currently |
| auto_acceptance.confidence_threshold | Frozen actual gate when task created, default 0.60 |

## decision_trace[] and review_history[]

| Path | Meaning |
| --- | --- |
| decision_trace[].code | Machine code, e.g. real_primary_auto_accepted, real_primary_review_required, no_detection |
| decision_trace[].message | Text explanation |
| decision_trace[].rule_version | Business-rule version |
| decision_trace[].is_demo | Currently true, demo business evidence |
| review_history[].request_id | Idempotent review ID |
| review_history[].action | confirm, correct class, dismiss |
| review_history[].recorded_at | UTC review time |
| review_history[].detection_id | Selected ID or null for dismissal |
| review_history[].original_damage_label | Original selected class or null for dismissal |
| review_history[].corrected_damage_label | Corrected class or null |
| review_history[].note | Caller note or null |
| review_history[].rule_version | Frozen review rules |
| review_history[].actor_source | user_declared_unverified: unauthenticated declared identity |

## task

No subfields exist when task=null.

| Field | Meaning |
| --- | --- |
| task_id | Unique repair-task ID |
| inspection_id | Source inspection |
| latitude | Current latitude; correctable through task API |
| longitude | Current longitude |
| damage_label | Final dispatch class, possibly different from model |
| severity | Frozen low/medium/high |
| priority | Frozen P1/P2/P3, P1 highest |
| service_minutes | Demo expected minutes; null unknown, not zero |
| created_at | UTC creation |
| due_at | Deadline, currently null/undefined |
| status | active/completed/cancelled; only active enters planning |
| rule_version | Mapping/duration/priority rules |
| is_demo | Currently true, course-simulation business |
| updated_at | Latest task change |
| record_version | Task expected_version, independent of inspection version |
| repair_recommendation | Rule-derived text |
| history | Creation/change audit |

## task.history[]

| Field | Meaning |
| --- | --- |
| request_id | Idempotent creation/change ID; automatic creation uses upload key |
| action | created or updated |
| recorded_at | Action time |
| changed_fields | Changed field names |
| before | Business snapshot, null on creation |
| after | Result snapshot |
| actor_source | system_confidence_policy for real automatic acceptance; system_demo_rules for synthetic; user_declared_unverified for declared manual actions |

before/after fields: status, latitude, longitude, damage_label, severity, priority, service_minutes, rule_version, as above.

## Actual examples and acceptance

[real-upload-example.json](../SystemCode/contracts/workflow/real-upload-example.json) comes from v5 isolated-DB real-model HTTP acceptance. A previously downloaded worn-road image produced confidence about 0.603604 and one automatic demo task. [real-auto-task-example.json](../SystemCode/contracts/workflow/real-auto-task-example.json) retains the historical full v4 response. IDs/image_url belong to temporary databases and cannot be queried on another machine. This proves routing behavior, not expert labeling or accuracy.

Another photo with primary about 0.457828 returned one pending box (four internally retained). A street image with no detection returned upload detection=null/details detections=[] and no task. Replay, post-disable restart reads and active snapshots were checked. v5 evidence: ignored Dataset/compact-upload-v1; v4: Dataset/single-box-auto-v1-verified.

This v5 round's full `python -m pytest SystemCode/tests -q`: 851 passed, 1 skipped (Windows symlink permission); repository checks/git diff --check passed. Coverage: four upload fields, detail queries, inclusive 0.60, primary raw confidence amid competitors, ambiguity, concurrency/deduplication, rollback, query/review/replay single-box projection, legacy reads, knowledge versions/sources. Real-model tests used isolated DBs without changing existing user inspections/tasks.
