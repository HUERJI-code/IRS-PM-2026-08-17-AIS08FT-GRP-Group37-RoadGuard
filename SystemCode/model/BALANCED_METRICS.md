# Balanced eight-class validation metrics and offline confidence sweeps

Owner: A. Keep all eight real source classes and seek improved precision and recall together using one global confidence, reducing missed detections. Primary matching IoU is fixed at 0.5; IoU 0.3 only diagnoses localization tolerance and does not replace primary metrics. Four-family and class-agnostic views diagnose errors/subclass confusion only; training labels and eight-class API outputs stay unchanged.

The tool reads all 1921 validation originals from frozen `Dataset/prepared/manifest.jsonl`. It selects val via manifest split metadata and rejects mirrors, excluded samples, inconsistent splits, invalid IDs and changed hashes before opening images/labels. It never opens train/test images/labels. Validation was already used for training/model selection and is reused for these thresholds/model choices; do not claim a new independent holdout, test score or generalization acceptance.

GPU inference and offline sweeps have separate entry points. Each model/resolution infers once; later sweeps import neither torch nor Ultralytics and never infer again. Repository-root examples (verify actual weight directories):

```powershell
.venv/Scripts/python.exe SystemCode/model/balanced_metrics.py export --weights Dataset/runs/yolo11s-rdd2022es-compare30-seed42/weights/best.pt --run-name s30-best-640 --imgsz 640 --device 0
.venv/Scripts/python.exe SystemCode/model/balanced_metrics.py analyze --export Dataset/balanced-metrics/s30-best-640/export.json
```

API: `export_predictions(weights: Path, run_name: str, *, root=REPO_ROOT, imgsz=640, device='cpu') -> Path` returns `export.json`; `analyze_export(export_path: Path, analysis_name='sweep', *, root=REPO_ROOT) -> Path` returns `analyses/sweep/report.json`. `imgsz` accepts only 640, 832 or 960; CPU is default, and one GPU uses string `'0'`. CLI requires all 1921 validation images. Injected fake-model test records explicitly say `injected_test_model` and cannot serve as real-model evidence.

Output is confined to `Dataset/balanced-metrics/<run-name>/`, entirely Git-ignored. New export/analysis names accept letters, digits, hyphens and underscores only; existing-directory overwrite and resolved storage-boundary escapes are rejected. Repository Dataset itself cannot redirect elsewhere via symlink/junction. Failed runs retain status/partial evidence without automatic deletion or appending; retries require new names. Invalid inputs produce no successful report.

Low-confidence export uses single PIL RGB images, `conf=0.001`, class-aware NMS `iou=0.7`, `max_det=100`, `batch=1`, `rect=true`, no augmentation. Ultralytics 8.4.176 requests FP32 via `quantize=None`, without relying on removed `predictor.args.half`. Real-model loading checks every parameter/buffer is finite. After first inference it checks backend `fp16=false`, all floating tensors are finite torch.float32 and actual device matches requested CPU/GPU. Record TF32/float32-matmul runtime state; GPU/CPU results need not be bitwise identical. Export records resolution, weights/manifest/data-YAML/label-schema/prediction SHA256, source-script hashes, actual packages and device. Offline analysis rechecks completion and these inputs, rejecting category-export mappings from low-confidence validator `predictions.json`.

Fixed global confidence grid: 0.001, 0.005, 0.01, 0.02, 0.03, 0.05, 0.075, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95. Filtering uses `confidence >= threshold`, with no per-class thresholds or repeated NMS. Low-confidence export floor and 100-detection cap limit candidates; reports retain this limitation.

For each matching-mode/IoU pair, each image runs confidence-ordered class-aware one-to-one greedy matching once via `analyze_errors.match_detections`. Highest confidence comes first; original prediction index breaks confidence ties, maximum IoU wins and annotation index breaks IoU ties. Lower-confidence predictions cannot change earlier matches, so confidence-ordered cumulative TP/FP and annotation-support counts supply every threshold without repeating IoU for all 25. Tests compare prefix counts with fresh per-threshold matching per class, covering duplicates, wrong classes, localization and equal confidence.

Reports include eight-class micro/macro/per-class TP/FP/FN, precision/recall/F1 at every threshold for primary IoU 0.5 and supplementary 0.3. Micro uses totals across eight classes; macro weights each class equally, with undefined entries contributing 0 to averages while individual values remain null (e.g. precision without predictions or recall without GT). Separately report whether micro reaches both P>=0.7/R>=0.7 and whether all eight classes meet targets at the selected point; micro success does not establish minority-class success.

Selection is frozen before export: choose one global threshold from the primary eight-class IoU 0.5 curves, maximizing micro `min(P,R)`, then eight-class macro F1, then micro recall. Exact ties retain the first threshold in ascending grid order, matching the frozen plan. Undefined micro metrics without predictions/GT cannot outrank defined metrics. Retain selected point and all curves, explicitly validation-tuned; do not modify model manifests, backend thresholds or activate models.

Reproduction records retain export-time and analysis-time hashes for `balanced_metrics.py`, `analyze_errors.py`, `evaluate.py`, `train.py` and `checkpointing.py`, covering reused matching/preparation logic. Git HEAD alone cannot establish equivalence of dirty scripts.

At the same selected threshold, diagnostics also show:

- Class-agnostic one-to-one matching measures localization of damage, then records an 8x8 source-class confusion matrix and correct/incorrect eight-class counts among localized objects. These are not eight-class TP.
- Four-family diagnostics temporarily merge 0/1, 2/3, 4/5 and 6/7 to explain wide/ordinary, sunken/ordinary and deep/ordinary confusion. They cannot replace eight-class metrics.
- IoU 0.3 allows looser localization and can only supplement IoU 0.5. Threshold selection and target achievement always use eight-class IoU 0.5.

These operating-point metrics are not official mAP and do not calibrate engineering severity, automatic acceptance or business rules. If primary eight-class IoU 0.5 fails either target, retain failure explicitly; looser localization/family numbers cannot be presented as acceptance.

```powershell
.venv/Scripts/python.exe -m pytest SystemCode/tests/test_balanced_metrics.py -q
```
