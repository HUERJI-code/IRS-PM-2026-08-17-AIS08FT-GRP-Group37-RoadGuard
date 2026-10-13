# RoadGuard vision model

A owns the eight-class RDD2022ES data pipeline, local YOLO11n training, checkpoint recovery, evaluation and backend inference adapter. See [Step 8 acceptance evidence](../../Miscellaneous/STEP8_VISION_ACCEPTANCE.md) for what has actually run and its limitations; implementation alone does not establish model accuracy.

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

Install the optional pinned GPU dependencies, interrupt/resume a smoke run, then train/evaluate using the [training guide](TRAINING.md). The default example permits at most 30 epochs; each actual run has its own frozen local configuration. The first bounded baseline uses ten epochs. Training and inference stay offline after explicit asset/dependency preparation.

## Artifacts and integration

All bulk data, manifests, runs, checkpoints, predictions, caches and actual uploads/database evidence are under ignored `Dataset/`. Git keeps source, configuration examples, tests and small summary evidence only. Keep best/last and the latest/previous full recovery checkpoints; validated cleanup has an explicit cache allowlist and cannot delete raw data or model evidence.

Validation exports `roadguard-model-v1` with local weights and hashes, source names, data/model version and inference parameters. The [backend real-vision guide](../../Miscellaneous/REAL_VISION_API.md) explains `ROADGUARD_VISION_MANIFEST_PATH` and `mode=real`. Every nonempty real result requires review; the detector is real, while the business rules, simulated task location and resulting task remain marked demo. Numerical validation does not calibrate automatic acceptance or establish engineering readiness.

The authorized follow-up [YOLO11n/YOLO11s 30 epoch comparison protocol](COMPARISON30.md) preregisters matched independent COCO initialization, exact epoch/batch evidence and validation-only selection. `compare_models.py` prepares frozen local configs and verifies both completed runs before recommending a manifest; it does not change the running backend or use held-out test results for selection.
