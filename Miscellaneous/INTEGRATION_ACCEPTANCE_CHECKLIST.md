# RoadGuard integration checklist and A-module readiness acceptance

2026-10-18 update: existing A/B/C modules underwent isolated-database frontend/backend integration. Actual passes, decoder fix and assistant/Google boundaries are in the [record](INTEGRATION_ACCEPTANCE_20261018.md). Below retains the 2026-10-14 A-stage baseline; its B/C-not-ready descriptions are historical, not current status.

Date: 2026-10-14; version integration-checklist-v1; owner A.

Rules: [baseline](BUSINESS_RULES_BASELINE.md). Interfaces: [contract](API_CONTRACT.md)/[fields](INSPECTION_RESPONSE_FIELDS.md). This round accepts A's rules/workflow/examples; **B/C are not ready and cross-module integration is deferred**. Expected behavior is not an already-completed result.

## 1. Conditions and recording

| Item | Requirement |
| --- | --- |
| Rules | demo-rules-v2; P3/P2/P1=60/120/240 minutes; mappings unchanged |
| Interface | a-workflow-v5; four upload fields, one display box, primary ≥0.60 auto-task |
| B fixtures | planning-synthetic-v2; 10/15/20 tasks, empty/unknown duration; no matrix/routes |
| C knowledge | a-knowledge-v6; content/citation/digest validation, not assistant execution |
| Isolation | Temporary SQLite/images; manual HTTP isolated DB/port, no normal DB pollution |
| Model boundary | Explicit fake detectors may control unit/HTTP thresholds; numerical quality requires separate real evaluation; stub results are not model performance |
| Status | passed executed with result; failed executed below expectation; not_run unexecuted; blocked missing module/parameter/credential; blocked is never passed |

Record case ID, commit/uncommitted status, rule/knowledge/model versions, executor/UTC, input source, request key/status, expected/actual, evidence and pass/fail/block reason. Extract random IDs from current responses rather than historical/other-machine examples.

## 2. Immediately executable A rules/API acceptance

All owned by A; paths relative to root. Actual results are separately in section 6; existing test files alone are not passing evidence.

| ID | Input/steps | Required observation | Automated entry |
| --- | --- | --- | --- |
| A01 | Eight classes through real-mode gate, injected 0.60 | Correct P3/60, P2/120, P1/240; active/due_at=null; consistent details/history/snapshot | test_business_baseline.py::test_v2_eight_class_durations_reach_task_detail_and_snapshot |
| A02 | Inject 0.599999, correct to each class | No task before; target v2 duration after; raw evidence/confidence retained/manual source | A01 review_correction parameter |
| A03 | 0.599999/0.60/0.600001, competitors and ranking_score below 0.60 | Raw primary confidence/inclusive equality, no ranking/secondary substitution | test_real_vision.py::test_real_primary_uses_inclusive_confidence_gate; test_single_box_workflow.py::test_gate_uses_primary_raw_confidence_not_best_score_or_ranking |
| A04 | Upload/details/list/replay | Exactly four upload fields; one object/null; other detections ≤1; raw candidates in DB | test_single_box_workflow.py::test_http_auto_upload_get_list_replay_all_have_one_box_and_raw_db_is_unchanged |
| A05 | No detection, attempt review | no_detection/null/no increment; no direct confirm/dismiss task creation | test_real_vision.py::test_real_no_detection_has_no_task_and_cannot_be_confirmed |
| A06 | confirm/correct/dismiss pending | One task for confirm/correct, none dismiss; evidence/history/version retained | test_workflow.py::test_review_records_declared_fact_keeps_raw_detection_and_uses_explicit_mapping; test_workflow_api.py::test_dismiss_keeps_inspection_history_without_task |
| A07 | Same-key retry/concurrency, then changed bytes/metadata | Same resource/200, one inference/task; changed payload 409/no overwrite | test_single_box_workflow.py::test_auto_task_is_exactly_once_including_concurrent_replay_and_restart; test_workflow.py::test_upload_key_reuse_with_changed_metadata_or_source_is_conflict |
| A08 | Review/patch retry, changed same-key payload, stale version | No duplicate; 409 conflict; no stale overwrite | test_workflow.py::test_review_replay_precedes_version_and_closed_state_validation; test_workflow.py::test_task_stale_write_and_key_payload_conflict |
| A09 | Label/legal location correction/no-op | Frozen-rule remap/history, real input +1, no-op no increment | test_workflow.py::test_task_label_and_location_corrections_audit_changes_and_preserve_inspection; test_workflow.py::test_noop_task_patch_has_no_record_or_input_revision_change |
| A10 | Complete/cancel/query/change | History retained, absent active, +1 each real change, no reopen | test_workflow.py::test_terminal_task_preserves_history_and_cannot_change_again |
| A11 | v1 pending/accepted, restart v2, review/correct old/new upload | Historical 20/45/60 preserved; new v2; mixed snapshots; replay without detector | test_business_baseline.py::test_v1_records_retain_frozen_durations_after_v2_restart |
| A12 | JE/JW inside/outside/edge, invalid coordinates/road, outside patch | Consistent covers, 422 invalid; no new records/images or existing changes | test_geography.py; test_workflow_api.py::test_invalid_scope_and_metadata_leave_no_records_or_images; test_workflow.py::test_active_task_outside_scope_patch_does_not_modify_history_or_revision |
| A13 | JPEG/PNG/EXIF/corruption/type/size/pixels | Normalize valid; 413/415/422 errors; no failed resources | test_images.py; test_workflow_api.py::test_binary_size_and_stream_body_limits |
| A14 | Detector unavailable/failure, commit/storage failure | Explicit errors, no no-detection/demo masquerade; atomic records/task/revision rollback/image cleanup | test_real_vision.py; test_workflow.py::test_database_commit_failure_rolls_back_upload_task_revision_and_new_image; test_images.py |
| A15 | Restart under read transaction, locked migration/retry, persistence | Current schema read-only startup; migration honors locks/rollback; data retained | test_backend.py::test_restart_current_database_while_external_transaction_is_open; test_backend.py::test_migration_still_requires_lock_and_rolls_back_before_retry; test_workflow_api.py::test_restart_preserves_records_and_images |
| A16 | Empty/>100/terminal/unknown/stale | Complete consistent snapshot, null retained, 409 stale, failures not empty | test_task_query.py; test_task_query_api.py |
| A17 | Generate/check fixtures/knowledge | v2 durations/version/digests match; no road-validation claim; v6 rules/citations/versions match | test_planning_fixtures.py; test_knowledge_handoff.py |
| A18 | Isolated HTTP example | Four demo inspections retained; review/replay/complete/cancel/snapshot/conflict assertions | test_handoff_demo.py; SystemCode/examples/handoff_demo.py |

Unit/component checks are not A/B/C acceptance. A01–A03 controlled detectors prove routing, not 70% Precision/Recall. Real confidence must not be manually entered; arbitrary images cannot be required to produce exactly 0.60.

## 3. Automated commands

Use the project environment with backend CI dependencies installed. Each acceptanceRun creates a separate ignored evidence directory:

```powershell
$acceptanceRun = Join-Path 'Dataset/acceptance' ([guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $acceptanceRun | Out-Null
$pytestTemp = Join-Path ([System.IO.Path]::GetTempPath()) ('roadguard-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -m pytest SystemCode/tests -q --basetemp "$pytestTemp" --junitxml "$acceptanceRun/pytest.xml"
.\.venv\Scripts\python.exe SystemCode/contracts/planning/generate.py --check
.\.venv\Scripts\python.exe .github/scripts/check_repository.py
```

Check every exit code zero/no pytest failures; record Windows symlink skips separately. Unexecuted cases are not passed. pytest temp must be outside Dataset because some cases test output rejection outside Dataset; JUnit remains inside ignored Dataset. Existing user SQLite is never used.

## 4. Manual Swagger/HTTP checks

Optional manual checks use a separate terminal/8001/new directory; set environment only there and close afterward. Never reuse existing evidence directories.

```powershell
$acceptanceRun = Join-Path 'Dataset/acceptance' ([guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $acceptanceRun | Out-Null
$env:ROADGUARD_DB_PATH = "$acceptanceRun/workflow.sqlite3"
$env:ROADGUARD_UPLOAD_PATH = "$acceptanceRun/uploads"
$env:ROADGUARD_DEMO_RULES_PATH = 'SystemCode/config/demo_rules.example.json'
$env:ROADGUARD_VISION_MANIFEST_PATH = 'disabled'
.\.venv\Scripts\python.exe -m uvicorn roadguard.main:app --app-dir SystemCode/backend --host 127.0.0.1 --port 8001
```

After Application startup complete, another terminal:

```powershell
.\.venv\Scripts\python.exe SystemCode/examples/handoff_demo.py --base-url http://127.0.0.1:8001 --confirm-demo-writes
```

This genuinely writes demo records; do not target normal 8000. Retain synthetic/demo labels in responses. In http://127.0.0.1:8001/docs upload JPEG/PNG with new key (e.g. acceptance-high-001), metadata:

```json
{"mode":"demo","scenario_id":"high_confidence","latitude":1.34,"longitude":103.72,"road_type":"public_motor_road"}
```

Expect 201/accepted/one detection/non-null task_id; task pothole/medium/P2/**120**/demo-rules-v2/due_at=null. New keys with low_confidence await review, no_detection creates none, threshold_boundary checks exact 0.60. Use IDs/versions from current details.

Real-model manual checks need another isolated instance, released weights/actual manifest, mode=real without scenario_id; retain responses/photo sources/hash. Misclassification/misses/box errors belong in quality records, never “fixed” by modifying confidence. This parameter change needs no retraining.

## 5. Integration only after B/C readiness

All are **blocked: B/C not delivered, not executed this round**. Agreed paths are not permission to create fixed-success empty endpoints for checkmarks.

| ID/owner | Prerequisite | Steps/acceptance | Evidence |
| --- | --- | --- | --- |
| BC01 C+A | Upload/review/task pages | Four fields displayed; details supply review IDs/version; automatic/confirmed/corrected/dismissed states match API | Requests/responses/UI/snapshots |
| BC02 B+A | Crews/input service | Same transaction tasks/four crews, unavailable excluded, saved duration/null preserved | Revision/crews/input |
| BC03 B | Entrance/eligible roads/matrix/constraints | Shared NUS-ISS, first travel counted, unreachable handled, shift/return confirmed first | Nodes/road checks/matrix/settings |
| BC04 B+A | Algorithms/persistence | Same input/matrix/constraints, no missing/duplicates, reasons, save-time revision check | IDs/revisions/assignments/seeds |
| BC05 A+B+C | Input change/recalculation/staleness | Task/crew change stale; no fake success or stale overwrite | Before/after/status/failure |
| BC06 C+B | Map | Four crews/depot/area/order; schematic versus roads; unassigned/stale | Plan/map correspondence |
| BC07 C+A+B | GPT/RAG/plan query | v6 citations/actual facts, rule versions, insufficiency without invented savings/accuracy | QA/citations/plans/versions |
| BC08 C+B | Preview/confirmation | Preview before disable, confirm through B, cancel no-op, duplicate/stale handled | IDs/preview/confirm/cancel/revision |
| BC09 A+B+C | All above | Understandable failures without fabricated success; empty/<4/all disabled/10/15/20 | Defects/recovery/end-to-end |

## 6. Execution in this round

2026-10-14; coding agent on behalf of A; base 21e17373749e43149b5c28ca3d214eb49f79ed40, feature/a-business-rules-baseline including uncommitted changes. Versions in section 1. Local only, not pushed/remote CI.

| Check | Actual result | Evidence |
| --- | --- | --- |
| A01–A18 full suite | passed: 871 passed/1 skipped/0 failed, 40.08 s | Local Dataset/acceptance/business-rules-v2-20261014/pytest-final.xml |
| New baseline/compatibility | passed: eight classes × auto/correction =16 plus v1→v2 restart, included above | test_business_baseline.py/same JUnit |
| Fixtures | passed generate.py --check, byte-identical to current sources | Command output |
| Repository/links | passed check_repository.py, 203 files | Command output |
| Isolated Uvicorn/actual TCP | passed 16 assertion groups; auto P2/120, corrected P1/240 | Local Dataset/acceptance/business-rules-v2-20261014/http-results.json |

HTTP timestamp 2026-10-14T01:45:40.580105+00:00; explicit demo, isolated temporary port/DB, real model disabled. End state: four inspections, two completed/cancelled tasks, zero active, input_revision=4. Service stopped; normal 8000/DB untouched.

One skip: Windows symlink permissions; one existing Starlette/httpx deprecation warning. First run placed pytest temp in Dataset, breaking the output-rejection test precondition; full rerun outside Dataset passed. Initial pytest.xml retained; pytest-final.xml is authoritative.

Evidence stays local/ignored. Members generate their own with section 3. Real-mode test values are fake-detector injections and HTTP examples synthetic; neither establishes real quality.

B/C integration: blocked. Real quality: not_run this round; simultaneous >70% Precision/Recall remains unmet.
