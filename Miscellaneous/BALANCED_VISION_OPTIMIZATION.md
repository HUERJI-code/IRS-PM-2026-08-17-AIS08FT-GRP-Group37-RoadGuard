# Balanced Precision / Recall optimization experiment

Date: 2026-10-13; owner A. **Both Precision and Recall did not reach 70% this round.** Frozen selection chose `new_best832`, global confidence 0.25: eight-class same-class IoU>=0.5 micro Precision **50.52%**, Recall **52.00%**, F1 **51.25%**. Versus parent best@640 at 48.62%/51.20%/49.88%, gains are **1.89/0.80/1.37 percentage points**, small validation improvements. No class reaches both 70%.

The user prioritizes fewer missed detections and correct eight-class distinctions; small box-position errors are secondary. Below retain preregistered budget, parameters, ranking, then actual results/engineering acceptance. Numerical/recovery/HTTP success is neither recognition-target achievement nor automatic acceptance readiness.

## Target and definitions

At one global threshold, target **eight-class same-class one-to-one IoU>=0.5 micro Precision and Recall both>=70%**. Report per-class support/P/R/F1 and macro averages; overall success would not establish every minority-class target.

Supplement IoU>=0.3 localization, class-agnostic and four-family diagnostics to distinguish displacement/class confusion. They cannot replace eight-class metrics or claim success by merging labels, ignoring false positives or relaxing matching. Since precise boxes are secondary, selection changes from prior mAP50-95 to balanced P/R; standard mAP remains supplementary evidence.

Precision, Recall and localization IoU are distinct. F1 summarizes balance but high F1 alone does not guarantee each P/R exceeds 70%. [Ultralytics metrics](https://docs.ultralytics.com/guides/yolo-performance-metrics).

## First-round budget and frozen training

One full-data fine-tune only: **40 additional epochs, 832 pixels, batch 16**, plus two-epoch recovery smoke on 64 train/32 val images for execution only. No dependency upgrades/weight downloads. Initialize existing s30 best.pt with new run name/optimizer; retain old experiments.

Machine-readable [plan](../SystemCode/experiments/vision/balanced70_plan.json). Local config `Dataset/balanced70/s40-config.json`; run `yolo11s-rdd2022es-balanced40-img832-seed42`.

| Setting | Frozen value/reason |
| --- | --- |
| Initialization | Prior s30 best.pt; SHA256 `92749da1b1c05f2186e388c9d0cee65cc868613662c5aa21d940d76ec003940a` |
| Data | Same frozen train/val, eight IDs unchanged; no test images/labels opened |
| Run | 40 epochs, patience 40, imgsz 832, batch 16, nbs 64, seed 42, workers 4 |
| Optimizer | AdamW, lr0 0.0002, lrf 0.1, warmup 1 epoch, warmup_bias_lr 0 |
| Classification | cls 0.75, cls_pw 0.25; moderately increase classification loss/minority weighting |
| Localization | box 7.5, dfl 1.5; retain detection localization learning |
| Augmentation | mosaic 0.5, off for final 10 epochs; scale 0.3, translate 0.05, hsv_s 0.4, hsv_v 0.3 |
| Other | amp false, cache false, deterministic true, fliplr 0; no rotation, vertical flip, mixup, cutmix, copy_paste |

Installed Ultralytics 8.4.176 natively supports `cls_pw`: normalized inverse-frequency powers from training annotation counts affect positive/negative classification BCE terms. This does not guarantee higher accuracy through duplicating rare classes; inspect rare false positives. Source mirrors mean rare box counts are not independent capture counts. [Custom Trainer](https://docs.ultralytics.com/guides/custom-trainer); pinned local source defines this round's API.

Most originals are600-720 pixels; 832 changes feature sampling without creating source detail. Resolution, learning rate, augmentation and class weights change together, so this purposeful optimization cannot isolate one cause. [Training guidance](https://docs.ultralytics.com/guides/model-training-tips).

## Threshold and model selection

Fixed candidate order: parent best@640, parent best@832, new best@832, new last@832. Parent resolutions distinguish inference-size changes from new training. Library mAP50-95 still chooses best.pt; last.pt is also checked to avoid inspecting only precise-localization-favored checkpoints. No exhaustive epoch-wise balanced selection is claimed.

Each candidate infers all 1,921 validation originals once at conf0.001, NMS IoU 0.7, max_det100, FP 32. Offline sweep uses25 frozen thresholds:

1. Maximize eight-class IoU 0.5 `min(micro Precision,micro Recall)`.
2. Tie: higher eight-class macro F1, then micro Recall.
3. Exact tie: earlier threshold, then earlier candidate.

One threshold covers every class, not separate settings chosen for attractive examples. IoU 0.3, four-family and class-agnostic diagnostics do not rank primary results. Retain full curves/per-class results, including failures.

Validation selects thresholds/models and was already used for training/selection; call these validation-tuned results, not new independent generalization. Historical test was inspected at baseline; this round opens no test images/labels and evaluates no candidates on test.

## Acceptance and storage

- Main agent reviews tools/configuration and relevant tests; GPT-6.1-sol subagent develops, with responsibilities/evidence in final acceptance.
- Complete real high-resolution/class-weighted recovery smoke before frozen full training.
- Save full recovery every epoch; retain best, last, resume-latest, resume-previous, configuration, logs, source hashes.
- Verify final weights/input identity, finite tensors, errors and real HTTP integration. Every nonempty real result still requires manual review; business rules remain demo.
- After validation, delete only listed reconstructible caches, never models, raw data or evaluation evidence.
- Entire Dataset remains Git-ignored; Git contains tools, docs, configuration and small summaries. English PRs follow existing automated CI/merge.

If dual 70% fails, report best actual results and limitations honestly, without renaming metrics or reporting only Precision as success.

## Actual training and four-candidate results

Frozen full training completed40 epochs in **4,762.9 seconds(79.4 minutes)**, seed 42. Clean source commit `bec6fb33d594544d00d06cbfb4ffeb74722cd138`; runtime/frozen source hashes match. Actual batch 16, nbs 64, nominal accumulation4, effective nominal batch 64, final epoch 40. New best is library mAP50-95 optimum at **epoch 10**; last is40. Only best/last were compared, without exporting every epoch for balanced selection.

Plan raw-byte `config_sha256` is `e73285b0b37ba1668da2ce12dc8a718d302df1de53cb700cbe2bcb17cde4a010`; training normalized-JSON identity is `0840d4e41a7babc51119b3da9a06414667e7ed93a009660039380078796f8695`. Different conventions, both separately verified.

All results below use1,921 originals/2,623 boxes, eight-class same-class IoU>=0.5. Each candidate selects one confidence for all classes on the frozen grid. P/R/F1 are percentages.

| Candidate | Resolution | confidence | TP/FP/FN | micro P | micro R | micro F1 | macro F1 |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| parent_best640 | 640 | 0.25 | 1343 / 1419 / 1280 | 48.62 | 51.20 | 49.88 | 40.92 |
| parent_best832 | 832 | 0.25 | 1241 / 1222 / 1382 | 50.39 | 47.31 | 48.80 | 37.67 |
| **new_best832(selected)** | **832** | **0.25** | **1364/1336/1259** | **50.52** | **52.00** | **51.25** | **42.62** |
| new_last832 | 832 | 0.35 | 1318 / 1254 / 1305 | 51.24 | 50.25 | 50.74 | 42.00 |

No candidate's25-point grid reaches dual 70% micro. Last has slightly higher precision but lower min(P, R), so best wins the preregistered rule. Versus parent 640, selected gains21 TP and removes83 FP/21 FN. Parent resolution832 alone lowers recall, so resolution alone cannot explain the trained result.

Selected equal-class macro P/R/F1 **42.02%/43.52%/42.62%** versus parent 640 **40.71%/41.93%/40.92%**. Macro is unweighted by class count; undefined averages contribute0 while individual values stay null. All eight classes have GT.

## Eight-class support and parent comparison

Retain source IDs0-7, one confidence 0.25, primary IoU 0.5. support counts validation boxes, not independent photos; P/R/F1 triplets are percentages.

| ID/source class | support | Parent640 P/R/F1 | Selected832 P/R/F1 |
| --- | ---: | --- | --- |
| 0 longitudinal crack | 941 | 51.67 / 61.00 / 55.95 | 57.66 / 60.79 / 59.18 |
| 1 longitudinal crack wide | 148 | 34.34 / 45.95 / 39.31 | 38.07 / 45.27 / 41.36 |
| 2 transverse crack | 541 | 49.29 / 51.39 / 50.32 | 50.28 / 49.54 / 49.91 |
| 3 transverse crack wide | 46 | 24.14 / 15.22 / 18.67 | 36.84 / 30.43 / 33.33 |
| 4 alligator crack | 526 | 56.93 / 51.52 / 54.09 | 57.89 / 54.37 / 56.08 |
| 5 alligator crack sunken | 77 | 36.99 / 35.06 / 36.00 | **24.49 / 31.17 / 27.43** |
| 6 pothole | 299 | 38.98 / 33.11 / 35.80 | 36.25 / 38.80 / 37.48 |
| 7 pothole deep | 45 | 33.33 / 42.22 / 37.25 | 34.69 / 37.78 / 36.17 |

Wide-transverse F1 improves, but sunken-alligator P/R/F1 all decline, FP 46->74, TP 27->24. Transverse/deep-pothole F1 declines too. This is not improvement across all eight classes or isolated proof that class weighting works.

## Supplementary localization and native mAP

Diagnostics use selected weights/confidence 0.25 only, without reselection/primary replacement.

| Matching diagnostic | micro P | micro R | micro F1 |
| --- | ---: | ---: | ---: |
| **Eight-class same-class IoU>=0.5(primary)** | **50.52** | **52.00** | **51.25** |
| Eight-class same-class IoU>=0.3 | 55.48 | 57.11 | 56.28 |
| Four-family IoU>=0.5, diagnostic | 54.41 | 56.00 | 55.19 |
| Class-agnostic IoU>=0.5, localization only | 55.67 | 57.30 | 56.47 |
| Class-agnostic IoU>=0.3, localization only | 61.78 | 63.59 | 62.67 |

Even class-agnostic IoU 0.3 misses dual 70%; box displacement cannot explain the whole gap. Different greedy matching may produce different pairs; increments are not additive mutually exclusive causal contributions. Eight names/API outputs remain.

Separate native Ultralytics report `Dataset/runs/yolo11s-rdd2022es-balanced40-img832-seed42/evaluation-val.json`: selected best **mAP50=40.16%, mAP50-95=20.27%**, parent 38.77%/20.23%. Native P/R/F1 use maximum mean-F1 curves collected at conf0.001/NMS 0.7, not confidence 0.25 micro counts above. mAP is not image-classification accuracy or dual 70% accuracy.

## Errors, data support and exploratory examples

Selected1,259 FN are mutually categorized by fixed precedence: missed **896(71.2%)**, localization220, confusion143. 1,336 FP: background628, localization340, confusion264, duplicate104. FP/FN are separate partitions; one wrong-class/displaced object can create both. Adding them does not count independent physical defects. Missed means no diagnostic match at this point, not no lower-confidence candidate; background does not prove missing annotations.

Class-agnostic IoU 0.5 gives190 wrong-eight-class pairs: 146 same-family subclasses, 44 different families. Ordinary/wide, sunken/deep subclass confusion remains. Forty targeted stratified comparisons and per-image evidence: `Dataset/balanced70/selected-errors/report.json`, not random quality estimation.

Frozen train: 8,958 originals plus 8,958 mirrors; mirrors double box counts. Original class supports in ID order: **4556,820,2614,243,2443,311,1477,193**; validation supports above. Rare wide-transverse, sunken-alligator, deep-pothole original group counts230,288,157 show imbalance; mirrors add no independent scenes. Observations suggest rare support/class ambiguity may limit quality but cannot prove enough/insufficient data.

For selected GT area<1% image, recall 424/934=45.4%; area>=20%, 81/108=75.0%. FN short-side median48 source pixels, TP 59.5, missed43. These are image geometry, not engineering dimensions. No frozen contrast field; contrast was not measured or used for conclusions. Country P/R: Czech 43.33%/34.32%, India 42.86%/37.40%, Japan 48.59%/48.48%, United States55.35%/65.38%; not Jurong performance.

Three preregistered val originals retain GT/parent/selected comparisons:`India_001650` still misses2 FN;`Japan_003097` goes0TP/1FP/1FN->1TP/0FP/0FN;`Japan_005511` goes3TP/5FP/3FN->2TP/4FP/4FN. Local exploratory examples in `Dataset/balanced70/selected-errors/illustrative/` show improvements, no change/regression, not overall accuracy. No annotation error was confirmed or labels altered.

Several parameters changed with one seed, no ablation, repeated seeds or confidence intervals. Small gains establish neither single-parameter causality, significance nor new-scene generalization. First audit labels/rare-subclass support, especially ordinary/wide, sunken/deep consistency. Preserve eight classes, build review evidence, then choose another bounded experiment instead of blindly adding epochs.

## Completed engineering acceptance and future use

- Before full training, real832/class-weighted two-epoch interruption/recovery smoke passed for mechanism only, not full accuracy.
- Full40 epochs/actual arguments verified. latest/previous retain epochs 40/39,255 optimizer entries; live/EMA and each best/last499 tensors finite; class weights match the frozen formula.
- Integrity checks verified **39,674 train/val image/label SHA256** against frozen manifest; train/val/test group metadata disjoint. Test metadata checked isolation only; test images/labels were not opened and no candidate test evaluation exists.
- Regression **761 passed, 1 skipped**; CI guards **44 passed**. Valid ranges, labels, samples, identities do not establish dual 70% success.
- Selected manifest passed isolated loopback Uvicorn **11 real HTTP cases**: upload/replay, review/replay, active/completed snapshots, completion, restart persistence, new 503 with detector disabled. Revision0->1->2; default 8000 unused.
- Real Detection `is_demo=false` still requires manual review. Automated review requests test connectivity only; coordinates are simulated Jurong locations and task rules demo, not expert/production acceptance.
- Main agent viewed two metric plots, four contact sheets covering40 stratified examples and three complete fixed comparisons. This checks evidence presentation/exploratory errors, not expert label confirmation; no labels changed.

Recommended local manifest `Dataset/balanced70/selected_model_manifest.json`, weights SHA256 `464f5f2af596140f71583e974146f10819765adf851bc8ac73198b7fa7f51488`, confidence 0.25, NMS IoU 0.7, imgsz 832, experimental. This round generated a recommendation/isolated acceptance only, **without modifying PyCharm launch settings, environment variables or running backend**. Opt in via `ROADGUARD_VISION_MANIFEST_PATH` under [real vision API](REAL_VISION_API.md); no automatic activation.

Shareable [summary](../SystemCode/experiments/vision/balanced70_summary.json), [four-candidate CSV](../SystemCode/experiments/vision/balanced70_operating_points.csv), [40-epoch CSV](../SystemCode/experiments/vision/balanced70_training_results.csv), [PR curves](../SystemCode/experiments/vision/balanced70_pr_curves.png), [per-class chart](../SystemCode/experiments/vision/balanced70_per_class.png). Full local `Dataset/balanced70/selection.json`,`integrity.json`,`selected-errors/`,`http-acceptance/`,`data-diagnostics/` and run directory remain Git-ignored.

After numerical, integrity, HTTP, error and visual checks, allowlisted cleanup was applied. Run `cleanup-applied.json` records only `prepared/labels/train.cache` **4,344,707 bytes** and `val.cache` **452,896 bytes**, total **4,797,603 bytes(4.80 MB/4.58 MiB)**. Raw data, splits, predictions, reports, all old/new best, last, resume-latest, resume-previous remain; test images/labels/model evidence were not deleted.
