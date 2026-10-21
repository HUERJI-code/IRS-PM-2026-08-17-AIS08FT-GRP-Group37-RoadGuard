# RoadGuard finalized business rules: course-simulation baseline

Date: 2026-10-14; owner: A; baseline: `business-baseline-v1`; runtime rules: `demo-rules-v2`.

This change covers business rules, reproducible development examples and acceptance preparation. B/C modules are not complete; four-crew planning, pages, map and assistant integration are deferred. See the [acceptance checklist](INTEGRATION_ACCEPTANCE_CHECKLIST.md).

## 1. Decision and versions

The initiator explicitly set expected repair duration to **P3=60, P2=120, P1=240 minutes**. Existing eight-label severity/priority mappings and the single-primary-box confidence gate of 0.60 remain. These are finalized course-simulation parameters, not engineering measurements or real repair commitments.

- Sole runtime configuration: [demo_rules.example.json](../SystemCode/config/demo_rules.example.json). Retain `is_demo=true`, `status=demonstration_assumptions`, the filename and `ROADGUARD_DEMO_RULES_PATH` compatibility.
- Historical reference: [demo-rules-v1.json](../SystemCode/config/rule_history/demo-rules-v1.json); never automatically loaded or substituted for frozen database rules.
- HTTP stays `a-workflow-v5`, snapshots `a-task-query-v1`, SQLite schema v2. Only rules, examples and knowledge change.
- C's knowledge package is `a-knowledge-v6`; B's fixed tasks are `planning-synthetic-v2`.

## 2. Eight classes and task attributes

| ID | label_key | Class | severity | priority | service_minutes | Simulated recommendation |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | longitudinal_crack | Longitudinal crack | low | P3 | 60 | Inspect and assess crack repair methods |
| 1 | longitudinal_crack_wide | Wide longitudinal crack | medium | P2 | 120 | Inspect and assess crack repair methods |
| 2 | transverse_crack | Transverse crack | low | P3 | 60 | Inspect and assess crack repair methods |
| 3 | transverse_crack_wide | Wide transverse crack | medium | P2 | 120 | Inspect and assess crack repair methods |
| 4 | alligator_crack | Alligator (network) cracking | medium | P2 | 120 | Inspect and assess pavement repair methods |
| 5 | alligator_crack_sunken | Sunken alligator cracking | high | P1 | 240 | Inspect and assess pavement repair methods |
| 6 | pothole | Pothole | medium | P2 | 120 | Inspect and assess pothole repair methods |
| 7 | pothole_deep | Deep pothole | high | P1 | 240 | Inspect and assess pothole repair methods |

Recommendations explain the configuration's English `recommendation`; API field names/language remain unchanged. `reason` explicitly records demonstration assumptions. P1 is more urgent than P2/P3, but priority is a task attribute, not a guarantee of strict P1→P2→P3 route order; scheduling constraints/objectives will determine routes.

`service_minutes` is simulated on-site duration for one task, **not a deadline, response limit, departure time or travel time**. B supplies travel minutes separately. A 240-minute task is not divided by four merely because there are four crews; multi-crew repair of one task is outside the implemented workflow.

wide/deep/sunken are visual dataset categories, not millimeter/centimeter measurements. Box area does not estimate real depth, road structure or duration. Confidence affects acceptance/review only, not severity or duration scaling.

## 3. Current routing, single box and task creation

Real uploads select one candidate under the released model's primary-box policy, then compare its raw `confidence`:

| Input | inspection.status | task_id | Input revision |
| --- | --- | --- | --- |
| No detection | no_detection | null | Unchanged |
| Primary confidence < 0.60 | pending_review | null | Unchanged |
| Primary confidence ≥ 0.60, inclusive | accepted | One active Task | +1 in same transaction |
| Confirm/correct pending_review | accepted | One active Task | +1 in same transaction |
| Dismiss pending_review | rejected | null | Unchanged |

- Upload returns only `inspection_id`, `status`, `detection`, `task_id`; detection is one object or null. Detail/list/review detections arrays contain at most one entry; raw candidates remain in the database.
- The manifest's existing `area_quarter` or other primary policy selects the box; changed durations do not introduce priority-based selection. A different high-confidence candidate does not replace a low-confidence primary. Ambiguity warnings remain without additionally blocking a qualifying primary.
- Inference filtering 0.20 differs from acceptance 0.60. No new “discard below 0.30” rule exists. 0.60 is not an accuracy guarantee.
- `/demo` previews and explicit demo uploads retain synthetic semantics: any below-threshold candidate requires review; if all pass, rank by priority, severity, service_minutes, confidence, ID. Preview `ready_for_task` creates no task. Equal duration within a priority removes former 35/45-minute ordering differences; confidence/ID then break ties.
- Real Detection is_demo=false; Inspection/Task is_demo=true because business parameters remain simulated. Real inference failures never fall back to demo success.

## 4. Review, changes and historical consistency

1. GET inspection details before review for detection_id/record_version, absent from the four-field upload response.
2. confirm retains class; correct maps the reviewed class while retaining raw label/confidence/review; dismiss retains rejection. Only pending_review may be reviewed; no_detection cannot directly create a task by confirmation.
3. Task class correction recalculates severity/priority/duration; callers cannot arbitrarily set derived fields.
4. completed/cancelled retain history and leave active snapshots; no terminal-task reopening API exists.
5. Retry one action with the same idempotency key; change the key when content changes. Replay creates no task/revision increment; upload replay returns 200, new creation 201.
6. expected_version prevents overwriting another resource change; input_revision identifies planning snapshots. Only real input changes increment revision, not reads, previews, unchanged patches or replays.

**No bulk migration of old records.** Rules freeze at inspection creation. A v1 inspection reviewed after v2 still creates a v1 task; class corrections use its original inspection rules. Only new inspections use startup-loaded v2. Active snapshots may mix v1/v2 Tasks; B must read each saved service_minutes rather than recalculate all from latest configuration.

For example, v1 potholes were P2/45 minutes and deep potholes P1/60, now P2/120 and P1/240. Historical examples/evidence retain original versions. For an all-v2 demo, create a new isolated database and new inspections through normal workflows.

## 5. Scope, nulls and open decisions

- Tasks remain inside frozen Jurong East/West polygons with permitted road declarations. NUS-ISS is a designated origin outside the area, not an eligible repair point.
- `due_at=null`: no deadline; do not infer deadlines/lateness from service duration.
- External/legacy `service_minutes=null` means unknown, not zero. All current v2 classes have explicit durations.
- Shift, return policy, capability, deadlines, objective weights, GA parameters and drivable depot entrance remain A/B decisions. `return_to_depot=null` cannot default to false.
- This change does not implement crews/routing/assistant/frontend, start training/Google/GPT calls or claim integration/model acceptance.

## 6. Release and use

Rules load at startup; restart after configuration changes. If PyCharm overrides ROADGUARD_DEMO_RULES_PATH, verify it points to v2. Check Task.rule_version and decision_trace, not just a “latest” UI label.

Run A's checks in the [acceptance checklist](INTEGRATION_ACCEPTANCE_CHECKLIST.md). Future threshold/mapping/duration/recommendation changes require a new version, synchronized docs/knowledge/fixtures and historical compatibility checks. Keep Dataset, runtime databases and uploads Git-ignored.
