# Experimental vision evidence

## Completed 30-epoch comparison

`compare30_plan.json` preserves the preregistered n/s configurations and input identities. `compare30_n_results.csv` and `compare30_s_results.csv` contain the 30 actual epochs; `compare30_curves.png` plots those curves alongside the historical baseline. `compare30_summary.json` combines validation metrics, operational errors at confidence 0.25, CPU latency, checkpoint integrity, HTTP acceptance and cache cleanup with hashes of the local original evidence.

Both paired runs used clean training commit `7cfd6ae82597fddb7a608df632a792df83176668`; the later CPU helper records its own source hash. No candidate test images or labels were evaluated this round. The prior baseline test has already been inspected and cannot be described as an unseen new holdout. See the [supervisor report](../../../Miscellaneous/VISION_30_EPOCH_COMPARISON.md) and [reproduction protocol](../../model/COMPARISON30.md).

These summaries do not contain images or weights. Full evidence remains under ignored `Dataset/`; pulling the repository alone does not install the selected model.

## Historical 10-epoch baseline

`step8_baseline_summary.json` contains actual 2026-10-13 run metadata, frozen split counts, source/checkpoint hashes, native Ultralytics eight-class validation and held-out test metrics, recovery evidence, HTTP acceptance and cleanup counts. `baseline10_results.csv` records the ten completed epochs. These small summaries are committed; images, weights, prediction exports, databases and full logs remain in ignored `Dataset/`.

The JSON `configuration` object is the exact `Dataset/baseline10-config.json` used for training: YOLO11n transfer, seed 42, 10 epochs, image size 640, batch 32, AdamW with lr0 0.001, CUDA device 0. The generic 30-epoch example is separate from both this historical baseline and the later frozen compare30 configurations above. On a new machine follow the [data pipeline](../../model/data_readme.md) and [training guide](../../model/TRAINING.md); paths in regenerated YAML and their digests will be machine-specific. Use a new run name for another experiment; do not overwrite completed evidence or extend a completed run through resume.

Training occurred on uncommitted implementation code. `training_runtime.git_commit` is the base commit, with `git_dirty:true` and source hashes identifying the actual files. Dataset/YAML input validation was tightened after training; model/data/optimizer/evaluation were unchanged. Do not claim that the base commit alone reproduces this run.

Metrics remain experimental. `map50` and `map50_95` are detection average precision, not the fraction of correctly classified photographs. P/R/F1 are descriptive points on each split's PR curves; the test split did not select the model or inference threshold. Confusion counts were collected at evaluation confidence 0.001 and must not be interpreted as deployed confidence 0.25 counts. No optional faster-coco-eval result is claimed. Dataset images do not establish Jurong geography, road permission or engineering severity. All real nonempty detections require review and tasks still use demo business rules.

See the [supervisor acceptance record](../../../Miscellaneous/STEP8_VISION_ACCEPTANCE.md) for results and limitations.
