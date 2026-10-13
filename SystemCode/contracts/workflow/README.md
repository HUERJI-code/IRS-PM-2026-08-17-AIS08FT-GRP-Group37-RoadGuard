# a-workflow-v3 response example

`real-primary-example.json` is an actual inspection response from isolated local release acceptance using the previously downloaded worn-pavement photograph. It contains real-model detections, a single display suggestion and simulated business coordinates; it is not an accepted task or an expert annotation. The image itself is not distributed here, and its generated image URL is only an example from that temporary database.

Validate using `roadguard.schemas.workflow.InspectionRecord`. The `primary_suggestion.detection_id` references retained evidence, while `selected_detection_id` remains null and status remains pending_review. Full field definitions, model installation and client compatibility are in the [model release guide](../../../Miscellaneous/MODEL_RELEASE_AND_BACKEND.md).
