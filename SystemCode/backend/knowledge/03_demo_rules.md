# Demo rules and confidence routing

document_id: `rg-kb-demo-rules`; document_version: `3`; owner: `A`.

<a id="demo-rule-table"></a>
## Exact demo mapping

classification: `demo_assumption`. citation_id: `rg-kb-demo-rules#demo-rule-table`.

Current rule version is `demo-rules-v2`, with `is_demo=true` and status `demonstration_assumptions`. On 2026-10-14 the project owner finalized durations as P3/P2/P1 = 60/120/240 minutes, retaining class-to-severity/priority mappings. These centrally configured course-simulation assumptions have no real-model calibration or measured engineering service-time basis and must not direct real repairs. Repair recommendations are also demonstration assessment prompts.

| label_key | Demo severity | Demo priority | Demo service_minutes |
| --- | --- | --- | --- |
| longitudinal_crack | low | P3 | 60 |
| longitudinal_crack_wide | medium | P2 | 120 |
| transverse_crack | low | P3 | 60 |
| transverse_crack_wide | medium | P2 | 120 |
| alligator_crack | medium | P2 | 120 |
| alligator_crack_sunken | high | P1 | 240 |
| pothole | medium | P2 | 120 |
| pothole_deep | high | P1 | 240 |

Sources: [src-demo-rules](../../config/demo_rules.example.json), [src-label-schema](../../model/label_schema.json).

<a id="demo-gate-selection"></a>
## Routing and single-candidate selection

classification: `demo_assumption`. citation_id: `rg-kb-demo-rules#demo-gate-selection`.

The following applies to stateless demo previews and explicit demo uploads. Real uploads use the model-selected primary box's raw confidence and do not apply demo multi-candidate ordering. With demo `confidence_threshold=0.60`, no detections means `no_detection`; any detection below threshold makes the entire inspection `pending_review`, retaining all detections without a candidate. Only when all detections are at or above threshold is it `ready_for_task`. 0.60 passes; 0.5999 requires review. Mixed high/low detections cannot be automatically accepted by discarding low boxes. Preview ready_for_task only means candidate calculation completed, not that an inspection was saved, a task queued or a route generated.

`selection_strategy=priority_severity_duration_confidence_id`: first P1->P2->P3, then high->medium->low, then known service minutes descending (null last), then confidence descending, and finally detection_id lexicographically. Input order does not affect the result; all detections remain retained. For example, pothole_deep at 0.90 precedes longitudinal_crack at 0.98 because demo P1 precedes P3. At most one task per inspection is also a demo policy, not a formal multiple-damage dispatch rule.

Sources: [src-demo-rules](../../config/demo_rules.example.json), [src-rule-service](../roadguard/rules/service.py), [src-workflow-service](../roadguard/inspections/service.py).

<a id="demo-null-provenance"></a>
## Unknown values and provenance

classification: `demo_assumption`. citation_id: `rg-kb-demo-rules#demo-null-provenance`.

Unknown service_minutes is null, never zero; all eight current configured durations are demo minutes. Task due_at remains null, so no deadlines or lateness metrics are generated. Inspections freeze the complete rule snapshot; reviews and task-label corrections use it rather than new configuration after restart. Preserve Detection model_version/is_demo when citing detections, read Inspection decision_trace for decisions and retain Task rule_version/is_demo when citing tasks. Do not assume Task itself contains a model version or full decision process. Explicit demo uploads use named synthetic scenarios; only real uploads invoke the actual detector. Service minutes are neither a deadline nor travel time and are not divided by four because there are four crews.

This package's static table explains demo-rules-v2 only; runtime records may use overridden configurations with other versions. Do not use this package or the latest rule table to recalculate or explain older tasks from another version. Use each record's saved rule version, decision_trace and history; acknowledge insufficient_data without matching evidence.

Sources: [src-demo-rules](../../config/demo_rules.example.json), [src-workflow-service](../roadguard/inspections/service.py), [src-workflow-schema](../roadguard/schemas/workflow.py).
