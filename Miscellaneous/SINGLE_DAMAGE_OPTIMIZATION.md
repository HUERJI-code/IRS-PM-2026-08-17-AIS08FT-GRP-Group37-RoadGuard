# Primary damage in a single photo: First optimisation and acceptance

Subsequent status: The project owner later explicitly requested release and backend integration. A default manifest and separate primary-suggestion fields were provided according to the [release and integration guide](MODEL_RELEASE_AND_BACKEND.md). The text below retains the decisions, metrics and local delivery record from the first experiment; integration does not establish acceptable recognition quality.

Date: 2026-10-13; owner: A. Completed scope: a comparison without training, primary-result selection tools, inference on real weights and regression checks. Model recognition quality has not passed acceptance.

## Scenario and delivery boundary

The project owner confirmed that a typical photo contains one primary damage type and one primary box. This is a capture/display objective, not a guarantee for every input. No result is allowed; multiple defects, class conflicts or background interference still require review. The eight source labels retain their meanings. Fewer boxes must not be described as improved recognition accuracy.

This round supplies an independent experiment entry point returning at most one `main_detection`, while retaining all `raw_detections` and ambiguity warnings. Without detections, the primary result is `null`; a nonempty result is marked `review_required:true`. It is not a Task and does not write to the inspection database. Existing upload, review, task, four-crew and model-manifest contracts remain unchanged; B/C do not yet need client changes.

## Method and evaluation definitions

The best YOLO11s is reused, with weights SHA-256 `464f5f2af596140f71583e974146f10819765adf851bc8ac73198b7fa7f51488`. No training, weight download or restoration of the deleted two-stage approach occurred.

Of all 1,921 original validation images, **581 single-annotation images and 649 empty-annotation images** support the primary evaluation. The other **691 multi-annotation images, with 2,042 boxes**, are reported separately. Annotations are neither deleted nor rewritten; empty annotations do not establish expert-verified absence of damage.

A fixed SHA-256 split by source `group_id` uses 853 calibration images to choose settings and 377 confirmation images to report the selected method. Confirmation contains 171 single-damage and 206 empty-annotation images. These validation data were previously used in training and selection; **this confirmation subset is not a new independent test set or a Jurong field-acceptance set**. Class 3 has no positive confirmation examples; other rare classes also have very limited support.

The plan was saved before reading predictions or calculating results. Eighty fixed candidates compare two inference recipes (832 original; 832 original plus flip), four rankings (confidence; confidence multiplied by the fourth root/square root of area fraction; confidence multiplied by a bounded centre weight), five confidence thresholds (0.10/0.20/0.30/0.40/0.50) and two ambiguity policies (retain suggestion with warning; withhold suggestion when strong competing classes/regions exist).

Selection uses calibration only: maximise the smaller of eight-class image-level Precision and Recall, then compare eight-class macro F1 and Recall; exact ties retain the preregistered candidate order. Confirmation results are not used to choose another method.

**Eight-class image-level judgement:** a correctly typed primary suggestion counts TP; a wrong type counts both FP and FN; no output counts FN; output on an empty-annotation image counts FP. This metric does not require box overlap. Stricter same-class IoU≥0.3/0.5 results are reported separately. It differs from historical full multi-object box-detection metrics; subtracting them must not be called model improvement.

## Actual results

Selected: **original 832, confidence threshold 0.20, confidence × fourth root of area fraction**. Ranking scores do not replace model confidence and are not probabilities of correctness. Ambiguity filtering reduces recall and was not selected in calibration. The inference tool therefore retains a primary suggestion for review while returning ambiguity information.

On the same 377 confirmation images:

| Method | Correct-type TP | FP | Missing/wrong-type FN | Eight-class Precision | Eight-class Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original 832, 0.25, highest-confidence single box | 98 | 62 | 73 | 61.25% | 57.31% |
| Flip 832, 0.30, highest-confidence single box | 100 | 60 | 71 | 62.50% | 58.48% |
| This round: area weighting, 0.20 | 106 | 66 | 65 | **61.63%** | **61.99%** |

Compared with the original highest-confidence baseline, eight more images are correctly typed but there are four more FP. Compared with the flip baseline, Recall increases while Precision falls slightly. No significance claim is made. No calibration candidate met both 70% targets, and the selected confirmation result also falls short.

Other selected-method results:

- Confirmation, damage present/absent without distinguishing type: Precision 79.65%, Recall 80.12%. **This does not establish acceptable eight-class recognition.**
- Confirmation, same class and IoU≥0.3: Precision 53.49%, Recall 53.80%; IoU≥0.5: 50.58%, 50.88%.
- Confirmation ordinary potholes: five correct among fourteen positives, Recall 35.71%; deep potholes: two correct among four, Recall 50.00%. Both remain inadequate.
- All 1,230 zero/single-annotation images: type Precision 65.68%, Recall 65.23%; includes selection data.
- Only 157/691 multi-annotation images triggered ambiguity warnings; 658 produced a primary suggestion. The warning does not reliably identify every multi-object photo.

## Retesting known photos

Actual CPU FP32 inference retested six earlier internet photos and the user’s AI-generated image. These are known exploratory examples, were not used to choose settings and have no new expert annotations; real-world accuracy cannot be calculated from them.

The clear pothole photo `05-pothole-asphalt` still produces a large left-side `alligator_crack` box with raw confidence 0.253. The user’s AI image still produces `pothole` on foreground gravel at confidence 0.692, failing to cover the main pothole. Other outputs include primary boxes on crack photos and an empty result for the Jurong street scene. Larger/fewer boxes do not by themselves demonstrate greater correctness.

Conclusion: ranking and threshold changes improve recall on a fixed single-target subset but do not resolve the obvious pothole failure. **Retain the experiment tools without promoting these settings to current API defaults or relaxing automatic task-creation rules.**

## Reproduction and photo inference

Run from repository root; output must be inside Dataset and must not already exist:

```powershell
.\.venv\Scripts\python.exe SystemCode/model/single_damage.py --output Dataset/single-damage-repeat
.\.venv\Scripts\python.exe SystemCode/model/predict_single_damage.py --image "your-photo.jpg" --output Dataset/single-damage-my-photo
```

The comparison verifies hashes for the two existing full prediction exports, weights, labels and data files; it does not use test images for selection. Photo inference defaults to the completed `Dataset/single-damage-v1`; `--experiment` selects a new comparison directory. The actual inference entry currently supports only the selected standard832 recipe and explicitly rejects others. Repeat `--image` for multiple photos.

Input follows backend JPEG/PNG, 8 MiB, 20-megapixel and EXIF rules. Outputs include `results.json`, per-image JSON (primary suggestion, all detections, ambiguity and hashes) and one primary-box JPG per image. Previews may be resized; JSON coordinates remain in original-image pixels. `inference_manifest.json` describes detection only and excludes primary-target postprocessing. It is not evidence that the existing API already supports a single primary box.

Code: [selector](../SystemCode/backend/roadguard/vision/primary.py), [comparison tool](../SystemCode/model/single_damage.py), [photo-inference entry](../SystemCode/model/predict_single_damage.py). The small [experiment summary](../SystemCode/experiments/vision/single_damage_summary.json) can be shared; full evidence/images stay in ignored `Dataset/single-damage-v1/`.

## Next-round data and integration requirements

Prioritise real photos matching the intended capture method: one primary defect, complete edges and surrounding road, especially large potholes at short range. Negatives should include wet surfaces, shadows, patches, gravel and manholes. AI images are exploratory stress cases only and excluded from real-photo acceptance.

For each image record source/licence, real/generated status, scene group, original hash, primary-object annotation and annotator. Keep the same location/pothole/adjacent frames in one split. Allow `uncertain`; appearance cannot establish engineering depth. Where multiple real objects exist, annotate all objects and the primary object rather than deleting labels to force one box per photo. Freeze independent acceptance data before model adjustments.

After real independent samples demonstrate improvement, A designs primary-suggestion API fields; C draws one suggestion by default while allowing original evidence to expand; B continues consuming reviewed TaskSnapshot. The existing acceptance/review meaning of `selected_detection_id` cannot be replaced by an experimental suggestion.

## Engineering acceptance and delivery

Full regression: 808 passed, 1 skipped (Windows symlink permission), including eighteen initial new tests. An existing sandbox TestClient hang was terminated; the run completed outside the sandbox using an isolated temporary database. Five evidence-tampering/path tests were then added, yielding 23 passing focused tests; those five are not included in the earlier full-run count. Actual inference completed on all seven images. Engineering acceptance does not establish recognition quality.

No training was started. Raw data, YOLO weights and checkpoints are retained; Dataset is entirely ignored. This delivery consisted of local feature-branch code and records, not yet committed or pushed to GitHub at this stage.
