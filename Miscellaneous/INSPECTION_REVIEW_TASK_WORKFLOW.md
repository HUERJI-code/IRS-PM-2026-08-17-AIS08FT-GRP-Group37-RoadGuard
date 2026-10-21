# Step 6: inspections, review and tasks

Owner: A; original date: 2026-10-12. This page describes original `a-workflow-v1` demo requests/workflows. Step 8 extends to `a-workflow-v2`; see [real vision API](REAL_VISION_API.md) for real requests/additions. The table below is original demo routing; current a-workflow-v5 real routing uses primary confidence ≥0.60 for automatic tasks, lower for review, and at most one response box; see [current fields/behavior](INSPECTION_RESPONSE_FIELDS.md). On 2026-10-14 current rules became `demo-rules-v2` (P3/P2/P1=60/120/240 minutes), per the [baseline](BUSINESS_RULES_BASELINE.md); old records retain frozen v1 rules. Parameters remain demo, with no Google/GPT/routes.

## 1. Inspections versus tasks

A valid submission saves `InspectionRecord`, retaining image reference/location/raw boxes/labels/confidence/model provenance/rule decisions/review history/revision. Only accepted inspections link a `TaskRecord`; a unique task.inspection_id constraint prevents duplication.

| Detection | Inspection status | Task/input revision |
| --- | --- | --- |
| None | `no_detection` | Save inspection; no task/increment |
| Any below demo threshold | `pending_review` | Retain all, await review; no increment |
| All meet demo threshold | `accepted` | Select one candidate/create task; increment once |
| Confirm/correct pending | `accepted` | Selected detection/review create one task; increment once |
| Dismiss pending | `rejected` | Retain record/note; no task/increment |

At most one task per inspection follows Step 5's demo policy, not a validated formal multiple-detection decision. No-detection records cannot acquire invented detections through review; resubmit. Accepted/rejected inspections cannot be reviewed again; corrections after acceptance use task patching. Completed/cancelled tasks retain history without deletion/reactivation.

Confirmation never changes raw confidence to 1.0; correction never overwrites raw labels. review_history separately stores selection, original/corrected labels, action/note/time/rule version. Reviews/later class corrections use the inspection's complete frozen configuration so restart/new rules cannot silently change historical rules.

## 2. Images, location and road declarations

- One fully decodable JPEG/PNG, maximum 8 MiB and 20 million pixels; reject corruption/animation/other formats/excess. Before multipart parsing, HTTP caps total at 8 MiB + 64 KiB and metadata at 16 KiB, independent of Content-Length.
- EXIF-normalize to RGB PNG without original metadata. Demo boxes scale to saved dimensions and are synthetic, not image recognition. No separate annotation currently: annotated_image_url=null; C may draw boxes.
- Server-generated filenames; access `/inspections/{id}/image` only with a database record, never public directory listing.
- Coordinates must be finite JSON numbers, within WGS84 and frozen JE/JW polygon union including edges, not merely its bounding rectangle. NUS-ISS's outside-area exception applies only to depot, not repair submissions.
- Explicit `road_type: "public_motor_road"` is mandatory under [road exclusions](JURONG_SCOPE_AND_DEPOT.md). Other categories rejected; road_type_source is user_declared. No road-network/access verification exists: **declaration is not automatic eligibility validation**. Callers check location; A/B separately verify formal experiment points.
- Coordinates/photo are separately submitted and do not prove capture in Jurong. Original demo inspections/tasks retain is_demo=true and require mode:"demo"/case ID; no automatic real-failure fallback.

Invalid uploads/locations/cases create no valid inspection/task. Storage failures cannot return success. Back up database/images together. Failed transactions clean new request images; a process crash between file write/DB commit may leave inaccessible orphans. No automatic orphan cleanup or cross-filesystem/SQLite atomicity is guaranteed.

## 3. HTTP

Prefix `/api/v1`; backend `/docs`; shared ErrorResponse. `/demo` previews remain read-only.

| Method/path | Input | Success |
| --- | --- | --- |
| `POST /inspections` | multipart image/metadata JSON, Idempotency-Key header | 201 new/200 retry; InspectionUploadResponse: inspection_id/status/detection/task_id only |
| `GET /inspections` | Optional status/limit/offset | InspectionList |
| `GET /inspections/{id}` | ID | InspectionRecord |
| `GET /inspections/{id}/image` | ID | Normalized image/png |
| `POST /inspections/{id}/review` | ReviewRequest | InspectionMutationResponse |
| `GET /tasks` | status active default or all/completed/cancelled; limit/offset | TaskList with same-read input_revision |
| `GET /tasks/{id}` | ID | TaskRecord/history |
| `PATCH /tasks/{id}` | TaskPatch | TaskMutation |

Defaults limit=50, offset=0; limit 1–100, nonnegative offset; status filters/total. Inspections default to all. Each page is consistent, but mutations may occur between pages; B must not mix revisions in one plan.

### Upload

UploadMetadata contains exactly:

```json
{
  "mode": "demo",
  "scenario_id": "low_confidence",
  "latitude": 1.34,
  "longitude": 103.72,
  "road_type": "public_motor_road"
}
```

Coordinates demonstrate format, not road-verified experiment points. Use checked eligible public motor roads within the area; obtain cases from GET /api/v1/demo/scenarios.

Save JSON as local upload-metadata.json, prepare a valid image and run PowerShell:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/inspections" -H "Idempotency-Key: inspection-demo-001" -F "image=@sample.jpg" -F "metadata=<upload-metadata.json"
```

Retries reuse the key; new inspections use new keys. Keys accept 1–64 English letters/digits/underscore/hyphen. Same key with different raw file/metadata yields 409 without overwrite. Renaming cannot bypass/change fingerprints based on raw bytes/normalized metadata.

### Review

Obtain inspection_id, record_version and detection_id from inspection details:

```json
{
  "request_id": "review-demo-001",
  "expected_version": 1,
  "action": "correct",
  "detection_id": "demo-low_confidence-01",
  "damage_label": "pothole_deep",
  "note": "Corrected the selected synthetic damage label."
}
```

- confirm requires this inspection's detection_id and no damage_label.
- correct requires detection_id and central-dictionary damage_label.
- dismiss permits neither selection nor correction; all actions allow note up to 500 characters.
- Only pending_review accepts new review. For multiple boxes, explicitly select the representative; other raw boxes remain. This is a review decision for the whole inspection.
- Since 2026-10-18, new review/task changes use actor_source=authenticated_user with account in auth_audit; legacy user_declared_unverified remains. Identity is not engineering qualification certification.

### Task changes

```json
{"request_id":"complete-demo-001","expected_version":1,"status":"completed"}
```

Allowed: completed/cancelled status, central damage_label, or latitude/longitude/road_type together. Label correction recalculates priority/severity/duration/advice and records before/after. Location correction revalidates scope and retains original inspection location. Reject empty patches, explicit nulls, partial locations, arbitrary priority/service_minutes/due_at and reopening.

Deadlines stay null without fabricated lateness; unknown duration stays null, not zero. Terminal records remain queryable by ID/status.

## 4. Versions, idempotency and responses

record_version is optimistic concurrency per inspection/task; review/patch supplies expected_version, stale yields 409. input_revision is shared planning input: actual task creation/correction/completion/cancellation increments once in the transaction. Replays, unchanged patches, pending/no-detection persistence and dismissal do not increment.

request_id deduplicates within inspection review or task changes. Exact retries are recognized first even with old expected_version; changed content under the same ID yields 409. Replay returns **current** resource/revision, not outdated historical response.

- InspectionUploadResponse: inspection_id/status/nullable detection/nullable task_id only; GET details separately.
- InspectionMutationResponse: inspection, nullable task, input_revision, planning_input_changed, replayed.
- TaskMutation: task, input_revision, planning_input_changed, replayed.
- planning_input_changed means actual input change, not completed route calculation. Step 6 calls no not-yet-implemented planner and invents no plan IDs.
- InspectionRecord/TaskRecord extend base DTO with timestamps/revision/provenance/history. Base extra=forbid cannot parse those records. C uses new records; B exact Task projection or new type. Original a-dto-v1 fixtures retain meaning.

Executable [workflow.py](../SystemCode/backend/roadguard/schemas/workflow.py); errors in [API contract](API_CONTRACT.md). Frontend uses code/status, not natural-language matching.

## 5. Database and verification

Startup migrates schema v1 to v2 in place, retaining input_revision and adding inspections/tasks/operation_keys/indexes. Shared transactions cover migration/writes; do not delete data or create separate business DBs. Unknown/corrupt schemas reject startup.

Default uploads live beside DB. ROADGUARD_UPLOAD_PATH independently overrides relative to root; ROADGUARD_DB_PATH changes default upload location, useful for isolation. Configuration changes do not move files. Reuse DB/uploads on restart.

`python -m pytest SystemCode/tests -q` covers seven cases, images/geography, raw evidence, statuses/idempotency/concurrency/rollback, rule snapshots, migration/restart. Test images are temporary; no uploads/real DB committed.

[Step 7 handoff](BC_HANDOFF.md) supplies consistent snapshots/fixed inputs/knowledge; Step 8 prepares training/real model. Crews/assistant/web/full integration proceed under original ownership.

## Account-permission increment (2026-10-18)

Examples now require login and X-CSRF-Token on writes. Inspectors upload/read own inspections; dispatchers review/manage; crews read/complete own tasks only. Four-field upload, single-box and 0.60 routing remain. See [account roles](ACCOUNT_ROLES.md) for roles/sessions/Swagger.


## Automatic planning update 2026-10-21

Accepted inspection uploads and review confirmation/correction automatically attempt paired GA/Greedy planning after the task transaction commits. Both algorithms share one task/crew snapshot and travel matrix and retain durable crew constraints. Pending review, no detection and dismissal trigger no planning. Completion, cancellation, crew changes and assistant confirmations still require explicit replanning.

The synchronous HTTP response waits for the attempt. The upload JSON retains exactly inspection_id, status, detection and task_id; X-RoadGuard-Replanning reports completed, failed or not_needed. An accepted idempotent replay repairs missing or stale plans and skips calculation when both latest plans are current. One process serializes automatic attempts and permits at most three total attempts (two retries), retrying stale-input conflicts only. A failure preserves the committed task and previous plans, which remain stale; the interface warns and retains manual recalculation. There is no durable worker or automatic restart recovery: a crash after task commit requires accepted replay or manual retry.

See [automatic planning acceptance](AUTOMATIC_PLANNING_ACCEPTANCE_20261021.md) for the focused verification record.
