# YOLO11n / YOLO11s 30-epoch comparison and lead-agent acceptance

Date: 2026-10-13; owner A. As authorised, validation errors from the ten-epoch model were analysed first, then YOLO11n and YOLO11s were independently trained for thirty epochs each. GPT-6.1-sol subagents developed analysis, comparison and latency tools. The lead agent reviewed implementation/error examples and ran training, independent validation, integrity checks and real HTTP acceptance.

The preregistered validation mAP50-95 rule selected **YOLO11s at thirty epochs**, exceeding the same-duration n model by **1.07 percentage points**, and by **1.50 percentage points** in mAP@50. Improvement is limited: at fixed confidence 0.25, s detects more objects but also more false positives and is slower on CPU. Selection acceptance does not establish business accuracy. It remains experimental; at this historical stage, all nonempty real detections required review.

## 1. Results on the same basis

All entries evaluate each run’s best.pt on the same **1,921 original validation images, 2,623 annotated boxes and eight classes**.

| Model | Validation mAP@50 | Validation mAP@50–95 | Library P | Library R | Best epoch in training log | Logged training time |
| --- | --- | --- | --- | --- | --- | --- |
| YOLO11n · Historical ten-epoch baseline | 34.28% | 16.93% | 35.04% | 42.94% | 10 | 8.28 minutes |
| YOLO11n · Thirty epochs | 37.27% | 19.16% | 38.26% | 40.74% | 29 | 23.76 minutes |
| YOLO11s · Thirty epochs | 38.77% | 20.23% | 40.62% | 43.48% | 26 | 35.00 minutes |

The previously cited **36.19% is test mAP@50 for the ten-epoch baseline**, which cannot be compared directly as improvement over this table’s validation scores. Candidate test images/annotations were not opened or inferred in this round, and test was not used to select models, thresholds or training parameters. The old baseline test results have already been inspected and cannot be described as an untouched independent new test set.

Library P/R are class means at the operating point selected from validation PR curves, not the fixed conf=0.25 count ratios below. mAP describes detection/localisation over a range of confidence values. The 50 in mAP@50 means box-matching IoU=0.50, distinct from confidence 0.25. Logged training time excludes subsequent independent evaluation, error analysis, CPU timing and HTTP acceptance.

![Validation curves by epoch](../SystemCode/experiments/vision/compare30_curves.png)

Per-class validation mAP@50:

| ID / Source label | Validation boxes | n · Ten epochs | n · Thirty epochs | s · Thirty epochs |
| --- | --- | --- | --- | --- |
| 0: longitudinal crack | 941 | 54.93% | 56.85% | 60.63% |
| 1: longitudinal crack wide | 148 | 29.63% | 34.88% | 34.28% |
| 2: transverse crack | 541 | 44.67% | 48.79% | 48.60% |
| 3: transverse crack wide | 46 | 17.67% | 14.36% | 18.16% |
| 4: alligator crack | 526 | 50.66% | 53.36% | 53.48% |
| 5: alligator crack sunken | 77 | 23.36% | 28.39% | 33.79% |
| 6: pothole | 299 | 26.74% | 29.31% | 30.80% |
| 7: pothole deep | 45 | 26.57% | 32.25% | 30.40% |

s does not win every class: wide longitudinal crack, transverse crack and deep pothole mAP@50 are slightly below n30. Rare classes have only 45–77 validation boxes and unstable single-run estimates. Overall means do not establish reliable deep-pothole or wide-crack recognition.

## 2. Error analysis before interpreting improvement

All three models perform single-image GPU inference on the same 1,921 original validation images with conf=0.25, NMS IoU=0.7, imgsz=640, max_det=100 and FP32. Matching is same-class, confidence-ordered, one-to-one at IoU≥0.5. The table gives all-class micro counts, distinct from official mAP/P/R. The backend actually uses CPU; GPU diagnostics and CPU kernels may differ slightly.

**Purpose of confidence 0.25:** the model scores each candidate box; this threshold filters scores below 0.25. A score of 0.18 is normally filtered, while 0.60 is normally retained, before further processing such as NMS. Scores are not probability-calibrated and cannot mean “25% chance this box is correct” or “25% model accuracy”. Raising the threshold usually reduces false positives but increases misses. This round did not change it.

| Model | TP: Correct matches | FP: Unmatched predictions | FN: Undetected annotations | Fixed-threshold precision | Fixed-threshold recall |
| --- | --- | --- | --- | --- | --- |
| YOLO11n · Historical ten-epoch baseline | 1080 | 978 | 1543 | 52.48% | 41.17% |
| YOLO11n · Thirty epochs | 1236 | 1199 | 1387 | 50.76% | 47.12% |
| YOLO11s · Thirty epochs | 1343 | 1419 | 1280 | 48.62% | 51.20% |

Against n30, s30 misses **107** fewer annotations but adds **220** unmatched predictions. Against n10, it misses **263** fewer and adds **441** unmatched predictions. “Switching to s also reduces false positives” is therefore unsupported. At conf=0.25, s precision is 48.62%, requiring continued review.

The lead agent inspected contact sheets of forty stratified error examples per model: 120 displayed examples in total, with possible overlap across models. Three baseline cases were also inspected individually:

| Fixed case | Baseline → n30 → s30: TP / FP / FN | Observation |
| --- | --- | --- |
| India_001650 | 0/0/2 → 0/2/2 → 0/0/2 | Low-contrast thin cracks remain missed; larger model alone did not resolve this case |
| Japan_003097 | 0/1/1 → 0/1/1 → 0/1/1 | Ordinary/wide classification confusion on the same crack persists |
| Japan_005511 | 1/3/5 → 2/3/4 → 3/5/3 | More overlapping cracks recovered, with more false positives |

s30 FP diagnostics: background 690, localization 358, confusion 266, duplicate 105. FN diagnostics: missed 894, localization 227, confusion 159. These are rules relative to existing annotations, not expert-confirmed causes. Predictions on empty-annotation images may suggest annotation issues but do not establish incorrect labels. Labels were unchanged; visual wide/deep/sunken qualifiers were not treated as measured engineering dimensions or repair grades.

## 3. Comparability controls

Frozen protocol: [COMPARISON30.md](../SystemCode/model/COMPARISON30.md); auditable plan: [compare30_plan.json](../SystemCode/experiments/vision/compare30_plan.json). Training code was committed first as `7cfd6ae82597fddb7a608df632a792df83176668`. Both runs recorded git_dirty=false with matching core-source hashes and environment.

- Each independently initialised from official COCO yolo11n.pt/yolo11s.pt rather than continuing the ten-epoch result. Seed 42; thirty continuous epochs, no OOM batch reduction and no mid-run resume.
- imgsz=640, batch=32, workers=4, device=0, deterministic=true, amp=false, cache=false, fliplr=0; AdamW, lr0=0.001, lrf=0.01, warmup_epochs=1, close_mosaic=2, patience=30. nbs=64 gives nominal accumulation 2; the library adjusts accumulation during warmup.
- Training includes 17,916 images: 8,958 originals and their mirrors. Validation uses originals only. The lead agent rechecked SHA-256 for 39,674 train/val image/label files and matching box counts, and checked grouping metadata across all three splits without overlap.
- Preparation groups mirrored, exact-duplicate and conservative near-duplicate images and retains quarantine records. Grouping does not prove independence of adjacent frames or photographic scenes.
- RTX 5090 32 GB; Python 3.12.14, torch 2.10.0+cu128, torchvision 0.25.0+cu128, Ultralytics 8.4.176. Evaluation uses native library metrics; optional faster-coco-eval was not claimed.
- Preregistered order: validation mAP50-95, then mAP50; only exact equality on both would invoke matched CPU latency as tiebreaker. No latency tiebreaker was needed.

Only one training seed was used, so training variance/statistical significance cannot be estimated. The ten-epoch model is context only: different total epochs change learning-rate schedule progress, so n10→n30 cannot be attributed solely to twenty additional epochs. The fair architecture comparison is n30 against s30.

## 4. Actual CPU latency

AMD Ryzen 7 9800X3D; CPU FP32; four intra-op threads and one inter-op thread. Ten fixed original validation images per country across four countries give forty images shared by both models. Each receives two warmups and three timed passes, totalling 120 measurements. Pass order: n/s, s/n, n/s.

| Model | Actual pre-fusion parameters | Per-image median | Per-image p95 |
| --- | --- | --- | --- |
| n30 | 2,606,584 | 53.27 ms | 63.59 ms |
| s30 | 9,430,888 | 81.87 ms | 91.85 ms |

Timing spans `ImageStore.prepare(bytes)` through `LocalVisionDetector.detect()` returning its DTO, including validation, decode, image normalisation, preprocessing/postprocessing and CPU inference. It excludes disk reads, cold weight loading, HTTP, database and rule/task handling, so it is not complete API response time. Forty fixed images are not production traffic; OS caches, scheduling and temperature may affect measurements.

The first latency run acceptance-v1 failed before timed measurements because current Ultralytics no longer exposes predictor.args.half. Checks were corrected to inspect quantize, actual backend fp16 and CPU/float32 parameters, with added tests. Cache-directory creation order was also corrected. Failed records remain; only acceptance-v2 is valid final evidence, without mixing failed samples.

## 5. Lead-agent acceptance, checkpoints and cleanup

| Check | Actual result |
| --- | --- |
| Application regression | 692 passed, 1 skipped; Windows user lacked actual symlink creation permission, covered by Linux CI |
| CI guard unit tests | 44 passed; attempt blocked by Windows sandbox temporary-directory permissions passed when rerun unchanged in an allowed environment |
| Paired-run evidence | Thirty continuous epochs, actual batch=32, matching shared parameters/input hashes, weights/validation reports |
| Recovery weights | n/s latest=30, previous=29; all readable, finite live/EMA/optimizer tensors, 255 optimiser state entries each |
| Real HTTP | Selected s30 passed eleven response cases through isolated Uvicorn |
| Cleanup | Removed train.cache and val.cache, 4,797,603 bytes total (about 4.8 MB); no data/weights deleted |

HTTP checks cover real upload entering review, upload idempotency, evidence image access, confirmation creating exactly one task, completion emptying the active snapshot/incrementing revision, restart persistence, completed-upload replay with the model disabled and a new real upload returning 503. Real weights/validation photos and synthetic Jurong coordinates verify business integration, not photo location or expert approval. Port 8000 was unused and the user’s PyCharm launch configuration was unchanged.

Each run retains `weights/best.pt`, `weights/last.pt`, `weights/resume-latest.pt`, `weights/resume-previous.pt`, recovery JSON, configuration and logs. best/last serve inference; resume files contain full recovery state. Both completed thirty epochs; resume must not silently extend this experiment. Recovery of a failed final epoch uses previous to replay it, following the [training guide](../SystemCode/model/TRAINING.md). Reading/checking checkpoints here is not a new interrupted-training experiment; the actual two-epoch interruption/recovery test recorded in step 8 remains runtime evidence for that mechanism.

## 6. Using the local model

Selected manifest, relative to repository root:

```text
Dataset/runs/yolo11s-rdd2022es-compare30-seed42/model_manifest.json
```

In the existing PyCharm backend Run Configuration, point `ROADGUARD_VISION_MANIFEST_PATH` at this manifest, then let the user restart the backend. See [real vision API](REAL_VISION_API.md). The running backend environment was not replaced automatically; the old baseline remains. New Git clones do not include local weights. Reproduce using the training guide or obtain/verify them through a separately agreed delivery mechanism.

Selected best.pt SHA-256: `92749da1b1c05f2186e388c9d0cee65cc868613662c5aa21d940d76ec003940a`. Contracts remained a-workflow-v2, a-task-query-v1 and a-knowledge-v2 at this stage. Business contracts/demo rules were unchanged; B/C needed no API changes for this offline experiment.

## 7. Evidence and reproduction

Git retains tools, tests, this record, the [small complete metric summary](../SystemCode/experiments/vision/compare30_summary.json), frozen plan and [n30](../SystemCode/experiments/vision/compare30_n_results.csv)/[s30](../SystemCode/experiments/vision/compare30_s_results.csv) training-curve CSVs. The summary includes data/source/weight/raw-report hashes and acceptance details. Dataset/ is entirely ignored; downloaded data, models, predictions, annotated images, HTTP databases and full logs remain local.

Full local evidence:

```text
Dataset/compare30/{plan.json,summary.json,summary-with-latency.json,integrity.json}
Dataset/error-analysis/{baseline10-val-errors,compare30-n-val-errors,compare30-s-val-errors}/
Dataset/compare30/cpu-latency/acceptance-v2/latency.json
Dataset/compare30/http-acceptance/summary.json
Dataset/runs/yolo11{n,s}-rdd2022es-compare30-seed42/
```

Do not overwrite completed experiments. See the [paired protocol](../SystemCode/model/COMPARISON30.md) for commands, unused run names and input constraints, and [ERROR_ANALYSIS.md](../SystemCode/model/ERROR_ANALYSIS.md) for diagnosis. Examples:

```powershell
.venv/Scripts/python.exe SystemCode/model/analyze_errors.py --weights Dataset/runs/yolo11s-rdd2022es-compare30-seed42/weights/best.pt --run-name new-s-val-errors --device 0
.venv/Scripts/python.exe SystemCode/model/benchmark_cpu.py --repo . --run-name new-cpu-check
.venv/Scripts/python.exe -m pytest SystemCode/tests -q
```

This round’s acceptance scope is complete. Business-threshold/review-load evaluation, targeted checks of rare classes/suspected annotations and Jurong real-scene generalisation remain separately scheduled work. No additional training or threshold change was performed without authorisation. The results demonstrate that these issues persist and do not guarantee that longer training alone will resolve them.
