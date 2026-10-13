# Workflow response examples

Current a-workflow-v5: `real-upload-example.json` is an actual `InspectionUploadResponse` from an isolated real-model test. It contains exactly inspection_id, status, detection and task_id; detection has label, confidence, bbox_xyxy and image dimensions. Detailed inspection/task records are read through their GET endpoints. See [all fields](../../../Miscellaneous/INSPECTION_RESPONSE_FIELDS.md). IDs belong to the temporary test database.

`real-auto-task-example.json` preserves the previous v4 complete `InspectionMutationResponse` example. It records a task created at confidence >= 0.60, with auto_acceptance and system_confidence_policy in task history. It is no longer the POST /inspections response shape; its business coordinates and task are simulated.

## Historical a-workflow-v3 fixture

`real-primary-example.json` is an actual inspection response from isolated local release acceptance using the previously downloaded worn-pavement photograph. It contains real-model detections, a single display suggestion and simulated business coordinates; it is not an accepted task or an expert annotation. The image itself is not distributed here, and its generated image URL is only an example from that temporary database.

Validate using `roadguard.schemas.workflow.InspectionRecord`. The `primary_suggestion.detection_id` references retained evidence, while `selected_detection_id` remains null and status remains pending_review. Full field definitions, model installation and client compatibility are in the [model release guide](../../../Miscellaneous/MODEL_RELEASE_AND_BACKEND.md).
