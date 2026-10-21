# Step 5: demo detection and business rules

Date: 2026-10-12; owner: A. This step implements runnable detection/rule previews reused by the [Step 6 persisted workflow](INSPECTION_REVIEW_TASK_WORKFLOW.md). `/demo` inputs explicitly select synthetic cases: no pixel reading, YOLO, Google or GPT. They return candidates without saving inspections/tasks or changing planning revisions. Step 6 provides separate upload/persistence APIs.

## Demo versus formal rules

The sole configuration is [demo_rules.example.json](../SystemCode/config/demo_rules.example.json), currently `demo-rules-v2`, `is_demo=true`, `status=demonstration_assumptions`. On 2026-10-14 the initiator finalized P3/P2/P1=60/120/240 simulated minutes while retaining severity/priority mappings and the confirmed `0.60` threshold; see the [business baseline](BUSINESS_RULES_BASELINE.md). These course-simulation values have no real-world threshold calibration or measured repair-time basis; RDD2022ES labels do not supply them.

| Dataset label | Demo severity | Demo priority | Demo repair minutes |
| --- | --- | --- | --- |
| longitudinal_crack | low | P3 | 60 |
| longitudinal_crack_wide | medium | P2 | 120 |
| transverse_crack | low | P3 | 60 |
| transverse_crack_wide | medium | P2 | 120 |
| alligator_crack | medium | P2 | 120 |
| alligator_crack_sunken | high | P1 | 240 |
| pothole | medium | P2 | 120 |
| pothole_deep | high | P1 | 240 |

The table describes current configuration; synchronize it with changes. Recommendations/reasons in configuration identify simulation and are not real repair instructions. Unknown duration may be `null`, never zero. Deadlines and lateness metrics are undefined.

Configuration must cover exactly the central dictionary's eight `label_key` values. Missing/extra classes, duplicate JSON keys, invalid priorities, boolean/string numbers and non-finite values are rejected. `ROADGUARD_DEMO_RULES_PATH` overrides the path, relative to the repository root. Restart and update `rule_version` after changes. Invalid configuration fails startup without silent fallback.

## Routing and candidate selection

This section describes stateless demo previews and explicit demo uploads. Real uploads compare the released model's selected primary box to 0.60; see the [business baseline](BUSINESS_RULES_BASELINE.md#3-current-routing-single-box-and-task-creation). Do not apply demo multi-candidate gating to real uploads.

1. No detections: `no_detection`, with null candidate/selected ID.
2. Any confidence **below** threshold: `pending_review`. Mixed high/low results retain all boxes for review rather than discarding low boxes and accepting.
3. All confidences **at least** threshold: `ready_for_task`; calculate rules/select one candidate. This means calculation complete, not accepted, queued or geographically validated.

Rank by P1/P2/P3, then high/medium/low, then known repair duration descending (unknown last), confidence descending and finally lexicographic `detection_id`. Earlier criteria dominate; input order does not affect selection. All detections remain in the response. This ranking is also a demo assumption, not a formal multiple-detection business policy.

`decision_trace` records demo provenance, gating, per-detection rule reasons and selection, each with version. Stable codes: `demo_assumptions`, `no_detection`, `confidence_review_required`, `confidence_gate_passed`, `rule_mapping`, `candidate_selected`. Callers use codes, not natural-language parsing.

## Running

Install/start per the [backend guide](../SystemCode/backend/README.md). Open `http://127.0.0.1:8000/docs`:

- `GET /api/v1/demo/scenarios`: seven cases, detector version, synthetic dimensions.
- `POST /api/v1/demo/assessments`: submit `{"scenario_id":"high_confidence"}` to run detector/rules.

PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/demo/scenarios
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/demo/assessments -ContentType 'application/json' -Body '{"scenario_id":"high_confidence"}' | ConvertTo-Json -Depth 10
```

| scenario_id | Fixed detections | Default result |
| --- | --- | --- |
| high_confidence | pothole, 0.96 | ready_for_task, medium / P2 / 120 minutes |
| low_confidence | pothole, 0.42 | pending_review, no candidate |
| no_detection | Empty | no_detection, no candidate |
| multiple_detections | longitudinal crack 0.98, deep pothole 0.90 | P1 deep pothole selected, not simply highest confidence |
| mixed_confidence | pothole 0.96, deep pothole 0.42 | pending_review, both retained |
| threshold_boundary | pothole, 0.60 | ready_for_task, equality tested |
| below_threshold | pothole, 0.5999 | pending_review |

Confidences are fixed; names assume default 0.60. Overrides may change results; responses carry actual `confidence_threshold`/`rule_version`. All boxes use synthetic 640×480 coordinates without downloadable real/annotated images. Repeated cases are deterministic and return independent copies; scenario IDs are not persisted inspection/task IDs.

## Integration and boundaries

- `DemoDetector.detect(scenario_id)` returns shared `Detection` lists. Even empty responses identify `model_version`, `is_demo` and dimensions. Real-model replacement requires an explicit adapter; there is no automatic demo fallback.
- `RuleService(policy).evaluate(detections)` returns `RuleAssessment`, evaluating a snapshot without writes. Internal inputs revalidate labels, boxes, duplicate IDs and shared dimensions.
- `RuleCandidate` supplies label/severity/priority/duration/recommendation/version/demo flag, but no task_id/location/creation time. B must use Task, not plan candidates directly.
- Step 6 owns image/location validation, persistence, confirm/correct/dismiss, idempotent task creation and same-transaction revision increments. Human confirmation records review facts and reuses class mappings rather than fabricating confidence 1.0.
- Original Step 3 JSON remains independent `a-dto-v1`/`demo-unconfirmed-v1` snapshots; live previews use `demo-rules-v2`. Do not load old snapshots as configuration.

See the [API contract](API_CONTRACT.md) for added DTOs/errors. This step does not validate Jurong roads, persist tasks or generate four-crew plans, and does not establish complete-workflow or accuracy validation.

## Verification

From root: `python -m pytest SystemCode/tests -q`. Coverage includes deterministic/copy-isolated cases, eight classes, thresholds/configuration, multi-detection ranking, unknown duration, versions, HTTP errors, repeated previews without writes/revision increments, startup overrides and failures not disguised as success. Maintain tests with rule/data-format changes.
