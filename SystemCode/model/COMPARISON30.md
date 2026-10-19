# YOLO11n / YOLO11s paired 30-epoch experiment

Owner: A. On 2026-10-13, after validation-error analysis of the completed 10-epoch baseline, the owner authorized separate 30-epoch n/s training. This is the protocol, not a completion/accuracy claim. Preserve the 10-epoch baseline and backend manifest without overwrite.

## Preregistered protocol

Both runs use inputs, inference and training parameters from the same `Dataset/baseline10-config.json`, changing only epochs/patience to 30 and independently initializing from official COCO-pretrained `yolo11n.pt`/`yolo11s.pt`. Do not extend the 10-epoch n checkpoint to 30 or initialize s from n. Interrupted runs may resume their own full recovery checkpoints to the originally planned 30 epochs.

Shared parameters: seed 42, deterministic true, imgsz 640, batch 32, workers 4, device 0, amp false, cache false, fliplr 0, AdamW, lr0 0.001, lrf 0.01, warmup_epochs 1, close_mosaic 2. nbs=64 gives nominal accumulation 2 and nominal effective batch 64; the library adjusts accumulation during warmup. Actual batch must stay 32; the guard rejects automatic OOM batch reduction rather than silently create an unfair comparison. Retain best, last, latest/previous recovery and logs.

Run names: `yolo11n-rdd2022es-compare30-seed42` and `yolo11s-rdd2022es-compare30-seed42`. Training files, data manifest/audit/split summary, pretrained provenance/hashes, preparation plan and full evidence stay in ignored `Dataset/`. Commit frozen training code first, then keep code/inputs unchanged throughout the pair. The operator may copy small summaries without absolute paths into `SystemCode/experiments/vision/` for version control.

Both weights come from Ultralytics assets v8.3.0. n SHA-256: `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`; s: `85a76fe86dd8afe384648546b56a7a78580c7cb7b404fc595f97969322d502d5`. These are local asset-verification records. GitHub metadata supplied no digest when s was downloaded, so this is not publisher-signature verification. Tools use existing local weights and fail if absent, without downloading.

## Prepare, train, validate and compare

Run from repository root:

```powershell
# All assets must already exist; run this before either compare30 run is created.
.venv/Scripts/python.exe SystemCode/model/compare_models.py prepare
# Creates Dataset/compare30/{n-config.json,s-config.json,plan.json}; rejects overwrite.
.venv/Scripts/python.exe SystemCode/model/train.py --config Dataset/compare30/n-config.json
.venv/Scripts/python.exe SystemCode/model/evaluate.py --config Dataset/compare30/n-config.json --split val
.venv/Scripts/python.exe SystemCode/model/train.py --config Dataset/compare30/s-config.json
.venv/Scripts/python.exe SystemCode/model/evaluate.py --config Dataset/compare30/s-config.json --split val
.venv/Scripts/python.exe SystemCode/model/compare_models.py compare
```

`prepare` reads baseline10 configuration, `Dataset/pretrained/download.json` and `Dataset/pretrained/download-yolo11s.json` by default. It freezes plan/config fingerprints and data YAML/manifest/audit/split-summary/pretrained-source hashes, retaining identical data and complete augmentation/optimizer parameters. Generated plans cannot be regenerated over existing ones; training still uses the original `train.py`.

Comparison rejects missing/mismatched evidence before ranking. Require exactly 30 contiguous results.csv epochs, 30-epoch recovery identity and latest-recovery hash, all four retained checkpoints, successful val status, validation report for current best, eight source names and model manifest. Actual args.yaml and `effective_training.json` must establish batch 32, nbs 64, final train_end and matching configuration parameters. Runtime packages, Python, training-source hashes, code revision/dirty state, actual shared training parameters, validation image count and per-class annotation counts must match. Report image count must equal the frozen val split summary.

`compare` writes `Dataset/compare30/summary.json` by default, rejecting overwrite. It retains checkpoint hashes, input/actual-training-parameter fingerprints, runtime provenance, val metrics and a suggested relative `model_manifest.json` path, excluding absolute paths/large files. It neither reads `evaluation-test.json`, infers test data nor changes `ROADGUARD_VISION_MANIFEST_PATH` or the existing backend. Integrating a suggested model still requires actual acceptance; every model remains experimental.

## Preregistered selection rule

Choose higher validation mAP50-95; exact ties use higher validation mAP50. Do not round floats first. Only exact ties in both use lower median latency under the same CPU single-image backend flow. P/R/F1, per-class metrics and business smoke tests are diagnostics and do not alter selection. Never use test results for selection, thresholds or retraining decisions.

If latency breaks a tie, first measure both best weights using identical validation images, CPU thread counts, frozen backend code, inference parameters and repetitions. Save evidence under `Dataset/` and supply `--cpu-latency PATH`. Example contract follows; hashes/numbers must come from actual measurements:

```json
{
  "schema_version": "roadguard-compare30-cpu-latency-v1",
  "device": "cpu",
  "test_used": false,
  "protocol": {
    "pipeline": "backend_real_single_image",
    "source_split": "val",
    "image_set_sha256": "64-lowercase-hex fingerprint of the fixed input list",
    "backend_source_sha256": "64-lowercase-hex backend source fingerprint",
    "imgsz": 640, "conf": 0.25, "iou": 0.7,
    "cpu_threads": 4, "warmup": 2, "repeats": 3
  },
  "candidates": {
    "n": {"weights_sha256": "SHA256 of n best.pt", "median_ms": 80.0},
    "s": {"weights_sha256": "SHA256 of s best.pt", "median_ms": 100.0}
  }
}
```

80/100 illustrate structure only, not measurements. Require at least one warmup and three formal repetitions; both candidates share the entire protocol. Exact metric ties without complete latency evidence, or equal latency, cause refusal to select an arbitrary winner.

Actual CPU-latency acceptance uses `benchmark_cpu.py` after both candidates finish training and val evaluation. It reuses comparison checks for the frozen plan/full evidence and fails before importing torch/creating output when incomplete. Commands below run from repository root; `--repo .` may be an absolute repository path, and `--run-name` must be unused:

```powershell
.venv/Scripts/python.exe SystemCode/model/benchmark_cpu.py --repo . --run-name acceptance-v1
# If latency must break a tie, pass actual evidence; existing summaries are not overwritten.
.venv/Scripts/python.exe SystemCode/model/compare_models.py compare --cpu-latency Dataset/compare30/cpu-latency/acceptance-v1/latency.json --output Dataset/compare30/summary-with-latency.json
```

The protocol selects 10 frozen val originals each from Czech, India, Japan and United_States (40 total), ordered within country by `SHA256("42:" + sample_id)`, taking the first 10 and interleaving countries in that order. Models share input order; every read checks image SHA256 and rejects mirrored/excluded inputs without opening train/test images. CPU intra-op threads=4, inter-op=1. Each model warms up on the first two inputs, then runs three full rounds, recording 120 single-image times per model. Model order is n/s, s/n, n/s. Actual CPU, float32, inference parameters and thread counts are verified. Library CPU selection resets threads, so the entry changes its thread constant to 4 only within this process, never installed source.

Timing starts before `ImageStore.prepare(bytes)` and ends when `LocalVisionDetector.detect(prepared)` returns DTOs. It includes image validation/decoding, EXIF/RGB/PNG normalization, prepared-image decoding, YOLO preprocessing, CPU inference, NMS/postprocessing and Detection DTO construction/validation. It excludes file reads, model/manifest loading, warmup, runtime assertions, result serialization, image storage and HTTP/database/rule/review/task flow. Weights/predictor stay warm, but prepared images and predictions are not reused. Median and nearest-rank p95 use each model's 120 formal samples. This fixed small sample does not represent production traffic or statistical significance; OS caches, scheduling and temperature can affect timing.

Outputs are confined to `Dataset/compare30/cpu-latency/{run-name}/`, rejecting existing directories/path escapes and retaining status, full `latency.json` and local tool cache. JSON extends the contract above with 40 inputs/hashes, per-image/per-round times and detection counts, median/p95, timed/total wall time, model/runtime environment and backend/entry SHA256. `helper_source_sha256` uses the tracked `benchmark_cpu.py` actually executed. Commands/protocol do not imply measurement occurred; actual values must come from saved evidence.

This single-seed limited comparison cannot estimate training variance or claim statistically significant superiority. RDD2022ES is not Jurong imagery; wide/deep/sunken are visual labels, not measured engineering dimensions. Valid validation numbers establish neither business-accuracy acceptance nor calibrated automatic acceptance. A separately authorized final held-out test should evaluate only the selected model once and remain independent post-selection evidence.

Lightweight validation (no torch/Ultralytics installation or GPU):

```powershell
.venv/Scripts/python.exe -m pytest SystemCode/tests/test_vision_comparison.py -q
.venv/Scripts/python.exe -m pytest SystemCode/tests/test_cpu_benchmark.py -q
```
