# Step 8 vision implementation and acceptance record

Date: 2026-10-13; owner: A. Development was divided among GPT-6.1-sol subagents; the main agent performed independent acceptance.

## Scope at this stage

Full-data preparation, recoverable training/evaluation and real-detector integration are implemented, with an actual 10-epoch GPU baseline and real HTTP acceptance. Functional acceptance passed; the model remains `experimental`, and numerical validity does not establish production accuracy. Business rules remain demo assumptions and every nonempty real detection requires manual review. B's routing, C's frontend/assistant and cross-module integration are outside this step.

## Data and hardware

- Fixed data: `juusos/rdd2022es` version 1, not Jurong field imagery.
- Complete ZIP: 2,611,933,018 bytes; SHA-256 `3ceb9de3b7ca7083379e4fc62748bafcda0a82d1baf4627cf87891c9595fa775`.
- All large files remain under root `Dataset/`, entirely excluded by `.gitignore`. Raw data, splits, models, databases and logs are not uploaded to GitHub; source, tests, example configuration and small statistical evidence remain in Git.
- Local RTX 5090, 32 GB VRAM, CUDA 12.8 / PyTorch 2.10.0 GPU computation verified. YOLO library pinned to Ultralytics 8.4.176; official initial YOLO11n COCO weights are not an eight-class road model.
- First per-image audit completed 25,600 images, finding `India_000430` (EXIF 8) and `India_004098` (EXIF 3). Original/mirror groups were quarantined after exact-hash verification, without editing images or guessing label rotation. First failure report: `Dataset/audits/initial-exif-failure/`.
- Existing missing-label `Czech_001003` original/mirror and orphan `India_001032.txt` were quarantined too; see [data pipeline](../SystemCode/model/data_readme.md).

The second full audit fully decoded all 25,600 images and validated labels, coordinates and mirror relationships, quarantining the three documented original/mirror groups without further unresolved errors. Grouping combines originals/mirrors, identical content and conservative near duplicates, adding 26 near-duplicate edges. Seed 42, country-stratified group-level approximately 70/15/15 splits have disjoint group IDs. Approximate checks cannot find every adjacent scene; without capture sequences/GPS, complete scene-leakage prevention cannot be claimed.

| Split | Images | Groups | Boxes | Use |
| --- | ---: | ---: | ---: | --- |
| train | 17,916 | 8,939 | 25,314 | 8,958 originals and their mirrors |
| val | 1,921 | 1,917 | 2,623 | Originals only; training selection |
| test | 1,918 | 1,915 | 2,673 | Originals only; evaluation after model freezing |

Prepared files reuse raw images/labels via 43,510 hard links, avoiding a second copy. Post-training checks reverified original/annotation SHA-256 across all 25,600 manifest rows: contents unchanged, prepared files still point to original content and groups remain disjoint. Audits/splits are in `Dataset/prepared/`.

## Actual training and metrics

Run: `Dataset/runs/yolo11n-rdd2022es-baseline10-seed42/`. YOLO11n transferred from official COCO weights to eight classes: 10 epochs, imgsz 640, batch 32, seed 42, AdamW, lr0 0.001, lrf 0.01, warmup 1, workers 4, amp=false, cache=false, fliplr=0. `results.csv` cumulative epoch time was approximately 496.9 seconds, excluding download/preparation, separate evaluation and acceptance. The 30-epoch example was not run here.

After freezing best weights, evaluate 1,921 validation and 1,918 test images separately. All 499 parameter/buffer tensors were finite and eight class names/order matched. Actual percentages:

| Split | Precision | Recall | Macro F1 | mAP@50 | mAP@50-95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| val | 35.04 | 42.94 | 37.61 | 34.28 | 16.93 |
| test | 39.15 | 41.21 | 38.56 | 36.19 | 18.38 |

| Class | val boxes | val AP@50 | test boxes | test AP@50 |
| --- | ---: | ---: | ---: | ---: |
| longitudinal crack | 941 | 54.93 | 908 | 51.67 |
| longitudinal crack wide | 148 | 29.63 | 202 | 41.29 |
| transverse crack | 541 | 44.67 | 573 | 46.48 |
| transverse crack wide | 46 | 17.67 | 65 | 24.00 |
| alligator crack | 526 | 50.66 | 488 | 44.67 |
| alligator crack sunken | 77 | 23.36 | 65 | 29.69 |
| pothole | 299 | 26.74 | 336 | 26.46 |
| pothole deep | 45 | 26.57 | 36 | 25.23 |

This initial baseline remains weak on rare classes and potholes. Detection mAP is not the fraction of correctly recognized images. P/R/F1 come from each curve's maximum mean-F1 descriptive point; test data did not select models, training parameters or deployment thresholds. Curves and confusion matrices use retained conf=0.001 predictions; background counts do not directly represent backend conf=0.25 false positives. Backend 0.25 filters returned predictions and is not calibrated automatic acceptance.

Metrics use the pinned Ultralytics native eight-class evaluator. Optional `faster-coco-eval` was absent with explicit log warnings; no alternate COCO evaluator is claimed. Original reports, per-class metrics, PR curves, confusion matrices, prediction JSON and visualizations remain in the run directory. Small evidence: [summary](../SystemCode/experiments/vision/step8_baseline_summary.json) and [epoch results](../SystemCode/experiments/vision/baseline 10_results.csv).

Best SHA-256: `6701105881507946244e27d4155fa9febc2ad0bd2657bf52ee519a824c1619de`. The worktree was uncommitted during training; metadata retains HEAD, dirty status and source hashes. Later Dataset/YAML path hardening changed neither model, optimizer, data, configuration nor evaluator. Recorded base HEAD is not the complete training-source version.

## Checkpoints and recovery

Each completed epoch atomically saves `resume-latest.pt` and retains `resume-previous.pt`, including live model, EMA, optimizer, scheduler and RNG states. `best.pt`/`last.pt` retain best/final models; independent recovery checkpoints keep full state. Interruption loses the unfinished epoch and resumes after the latest completed one.

Actual recovery acceptance passed: separate fixed 64/32-image train/val smoke, two epochs. Deliberately interrupt after durable epoch 1, explicitly resume `resume-latest.pt`, continue epoch 2. `resume_verified.json`: zero-based start_epoch=1, optimizer_state_entries=255. Subsequent validation produced an eight-class manifest. Smoke quality is excluded from formal baseline metrics.

Formal checkpoints retain latest epoch 10, previous epoch 9, best and last. See [training](../SystemCode/model/TRAINING.md) for commands, corruption fallback and configuration identity. A completed ten-epoch run cannot restart via resume; new experiments require new names/configuration.

## Interfaces and subsequent integration

Contract extended to `a-workflow-v2`; [real vision API](REAL_VISION_API.md). `mode=demo` preserves prior behavior; `mode=real` loads configured local weights without simulated fallback. Real Detection.is_demo=false; Inspection/Task.is_demo=true identify demo business rules/location scenarios. Nonempty real results require review; missing model returns 503. Existing uploads replay safely while the detector is unavailable.

B's `a-task-query-v1` is unchanged. C must update inspection schemas, display model provenance and real-detection/demo-business distinctions, and update its `a-knowledge-v2` index.

Real HTTP acceptance used a random free local port, isolated database/uploads, never 8000 and without modifying PyCharm service. First annotated validation original by file order, `Czech_000006`, yielded one real longitudinal_crack prediction. Submitted Jurong coordinates are simulated, not photo location. Review creates one task, completion changes snapshot revision 0->1->2; upload/review retries duplicate nothing. Stop the isolated service, disable model and restart: same upload replays, completed task/history survive, new real upload returns 503. Eleven responses/logs: `Dataset/evidence/http-acceptance/`. Automated review calls test APIs, not expert agreement with detections.

Set in local PyCharm Run Configuration -> Environment variables:

```text
ROADGUARD_VISION_MANIFEST_PATH=Dataset/runs/yolo11n-rdd2022es-baseline10-seed42/model_manifest.json
```

After restarting, upload `mode:"real"` without `scenario_id`. See [real vision API](REAL_VISION_API.md); demo remains usable when this variable is unset by default.

## Storage cleanup

After training, val/test evaluation and main-agent HTTP/data-integrity acceptance, preview then apply cleanup:

- 156 redundant download chunks/hash files: 2,611,938,166 bytes; before deletion recheck full ZIP SHA-256, absolute paths, file allowlist and absence of symlinks.
- Three reconstructible YOLO label caches: 5,252,792 bytes; only prepared/labels train/val/test.cache.
- Total **2,617,190,958 bytes, approximately 2.62 GB (2.44 GiB)**.

Raw ZIP, images/labels, splits/hashes, best/latest/two recovery weights, configuration/logs/evaluation remain. No virtual environments or shared system caches were removed. Records: run `cleanup-*.json` and `Dataset/evidence/download-parts-cleanup-*.json`. Small label caches regenerate on training/validation.

## Validation evidence

- Full Python regression: **611 passed, 1 skipped**. Current Windows user cannot create a real symlink; Linux CI covers that path. One Starlette/httpx deprecation warning does not affect results.
- CI guard tests: **44 passed**; `pip check` passed.
- Actual GPU recovery smoke, full ten epochs, val/test evaluations, isolated HTTP and post-training data-hash verification passed.
- Dataset is entirely ignored; verify its absence from staging before commits. Upload only source/docs/example configuration/small statistics.

Business accuracy acceptance and calibrated auto-acceptance were not defined. Further improvement must use train/val. This test set has now been inspected; preserve its use history and do not repeatedly tune to these results while calling it unused.
