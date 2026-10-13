# Step 8 experimental vision baseline

`step8_baseline_summary.json` contains actual 2026-10-13 run metadata, frozen split counts, source/checkpoint hashes, native Ultralytics eight-class validation and held-out test metrics, recovery evidence, HTTP acceptance and cleanup counts. `baseline10_results.csv` records the ten completed epochs. These small summaries are committed; images, weights, prediction exports, databases and full logs remain in ignored `Dataset/`.

The JSON `configuration` object is the exact `Dataset/baseline10-config.json` used for training: YOLO11n transfer, seed 42, 10 epochs, image size 640, batch 32, AdamW with lr0 0.001, CUDA device 0. The 30-epoch model example is a separate bounded configuration, not an experiment already run. On a new machine follow the [data pipeline](../../model/data_readme.md) and [training guide](../../model/TRAINING.md); paths in regenerated YAML and their digests will be machine-specific. Use a new run name for another experiment; do not overwrite completed evidence or extend a completed run through resume.

Training occurred on uncommitted implementation code. `training_runtime.git_commit` is the base commit, with `git_dirty:true` and source hashes identifying the actual files. Dataset/YAML input validation was tightened after training; model/data/optimizer/evaluation were unchanged. Do not claim that the base commit alone reproduces this run.

Metrics remain experimental. `map50` and `map50_95` are detection average precision, not the fraction of correctly classified photographs. P/R/F1 are descriptive points on each split's PR curves; the test split did not select the model or inference threshold. Confusion counts were collected at evaluation confidence 0.001 and must not be interpreted as deployed confidence 0.25 counts. No optional faster-coco-eval result is claimed. Dataset images do not establish Jurong geography, road permission or engineering severity. All real nonempty detections require review and tasks still use demo business rules.

See the [supervisor acceptance record](../../../Miscellaneous/STEP8_VISION_ACCEPTANCE.md) for results and limitations.
