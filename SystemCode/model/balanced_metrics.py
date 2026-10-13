"""One low-confidence validation export, reusable offline eight-class sweeps."""

from __future__ import annotations

import argparse
from collections import Counter
import importlib.metadata
import json
import math
from pathlib import Path
import platform

try:
    from .analyze_errors import validation_records, validate_box, match_detections
    from .checkpointing import sha256_file, write_json
    from .evaluate import source_names
    from .train import REPO_ROOT, configure_local_runtime, local_path, validate_dataset_yaml
except ImportError:
    from analyze_errors import validation_records, validate_box, match_detections
    from checkpointing import sha256_file, write_json
    from evaluate import source_names
    from train import REPO_ROOT, configure_local_runtime, local_path, validate_dataset_yaml


THRESHOLDS = (0.001, 0.005, 0.01, 0.02, 0.03, 0.05, 0.075, 0.1, 0.15, 0.2,
              0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95)
PRIMARY_IOU = 0.5
SECONDARY_IOU = 0.3
FAMILIES = ("longitudinal crack", "transverse crack", "alligator crack", "pothole")


def _name(value: str) -> str:
    if not isinstance(value, str) or not value or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in value):
        raise ValueError("Output name must contain only letters, digits, hyphens and underscores")
    return value


def _inside(path: Path, directory: Path, *, file: bool = False) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(directory) or (file and not resolved.is_file()):
        raise ValueError("Input/output must remain inside its Dataset storage boundary")
    return resolved


def _dataset(root: Path) -> Path:
    expected = root.resolve() / "Dataset"
    dataset = (root / "Dataset").resolve()
    if dataset != expected:
        raise ValueError("Repository Dataset must not be redirected by symlink/junction")
    return dataset


def _source_hashes() -> dict:
    return {name: sha256_file(Path(__file__).with_name(name))
            for name in ("balanced_metrics.py", "analyze_errors.py", "evaluate.py", "train.py", "checkpointing.py")}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"Non-finite JSON constant: {value}")


def _json(text: str):
    return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)


def _prepared(root: Path, expected_images: int) -> tuple[Path, Path, Path, list[dict]]:
    dataset = _dataset(root)
    prepared = _inside(dataset / "prepared", dataset)
    manifest = _inside(prepared / "manifest.jsonl", prepared, file=True)
    yaml = _inside(prepared / "data.yaml", prepared, file=True)
    validate_dataset_yaml(yaml, dataset)
    fields = {line.split(":", 1)[0]: line.split(":", 1)[1].strip() for line in yaml.read_text(encoding="utf-8").splitlines()
              if line.strip() and not line.lstrip().startswith("#")}
    if Path(json.loads(fields["path"])).resolve() != prepared or fields["val"] != "images/val":
        raise ValueError("Requires frozen preparation validation layout")
    return dataset, manifest, yaml, validation_records(manifest, dataset, expected_images)


def _identity(weights: Path, manifest: Path, yaml: Path) -> dict:
    return {"weights_sha256": sha256_file(weights), "manifest_sha256": sha256_file(manifest), "data_yaml_sha256": sha256_file(yaml),
            "label_schema_sha256": sha256_file(Path(__file__).with_name("label_schema.json"))}


def _prediction(value: dict, width: int, height: int) -> None:
    if not isinstance(value, dict) or set(value) != {"class_id", "confidence", "bbox_xyxy"}:
        raise ValueError("Prediction requires class_id, confidence and bbox_xyxy")
    if type(value["class_id"]) is not int or not 0 <= value["class_id"] < 8:
        raise ValueError("Prediction must use source class IDs 0..7")
    score = value["confidence"]
    if type(score) not in (int, float) or not math.isfinite(score) or not 0.001 <= score <= 1:
        raise ValueError("Invalid exported confidence")
    box = value["bbox_xyxy"]
    if not isinstance(box, list) or any(type(v) not in (int, float) for v in box):
        raise ValueError("Prediction box must be a numerical list")
    validate_box(box, width, height)


def export_predictions(weights: Path, run_name: str, *, root: Path = REPO_ROOT, imgsz: int = 640,
                       device: str = "cpu", model_factory=None, expected_images: int = 1921) -> Path:
    """Infer only val originals, once per model/resolution; no threshold choice."""
    _name(run_name)
    if type(imgsz) is not int or imgsz not in (640, 832, 960):
        raise ValueError("imgsz must be 640, 832 or 960")
    if device != "cpu" and (not isinstance(device, str) or not device.isdigit()):
        raise ValueError("Device must be cpu or one CUDA index")
    dataset = _dataset(root)
    output = _inside(dataset / "balanced-metrics" / run_name, dataset / "balanced-metrics")
    if output.exists():
        raise ValueError("Export output already exists; use a new name")
    weights = _inside(local_path(str(weights), root), dataset, file=True)
    if weights.suffix != ".pt":
        raise ValueError("Explicit local .pt weights required")
    dataset, manifest, yaml, records = _prepared(root, expected_images)
    identity = _identity(weights, manifest, yaml)
    settings = {"conf": 0.001, "iou": 0.7, "max_det": 100, "imgsz": imgsz, "batch": 1,
                "device": device, "quantize": None, "rect": True, "augment": False,
                "agnostic_nms": False, "save": False, "verbose": False}
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "status.json", {"status": "running", **identity})
    try:
        genuine = model_factory is None
        if genuine:
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
        model_state = {"checked": False, "reason": "injected_test_model"}
        precision_state = {"checked": False, "reason": "injected_test_model"}
        if genuine:
            tensors = list(model.model.state_dict().values())
            if not tensors or any(not bool(torch.isfinite(tensor).all()) for tensor in tensors):
                raise ValueError("Model contains missing or non-finite parameter/buffer tensors")
            model_state = {"checked": True, "finite_tensors": len(tensors)}
        actual = model.names
        names = [actual[i] for i in range(8)] if isinstance(actual, dict) and set(actual) == set(range(8)) else list(actual)
        if names != source_names():
            raise ValueError("Actual model.names must match the eight ordered source classes")
        from PIL import Image
        prediction_path = output / "predictions.jsonl"
        total = 0
        with prediction_path.open("w", encoding="utf-8", newline="\n") as stream:
            for number, row in enumerate(records, 1):
                with Image.open(row["image_path"]) as image:
                    if image.size != (row["width"], row["height"]):
                        raise ValueError("Frozen image dimensions changed")
                    pixels = image.convert("RGB")
                result = model.predict(source=pixels, **settings)
                if genuine and number == 1:
                    predictor = model.predictor
                    backend = predictor.model
                    actual_device = predictor.device
                    tensors = list(backend.model.state_dict().values())
                    floating = [tensor for tensor in tensors if tensor.is_floating_point()]
                    if (backend.fp16 or predictor.args.quantize is not None or not floating
                            or any(tensor.dtype != torch.float32 for tensor in floating)
                            or any(not bool(torch.isfinite(tensor).all()) for tensor in tensors)):
                        raise ValueError("Actual prediction backend is not finite FP32")
                    if actual_device.type != ("cpu" if device == "cpu" else "cuda") or (device != "cpu" and actual_device.index != int(device)):
                        raise ValueError("Actual inference device differs from requested CPU/CUDA index")
                    precision_state = {"checked": True, "floating_tensor_dtype": "torch.float32", "fp16": False,
                                       "quantize": predictor.args.quantize, "actual_device": str(actual_device),
                                       "cuda_matmul_allow_tf32": torch.backends.cuda.matmul.allow_tf32,
                                       "cudnn_allow_tf32": torch.backends.cudnn.allow_tf32,
                                       "float32_matmul_precision": torch.get_float32_matmul_precision()}
                if len(result) != 1 or tuple(result[0].orig_shape) != (row["height"], row["width"]) or result[0].boxes is None:
                    raise ValueError("Missing or incompatible detection result")
                boxes = result[0].boxes
                coordinates, classes, scores = boxes.xyxy.tolist(), boxes.cls.tolist(), boxes.conf.tolist()
                if not len(coordinates) == len(classes) == len(scores) or len(classes) > 100:
                    raise ValueError("Prediction tensor sizes are inconsistent or exceed max_det")
                predictions = []
                for box, class_id, score in zip(coordinates, classes, scores):
                    if not math.isfinite(class_id) or int(class_id) != class_id:
                        raise ValueError("Non-integer source class")
                    prediction = {"class_id": int(class_id), "confidence": float(score), "bbox_xyxy": box}
                    _prediction(prediction, row["width"], row["height"])
                    predictions.append(prediction)
                # Keep model order, including equal-score ties, for reproducibility.
                stream.write(json.dumps({"sample_id": row["sample_id"], "predictions": predictions}, allow_nan=False) + "\n")
                total += len(predictions)
                if number % 100 == 0 or number == len(records):
                    print(f"Raw validation predictions: {number}/{len(records)}", flush=True)
        if _identity(weights, manifest, yaml) != identity:
            raise ValueError("Inputs changed during prediction export")
        versions = {}
        for package in ("torch", "ultralytics", "Pillow"):
            try:
                versions[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                versions[package] = None
        metadata = {"schema_version": "roadguard-balanced-export-v1", "status": "complete", "split": "val",
                    "images": len(records), "predictions": total, "execution": "real_local_weights" if genuine else "injected_test_model",
                    "weights_path": weights.relative_to(root).as_posix(), **identity, "source_names": names,
                    "predictions_file": "predictions.jsonl", "predictions_sha256": sha256_file(prediction_path),
                    "inference": settings, "seed": 42, "source_sha256": sha256_file(Path(__file__)), "source_file_sha256": _source_hashes(),
                    "model_state_validation": model_state, "precision_validation": precision_state,
                    "runtime": {"python": platform.python_version(), "platform": platform.platform(), "packages": versions,
                                "actual_device": str(getattr(getattr(model, "predictor", None), "device", device))},
                    "validation_role": "already_used_for_training_and_model_selection_not_held_out_test"}
        path = output / "export.json"
        write_json(path, metadata)
        write_json(output / "status.json", {"status": "complete", "export_sha256": sha256_file(path), **identity})
        return path
    except Exception as error:
        write_json(output / "status.json", {"status": "failed", "error": str(error), **identity})
        raise


def _thresholds(values) -> tuple[float, ...]:
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError("Thresholds must be a nonempty ordered numerical sequence")
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0.001 <= v <= 1 for v in values):
        raise ValueError("Thresholds must be finite and within export confidence..1")
    if any(a >= b for a, b in zip(values, values[1:])):
        raise ValueError("Thresholds must be strictly increasing and unique")
    return tuple(float(v) for v in values)


def _scores(tp: int, predicted: int, instances: int) -> dict:
    fp, fn = predicted - tp, instances - tp
    return {"tp": tp, "fp": fp, "fn": fn, "instances": instances,
            "precision": tp / predicted if predicted else None, "recall": tp / instances if instances else None,
            "f1": 2 * tp / (predicted + instances) if predicted + instances else None}


def sweep_metrics(rows: list[dict], *, iou: float = PRIMARY_IOU, mode: str = "eight_class", thresholds=THRESHOLDS) -> list[dict]:
    """Match once/image, then accumulate confidence prefixes for every threshold.

    Lower-confidence detections cannot alter earlier greedy TP assignments, so
    prefix TP counts equal rerunning the matcher after each confidence filter.
    """
    thresholds = _thresholds(thresholds)
    if iou not in (PRIMARY_IOU, SECONDARY_IOU) or mode not in ("eight_class", "class_agnostic", "four_family_diagnostic"):
        raise ValueError("Only planned IoUs .5/.3 and named diagnostic modes are allowed")
    names = source_names() if mode == "eight_class" else (list(FAMILIES) if mode == "four_family_diagnostic" else ["damage_any_class_diagnostic"])
    mapping = (lambda class_id: class_id) if mode == "eight_class" else ((lambda class_id: class_id // 2) if mode == "four_family_diagnostic" else (lambda class_id: 0))
    supports = Counter()
    events = []
    seen = set()
    for row in rows:
        if row["sample_id"] in seen:
            raise ValueError("Duplicate sample ID in sweep")
        seen.add(row["sample_id"])
        truth = [{**target, "class_id": mapping(target["class_id"])} for target in row["truth"]]
        predictions = [{**prediction, "class_id": mapping(prediction["class_id"])} for prediction in row["predictions"]]
        supports.update(target["class_id"] for target in truth)
        matches = {entry["prediction_index"]: entry["truth_index"] for entry in match_detections(truth, predictions, iou)["matches"]}
        for index, prediction in enumerate(predictions):
            truth_index = matches.get(index)
            events.append((prediction["confidence"], prediction["class_id"], truth_index is not None,
                           row["predictions"][index]["class_id"], row["truth"][truth_index]["class_id"] if truth_index is not None else None))
    events.sort(key=lambda event: -event[0])
    cursor = 0
    predicted, true_positives = Counter(), Counter()
    subtype_matrix = [[0 for _ in range(8)] for _ in range(8)]
    curve = []
    for threshold in reversed(thresholds):
        while cursor < len(events) and events[cursor][0] >= threshold:
            _, class_id, matched, original_predicted, original_truth = events[cursor]
            predicted[class_id] += 1
            if matched:
                true_positives[class_id] += 1
                subtype_matrix[original_predicted][original_truth] += 1
            cursor += 1
        per_class = [{"class_id": class_id, "source_name": name, **_scores(true_positives[class_id], predicted[class_id], supports[class_id])}
                     for class_id, name in enumerate(names)]
        micro = _scores(sum(true_positives.values()), sum(predicted.values()), sum(supports.values()))
        macro = {metric: sum(row[metric] or 0.0 for row in per_class) / len(names) for metric in ("precision", "recall", "f1")}
        result = {"threshold": threshold, "iou": iou, "mode": mode, "micro": micro, "macro": macro, "per_class": per_class,
                  "macro_definition": f"Unweighted {len(names)} classes; undefined class metrics contribute zero, per_class retains null.",
                  "target_met_micro": micro["precision"] is not None and micro["recall"] is not None and micro["precision"] >= 0.7 and micro["recall"] >= 0.7}
        if mode == "class_agnostic":
            result["localization_matched_subtype_matrix"] = {"rows": "predicted_source_class", "columns": "truth_source_class", "source_names": source_names(),
                                                            "counts": [list(row) for row in subtype_matrix]}
            result["correct_eight_type_among_localized"] = sum(subtype_matrix[i][i] for i in range(8))
            result["wrong_eight_type_among_localized"] = sum(true_positives.values()) - result["correct_eight_type_among_localized"]
        curve.append(result)
    return list(reversed(curve))


def choose_threshold(primary_curve: list[dict]) -> dict:
    """One global confidence threshold; never select using relaxed-IoU results."""
    if not primary_curve or any(row["mode"] != "eight_class" or row["iou"] != PRIMARY_IOU for row in primary_curve):
        raise ValueError("Threshold selection requires primary eight-class IoU=.5 curve")

    def objective(row):
        precision, recall = row["micro"]["precision"], row["micro"]["recall"]
        return (min(precision, recall) if precision is not None and recall is not None else -1,
                row["macro"]["f1"], recall if recall is not None else -1)

    return max(primary_curve, key=objective)


def _load_export(path: Path, root: Path, expected_images: int) -> tuple[dict, list[dict]]:
    dataset = _dataset(root)
    path = _inside(local_path(str(path), root), dataset / "balanced-metrics", file=True)
    metadata = _json(path.read_text(encoding="utf-8"))
    status_path = _inside(path.parent / "status.json", path.parent, file=True)
    status = _json(status_path.read_text(encoding="utf-8"))
    if status.get("status") != "complete" or status.get("export_sha256") != sha256_file(path):
        raise ValueError("Export must have a completed, hash-verified status")
    if (metadata.get("schema_version") != "roadguard-balanced-export-v1" or metadata.get("status") != "complete"
            or metadata.get("split") != "val" or metadata.get("images") != expected_images
            or metadata.get("source_names") != source_names() or metadata.get("predictions_file") != "predictions.jsonl"):
        raise ValueError("Export is not the complete frozen eight-class validation export")
    settings = metadata.get("inference", {})
    if any(settings.get(key) != value for key, value in {"conf": 0.001, "iou": 0.7, "max_det": 100, "batch": 1, "quantize": None,
                                                       "rect": True, "augment": False, "agnostic_nms": False, "save": False}.items()) or settings.get("imgsz") not in (640, 832, 960):
        raise ValueError("Export inference settings differ from planned sweep protocol")
    dataset, manifest, yaml, records = _prepared(root, expected_images)
    weights = _inside(local_path(metadata["weights_path"], root), dataset, file=True)
    identity = _identity(weights, manifest, yaml)
    if identity != {key: metadata.get(key) for key in identity}:
        raise ValueError("Export weights, manifest, YAML or label schema hash changed")
    raw_path = _inside(path.parent / "predictions.jsonl", path.parent, file=True)
    if sha256_file(raw_path) != metadata["predictions_sha256"]:
        raise ValueError("Raw predictions hash changed")
    by_id = {row["sample_id"]: row for row in records}
    rows = []
    total = 0
    seen = set()
    with raw_path.open(encoding="utf-8") as stream:
        for line in stream:
            raw = _json(line)
            if not isinstance(raw, dict) or set(raw) != {"sample_id", "predictions"} or not isinstance(raw["predictions"], list):
                raise ValueError("Invalid raw prediction record")
            sample_id = raw["sample_id"]
            if not isinstance(sample_id, str) or sample_id not in by_id or sample_id in seen:
                raise ValueError("Raw export contains unknown/non-validation/duplicate sample ID")
            seen.add(sample_id)
            row = by_id[sample_id]
            if len(raw["predictions"]) > 100:
                raise ValueError("Raw export exceeds max_det")
            for prediction in raw["predictions"]:
                _prediction(prediction, row["width"], row["height"])
            total += len(raw["predictions"])
            rows.append({**row, "predictions": raw["predictions"]})
    if seen != set(by_id) or total != metadata["predictions"]:
        raise ValueError("Raw export does not contain every frozen validation image/prediction")
    return metadata, sorted(rows, key=lambda row: row["sample_id"])


def analyze_export(export_path: Path, analysis_name: str = "sweep", *, root: Path = REPO_ROOT,
                   thresholds=THRESHOLDS, expected_images: int = 1921) -> Path:
    """Pure offline analysis; refuses partial, changed or non-val prediction data."""
    _name(analysis_name)
    thresholds = _thresholds(thresholds)
    dataset = _dataset(root)
    export_path = _inside(local_path(str(export_path), root), dataset / "balanced-metrics", file=True)
    output = _inside(export_path.parent / "analyses" / analysis_name, export_path.parent / "analyses")
    if output.exists():
        raise ValueError("Analysis output already exists; use a new name")
    metadata, rows = _load_export(export_path, root, expected_images)
    output.mkdir(parents=True, exist_ok=False)
    export_digest = sha256_file(export_path)
    write_json(output / "status.json", {"status": "running", "export_sha256": export_digest})
    try:
        curves = {}
        for iou, role in ((PRIMARY_IOU, "primary_iou_0_5"), (SECONDARY_IOU, "secondary_iou_0_3_diagnostic")):
            curves[role] = {mode: sweep_metrics(rows, iou=iou, mode=mode, thresholds=thresholds)
                            for mode in ("eight_class", "class_agnostic", "four_family_diagnostic")}
        selected = choose_threshold(curves["primary_iou_0_5"]["eight_class"])
        threshold = selected["threshold"]
        selected_diagnostics = {role: {mode: next(row for row in curve if row["threshold"] == threshold) for mode, curve in modes.items()}
                                for role, modes in curves.items()}
        report = {"schema_version": "roadguard-balanced-sweep-v1", "status": "complete", "split": "val", "images": len(rows),
                  "execution": metadata["execution"], "export_path": export_path.relative_to(root).as_posix(), "export_sha256": export_digest,
                  "input_identity": {key: metadata[key] for key in ("weights_sha256", "manifest_sha256", "data_yaml_sha256", "label_schema_sha256", "predictions_sha256")},
                  "export_source_sha256": metadata["source_sha256"], "analysis_source_sha256": sha256_file(Path(__file__)),
                  "export_source_file_sha256": metadata["source_file_sha256"], "analysis_source_file_sha256": _source_hashes(),
                  "inference": metadata["inference"], "thresholds": list(thresholds), "primary_iou": PRIMARY_IOU, "secondary_iou": SECONDARY_IOU,
                  "selection_rule": "one global threshold: maximize micro min(P,R), then eight-class macro F1, then micro recall; exact ties keep the first ascending grid value; primary IoU=.5 only",
                  "selected_threshold": threshold, "selected_primary": selected, "selected_diagnostics": selected_diagnostics,
                  "any_threshold_meets_micro_target": any(row["target_met_micro"] for row in curves["primary_iou_0_5"]["eight_class"]),
                  "selected_all_eight_classes_meet_target": all((row["precision"] or 0) >= 0.7 and (row["recall"] or 0) >= 0.7 for row in selected["per_class"]),
                  "curves": curves,
                  "limitations": ["Threshold and model selection use validation already used during training; this is not a new holdout or test result.",
                                  "Primary matching remains eight source types at IoU=.5. IoU=.3, class-agnostic and four-family numbers are separate diagnostics only.",
                                  "Validation operating-point P/R are not official mAP, business acceptance or calibrated probabilities.",
                                  "Raw confidence floor=.001, max_det=100 and class-aware NMS=.7 limit retained candidates; sweep does not rerun NMS.",
                                  "Macro averages all eight types with undefined values contributing zero; each undefined per-class value remains null."]}
        if sha256_file(export_path) != export_digest or sha256_file(export_path.parent / "predictions.jsonl") != metadata["predictions_sha256"]:
            raise ValueError("Export changed during offline analysis")
        path = output / "report.json"
        write_json(path, report)
        write_json(output / "status.json", {"status": "complete", "report_sha256": sha256_file(path), "export_sha256": export_digest})
        return path
    except Exception as error:
        write_json(output / "status.json", {"status": "failed", "error": str(error), "export_sha256": export_digest})
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="one actual GPU/CPU inference pass on validation only")
    export.add_argument("--weights", type=Path, required=True)
    export.add_argument("--run-name", required=True)
    export.add_argument("--imgsz", type=int, choices=(640, 832, 960), default=640)
    export.add_argument("--device", default="cpu")
    sweep = commands.add_parser("analyze", help="offline confidence sweep; no vision runtime import")
    sweep.add_argument("--export", dest="export_path", type=Path, required=True)
    sweep.add_argument("--analysis-name", default="sweep")
    args = parser.parse_args()
    if args.command == "export":
        print(export_predictions(args.weights, args.run_name, imgsz=args.imgsz, device=args.device))
    else:
        print(analyze_export(args.export_path, args.analysis_name))


if __name__ == "__main__":
    main()
