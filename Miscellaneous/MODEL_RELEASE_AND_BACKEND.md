# Current model release and backend integration

Date: 2026-10-13; owner: A. At the initiator's request, this publishes the best trained weight and integrates it without new training. Contract **a-workflow-v5**, FastAPI documentation **0.8.0**; snapshot a-task-query-v1 unchanged.

2026-10-14: the user requested default weights in `SystemCode/backend/roadguard/model/`, committed as one ordinary Git file for clone/pull. Model bytes/parameters/API behavior are unchanged; raw data/checkpoints remain local in Dataset/.

## Selected model

YOLO11s balanced40/img832 best checkpoint (epoch 10), byte-identical to the previously selected best:

- `roadguard-yolo11s-single-v1.pt`, 19,218,837 bytes.
- SHA-256 `464f5f2af596140f71583e974146f10819765adf851bc8ac73198b7fa7f51488`.
- Eight RDD2022ES classes 0–7; wide/deep distinctions retained.
- Main-damage-per-image setting: original-image inference 832, raw confidence filter 0.20, NMS IoU 0.70, at most 100 raw detections, CPU FP32.
- Primary suggestion: raw confidence × fourth root of box-area ratio. HTTP returns at most one box; database retains competition warnings/all raw evidence.

“Best” means the completed experiments' balanced choice for this scenario, not highest on every metric. Multi-object detection previously selected original-plus-flip; single-primary calibration selects original-only with the same weights. On 377 confirmed images in the [single-target experiment](SINGLE_DAMAGE_OPTIMIZATION.md), image-level eight-class Precision/Recall were **61.63%/61.99%**; neither 70% target was met, and this was not independent real-world testing. Obvious pothole photos and AI imagery still failed. Release remains experimental. The user confirmed raw primary confidence ≥0.60 creates a Task, below requires review; this business behavior does not improve model accuracy.

## GitHub contents

Source, manifest, evaluation summary, tests, docs and the 19,218,837-byte deployment weight enter main through PR. This ordinary Git binary uses no LFS; authorized members receive it through clone/pull. CI checks exact path/size/hash/manifest consistency. Other weights/all Dataset content remain prohibited.

The [vision-single-v1 Release](https://github.com/HUERJI-code/IRS-PM-2026-08-17-AIS08FT-GRP-Group37-RoadGuard/releases/tag/vision-single-v1) remains a backup download.

Authorization covers only this weight. Dataset images/raw labels/full predictions/uploads/databases/recovery checkpoints stay ignored. Existing best/last/resume-latest/resume-previous are not moved/deleted. Repository remains private.

## First installation for members

Pull main; install backend/optional vision dependencies at root. Below is CPU inference; retain existing GPU training environments per training guide without reinstalling PyTorch:

```powershell
python -m pip install -r SystemCode/backend/requirements.txt
python -m pip install torch==2.10.0 torchvision==0.25.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r SystemCode/model/requirements-vision.txt
```

Clone/pull contains the model; verify:

```text
SystemCode/backend/roadguard/model/roadguard-yolo11s-single-v1.pt
```

This is the default backend location, with no separate download/installer/code change. First real inference checks SHA-256/classes. Start/restart after dependency installation.

To restore the identical Release backup, the installer can verify/copy it:

```powershell
.\.venv\Scripts\python.exe SystemCode/model/install_released_model.py --file "C:\Users\your-username\Downloads\roadguard-yolo11s-single-v1.pt"
```

It checks size/hash and installs atomically at the default location. Identical reinstallation is harmless; different existing bytes are not overwritten. It does not deserialize weights or search other websites. Normal clone/pull needs no installer.

The repository manifest uses the new path. Release attachments/2026-10-13 acceptance retain historical paths/manifest hashes. Use the current repository manifest normally, without downloading Release JSON. Old Dataset/models/ files may remain but are not fallback weights.

The default is the committed [release manifest](../SystemCode/model/releases/roadguard-single-v1.json):

```powershell
.\.venv\Scripts\python.exe -m uvicorn roadguard.main:app --app-dir SystemCode/backend --host 127.0.0.1 --port 8000 --reload
```

Run at repository root. PyCharm Parameters match arguments after `-m uvicorn`. Existing explicit ROADGUARD_VISION_MANIFEST_PATH overrides still win; change to SystemCode/model/releases/roadguard-single-v1.json or remove. `disabled` disables real inference.

Without weights/dependencies, backend/demo still start; first real upload returns 503 detector_unavailable without download/mock fallback. Restart after repair. /health checks app/database only, not model loading.

## API tests and new fields

At `http://127.0.0.1:8000/docs`, POST /api/v1/inspections with JPEG/PNG, Idempotency-Key: real-test-001 and metadata:

```json
{"mode":"real","latitude":1.3405,"longitude":103.706,"road_type":"public_motor_road"}
```

Coordinates are demonstration input, not photo provenance; road type is user-declared. Omit scenario_id for real. See [compact example](../SystemCode/contracts/workflow/real-upload-example.json)/[field reference](INSPECTION_RESPONSE_FIELDS.md). real-primary-example.json remains historical v3 compatibility evidence.

Upload returns only inspection_id/status/detection/task_id. Query the following through GET /api/v1/inspections/{id}; upload no longer returns full inspection/task.

Detail primary_suggestion:

| Field | Meaning |
| --- | --- |
| policy_version / strategy / threshold | Selection configuration frozen at upload |
| detection_id | Primary reference to detections; null without candidate |
| ranking_score | Ranking, not correctness probability or replacement for confidence |
| ambiguous | Similar-score other class/disjoint region; false does not guarantee correctness |
| competing_detection_ids | Raw IDs including primary/competitors |

Ordinary demo/legacy manifests without primary policy return primary_suggestion:null. The default release with no detections returns the object with null detection_id/ranking_score. Missing historical fields load as null, without re-inference/evidence rewriting.

C draws detections[0], or nothing for empty results. All raw evidence stays in the database without an HTTP “all boxes” endpoint. Projection prefers accepted selected_detection_id, then primary_suggestion, then highest-confidence legacy evidence. Historical manual selection may differ; competing IDs can refer internally. Ambiguity warns without overriding confidence routing. Review still accepts retained IDs from the inspection; normal UI uses the sole returned ID.

A real primary raw confidence meeting configured confidence_threshold (default 0.60) returns accepted/task_id. Details expose task/auto_acceptance; input_revision increments once. Below threshold gives pending_review/task_id=null without increment; manual review may accept low scores. Automatic task history.actor_source=system_confidence_policy. Task/rules remain demo. Replays, reads while unavailable, restart and review retain the original suggestion snapshot. SQLite v2 remains without destructive migration.

HTTP clients use a-workflow-v5 InspectionUploadResponse and InspectionResponse/InspectionMutationResponse/InspectionListResponse for detail/review/list, accepting nullable auto_acceptance and at most one detection. Do not parse the single-box view as internal InspectionRecord. Old records are not retroactively tasked/re-inferred. TaskRecord history adds system_confidence_policy; base Detection/Task/snapshot/review fields are unchanged.

## Acceptance

Completed real CPU FP32 uploads of seven known images, comparisons with experimental entry points, retries/restarts, reads and 503 after disabling model, manual review and unique task snapshots. Tests/regression, source hashes and full local evidence location are in the [release summary](../SystemCode/experiments/vision/model_release_summary.json). Numerical consistency establishes integration correctness, not recognition correctness.
