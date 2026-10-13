# RoadGuard vision model

A owns the eight-class RDD2022ES data pipeline, local YOLO11n/YOLO11s training, checkpoint recovery, evaluation and backend inference adapter. See [Step 8 acceptance evidence](../../Miscellaneous/STEP8_VISION_ACCEPTANCE.md) for what has actually run and its limitations; implementation alone does not establish model accuracy.

The source is `juusos/rdd2022es` version 1. The ordered IDs 0–7 and source names are fixed by [label_schema.json](label_schema.json). These images are not from Jurong; visual modifiers such as wide, sunken and deep are not measured dimensions or engineering priorities. The [original audit](../../Miscellaneous/DATASET_AND_LABEL_AUDIT.md) retains the publisher's conflicting BY-SA description and BY-NC-SA metadata.

## Reproduce the pipeline

Use the repository environment and run from the repository root:

```powershell
.venv/Scripts/python.exe SystemCode/model/download_data.py
.venv/Scripts/python.exe SystemCode/model/data_pipeline.py prepare
.venv/Scripts/python.exe SystemCode/model/make_smoke.py
```

The resumable downloader verifies byte ranges and the prepared pipeline pins the complete archive SHA-256. Preparation validates all images and boxes, quarantines missing-label and observed EXIF-ambiguous groups, groups source mirrors and exact/conservative perceptual duplicates before a seeded country-aware split, and uses only originals for validation/test. See [data preparation](data_readme.md) for exact rules and remaining scene-independence limits. Prepared hardlinks must remain read-only.

Download official YOLO11n starting weights into `Dataset/pretrained/yolo11n.pt` before training. The inspected source is the [Ultralytics v8.3.0 asset](https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt), 5,613,764 bytes, SHA-256 `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`. This is a COCO checkpoint for transfer learning, not an eight-class RoadGuard checkpoint.

Install the optional pinned GPU dependencies, interrupt/resume a smoke run, then train/evaluate using the [training guide](TRAINING.md). The generic example specifies 30 epochs; the runner currently validates bounded configurations up to 60 epochs, while every actual run requires its own authorized frozen configuration. Completed work comprises the historical ten-epoch baseline, the paired 30-epoch comparison and one authorized additional 40-epoch YOLO11s fine-tune. The runner limit does not authorize another run. Training and inference stay offline after explicit asset/dependency preparation.

## Artifacts and integration

All bulk data, manifests, runs, checkpoints, predictions, caches and actual uploads/database evidence are under ignored `Dataset/`. Git keeps source, configuration examples, tests and small summary evidence only. Keep best/last and the latest/previous full recovery checkpoints; validated cleanup has an explicit cache allowlist and cannot delete raw data or model evidence.

Validation exports `roadguard-model-v1` with local weights and hashes, source names, data/model version and inference parameters. The [backend real-vision guide](../../Miscellaneous/REAL_VISION_API.md) explains `ROADGUARD_VISION_MANIFEST_PATH` and `mode=real`. Every nonempty real result requires review; the detector is real, while the business rules, simulated task location and resulting task remain marked demo. Numerical validation does not calibrate automatic acceptance or establish engineering readiness.

The authorized follow-up [YOLO11n/YOLO11s 30 epoch comparison protocol](COMPARISON30.md) preregisters matched independent COCO initialization, exact epoch/batch evidence and validation-only selection. `compare_models.py` prepares frozen local configs and verifies both completed runs before recommending a manifest; it does not change the running backend or use held-out test results for selection.

The [completed supervisor acceptance](../../Miscellaneous/VISION_30_EPOCH_COMPARISON.md) records both 30-epoch runs, fixed-threshold errors, actual CPU latency and selected-model HTTP checks. YOLO11s has higher validation mAP but more false positives at confidence 0.25. `analyze_errors.py` produces validation-only diagnostics; `benchmark_cpu.py` measures the matched backend image preparation and real inference path. The selected manifest is a local recommendation, not an automatic change to the running backend.

The [balanced precision/recall follow-up](../../Miscellaneous/BALANCED_VISION_OPTIMIZATION.md) did **not** meet both 70% targets. Its selected `new_best832` checkpoint at confidence 0.25 achieved eight-class micro P/R/F1 of **50.52% / 52.00% / 51.25%** at class-aware IoU≥0.5, versus **48.62% / 51.20% / 49.88%** for the parent at 640. This is a small validation-tuned gain; the sunken-alligator class declined, and macro F1 is only 42.62%. IoU0.3, class-agnostic and four-family results are separate diagnostics and retain the eight source types. Native validation mAP50/mAP50–95 were 40.16%/20.27%, measured under the validator's distinct curve protocol.

`balanced_metrics.py` exports each model/resolution once at confidence 0.001 and performs the frozen global confidence sweep offline; see [metric definitions](BALANCED_METRICS.md). The 40-epoch run took 4,762.9 seconds with seed 42; best is epoch 10 and last epoch 40. Recovery/numerical checks, 761 regression tests passed with one additional Windows symlink-permission skip, 44 guard tests and 11 isolated real HTTP cases passed. These checks establish reproducible execution and integration, not recognition acceptance or independent generalization. [Shareable evidence](../experiments/vision/README.md) links the four candidates, all eight class supports and curves. Data-label review and rare-type support work should precede another blind epoch extension.

The local recommended manifest (`Dataset/balanced70/selected_model_manifest.json`) points to the new best checkpoint with confidence 0.25, NMS IoU 0.7 and imgsz 832, remains experimental, and requires explicit opt-in through the real-vision guide. Existing PyCharm settings, environment variables and running backend were not changed. After acceptance, cleanup deleted only train/val label caches, releasing 4,797,603 bytes (4.80 MB / 4.58 MiB). Raw data, old/new checkpoints and bulk evidence remain in ignored `Dataset/`.

## Completed inference-method follow-up

The [eight-method comparison](../../Miscellaneous/INFERENCE_OPTIMIZATION.md) added no training. Original-plus-horizontal-flip inference at 832, class-aware global NMS 0.5 and confidence 0.30 improved validation micro Precision/Recall from 50.52%/52.00% to **53.02%/53.26%**. Both 70% targets remain unmet; some rare-class recalls declined. The exact experiment recipe took 142.64 ms median CPU time versus 85.19 ms for the baseline on 40 fixed validation images. This is validation-tuned evidence, and the six exploratory external photos still include a missed obvious pothole.

`inference_experiments.py` provides atomic per-image recovery, explicit flip/tile geometry, class-aware cached NMS and two-model fusion, and fixed eight-candidate comparison. It preserves the old `balanced_metrics.py` export contract. [The frozen plan](../experiments/vision/inference_followup_plan.json), [clarifications](../experiments/vision/inference_followup_clarifications.json) and [results](../experiments/vision/inference_followup_summary.json) define exact settings and selection. A composite recipe cannot be activated by the existing single-weight model manifest; no backend/DTO integration, business thresholds or running model were changed. Keep the original checkpoints and all evidence in ignored `Dataset/`.
