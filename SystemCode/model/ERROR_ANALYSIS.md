# Validation operating-point error analysis

Owner: A. `analyze_errors.py` analyzes all 1921 nonmirrored validation originals from frozen `Dataset/prepared/manifest.jsonl`. It reads full manifest metadata to select `split=val`, opens only validation images/labels, and neither reads train/test images/labels nor selects test thresholds. Data YAML must preserve preparation layout and the eight-class dictionary. Original images/labels are read-only; each SHA256 is checked against the manifest and label numbers must match manifest boxes.

From repository root, specify completed local weights and a fresh output name. For example, the 10-epoch baseline (verify actual local run paths):

```powershell
.venv/Scripts/python.exe SystemCode/model/analyze_errors.py --weights Dataset/runs/yolo11n-rdd2022es-baseline10-seed42/weights/best.pt --run-name baseline10-val-errors --device 0
```

`--device cpu` is default; use `--device 0` for one GPU. Check the weights directory against training records before running. Missing weights fail without model downloads. Output is confined to ignored `Dataset/error-analysis/<run-name>/`; existing directories, path traversal and resolved links outside data storage are rejected. Failure retains `status.json` and partial evidence without a successful report; retries require new names.

The tool invokes real `model.predict` on individual PIL RGB images and verifies source classes 0-7 against actual `model.names`. Defaults: `conf=0.25`, NMS `iou=0.7`, `max_det=100`, `imgsz=640`, `batch=1`, `half=false`, `rect=true`, no test-time augmentation, class-aware NMS. Explicit `--conf`/`--match-iou` changes require new run names; diagnostic matching IoU defaults to 0.5. Reports record actual device, package versions, weights/manifest/data-YAML SHA256 and analysis-script SHA256. GPU/CPU numbers need not be bitwise identical; stable sorting, fixed seeds and sample selection do not make GPU computation fully deterministic.

The backend API likewise uses single PIL RGB images, CPU, `max_det=100` and manifest `conf/iou/imgsz`. Check default-manifest parameters separately; GPU analysis explicitly records its device difference from the API. Validator `predictions.json` comes from low-confidence multi-label validation and category-export mapping and cannot directly supply this tool's predictions. Here P/R describes a fixed deployment experiment operating point, neither maximum mean-F1 curve position nor official mAP. It cannot establish calibration or automatic-acceptance readiness.

Matching processes predictions by descending confidence (original prediction index breaks ties), finding unmatched same-class annotations with maximum IoU (annotation index breaks ties). IoU at/above threshold gives TP. Every prediction/annotation contributes at most one TP; unmatched predictions are FP and annotations FN. Class/position errors can create both FP and FN. Diagnostic associations may reuse objects only to explain errors, without changing one-to-one TP relationships:

- For FP, first check high-IoU duplicates of already matched same-class annotations, then high-IoU different-class confusion, then same-class localization with `0.1 <= IoU < match_iou`; otherwise classify as background.
- For FN, first check high-IoU different-class prediction confusion, then same-class low-IoU localization; otherwise classify as missed detection.
- Background FP can indicate missing annotations or model false positives. This tool cannot confirm annotation errors and never edits data.

`report.json` contains eight-class TP/FP/FN, precision/recall and error-type counts; absent prediction/annotation denominators yield null metrics. `image-results.jsonl` stores ground truth, original-pixel predictions and diagnostic object indices for every validation image. `sample_selection` rotates FP/FN and error types, covers classes/countries and uses fixed-seed hash ordering to select at most 40 distinct images. This is targeted error-review sampling, not a random quality estimate.

`samples/*.jpg` shows frozen labels on the left and predictions on the right: green TP, red FN and orange FP, with class ID/source name, object index, confidence and diagnostic type. Each `contact-sheet-*.jpg` contains at most 12 comparisons for screening; inspect individual 1200x600 images for box/text detail. Suspected missing labels/class ambiguity are manual-review candidates, not authorization to relabel.

Ordinary CI requires neither torch nor GPU. Explicit fake-model tests cover confidence ordering/ties, boundary IoU, one-to-one duplicates, wrong classes, localization, empty cases, full validation count, mirror/path rejection, real-input digests, stratified examples and fake-model end-to-end artifacts.

```powershell
.venv/Scripts/python.exe -m pytest SystemCode/tests/test_error_analysis.py -q
```
