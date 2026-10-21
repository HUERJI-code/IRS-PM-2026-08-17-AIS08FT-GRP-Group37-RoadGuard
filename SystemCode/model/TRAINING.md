# Step 8: real vision training, recovery and evaluation

Owner: A. These are reproducible entry points, not achieved accuracy claims. Eight class names retain the original `label_schema.json` order. RDD2022ES v1 is not Jurong road imagery; source-license conflicts remain documented in the data audit.

Use the existing repository `.venv`. The formal local training environment is Windows / Python 3.12 / RTX 5090. Install PyTorch from the official CUDA 12.8 index, then optional vision dependencies. Ordinary backend CI does not install torch; dependency-injected tests verify recovery and cleanup contracts.

```powershell
.venv/Scripts/python.exe -m pip install torch==2.10.0 torchvision==0.25.0 --index-url https://download.pytorch.org/whl/cu128
.venv/Scripts/python.exe -m pip install -r SystemCode/model/requirements-vision.txt
```

Before running, complete full content verification and grouped splitting with `data_pipeline.py`. Data, official pretrained `yolo11n.pt`, logs, weights, metrics and tool caches stay under ignored `Dataset/`. The operator must explicitly download pretrained weights and retain provenance and SHA256; training/backend never download models automatically. Before first Ultralytics import, the entry sets offline environment, disables automatic installation and turns off sync/cloud logging integrations.

Configuration validation confines resolved `dataset_root` to the repository `Dataset/` subtree. Data YAML and its `path`, `train`, `val` and optional `test` must stay there too; existing preparation/smoke absolute `path` and relative image directories are supported directly. Omitting `path` uses the YAML directory. Relative `path` is rejected because it depends on global Ultralytics datasets settings. To avoid parser dependencies in ordinary CI, only generator-style top-level line keys, JSON scalars/arrays and plain local-directory strings are accepted. Complex YAML, duplicate/unknown keys, download directives and indirect image-list files are rejected; eight class names are verified. Resolved-path checks reject external symlink/junction targets; they do not repeat the full image-content audit.

`training.example.json` retains its initial example: 30 epochs, 640 pixels, batch 16, seed 42, patience 10. Subsequent optimization authorization permits at most 60 epochs per new run, patience 1-60, imgsz 32-960 in multiples of 32, batch 1-64 and workers 0-4. Integer parameters and seed reject booleans; implicit stride rounding must not change frozen dimensions. Limits define permitted ranges, not each run's budget; use the configuration authorized for that run. The frozen 30-epoch n/s comparison protocol remains unchanged.

`cache=false` avoids decoded-image caching; `fliplr=0` avoids repeated mirrored augmentation; AdamW is fixed. Initial `workers=0` is conservative for Windows; after smoke testing it may be 2 or 4. `amp=false` avoids auxiliary weight downloads during automatic AMP checks. Parameter changes require a new run name; resume requires an identical configuration hash.

For higher-resolution fine-tuning from an existing model, new configuration `model` may reference `Dataset/runs/<parent-run>/weights/best.pt`, with new `run_name` and `model_version`; run with `--config` only. This is a new experiment initialized from parent weights, recreating optimizer, scheduler and epoch count. `identity.pretrained_sha256` records the parent checkpoint SHA256 (legacy field name); parent weights must remain unchanged, and resuming the new experiment verifies this hash. `--resume` cannot extend a completed run; it resumes an interrupted full checkpoint of the same new run with exactly matching configuration. Retain parent best/last/recovery, splits and old model manifests.

Keep all eight classes and the model architecture. After fine-tuning, `evaluate.py --split val` uses the actual loader to verify eight source names, finite model parameters and reports before exporting a new experimental manifest. Merely starting training does not replace evaluation. Whether higher resolution improves both precision and recall must follow actual validation records, not configuration promises.

First use `make_smoke.py` with the fully audited frozen splits to create 64 training and 32 validation images for recovery testing, without reading test data. Generated configuration is 2 epochs, 320 pixels, batch 8, workers 0 and the eight-class dictionary. Do not report its metrics as full-data results. Formal run configurations live separately in `Dataset/`. Existing smoke data/configuration are not overwritten.

```powershell
.venv/Scripts/python.exe SystemCode/model/make_smoke.py
.venv/Scripts/python.exe SystemCode/model/train.py --config Dataset/smoke-config.json --stop-after-epoch 1
# The preceding command deliberately exits after completing and saving one epoch, with exit code 75.
.venv/Scripts/python.exe SystemCode/model/train.py --config Dataset/smoke-config.json --resume Dataset/runs/recovery-smoke/weights/resume-latest.pt
.venv/Scripts/python.exe SystemCode/model/evaluate.py --config Dataset/smoke-config.json --split val
.venv/Scripts/python.exe SystemCode/model/train.py --config SystemCode/model/training.example.json
```

At each completed epoch, `on_model_save` saves full recovery state to a same-directory temporary file, then flush/fsync and atomic replace publish `weights/resume-latest.pt`; the previous copy becomes `resume-previous.pt`. Windows guarantees the file-replacement publication boundary; sudden-power-loss durability still depends on filesystem/hardware. Interruption loses the unfinished epoch and resumes from the latest completed one. If latest is corrupt, explicitly select previous; never silently retrain.

At every epoch start, including OOM retries, the training entry checks actual batch against frozen configuration. If Ultralytics automatically reduces batch, fail explicitly and preserve evidence rather than claim an equal-batch comparison. `effective_training.json` atomically records actual batch, library `nbs`, nominal gradient accumulation and configured parameters, with a final update at training end. For default `nbs=64`, batch 32 yields nominal accumulation 2 and nominal effective batch 64 after warmup; warmup accumulation may be smaller.

Resume checks configuration, data YAML, manifest, pretrained SHA256 and Python/key-package versions. Full state includes epoch, original-precision optimizer, AMP scaler, scheduler, live model, EMA, early-stop state, Python/NumPy/torch/CUDA RNG and dataloader generator. Ultralytics performs its own recovery first; `on_pretrain_routine_end` then restores live state. `resume_verified.json` records next epoch and optimizer-state count. Multiworker prefetch and GPU operations prevent a guarantee of bitwise equivalence between resumed and continuous runs.

Ultralytics strips optimizers from `last.pt`/`best.pt` after training; these serve inference/selection. Independent recovery weights retain full state. Resume cannot restart the final epoch of a completed configuration; evaluate directly. No per-epoch historical copies are produced by default; retain last, best, latest, previous and supporting evidence.

If the last epoch was saved but final library validation/plotting was interrupted, leaving `run_status.json` interrupted/failed, the entry does not claim completion based only on the final checkpoint. Explicitly replay the final epoch from `resume-previous.pt` and let the whole training flow finish, then evaluate. Do not manually edit status to bypass completion checks.

```powershell
.venv/Scripts/python.exe SystemCode/model/evaluate.py --config SystemCode/model/training.example.json --split val
.venv/Scripts/python.exe SystemCode/model/evaluate.py --config SystemCode/model/training.example.json --split test
# Cleanup preview; cite an existing successful validation report to avoid another validation run.
.venv/Scripts/python.exe SystemCode/model/evaluate.py --config SystemCode/model/training.example.json --cleanup --existing-report Dataset/runs/yolo11n-rdd2022es-v1-seed42/evaluation-val.json
# Add --apply-cleanup only when a human has authorized cleanup.
```

Evaluation outputs `evaluation-val.json`/`evaluation-test.json`: overall and eight-class P/R/F1/mAP50/mAP50-95, annotation counts, a 9x9 confusion matrix including background, and confusing-class examples. `evaluation-{split}/val_batch*.jpg` compares predictions/labels for a limited number of batches; `predictions.json` retains predictions. Classes without ground truth have null metrics and are marked unevaluated. P/R/F1 use the library's maximum mean-F1 curve location; on test data this is descriptive only and cannot tune deployment confidence. Deployment `conf=0.25` is an explicit experiment parameter, not a calibrated automatic-acceptance threshold. Metric curves use fixed `conf=0.001,iou=0.7`.

Numerical checks establish only valid names, samples and finite in-range metrics; `accuracy_acceptance=not_defined_not_claimed`. Low accuracy or missing classes cannot be packaged as business acceptance. Successful val exports `model_manifest.json`, always `experimental`, including local weights path, SHA256, eight source names, model/data versions, data-manifest hash, inference parameters and validation-report path. The backend validates shared `roadguard-model-v1`; uncalibrated real results retain manual review.

Cleanup defaults to dry-run and is allowed only after training completes, current best validates and manifest remains unchanged. The allowlist is `Dataset/prepared/labels/{train,val,test}.cache` and `Dataset/prepared/images/{train,val,test}/*.npy`; symlink/junction paths are rejected. Raw archives, source images/labels, splits, manifest, audit, best/last/recovery, model manifests, logs, evaluations and metrics are excluded from cleanup. Cleanup plans and actual freed bytes are written to the run directory.

Runtime metadata records actual package versions, Git HEAD, dirty status and training/data-script SHA256. Training with uncommitted code cannot be described as fully reproducible from HEAD; retain source hashes alongside subsequently committed code. Real training results must come from run-directory evidence, never fabricated from smoke runs or fake-object tests.

Implementation references: [Ultralytics Trainer source](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/engine/trainer.py), [validation source](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/models/yolo/detect/val.py), [PyTorch version installation](https://pytorch.org/get-started/previous-versions/). Source files from locally pinned versions are the final authority for recovery callbacks and evaluation interfaces.

The recovery test and full-data 10-epoch baseline were actually completed on 2026-10-13; see [acceptance records](../../Miscellaneous/STEP8_VISION_ACCEPTANCE.md). The 30-epoch example was not that run's configuration. See the [experiment summary](../experiments/vision/step8_baseline_summary.json) for actual configuration, per-class metrics, checkpoint digests and limitations.
