# Step 8: local real vision and reviewed demo tasks

Owner: A. Contract: **a-workflow-v5**. The task snapshot stays **a-task-query-v1**.

The existing image upload endpoint now accepts an explicitly selected detector mode. `mode:"real"` means inference on the uploaded image pixels using a trusted, locally trained eight-class RDD2022ES checkpoint. It does not mean the repair rules, road qualification, simulated department or tasks are production validated.

## Enable the local detector

The default manifest is now `SystemCode/model/releases/roadguard-single-v1.json`. Follow [released model installation](MODEL_RELEASE_AND_BACKEND.md) to obtain and verify its weight from the private repository Release. The base backend and CI do not require Ultralytics; real uploads require the optional runtime and local weight. Set `ROADGUARD_VISION_MANIFEST_PATH=disabled` to disable real inference. An explicit trusted local manifest can still override the default:

```powershell
$env:ROADGUARD_VISION_MANIFEST_PATH = "Dataset/runs/<run-id>/model_manifest.json"
python -m uvicorn roadguard.main:app --app-dir SystemCode/backend --host 127.0.0.1 --port 8000
```

The manifest environment path and relative weights paths resolve from the repository root, independently of the process working directory. Absolute local paths are also accepted as operator overrides. The application starts without loading weights. The first new real upload validates the manifest and weights, then imports the optional runtime and loads the model. A failed load stays unavailable until the application restarts; repair the local configuration and restart. Health checks report database health, not detector readiness. Persisted records, replay, review and demo mode still work when the detector is unavailable.

The backend enforces `YOLO_OFFLINE=true`, `YOLO_AUTOINSTALL=false`, uses `Dataset/tool-cache/ultralytics-backend` for optional runtime settings and disables supported cloud/logging integrations before model loading. It passes a verified existing local `.pt` path and decoded image pixels, never a model alias, remote image URL or omitted source. There is no runtime download, dependency installation or fallback to synthetic detections.

**Only load checkpoints from a source you trust.** PyTorch checkpoint loading may deserialize executable Python data. A digest identifies an approved artifact; it does not turn an untrusted checkpoint into a safe file.

The manifest shape is:

```json
{
  "schema_version": "roadguard-model-v1",
  "status": "experimental",
  "model_version": "rdd2022es-baseline-<run-id>",
  "weights_path": "Dataset/runs/<run-id>/weights/best.pt",
  "weights_sha256": "<64 lowercase hex characters>",
  "source_class_names": [
    "longitudinal crack", "longitudinal crack wide",
    "transverse crack", "transverse crack wide",
    "alligator crack", "alligator crack sunken", "pothole", "pothole deep"
  ],
  "source_dataset": {
    "ref": "juusos/rdd2022es", "version": 1,
    "manifest_sha256": "<64 lowercase hex characters>"
  },
  "inference": {"conf": 0.25, "iou": 0.7, "imgsz": 640},
  "evaluation_path": "Dataset/runs/<run-id>/evaluation.json"
}
```

Training/evaluation metadata may accompany these fields. The loader checks the actual checkpoint names and ID order against all eight source names from [label_schema.json](../SystemCode/model/label_schema.json), in addition to the manifest names and weights SHA-256. A COCO checkpoint cannot be relabelled as road damage by changing the manifest. It must be a detection model. The runtime bounds `imgsz` to 32–1280, `conf`/`iou` to finite numbers greater than zero and at most one, uses CPU inference and caps results at 100 detections. The manifest accepts exactly `conf`, `iou`, and `imgsz` as inference settings and explicitly uses CPU FP32. An optional top-level `primary_policy` contains exactly `policy_version:single-damage-v1`, a supported `strategy`, and `threshold` equal to inference `conf`; the release uses `area_quarter` and 0.20. Old manifests without this object return no primary suggestion.

## Upload and detector provenance

POST /inspections now returns only inspection_id, status, detection and task_id. detection is one object (label, confidence, bbox_xyxy, image_width, image_height), or null. Query GET /inspections/{id} for full provenance, review IDs and record_version; GET /tasks/{id} provides the task. Review/list/detail responses retain their previous shape. HTTP 201 is new, 200 is an idempotent replay; upload responses no longer include replayed or input_revision.

Use the existing `POST /api/v1/inspections` multipart fields `image` and `metadata`, with an `Idempotency-Key` header. For real inference, metadata must omit `scenario_id`, including a null-valued field:

```json
{"mode":"real","latitude":1.3405,"longitude":103.706,"road_type":"public_motor_road"}
```

The coordinate illustrates request syntax; it is not an independently verified road location or proof that the photograph was captured in Jurong. The existing frozen polygon validation and explicitly user-declared road type still apply.

For demo mode, the previous format stays valid and a named scenario remains mandatory:

```json
{"mode":"demo","scenario_id":"low_confidence","latitude":1.3405,"longitude":103.706,"road_type":"public_motor_road"}
```

The same limits apply to both modes: one completely decoded JPEG/PNG, at most 8 MiB and 20 million pixels; bounded multipart body and metadata; no animation. The existing image preparation path normalizes EXIF orientation and removes original metadata. Model input and boxes refer to the dimensions of that normalized original image, before inference resizing. Invalid IDs, confidence, nonfinite values, mismatched dimensions or out-of-bounds boxes fail inference; the adapter does not silently clip malformed model output. `annotated_image_url` remains null; the frontend can render the returned boxes.

Real `InspectionResponse` responses contain `mode:"real"`, `demo_scenario_id:null`, `model_version`, `model_weights_sha256` and `model_manifest_version:"roadguard-model-v1"`. Each real `Detection` has `is_demo:false` and matching image dimensions/model version. The inspection itself retains **`is_demo:true`**, because its business context and rule assumptions remain simulated. Those meanings are stated in `decision_trace`; clients should use `mode` and per-detection `is_demo` to display detector provenance.

Detail responses use a-workflow-v5: detections has at most one box, and nullable auto_acceptance records automatic acceptance. primary_suggestion preserves the original ranking snapshot; competing IDs can reference internally retained evidence. The returned box is the accepted selection, then the original suggestion, or highest-confidence legacy evidence. See the [field definitions and migration](MODEL_RELEASE_AND_BACKEND.md). Strict clients must use InspectionResponse, including auto_acceptance and the new TaskHistory actor_source system_confidence_policy. See [all response fields](INSPECTION_RESPONSE_FIELDS.md). Old records default it to null and are not re-inferred. Clients parsing a-workflow-v1 with `extra=forbid` must update their inspection record schema to accept these added provenance fields and the real mode. Existing persisted demo records load with default null checkpoint fields, retain their named scenario and preserve their original evidence/history. SQLite schema remains v2; there is no destructive migration or task-query contract change.

## Primary confidence gate and task creation

The user-selected single-primary-auto-v1 workflow first chooses the primary box using the existing manifest ranking policy (highest confidence for legacy manifests without a primary policy). Only that box's raw confidence is compared with the configured RulePolicy.confidence_threshold, default 0.60, inclusively. Passing creates one Task atomically and returns accepted with auto_acceptance; otherwise nonempty results wait in pending_review. Competing low scores do not block the chosen high score; a high-scoring secondary box does not replace a low-scoring primary. Ambiguity remains a warning, not a second gate. The threshold is an explicit project setting, not a calibrated accuracy claim. Inference conf remains 0.20 in the released manifest, so lower-confidence evidence remains available for review. An empty result becomes `no_detection` without a task; it does not prove that the image is damage-free.

For pending_review records, use the existing review endpoint to confirm one detection, correct its label or dismiss the inspection. Original detection labels, confidence, boxes and checkpoint provenance remain frozen; review records remain user-declared and identity-unverified. Confirmation/correction uses the inspection's frozen demo policy to create one task. The resulting `TaskRecord`, its public `Task` projection and `TaskSnapshot` retain `is_demo:true`. Creating the task increments the shared input revision once; a pending/no-detection inspection or dismissal does not. Dispatch/business assumptions have not become real merely because the detector reads pixels.

## Failure, retries and concurrency

| HTTP | Code | Meaning |
| --- | --- | --- |
| 422 | `validation_error` | Invalid metadata or detector mode/scenario combination |
| 503 | `detector_unavailable` | Disabled detector, missing optional dependency, unreadable/invalid manifest or checkpoint, incorrect digest or class names |
| 502 | `detector_inference_failed` | Prediction failed or returned an invalid result; no inspection/task/image is saved |
| 409 | `idempotency_conflict` | An existing key was used with different image bytes or metadata |

Errors use fixed public messages; they do not expose local paths, checkpoint content or exception text. Storage/database errors keep their existing codes and rollback behavior.

Durable idempotency is checked in a consistent read transaction before loading a model. An identical replay returns the current persisted resource and input revision even after a model disappears. Per-key locks prevent duplicate inference for concurrent same-key requests in one application process; model load/predict is separately serialized. Inference happens outside the SQLite write transaction so unrelated mutations can proceed. The durable key is checked again inside the write transaction; multiple application processes may each infer the same new request, but only one persists it. Failed commits roll back records, keys and revision, and clean up the newly saved image under the existing file/SQLite limitations.

## Verification

`SystemCode/tests/test_real_vision.py` injects detectors/model objects and covers modes, review-before-task behavior, genuine-vs-demo flags, no detection, replay while unavailable, concurrency/write-lock separation, rollback, names/digests, malformed predictions and HTTP persistence/restart. These tests do not establish numerical model quality. Genuine trained-weight inference and held-out numerical evaluation must be reported from their actual run artifacts separately. The adapter follows the [Ultralytics prediction interface](https://docs.ultralytics.com/modes/predict/); the project pins its optional runtime version in the model dependency list.
