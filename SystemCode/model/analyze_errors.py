"""Validation-only operational error diagnostics; deliberately not official mAP."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.metadata
from itertools import zip_longest
import json
import math
from pathlib import Path
import platform

from PIL import Image, ImageDraw

try:
    from .checkpointing import sha256_file, write_json
    from .evaluate import source_names
    from .train import REPO_ROOT, configure_local_runtime, local_path, validate_dataset_yaml
except ImportError:
    from checkpointing import sha256_file, write_json
    from evaluate import source_names
    from train import REPO_ROOT, configure_local_runtime, local_path, validate_dataset_yaml


def box_iou(a: list[float], b: list[float]) -> float:
    intersection = max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union if union > 0 else 0.0


def validate_box(box: list[float], width: int, height: int) -> None:
    if (len(box) != 4 or any(not math.isfinite(v) for v in box)
            or not 0 <= box[0] < box[2] <= width or not 0 <= box[1] < box[3] <= height):
        raise ValueError("Invalid finite original-image xyxy box")


def match_detections(truth: list[dict], predictions: list[dict], threshold: float = 0.5) -> dict:
    """Greedy confidence-ordered, same-class, one-to-one match with stable ties.

    Diagnostic links are explanatory and can reuse objects; only TP assignments
    are one-to-one. Confusion/localization still count as an FP and an FN.
    """
    if not 0 < threshold <= 1:
        raise ValueError("Matching IoU must be in (0,1]")
    matched = set()
    matches = []
    false_positives = []
    order = sorted(range(len(predictions)), key=lambda i: (-predictions[i]["confidence"], i))
    overlaps = [[box_iou(p["bbox_xyxy"], t["bbox_xyxy"]) for t in truth] for p in predictions]
    for p_index in order:
        prediction = predictions[p_index]
        same = [t for t in range(len(truth)) if truth[t]["class_id"] == prediction["class_id"]]
        available = [t for t in same if t not in matched and overlaps[p_index][t] >= threshold]
        if available:
            t_index = max(available, key=lambda t: (overlaps[p_index][t], -t))
            matched.add(t_index)
            matches.append({"prediction_index": p_index, "truth_index": t_index, "iou": overlaps[p_index][t_index]})
            continue
        duplicate = [t for t in same if t in matched and overlaps[p_index][t] >= threshold]
        confusion = [t for t in range(len(truth)) if t not in same and overlaps[p_index][t] >= threshold]
        localization = [t for t in same if 0.1 <= overlaps[p_index][t] < threshold]
        category, candidates = ("duplicate", duplicate) if duplicate else (("confusion", confusion) if confusion else (("localization", localization) if localization else ("background", [])))
        t_index = max(candidates, key=lambda t: (overlaps[p_index][t], -t)) if candidates else None
        false_positives.append({"prediction_index": p_index, "category": category, "truth_index": t_index,
                                "iou": overlaps[p_index][t_index] if t_index is not None else 0.0})
    false_negatives = []
    for t_index, target in enumerate(truth):
        if t_index in matched:
            continue
        confusion = [p for p in order if predictions[p]["class_id"] != target["class_id"] and overlaps[p][t_index] >= threshold]
        localization = [p for p in order if predictions[p]["class_id"] == target["class_id"] and 0.1 <= overlaps[p][t_index] < threshold]
        category, candidates = ("confusion", confusion) if confusion else (("localization", localization) if localization else ("missed", []))
        p_index = max(candidates, key=lambda p: (overlaps[p][t_index], predictions[p]["confidence"], -p)) if candidates else None
        false_negatives.append({"truth_index": t_index, "category": category, "prediction_index": p_index,
                                "iou": overlaps[p_index][t_index] if p_index is not None else 0.0})
    return {"matches": matches, "false_positives": false_positives, "false_negatives": false_negatives}


def validation_records(manifest: Path, dataset: Path, expected_images: int = 1921) -> list[dict]:
    """Read manifest metadata, but open image/label bytes only for val originals."""
    records = []
    seen = set()
    prepared = (dataset / "prepared").resolve()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["split"] != "val":
            continue
        sample_id = row["sample_id"]
        if (not isinstance(sample_id, str) or not sample_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in sample_id)
                or row.get("is_mirror") is not False or sample_id.lower().startswith("xmirror_")
                or row.get("assigned_split") != "val" or row.get("exclusion_reason") is not None):
            raise ValueError("Validation requires original, non-excluded frozen val records")
        if sample_id in seen:
            raise ValueError("Duplicate validation sample ID")
        seen.add(sample_id)
        for kind, suffix, digest_key in (("images", ".jpg", "image_sha256"), ("labels", ".txt", "label_sha256")):
            path = (prepared / kind / "val" / (sample_id + suffix)).resolve()
            if not path.is_relative_to(prepared / kind / "val") or not path.is_file() or sha256_file(path) != row[digest_key]:
                raise ValueError(f"Validation {kind} escaped frozen path or digest changed: {sample_id}")
        width, height = row["width"], row["height"]
        if type(width) is not int or type(height) is not int or min(width, height) <= 0 or row.get("exif_orientation") != 1:
            raise ValueError("Validation image dimensions/orientation must be frozen and unambiguous")
        truth = []
        for class_id, x, y, w, h in row["boxes"]:
            if type(class_id) is not int or not 0 <= class_id < 8:
                raise ValueError("Ground truth must use source class IDs 0..7")
            box = [(x - w / 2) * width, (y - h / 2) * height, (x + w / 2) * width, (y + h / 2) * height]
            # Decimal source labels can land a few ulps beyond a border.
            box = [max(0.0, min(value, width if i % 2 == 0 else height)) for i, value in enumerate(box)]
            validate_box(box, width, height)
            truth.append({"class_id": class_id, "bbox_xyxy": box})
        # Ensure the frozen boxes and hashed source labels describe the same objects.
        label_path = prepared / "labels" / "val" / (sample_id + ".txt")
        label_boxes = [[float(value) for value in line.split()] for line in label_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if label_boxes != row["boxes"]:
            raise ValueError(f"Manifest boxes disagree with validation labels: {sample_id}")
        records.append({"sample_id": sample_id, "country": row["country"], "width": width, "height": height,
                        "image_path": str(prepared / "images" / "val" / (sample_id + ".jpg")), "truth": truth})
    if len(records) != expected_images:
        raise ValueError(f"Expected all {expected_images} frozen validation originals, got {len(records)}")
    return sorted(records, key=lambda row: row["sample_id"])


def select_samples(results: list[dict], count: int = 40, seed: int = 42) -> list[dict]:
    """Round-robin error-kind/category/class/country strata, unique images."""
    strata = defaultdict(dict)
    for row in results:
        for kind, objects, index_key in (("FP", row["predictions"], "prediction_index"), ("FN", row["truth"], "truth_index")):
            errors = row["false_positives" if kind == "FP" else "false_negatives"]
            for error in errors:
                class_id = objects[error[index_key]]["class_id"]
                key = (kind, error["category"], class_id, row["country"])
                strata[key][row["sample_id"]] = row
    queues = {key: sorted(values.values(), key=lambda row: hashlib.sha256(f'{seed}:{row["sample_id"]}'.encode()).hexdigest())
              for key, values in strata.items()}
    groups = defaultdict(list)
    for key in sorted(queues):
        groups[key[:2]].append(key)
    # Interleave FP/FN categories before class/country subdivisions, so a large
    # FN stratum cannot consume the entire review budget before any FP appears.
    key_order = [key for layer in zip_longest(*(groups[group] for group in sorted(groups))) for key in layer if key is not None]
    selected, seen = [], set()
    while len(selected) < count:
        progress = False
        for key in key_order:
            queue = queues[key]
            while queue and queue[0]["sample_id"] in seen:
                queue.pop(0)
            if queue and len(selected) < count:
                row = queue.pop(0)
                seen.add(row["sample_id"])
                selected.append({"sample_id": row["sample_id"], "selection_stratum": list(key)})
                progress = True
        if not progress:
            break
    return selected


def render_samples(results: list[dict], selected: list[dict], output: Path, names: list[str]) -> list[str]:
    by_id = {row["sample_id"]: row for row in results}
    directory = output / "samples"
    directory.mkdir()
    comparisons = []
    colors = {"TP": "#30b050", "FN": "#e04040", "FP": "#ff9a00"}
    for number, selection in enumerate(selected, 1):
        row = by_id[selection["sample_id"]]
        with Image.open(row["image_path"]) as raw:
            if raw.size != (row["width"], row["height"]):
                raise ValueError("Image size changed from frozen manifest")
            image = raw.convert("RGB")
        panels = []
        for side, objects in (("truth", row["truth"]), ("predictions", row["predictions"])):
            panel = image.copy()
            draw = ImageDraw.Draw(panel)
            errors = {entry["truth_index" if side == "truth" else "prediction_index"]: entry["category"] for entry in row["false_negatives" if side == "truth" else "false_positives"]}
            for index, obj in enumerate(objects):
                status = ("FN" if side == "truth" else "FP") if index in errors else "TP"
                label = f'{index} {obj["class_id"]}:{names[obj["class_id"]]} {status}'
                if index in errors:
                    label += " " + errors[index]
                if side == "predictions":
                    label += f' {obj["confidence"]:.2f}'
                draw.rectangle(obj["bbox_xyxy"], outline=colors[status], width=3)
                draw.text((obj["bbox_xyxy"][0] + 2, max(0, obj["bbox_xyxy"][1] - 12)), label, fill=colors[status], stroke_width=1, stroke_fill="black")
            panel.thumbnail((600, 560))
            canvas = Image.new("RGB", (600, 600), "white")
            canvas.paste(panel, ((600 - panel.width) // 2, 40))
            ImageDraw.Draw(canvas).text((8, 8), f'{number:02d} {row["sample_id"]} {side} | TP green; FN red; FP orange', fill="black")
            panels.append(canvas)
        comparison = Image.new("RGB", (1200, 600), "white")
        for side, panel in enumerate(panels):
            comparison.paste(panel, (side * 600, 0))
        filename = f'{number:02d}_{row["sample_id"]}.jpg'
        comparison.save(directory / filename, quality=92)
        selection["comparison"] = "samples/" + filename
        comparisons.append(comparison)
    artifacts = [selection["comparison"] for selection in selected]
    for start in range(0, len(comparisons), 12):
        sheet = Image.new("RGB", (1800, 1200), "#dddddd")
        for index, comparison in enumerate(comparisons[start:start + 12]):
            sheet.paste(comparison.resize((600, 300)), ((index % 3) * 600, (index // 3) * 300))
        filename = f"contact-sheet-{start // 12 + 1:02d}.jpg"
        sheet.save(output / filename, quality=90)
        artifacts.append(filename)
    return artifacts


def analyze(weights: Path, run_name: str, *, root: Path = REPO_ROOT, device: str = "cpu", conf: float = 0.25,
            match_iou: float = 0.5, model_factory=None, expected_images: int = 1921) -> Path:
    dataset = (root / "Dataset").resolve()
    if not run_name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in run_name):
        raise ValueError("run_name must contain only letters, digits, hyphens and underscores")
    if not dataset.is_relative_to(root.resolve()) or not 0 < conf < 1 or not 0.1 < match_iou <= 1:
        raise ValueError("Dataset must stay inside repository; conf/matching IoU are invalid")
    if device != "cpu" and not device.isdigit():
        raise ValueError("Device must be cpu or a single CUDA index")
    weights = local_path(str(weights), root)
    if not weights.is_relative_to(dataset) or not weights.is_file() or weights.suffix != ".pt":
        raise ValueError("Weights must be an existing explicit local .pt under Dataset")
    output = (dataset / "error-analysis" / run_name).resolve()
    if not output.is_relative_to(dataset / "error-analysis") or output.exists():
        raise ValueError("Output escaped Dataset/error-analysis or already exists; use a new run name")
    manifest = (dataset / "prepared" / "manifest.jsonl").resolve()
    data_yaml = (dataset / "prepared" / "data.yaml").resolve()
    if not manifest.is_relative_to(dataset / "prepared") or not data_yaml.is_relative_to(dataset / "prepared"):
        raise ValueError("Prepared inputs must remain inside Dataset/prepared")
    validate_dataset_yaml(data_yaml, dataset)
    # Require the actual frozen preparation layout. Do not ask a val loader to
    # discover files or ever enumerate/open train/test images or labels.
    yaml_fields = {line.split(":", 1)[0]: line.split(":", 1)[1].strip() for line in data_yaml.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")}
    if Path(json.loads(yaml_fields["path"])).resolve() != dataset / "prepared" or yaml_fields["val"] != "images/val":
        raise ValueError("Analysis requires frozen Dataset/prepared validation layout")
    input_identity = {"weights_sha256": sha256_file(weights), "manifest_sha256": sha256_file(manifest), "data_yaml_sha256": sha256_file(data_yaml)}
    records = validation_records(manifest, dataset, expected_images)
    real_runtime = model_factory is None
    if real_runtime:
        configure_local_runtime(dataset)
        import torch
        from ultralytics import YOLO
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        model_factory = YOLO
    model = model_factory(str(weights))
    actual_names = model.names
    names = [actual_names[i] for i in range(8)] if isinstance(actual_names, dict) and set(actual_names) == set(range(8)) else list(actual_names)
    if names != source_names():
        raise ValueError("Actual model.names must match eight ordered source IDs 0..7")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "status.json", {"status": "running", **input_identity})
    settings = {"conf": conf, "iou": 0.7, "max_det": 100, "imgsz": 640, "batch": 1,
                "device": device, "half": False, "rect": True, "augment": False, "agnostic_nms": False,
                "save": False, "verbose": False}
    results = []
    counts = [{"tp": 0, "fp": 0, "fn": 0} for _ in names]
    categories = {"fp": Counter(), "fn": Counter()}
    try:
        with (output / "image-results.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
            for number, row in enumerate(records, 1):
                # The API also uses PIL RGB source and single-image CPU inference.
                with Image.open(row["image_path"]) as raw:
                    if raw.size != (row["width"], row["height"]):
                        raise ValueError("Image size differs from frozen manifest")
                    pixels = raw.convert("RGB")
                predicted = model.predict(source=pixels, **settings)
                if len(predicted) != 1:
                    raise ValueError("Single-image predict must return exactly one result")
                if tuple(predicted[0].orig_shape) != (row["height"], row["width"]):
                    raise ValueError("Prediction original shape differs from frozen image")
                boxes = predicted[0].boxes
                if boxes is None:
                    raise ValueError("Prediction is missing detection boxes; empty detections require empty tensors")
                predictions = []
                if boxes is not None:
                    xyxy, classes, confidence = boxes.xyxy.tolist(), boxes.cls.tolist(), boxes.conf.tolist()
                    if not len(xyxy) == len(classes) == len(confidence) or len(xyxy) > settings["max_det"]:
                        raise ValueError("Prediction tensors differ in size or exceed max_det")
                    for box, class_id, score in zip(xyxy, classes, confidence):
                        if not math.isfinite(class_id) or int(class_id) != class_id or not 0 <= class_id < 8 or not math.isfinite(score) or not conf <= score <= 1:
                            raise ValueError("Invalid source class/confidence from predict")
                        validate_box(box, row["width"], row["height"])
                        predictions.append({"class_id": int(class_id), "confidence": float(score), "bbox_xyxy": box})
                diagnostics = match_detections(row["truth"], predictions, match_iou)
                result = {**row, "predictions": predictions, **diagnostics}
                for match in diagnostics["matches"]:
                    counts[predictions[match["prediction_index"]]["class_id"]]["tp"] += 1
                for kind, errors, objects, key in (("fp", diagnostics["false_positives"], predictions, "prediction_index"), ("fn", diagnostics["false_negatives"], row["truth"], "truth_index")):
                    for error in errors:
                        counts[objects[error[key]]["class_id"]][kind] += 1
                        categories[kind][error["category"]] += 1
                stream.write(json.dumps(result, allow_nan=False) + "\n")
                results.append(result)
                if number % 100 == 0 or number == len(records):
                    print(f"Validation originals: {number}/{len(records)}", flush=True)
        if input_identity != {"weights_sha256": sha256_file(weights), "manifest_sha256": sha256_file(manifest), "data_yaml_sha256": sha256_file(data_yaml)}:
            raise ValueError("Analysis inputs changed during inference")
        per_class = []
        for class_id, values in enumerate(counts):
            tp, fp, fn = values["tp"], values["fp"], values["fn"]
            per_class.append({"class_id": class_id, "source_name": names[class_id], **values,
                              "instances": tp + fn, "precision": tp / (tp + fp) if tp + fp else None,
                              "recall": tp / (tp + fn) if tp + fn else None})
        selected = select_samples(results)
        artifacts = render_samples(results, selected, output, names)
        versions = {}
        for package in ("torch", "ultralytics", "Pillow"):
            try:
                versions[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                versions[package] = None
        totals = {key: sum(values[key] for values in counts) for key in ("tp", "fp", "fn")}
        report = {"schema_version": "roadguard-operational-errors-v1", "status": "complete", "split": "val",
                  "images": len(results), "weights_path": weights.relative_to(root).as_posix(), **input_identity,
                  "source_sha256": sha256_file(Path(__file__)), "inference": settings, "match_iou": match_iou,
                  "localization_diagnostic_min_iou": 0.1, "seed": 42,
                  "runtime": {"python": platform.python_version(), "platform": platform.platform(), "packages": versions,
                              "actual_inference_device": str(getattr(getattr(model, "predictor", None), "device", device))},
                  "execution": "real_local_weights" if real_runtime else "injected_test_model",
                  "api_comparison": {"api_device": "cpu", "device_differs": device != "cpu",
                                     "same_rgb_single_image_input": True,
                                     "notes": "Uses conf=.25 by default, IoU=.7, imgsz=640, max_det=100; compare deployed manifest settings separately. GPU kernels can differ from CPU. Explicit float32, rect=True and no augmentation."},
                  "totals": totals, "per_class": per_class, "diagnostic_categories": categories,
                  "sample_selection": selected, "artifacts": artifacts,
                  "limitations": ["Fixed operational point diagnostics, not official mAP or max-F1 validation P/R.",
                                  "Diagnostic links can reuse objects; confusion/localization contribute both FP and FN.",
                                  "Background FP can suggest missing annotations but is not a confirmed label defect.",
                                  "Only frozen validation originals are inferred; no threshold selection or test-image access.",
                                  "Stable ordering/selection; GPU inference is not guaranteed bitwise reproducible.",
                                  "Experimental model; no business acceptance threshold is established."]}
        write_json(output / "report.json", report)
        write_json(output / "status.json", {"status": "complete", "images": len(results), **input_identity})
    except Exception as error:
        write_json(output / "status.json", {"status": "failed", "error": str(error), **input_identity})
        raise
    return output / "report.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", required=True, type=Path)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--match-iou", type=float, default=0.5)
    args = parser.parse_args()
    print(analyze(args.weights, args.run_name, device=args.device, conf=args.conf, match_iou=args.match_iou))


if __name__ == "__main__":
    main()
