# Inference optimization and training-data diagnosis

Owner A; 2026-10-13. Target remains correct detection of the original eight classes with both Precision and Recall above 70% at one global confidence. This round tests existing-weight inference with zero training, zero weight downloads and zero dependency upgrades. Business APIs, manual-review policy and running backend remain unchanged.

## Preregistered comparisons

The [plan](../SystemCode/experiments/vision/inference_followup_plan.json) and [clarifications](../SystemCode/experiments/vision/inference_followup_clarifications.json) froze eight candidates, budgets, input hashes and selection before execution. All use existing 1,921 validation originals/2,623 boxes. Previously used development validation is not a new independent test.

| Candidate | Method | Question |
| --- | --- | --- |
| baseline 832 | Current best, 832, full image | Existing baseline P50.52%, R52.00% |
| renms832 | Reapply class-aware NMS 0.5 to cached results | Can fewer duplicate boxes improve precision? |
| standard640 | Current best, full image640 | Does lower resolution fit source scales? |
| standard960 | Current best, full image960 | Does higher resolution reduce misses? |
| flip832 | Original plus horizontal flip, two views | Can view candidates complement each other? |
| tiles832 | Full image plus four overlapping corners, five views | Does enlarged small damage improve recall? |
| ensemble_union | Merge parent 640/current832 candidates | Do checkpoint errors complement each other? |
| ensemble_paired | Same-class paired/rescored boxes from two models | Does agreement improve ranking? |

All new views use FP 32, batch 1, GPU 0, confidence floor0.001, class-aware within-view NMS 0.7, max100 boxes/view and after fusion. Standard candidates retain original-view outputs; others use class-aware NMS 0.5. Tile dimensions are ceil(original dimension x0.625), restored to original coordinates, retaining full image. Additional budget: 17,289 view inferences.

Pairing is not standard WBF: fixed greedy same-class one-to-one IoU>=0.55 pairing, confidence-weighted coordinates, mean paired score and half-score single-model boxes. Discard scores below 0.001. This ranking heuristic is unvalidated, not calibrated correctness probability; parent/child fine-tuned checkpoints are not independent voters.

Cached candidates already passed NMS 0.7/top100, so re-NMS 0.5 differs from rerunning detector NMS 0.5. Flip/tiles are explicitly implemented here; SAHI is not installed and no library multiscale-TTA reproduction is claimed.

## Metrics and selection

Primary metrics retain eight-class same-class one-to-one IoU>=0.5. IoU>=0.3 diagnoses localization only, not selection/primary replacement. All methods use the same 25 thresholds, maximizing `min(micro P,micro R)`, then macro F1, then micro R; ties retain earlier threshold/candidate.

Report both overall winner and recommendable candidate. Recommendations must strictly improve **both P and R** at their selected point versus baseline; otherwise retain baseline. Report per-class support/regressions without hiding rare-class decline. Composite methods output experimental recipes, not disguised single-weight `roadguard-model-v1` manifests.

Atomic per-image output supports `--resume` with identical weights/data/source/runtime/settings identities. Bulk evidence remains under ignored `Dataset/inference-followup/`. Original best/last/full recovery checkpoints remain retained.

## Data and loss diagnosis

Targeted review covers20 training originals: four each wide-longitudinal, wide-transverse, sunken-alligator, deep-pothole plus four empty-label images. This is not full-dataset quality assessment; labels are unchanged. IDs, image/label SHA256, boxes/contact sheets: `Dataset/inference-followup/data-audit/`.

- 8,958 original training images, 2,865 empty(32.0%), with equal mirror counts. Mirrors add presentations, not independent scenes. Rare original boxes: wide transverse243, sunken alligator311, deep pothole193.
- Two empty-label images show crack-like seams/textures; source annotation policy and human review must determine whether they are damage. Empty-label images are not automatically reliable hard negatives.
- Metadata contains16 same-family/different-subclass box pairs at IoU>=0.9, review candidates only. Overlap does not confirm label errors; single RGB images cannot independently establish engineering depth.
- Installed Ultralytics 8.4.176 class weights affect positive/negative BCE terms, not only rare positives. Albumentations is absent; its default augmentation was not used.
- Previous epochs 10->40: train classification loss 1.661->0.939, val 2.214->2.481, native mAP50-95 0.203->0.182. Consistent with a generalization gap, but augmentation changed too; not single-parameter causality or support for blindly adding epochs.

At confidence 0.05 current best reaches eight-class recall 72.05% but precision 23.68%(TP 1890, FP 6090). Within this candidate pool, dual 70 requires at least 1,837 TP and fewer than 787 FP: retain at least 97.2% existing TP while filtering at least 87.1% FP. Arithmetic illustrates difficulty, not a prediction that a new method achieves it.

If inference gains remain limited, investigate a candidate-box second-stage review model with damage/background rejection plus the original eight classes, using training crops and manually screened hard negatives. A plain eight-class classifier must assign background to damage and cannot alone solve false positives. Freeze a separate small training budget, preserve source/mirror groups and evaluate the complete two-stage pipeline. Do not feed validation false positives into training or relabel automatically without review.

## References

[Ultralytics tiled inference](https://docs.ultralytics.com/guides/sahi-tiled-inference/) and [SAHI guide](https://obss.github.io/sahi/guides/sliced-inference/) explain enlarging small objects with slices and merging detections; this project uses fixed corner tiles.

[Ultralytics TTA](https://docs.ultralytics.com/yolov5/tutorials/test-time-augmentation/) explains multiview inference. Here only explicit original/flip views are compared, not its YOLOv5 implementation. [Weighted Boxes Fusion](https://arxiv.org/abs/1910.13302) informs multimodel fusion; our frozen pairing protocol defines behavior, without borrowing the paper's name as an effectiveness guarantee.

## Results

All eight candidates completed all validation originals/25-threshold comparisons. None reaches primary dual 70% on the grid; no class reaches both P/R70%. Percentages:

| Candidate | confidence | TP/FP/FN | P | R | F1 | macro F1 |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| baseline 832 | 0.25 | 1364 / 1336 / 1259 | 50.52 | 52.00 | 51.25 | 42.62 |
| renms832 | 0.25 | 1347 / 1159 / 1276 | 53.75 | 51.35 | 52.52 | 43.30 |
| standard640 | 0.25 | 1279 / 1273 / 1344 | 50.12 | 48.76 | 49.43 | 39.54 |
| standard960 | 0.25 | 1331 / 1378 / 1292 | 49.13 | 50.74 | 49.92 | 42.00 |
| flip832 | 0.3 | 1397 / 1238 / 1226 | 53.02 | 53.26 | 53.14 | 43.08 |
| tiles832 | 0.35 | 1271 / 1404 / 1352 | 47.51 | 48.46 | 47.98 | 38.70 |
| ensemble_union | 0.3 | 1408 / 1321 / 1215 | 51.59 | 53.68 | 52.62 | 43.70 |
| ensemble_paired | 0.2 | 1446 / 1362 / 1177 | 51.50 | 55.13 | 53.25 | 44.09 |

Overall winner and strict-both-metrics recommendation: **flip832, confidence 0.30**. Versus baseline, P +2.50 percentage points, R +1.26,33 more TP, 98 fewer FP/33 fewer FN. Macro P/R/F1=43.24%/43.46%/43.08%; macro recall is slightly below baseline 43.52%, so not universal class improvement. Paired fusion has higher recall 55.13% but precision 51.50%, losing the frozen balanced ranking.

| ID/class | support | Baseline P/R/F1 | flip832 P/R/F1 |
| --- | ---: | --- | --- |
| 0 longitudinal crack | 941 | 57.66 / 60.79 / 59.18 | 60.51 / 63.02 / 61.74 |
| 1 longitudinal crack wide | 148 | 38.07 / 45.27 / 41.36 | 38.17 / 47.97 / 42.51 |
| 2 transverse crack | 541 | 50.28 / 49.54 / 49.91 | 53.23 / 50.28 / 51.71 |
| 3 transverse crack wide | 46 | 36.84 / 30.43 / 33.33 | 36.36 / 26.09 / 30.38 |
| 4 alligator crack | 526 | 57.89 / 54.37 / 56.08 | 62.86 / 54.37 / 58.31 |
| 5 alligator crack sunken | 77 | 24.49 / 31.17 / 27.43 | 28.21 / 28.57 / 28.39 |
| 6 pothole | 299 | 36.25 / 38.80 / 37.48 | 36.98 / 41.81 / 39.25 |
| 7 pothole deep | 45 | 34.69 / 37.78 / 36.17 | 29.63 / 35.56 / 32.32 |

Wide-transverse, sunken-alligator and deep-pothole recall declines; wide-transverse/deep-pothole F1 declines too. Higher overall scores still reflect common-class support. IoU 0.3 remains supplementary JSON diagnostics, without changing this conclusion.

## CPU and external-image acceptance

Same40 country-balanced validation originals, two warmups each, three rounds/120 measurements, four CPU threads, one interop, FP 32: baseline median **85.19 ms**, P95 **99.00 ms**; flip832 median **142.64 ms**, P95 **160.94 ms**, median about **1.67x** baseline.

Timing includes ImageStore.prepare, normalized PNG decoding, full view/fusion/threshold filtering; excludes weight loading, disk reads, DTO and HTTP/database. This is experimental-recipe CPU verification, not API integration. First timing overlapped six-image CPU inference and is retained but excluded. Formal `acceptance-isolated-v2` had no concurrent inference from this task.

RGB pixels are identical before/after normalization on 40 inputs. Each candidate differs numerically between CPU/GPU on 25 images; each exceeds strict IoU 0.99/score1e-4 tolerance on 23. At same-class IoU 0.5 all flip detections match; baseline lacks one GPU candidate. Summary records CPU repeat consistency/max numerical differences. Full GPU validation metrics are not remeasured full-CPU accuracy.

The existing six real external photos were retested only after selection, with no new selection/tuning. Alligator images remain detected; one road photo gains a right-side crack region, but sunken remains unverified engineering interpretation. An obvious close-up pothole is still missed and speed-bump edge false positives persist. Selected0.30 also filters a previous real-pothole candidate below 0.30. This cannot support operational automatic acceptance. Six photos lack expert GT, so no accuracy calculation. Original outputs, provenance/licenses, new comparisons: `Dataset/inference-followup/external-selected/`.

## Engineering acceptance and delivery limits

- Relevant new/existing metric tests64 passed; full regression790 passed, one Windows symlink-permission skip; CI guards44 passed. Initial default-temp/sandbox TestClient restrictions were resolved using workspace temporary directories for the complete checks.
- Independent review fixed/verified interrupted-cache integrity and source ordering for final fusion score ties. Main agent viewed five training-audit contact sheets and six external comparisons.
- Inference source commit `173d0e1`, SHA256 `e6856697cd5a6bfd816a860b85441b5563f23a55887e4142d1454d11fcb3833f`; both standard resolutions reuse unchanged balanced_metrics.py exporter.
- All input/model/protocol/per-image identities verified. No test images/labels opened for selection; labels, dependencies, business APIs, workflow and PyCharm unchanged.
- All training checkpoints retained. No training/new train.cache/val.cache this round. Prediction evidence is not redundant cache; Dataset remains entirely Git-ignored.

This recipe supports further verification and **does not replace the running model**. Given small gains, CPU costs, rare-class regressions and missed real potholes, prioritize label/hard-negative review, then a budgeted background-rejection second-stage pilot. No dual 70 guarantee or unlimited threshold/epoch experimentation.

Shareable evidence: [summary](../SystemCode/experiments/vision/inference_followup_summary.json), [operating CSV](../SystemCode/experiments/vision/inference_followup_operating_points.csv), [metric chart](../SystemCode/experiments/vision/inference_followup_operating_points.png), [class F1](../SystemCode/experiments/vision/inference_followup_per_class.png), [data diagnosis](../SystemCode/experiments/vision/inference_followup_data_diagnosis.json).

## Reproduction commands

Run from repository root with matching existing weights, data, frozen plan. standard640/960 used the original exporter. Commands illustrate patterns only; use resume/new names for existing outputs, never overwrite evidence.

```powershell
.venv/Scripts/python.exe SystemCode/model/balanced_metrics.py export --weights Dataset/runs/yolo11s-rdd2022es-balanced40-img832-seed42/weights/best.pt --run-name inference-followup-standard640 --imgsz 640 --device 0
.venv/Scripts/python.exe SystemCode/model/inference_experiments.py export --weights Dataset/runs/yolo11s-rdd2022es-balanced40-img832-seed42/weights/best.pt --run-name flip832 --method flip --imgsz 832 --nms-iou 0.5 --device 0
.venv/Scripts/python.exe SystemCode/model/inference_experiments.py analyze --export Dataset/inference-followup/flip832/export.json
```

Tiles: `--method tiles`; cached fusion: `fuse --exports ... --strategy union_nms|paired_score --run-name ...`. `compare --exports ... --run-name ...` requires frozen order baseline 832, renms832, standard640, standard960, flip832, tiles832, ensemble_union, ensemble_paired. Only the new tool supports per-image `--resume`; original exporter rejects existing output. Local task scripts performed CPU/external checks; reports retain their hashes/full timing boundaries without claiming those temporary scripts ship in Git.
