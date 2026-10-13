"""Bounded validation inference experiments with atomic image-by-image recovery.

New experiment exports are separate from frozen balanced-export-v1 artifacts.
No training, downloads, backend changes, test access or class merging occurs.
"""

from __future__ import annotations

import argparse
import copy
import importlib.metadata
import math
from pathlib import Path
import platform

try:
    from . import balanced_metrics as balanced
    from .analyze_errors import box_iou, validate_box
    from .checkpointing import fingerprint, sha256_file, write_json
    from .train import REPO_ROOT, configure_local_runtime, local_path
except ImportError:
    import balanced_metrics as balanced
    from analyze_errors import box_iou, validate_box
    from checkpointing import fingerprint, sha256_file, write_json
    from train import REPO_ROOT, configure_local_runtime, local_path

SCHEMA = "roadguard-inference-experiment-v1"
MAX_DET = 100
PAIRED_IOU = 0.55
TILE_FRACTION = 0.625
SELECTION_RULE = "max primary same-class IoU=.5 micro min(P,R), then eight-class macro F1, then micro recall; exact ties keep ascending threshold/input candidate order"


def _validate_prediction_geometry(prediction: dict) -> None:
    if not isinstance(prediction, dict) or set(prediction) != {"class_id", "confidence", "bbox_xyxy"}:
        raise ValueError("Detection must preserve source class, confidence and original pixel xyxy")
    box = prediction["bbox_xyxy"]
    if (not isinstance(box, list) or len(box) != 4 or any(type(value) not in (int, float) or not math.isfinite(value) for value in box)):
        raise ValueError("Detection box must contain four finite numeric coordinates")
    balanced._prediction(prediction, max(box[2], 1), max(box[3], 1))


def tile_regions(width: int, height: int) -> list[list[int]]:
    if type(width) is not int or type(height) is not int or min(width, height) < 1:
        raise ValueError("Tile dimensions must be positive integers")
    tw, th = math.ceil(width * TILE_FRACTION), math.ceil(height * TILE_FRACTION)
    # Deduplicate identical corners for tiny images; full image is kept separately.
    return [list(region) for region in dict.fromkeys((x, y, x + tw, y + th)
            for y in (0, height - th) for x in (0, width - tw))]


def views(method: str, width: int, height: int) -> list[dict]:
    full = {"crop": [0, 0, width, height], "flip": False}
    if method == "standard":
        return [full]
    if method == "flip":
        return [full, {**full, "flip": True}]
    if method == "tiles":
        return [full, *[{"crop": region, "flip": False} for region in tile_regions(width, height)]]
    raise ValueError("Method must be standard, flip or tiles")


def project_box(box: list[float], view: dict, width: int, height: int) -> list[float]:
    left, top, right, bottom = view["crop"]
    if not 0 <= left < right <= width or not 0 <= top < bottom <= height:
        raise ValueError("View crop escapes original image")
    if not isinstance(box, list) or any(type(value) not in (int, float) for value in box):
        raise ValueError("View box must contain finite numeric pixel coordinates")
    validate_box(box, right - left, bottom - top)
    x1, y1, x2, y2 = box
    if view["flip"]:
        x1, x2 = right - left - x2, right - left - x1
    projected = [x1 + left, y1 + top, x2 + left, y2 + top]
    validate_box(projected, width, height)
    return projected


def class_aware_nms(predictions: list[dict], iou: float = 0.5, max_det: int = MAX_DET) -> list[dict]:
    if type(iou) not in (int, float) or iou not in (0.5, 0.7) or type(max_det) is not int or not 1 <= max_det <= MAX_DET:
        raise ValueError("Global class-aware NMS requires IoU .5/.7 and max_det<=100")
    retained = []
    for prediction in predictions:
        _validate_prediction_geometry(prediction)
    for index in sorted(range(len(predictions)), key=lambda index: (-predictions[index]["confidence"], index)):
        prediction = predictions[index]
        if not any(prediction["class_id"] == other["class_id"] and box_iou(prediction["bbox_xyxy"], other["bbox_xyxy"]) > iou for other in retained):
            retained.append(copy.deepcopy(prediction))
            if len(retained) == max_det:
                break
    return retained


def paired_score_fusion(models: list[list[dict]], *, iou: float = PAIRED_IOU) -> list[dict]:
    """Two-model heuristic: one vote/model, weighted boxes, absent vote scores zero.

    Highest-score seeds greedily match one unused same-class box from the other
    model by IoU, then score/index. This is not calibrated confidence or library WBF.
    """
    if len(models) != 2 or iou != PAIRED_IOU:
        raise ValueError("Paired-score requires exactly two models and fixed IoU .55")
    for predictions in models:
        for prediction in predictions:
            _validate_prediction_geometry(prediction)
    candidates = [(model, index, prediction) for model, predictions in enumerate(models) for index, prediction in enumerate(predictions)]
    candidates.sort(key=lambda item: (-item[2]["confidence"], item[0], item[1]))
    used, fused = set(), []
    for model, index, seed in candidates:
        if (model, index) in used:
            continue
        used.add((model, index))
        other_model = 1 - model
        possible = [(other_index, prediction) for other_index, prediction in enumerate(models[other_model])
                    if (other_model, other_index) not in used and prediction["class_id"] == seed["class_id"]
                    and box_iou(prediction["bbox_xyxy"], seed["bbox_xyxy"]) >= iou]
        cluster = [seed]
        provenance = [(model, index)]
        if possible:
            other_index, other = max(possible, key=lambda item: (box_iou(item[1]["bbox_xyxy"], seed["bbox_xyxy"]), item[1]["confidence"], -item[0]))
            used.add((other_model, other_index))
            cluster.append(other)
            provenance.append((other_model, other_index))
        total = sum(prediction["confidence"] for prediction in cluster)
        score = total / 2
        if score >= 0.001:  # Below the fixed sweep floor cannot affect any point.
            coordinates = list(seed["bbox_xyxy"]) if len(cluster) == 1 else [
                min(max(sum(prediction["bbox_xyxy"][axis] * prediction["confidence"] for prediction in cluster) / total,
                        min(prediction["bbox_xyxy"][axis] for prediction in cluster)),
                    max(prediction["bbox_xyxy"][axis] for prediction in cluster)) for axis in range(4)]
            fused.append((min(provenance), {"class_id": seed["class_id"], "confidence": score, "bbox_xyxy": coordinates}))
    # Pairing uses raw-score seed order, but final equal fused-score ties must
    # follow original source/model index, not the raw score of a seed.
    return [prediction for _, prediction in sorted(fused, key=lambda item: item[0])]


def _read(path: Path) -> dict:
    value = balanced._json(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def _runtime() -> dict:
    versions = {}
    for package in ("torch", "ultralytics", "Pillow", "numpy"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return {"python": platform.python_version(), "platform": platform.platform(), "packages": versions}


def _source_hashes() -> dict:
    return {**balanced._source_hashes(), Path(__file__).name: sha256_file(Path(__file__))}


def _protocol(root: Path) -> dict:
    directory = balanced._dataset(root) / "inference-followup"
    paths = [directory / "plan.json", directory / "protocol-clarifications.json"]
    if not any(path.exists() for path in paths):
        return {}  # Isolated fake-model unit fixtures do not contain a live plan.
    if not all(path.is_file() for path in paths):
        raise ValueError("Both preregistered inference plan and clarifications are required")
    plan, clarifications = [_read(path) for path in paths]
    if (plan.get("schema_version") != "roadguard-inference-followup-plan-v1"
            or clarifications.get("schema_version") != "roadguard-inference-followup-clarifications-v1"
            or clarifications.get("base_plan_sha256") != sha256_file(paths[0])
            or plan.get("budget", {}).get("candidate_count") != 8
            or plan.get("common", {}).get("threshold_grid") != list(balanced.THRESHOLDS)):
        raise ValueError("Invalid frozen eight-candidate plan/clarification linkage")
    inputs = plan.get("inputs", {})
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError("Preregistered plan must bind original input file hashes")
    for item in inputs.values():
        path = local_path(item["path"], root)
        allowed_schema = (root / "SystemCode/model/label_schema.json").resolve()
        if (not path.is_relative_to(balanced._dataset(root)) and path != allowed_schema) or not path.is_file():
            raise ValueError("Registered input escaped its Dataset/label-schema boundary or is missing")
        if sha256_file(path) != item["sha256"]:
            raise ValueError("Preregistered original input hash changed")
    return {path.name: sha256_file(path) for path in paths}


def _record_hash(record: dict) -> str:
    # image_path is machine-specific; bytes are already checked against manifest.
    return fingerprint({key: value for key, value in record.items() if key != "image_path"})


def _output(root: Path, name: str) -> Path:
    balanced._name(name)
    dataset = balanced._dataset(root)
    return balanced._inside(dataset / "inference-followup" / name, dataset / "inference-followup")


def _identity(config: dict, root: Path, manifest: Path, yaml: Path, execution: str) -> dict:
    identity = {"config": config, "manifest_sha256": sha256_file(manifest), "data_yaml_sha256": sha256_file(yaml),
                "label_schema_sha256": sha256_file(Path(__file__).with_name("label_schema.json")),
                "source_file_sha256": _source_hashes(), "runtime": _runtime(), "execution": execution,
                "preregistered_protocol_sha256": _protocol(root)}
    identity["weights"] = [{"path": path, "sha256": sha256_file(balanced._inside(local_path(path, root), balanced._dataset(root), file=True))}
                           for path in config.get("weights", [])]
    identity["source_exports"] = [{"path": path, "sha256": sha256_file(local_path(path, root))} for path in config.get("exports", [])]
    return identity


def _start(output: Path, identity: dict, resume: bool) -> dict:
    plan = {"schema_version": SCHEMA, "identity": identity, "identity_sha256": fingerprint(identity)}
    if output.exists():
        if not resume:
            raise ValueError("Experiment exists; explicit --resume is required")
        if _read(output / "plan.json") != plan:
            raise ValueError("Resume identity changed: config/input/weights/code/runtime/execution differ")
    else:
        if resume:
            raise ValueError("Cannot resume a nonexistent experiment")
        output.mkdir(parents=True)
        write_json(output / "plan.json", plan)
        (output / "images").mkdir()
    return plan


def _image_path(output: Path, sample_id: str) -> Path:
    balanced._name(sample_id)
    return balanced._inside(output / "images" / f"{sample_id}.json", output / "images")


def _realized_views(config: dict, row: dict) -> list[dict]:
    return views(config["method"], row["width"], row["height"]) if config["method"] in ("standard", "flip", "tiles") else []


def _read_image(path: Path, row: dict, identity_sha256: str, config: dict) -> dict:
    value = _read(path)
    if (set(value) != {"sample_id", "record_sha256", "identity_sha256", "predictions", "realized_views", "payload_sha256"}
            or value["sample_id"] != row["sample_id"] or value["record_sha256"] != _record_hash(row)
            or value["identity_sha256"] != identity_sha256 or not isinstance(value["predictions"], list)
            or len(value["predictions"]) > MAX_DET or value["realized_views"] != _realized_views(config, row)):
        raise ValueError("Per-image result has a mismatched input/config identity")
    if value["payload_sha256"] != fingerprint({key: item for key, item in value.items() if key != "payload_sha256"}):
        raise ValueError("Per-image prediction payload changed since atomic publication")
    for prediction in value["predictions"]:
        balanced._prediction(prediction, row["width"], row["height"])
    return value


def _write_image(output: Path, row: dict, predictions: list[dict], identity_sha256: str, config: dict) -> None:
    for prediction in predictions:
        balanced._prediction(prediction, row["width"], row["height"])
    if len(predictions) > MAX_DET:
        raise ValueError("Global output exceeds max_det")
    value = {"sample_id": row["sample_id"], "record_sha256": _record_hash(row), "identity_sha256": identity_sha256,
             "predictions": predictions, "realized_views": _realized_views(config, row)}
    value["payload_sha256"] = fingerprint(value)
    write_json(_image_path(output, row["sample_id"]), value)


def _finish(output: Path, rows: list[dict], plan: dict, validation: dict) -> Path:
    expected = {row["sample_id"] + ".json" for row in rows}
    if {path.name for path in (output / "images").glob("*.json")} != expected:
        raise ValueError("Experiment requires exactly all frozen validation image results")
    index, total = {}, 0
    for row in rows:
        path = _image_path(output, row["sample_id"])
        value = _read_image(path, row, plan["identity_sha256"], plan["identity"]["config"])
        index[row["sample_id"]] = sha256_file(path)
        total += len(value["predictions"])
    metadata = {**plan, "status": "complete", "split": "val", "images": len(rows), "predictions": total,
                "source_names": balanced.source_names(), "image_results_sha256": index, "validation": validation,
                "validation_role": "already_used_for_training_and_model_selection_not_held_out_test"}
    path = output / "export.json"
    write_json(path, metadata)
    write_json(output / "status.json", {"status": "complete", "identity_sha256": plan["identity_sha256"], "export_sha256": sha256_file(path)})
    return path


def _genuine(metadata: dict) -> bool:
    if metadata.get("schema_version") == SCHEMA:
        checks = metadata.get("validation", {})
        return (metadata["identity"].get("execution") == "real_local_weights" and checks.get("model_state_validation", {}).get("checked") is True
                and checks.get("precision_validation", {}).get("checked") is True)
    precision = metadata.get("precision_validation", {})
    return (metadata.get("execution") == "real_local_weights" and metadata.get("model_state_validation", {}).get("checked") is True
            and precision.get("checked") is True and precision.get("floating_tensor_dtype") == "torch.float32"
            and precision.get("fp16") is False and precision.get("quantize") is None)


def load_export(path: Path, *, root: Path = REPO_ROOT, expected_images: int = 1921) -> tuple[dict, list[dict]]:
    path = local_path(str(path), root)
    dataset = balanced._dataset(root)
    if path.resolve().is_relative_to(dataset / "balanced-metrics"):
        # Original frozen loader and its restrictions are deliberately untouched.
        return balanced._load_export(path, root, expected_images)
    path = balanced._inside(path, dataset / "inference-followup", file=True)
    metadata = _read(path)
    if (metadata.get("schema_version") != SCHEMA or metadata.get("status") != "complete" or metadata.get("split") != "val"
            or metadata.get("images") != expected_images or metadata.get("source_names") != balanced.source_names()):
        raise ValueError("Experiment is not a complete eight-class validation export")
    plan = _read(path.parent / "plan.json")
    if metadata.get("identity") != plan.get("identity") or metadata.get("identity_sha256") != fingerprint(plan["identity"]):
        raise ValueError("Changed experiment plan/identity")
    status = _read(path.parent / "status.json")
    if status != {"status": "complete", "identity_sha256": metadata["identity_sha256"], "export_sha256": sha256_file(path)}:
        raise ValueError("Export must have a complete hash-verified status")
    _, manifest, yaml, rows = balanced._prepared(root, expected_images)
    identity = _identity(plan["identity"]["config"], root, manifest, yaml, plan["identity"]["execution"])
    if identity != plan["identity"]:
        raise ValueError("Experiment input/weights/source export/code/runtime changed")
    for source in plan["identity"]["config"].get("exports", []):
        # Verify underlying raw source exports and checkpoints too, not just their metadata.
        source_metadata, _ = load_export(Path(source), root=root, expected_images=expected_images)
        if not _genuine(source_metadata):
            raise ValueError("Derived experiment source is not genuine validated model evidence")
    index = metadata.get("image_results_sha256", {})
    if (set(index) != {row["sample_id"] for row in rows}
            or {image.name for image in (path.parent / "images").glob("*.json")} != {row["sample_id"] + ".json" for row in rows}):
        raise ValueError("Incomplete or extra experiment image results")
    results, total = [], 0
    for row in rows:
        image_path = _image_path(path.parent, row["sample_id"])
        if sha256_file(image_path) != index[row["sample_id"]]:
            raise ValueError("Per-image result changed after completion")
        predictions = _read_image(image_path, row, metadata["identity_sha256"], plan["identity"]["config"])["predictions"]
        total += len(predictions)
        results.append({**row, "predictions": predictions})
    if total != metadata["predictions"]:
        raise ValueError("Export prediction count mismatch")
    return metadata, results


def _decode_prediction(result, width: int, height: int) -> list[dict]:
    if len(result) != 1 or tuple(result[0].orig_shape) != (height, width) or result[0].boxes is None:
        raise ValueError("Missing or incompatible single-view detection result")
    boxes = result[0].boxes
    coordinates, classes, scores = boxes.xyxy.tolist(), boxes.cls.tolist(), boxes.conf.tolist()
    if not len(coordinates) == len(classes) == len(scores) or len(classes) > MAX_DET:
        raise ValueError("Prediction tensors are inconsistent or exceed max_det")
    predictions = []
    for box, class_id, score in zip(coordinates, classes, scores):
        if not math.isfinite(class_id) or int(class_id) != class_id:
            raise ValueError("Non-integer source class")
        prediction = {"class_id": int(class_id), "confidence": float(score), "bbox_xyxy": box}
        balanced._prediction(prediction, width, height)
        predictions.append(prediction)
    return predictions


def _precision_check(model, torch, device: str) -> dict:
    predictor, backend = model.predictor, model.predictor.model
    tensors = list(backend.model.state_dict().values())
    floating = [tensor for tensor in tensors if tensor.is_floating_point()]
    actual = predictor.device
    if (backend.fp16 or predictor.args.quantize is not None or not floating
            or any(tensor.dtype != torch.float32 for tensor in floating)
            or any(not bool(torch.isfinite(tensor).all()) for tensor in tensors)
            or actual.type != ("cpu" if device == "cpu" else "cuda") or (device != "cpu" and actual.index != int(device))):
        raise ValueError("Actual prediction backend is not finite FP32 on requested device")
    return {"checked": True, "floating_tensor_dtype": "torch.float32", "fp16": False, "quantize": None, "actual_device": str(actual),
            "cuda_matmul_allow_tf32": torch.backends.cuda.matmul.allow_tf32, "cudnn_allow_tf32": torch.backends.cudnn.allow_tf32,
            "float32_matmul_precision": torch.get_float32_matmul_precision()}


def export_predictions(weights: Path, run_name: str, *, root: Path = REPO_ROOT, method: str = "standard", imgsz: int = 832,
                       nms_iou: float = 0.7, device: str = "cpu", resume: bool = False, model_factory=None, expected_images: int = 1921) -> Path:
    if type(imgsz) is not int or imgsz not in (640, 832, 960) or nms_iou not in (0.5, 0.7):
        raise ValueError("Planned sizes are 640/832/960; global NMS IoU .5/.7")
    if not isinstance(device, str) or (device != "cpu" and not device.isdigit()):
        raise ValueError("Device must be cpu or one CUDA index")
    views(method, 100, 100)
    dataset, manifest, yaml, rows = balanced._prepared(root, expected_images)
    weights = balanced._inside(local_path(str(weights), root), dataset, file=True)
    if weights.suffix != ".pt":
        raise ValueError("Explicit local .pt weights required")
    settings = {"conf": 0.001, "iou": 0.7, "max_det": MAX_DET, "imgsz": imgsz, "batch": 1, "device": device,
                "quantize": None, "rect": True, "augment": False, "agnostic_nms": False, "save": False, "verbose": False}
    config = {"method": method, "weights": [weights.relative_to(root).as_posix()], "settings": settings,
              "global_nms_iou": nms_iou, "max_det": MAX_DET, "tile_fraction": TILE_FRACTION if method == "tiles" else None,
              "seed": 42, "expected_images": expected_images}
    genuine = model_factory is None
    execution = "real_local_weights" if genuine else "injected_test_model"
    identity = _identity(config, root, manifest, yaml, execution)
    output = _output(root, run_name)
    plan = _start(output, identity, resume)
    if (output / "status.json").is_file() and _read(output / "status.json").get("status") == "complete":
        load_export(output / "export.json", root=root, expected_images=expected_images)
        return output / "export.json"
    validation = {"model_state_validation": {"checked": False, "reason": "injected_test_model"},
                  "precision_validation": {"checked": False, "reason": "injected_test_model"}}
    try:
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
        actual = model.names
        names = [actual[index] for index in range(8)] if isinstance(actual, dict) and set(actual) == set(range(8)) else list(actual)
        if names != balanced.source_names():
            raise ValueError("Actual model.names must preserve all eight ordered source classes")
        if genuine:
            tensors = list(model.model.state_dict().values())
            if not tensors or any(not bool(torch.isfinite(tensor).all()) for tensor in tensors):
                raise ValueError("Missing/non-finite model tensors")
            validation["model_state_validation"] = {"checked": True, "finite_tensors": len(tensors)}
        # A prior precision check belongs to the same bound runtime/config/weights.
        if resume and (output / "validation.json").is_file():
            validation = _read(output / "validation.json")
        backend_checked_this_process = False
        from PIL import Image
        for number, row in enumerate(rows, 1):
            image_path = _image_path(output, row["sample_id"])
            if image_path.is_file():
                _read_image(image_path, row, plan["identity_sha256"], config)
                continue
            write_json(output / "status.json", {"status": "running", "identity_sha256": plan["identity_sha256"], "next_image": row["sample_id"]})
            with Image.open(row["image_path"]) as raw:
                if raw.size != (row["width"], row["height"]):
                    raise ValueError("Frozen image dimensions changed")
                pixels = raw.convert("RGB")
            predictions = []
            for view in views(method, row["width"], row["height"]):
                source = pixels.crop(view["crop"])
                if view["flip"]:
                    source = source.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                result = model.predict(source=source, **settings)
                if genuine and not backend_checked_this_process:
                    validation["precision_validation"] = _precision_check(model, torch, device)
                    backend_checked_this_process = True
                    write_json(output / "validation.json", validation)
                for prediction in _decode_prediction(result, source.width, source.height):
                    prediction["bbox_xyxy"] = project_box(prediction["bbox_xyxy"], view, row["width"], row["height"])
                    predictions.append(prediction)
            # Standard .7 is exactly the original detector export semantics: no
            # second suppression or reordering after its own per-view NMS .7.
            merged = predictions if method == "standard" and nms_iou == 0.7 else class_aware_nms(predictions, nms_iou)
            _write_image(output, row, merged, plan["identity_sha256"], config)
            if number % 100 == 0 or number == len(rows):
                print(f"{method}: validation originals {number}/{len(rows)}", flush=True)
        if _identity(config, root, manifest, yaml, execution) != identity:
            raise ValueError("Inputs changed during experiment")
        if genuine and validation["precision_validation"].get("checked") is not True:
            raise ValueError("Missing actual FP32 backend check")
        return _finish(output, rows, plan, validation)
    except BaseException as error:
        write_json(output / "status.json", {"status": "failed", "identity_sha256": plan["identity_sha256"], "error": str(error)})
        raise


def fuse_exports(exports: list[Path], run_name: str, *, root: Path = REPO_ROOT, strategy: str = "union_nms",
                 nms_iou: float = 0.5, resume: bool = False, expected_images: int = 1921) -> Path:
    if len(exports) not in (1, 2) or strategy not in ("union_nms", "paired_score") or nms_iou not in (0.5, 0.7):
        raise ValueError("Fusion requires one/two exports, union_nms/paired_score, and NMS .5/.7")
    loaded = [load_export(path, root=root, expected_images=expected_images) for path in exports]
    if not all(_genuine(metadata) for metadata, _ in loaded):
        raise ValueError("Fusion requires real validated exports; injected models cannot become real evidence")
    if strategy == "paired_score":
        hashes = [[metadata["weights_sha256"]] if metadata.get("schema_version") != SCHEMA else
                  [entry["sha256"] for entry in metadata["identity"]["weights"]] for metadata, _ in loaded]
        if len(exports) != 2 or any(len(items) != 1 for items in hashes) or hashes[0] == hashes[1]:
            raise ValueError("Paired-score requires two distinct model checkpoints")
    rows = loaded[0][1]
    if any([_record_hash({key: value for key, value in row.items() if key != "predictions"}) for row in records] !=
           [_record_hash({key: value for key, value in row.items() if key != "predictions"}) for row in rows] for _, records in loaded[1:]):
        raise ValueError("Source exports use different frozen validation inputs")
    rows = [{key: value for key, value in row.items() if key != "predictions"} for row in rows]
    dataset, manifest, yaml, _ = balanced._prepared(root, expected_images)
    config = {"method": "cached_post_nms" if len(exports) == 1 else strategy, "exports": [local_path(str(path), root).relative_to(root).as_posix() for path in exports],
              "global_nms_iou": nms_iou, "paired_iou": PAIRED_IOU if strategy == "paired_score" else None,
              "max_det": MAX_DET, "expected_images": expected_images}
    identity = _identity(config, root, manifest, yaml, "real_local_weights")
    output = _output(root, run_name)
    plan = _start(output, identity, resume)
    if (output / "status.json").is_file() and _read(output / "status.json").get("status") == "complete":
        load_export(output / "export.json", root=root, expected_images=expected_images)
        return output / "export.json"
    try:
        for number, row in enumerate(rows):
            image_path = _image_path(output, row["sample_id"])
            if image_path.is_file():
                _read_image(image_path, row, plan["identity_sha256"], config)
                continue
            model_predictions = [records[number]["predictions"] for _, records in loaded]
            merged = paired_score_fusion(model_predictions) if strategy == "paired_score" else [prediction for predictions in model_predictions for prediction in predictions]
            _write_image(output, row, class_aware_nms(merged, nms_iou), plan["identity_sha256"], config)
        if _identity(config, root, manifest, yaml, "real_local_weights") != identity:
            raise ValueError("Fusion input export changed")
        for source in exports:
            load_export(source, root=root, expected_images=expected_images)
        return _finish(output, rows, plan, {"model_state_validation": {"checked": True, "inherited_from_validated_sources": True},
                       "precision_validation": {"checked": True, "inherited_from_validated_sources": True}})
    except BaseException as error:
        write_json(output / "status.json", {"status": "failed", "identity_sha256": plan["identity_sha256"], "error": str(error)})
        raise


def metrics(metadata: dict, rows: list[dict]) -> dict:
    primary = balanced.sweep_metrics(rows, iou=0.5, thresholds=balanced.THRESHOLDS)
    secondary = balanced.sweep_metrics(rows, iou=0.3, thresholds=balanced.THRESHOLDS)
    selected = balanced.choose_threshold(primary)
    return {"schema_version": "roadguard-inference-experiment-metrics-v1", "split": "val", "images": len(rows),
            "execution": "real_local_weights" if _genuine(metadata) else "injected_test_model",
            "thresholds": list(balanced.THRESHOLDS), "primary_iou": 0.5, "secondary_iou": 0.3,
            "selection_rule": SELECTION_RULE, "selected_primary": selected,
            "selected_secondary_diagnostic": next(point for point in secondary if point["threshold"] == selected["threshold"]),
            "primary_curve": primary, "secondary_curve_diagnostic": secondary,
            "target_met_micro": selected["target_met_micro"],
            "selected_all_eight_classes_meet_target": all((row["precision"] or 0) >= 0.7 and (row["recall"] or 0) >= 0.7 for row in selected["per_class"]),
            "test_used": False, "status": "experimental",
            "limitations": ["Already-used validation is not a new holdout or test result.", "All eight source classes retained; secondary IoU=.3 does not select candidates.",
                            "Paired-score is an uncalibrated heuristic, not a probability or library WBF implementation.",
                            "Local confidence floor .001 and per-view/global max_det100 bound retained candidates."]}


def analyze_export(path: Path, *, root: Path = REPO_ROOT, expected_images: int = 1921) -> Path:
    metadata, rows = load_export(path, root=root, expected_images=expected_images)
    path = local_path(str(path), root)
    report = metrics(metadata, rows)
    report.update(export_path=path.relative_to(root).as_posix(), export_sha256=sha256_file(path), source_file_sha256=_source_hashes())
    output = path.parent / "experiment-metrics.json"
    if output.exists():
        raise ValueError("Metrics already exist; refusing to replace evidence")
    # Do not write into the original balanced export storage subtree.
    if not output.resolve().is_relative_to(balanced._dataset(root) / "inference-followup"):
        raise ValueError("Analyze new experiment exports only; existing frozen exports use their original analyzer")
    write_json(output, report)
    return output


def select_methods(candidates: list[dict]) -> dict:
    """Separate the global objective winner from a both-metrics improvement."""
    if not candidates:
        raise ValueError("Missing baseline/candidates")
    selected = balanced.choose_threshold([row["selected_primary"] for row in candidates])
    global_winner = next(row for row in candidates if row["selected_primary"] is selected)
    baseline = candidates[0]
    reference = baseline["selected_primary"]["micro"]
    eligible = [row for row in candidates[1:] if all(reference.get(key) is not None
                and row["selected_primary"]["micro"].get(key) is not None
                and row["selected_primary"]["micro"][key] > reference[key] for key in ("precision", "recall"))]
    if eligible:
        chosen = balanced.choose_threshold([row["selected_primary"] for row in eligible])
        recommendation = next(row for row in eligible if row["selected_primary"] is chosen)
    else:
        recommendation = baseline
    return {"global_winner": global_winner, "recommendation": recommendation,
            "recommendation_improves_both": bool(eligible), "baseline": baseline}


def _check_candidate(metadata: dict, path: Path, candidate: dict, root: Path) -> None:
    method = candidate["method"]
    if method == "existing_balanced_export":
        if path.relative_to(root).as_posix() != candidate["source_exports"][0]:
            raise ValueError("First candidate must be the preregistered baseline export")
        return
    if metadata.get("schema_version") != SCHEMA:
        if (method != "standard" or metadata.get("inference", {}).get("imgsz") != candidate["imgsz"]
                or metadata.get("weights_path") != candidate["weights"] or metadata.get("inference", {}).get("device") != "0"):
            raise ValueError("Old-schema export does not match preregistered standard candidate")
        return
    config = metadata["identity"]["config"]
    expected_method = "cached_post_nms" if method == "union_nms" and len(candidate["source_exports"]) == 1 else method
    if config.get("method") != expected_method or config.get("global_nms_iou") != candidate["global_nms_iou"]:
        raise ValueError("Candidate method/global NMS differs from preregistration")
    if method in ("standard", "flip", "tiles"):
        if (config.get("weights") != [candidate["weights"]] or config.get("settings", {}).get("imgsz") != candidate["imgsz"]
                or config["settings"].get("iou") != 0.7 or config["settings"].get("device") != "0"):
            raise ValueError("Candidate model/resolution/view NMS/device differs from preregistration")
    elif config.get("exports") != candidate["source_exports"]:
        raise ValueError("Fusion source export order differs from preregistration")
    if method == "paired_score" and config.get("paired_iou") != PAIRED_IOU:
        raise ValueError("Paired-score matching IoU differs from preregistration")


def compare_candidates(exports: list[Path], run_name: str, *, root: Path = REPO_ROOT, expected_images: int = 1921) -> Path:
    if len(exports) != 8 or len({str(local_path(str(path), root)) for path in exports}) != 8:
        raise ValueError("This bounded comparison requires exactly eight distinct candidate exports")
    protocol_hashes = _protocol(root)
    if not protocol_hashes:
        raise ValueError("Real method comparison requires the preregistered eight-candidate plan")
    frozen_plan = _read(balanced._dataset(root) / "inference-followup/plan.json")
    order = frozen_plan["candidates"]
    if [candidate["id"] for candidate in order] != frozen_plan["candidate_order_for_ties"] or len(order) != 8:
        raise ValueError("Preregistered candidate order is invalid")
    candidates, source_records = [], None
    for path, candidate in zip(exports, order):
        metadata, rows = load_export(path, root=root, expected_images=expected_images)
        if not _genuine(metadata):
            raise ValueError("Method selection requires genuine exports; injected results are test diagnostics only")
        _check_candidate(metadata, local_path(str(path), root), candidate, root)
        record_hashes = [_record_hash({key: value for key, value in row.items() if key != "predictions"}) for row in rows]
        if source_records is not None and record_hashes != source_records:
            raise ValueError("Candidates do not share identical frozen validation inputs")
        source_records = record_hashes
        report = metrics(metadata, rows)
        candidates.append({"id": candidate["id"], "recipe": candidate, "export_path": local_path(str(path), root).relative_to(root).as_posix(), "export_sha256": sha256_file(local_path(str(path), root)),
                           "selected_primary": report["selected_primary"], "selected_secondary_diagnostic": report["selected_secondary_diagnostic"],
                           "target_met_micro": report["target_met_micro"], "selected_all_eight_classes_meet_target": report["selected_all_eight_classes_meet_target"]})
    selection = select_methods(candidates)
    output = _output(root, run_name)
    if output.exists():
        raise ValueError("Comparison output already exists")
    write_json(output / "comparison.json", {"schema_version": "roadguard-inference-comparison-v1", "split": "val", "images": expected_images,
               "execution": "real_local_weights", "status": "experimental", "selection_rule": SELECTION_RULE,
               "thresholds": list(balanced.THRESHOLDS), "primary_iou": 0.5, "secondary_iou": 0.3,
               "source_names": balanced.source_names(), "candidates": candidates, **selection, "test_used": False,
               "backend_environment_changed": False, "source_file_sha256": _source_hashes(), "preregistered_protocol_sha256": protocol_hashes,
               "deployment_note": "Composite experimental recipes need exact-pipeline CPU and business-integration verification; ordinary single-weight manifests cannot activate them."})
    return output / "comparison.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--weights", type=Path, required=True)
    export.add_argument("--run-name", required=True)
    export.add_argument("--method", choices=("standard", "flip", "tiles"), default="standard")
    export.add_argument("--imgsz", type=int, choices=(640, 832, 960), default=832)
    export.add_argument("--device", default="cpu")
    for subparser in (export, commands.add_parser("fuse")):
        subparser.add_argument("--nms-iou", type=float, choices=(0.5, 0.7), default=0.7 if subparser is export else 0.5)
        subparser.add_argument("--resume", action="store_true")
    fuse = commands.choices["fuse"]
    fuse.add_argument("--exports", type=Path, nargs="+", required=True)
    fuse.add_argument("--run-name", required=True)
    fuse.add_argument("--strategy", choices=("union_nms", "paired_score"), default="union_nms")
    analyze = commands.add_parser("analyze")
    analyze.add_argument("--export", dest="export_path", type=Path, required=True)
    compare = commands.add_parser("compare")
    compare.add_argument("--exports", type=Path, nargs="+", required=True)
    compare.add_argument("--run-name", required=True)
    args = parser.parse_args()
    if args.command == "export":
        result = export_predictions(args.weights, args.run_name, method=args.method, imgsz=args.imgsz, nms_iou=args.nms_iou, device=args.device, resume=args.resume)
    elif args.command == "fuse":
        result = fuse_exports(args.exports, args.run_name, strategy=args.strategy, nms_iou=args.nms_iou, resume=args.resume)
    elif args.command == "analyze":
        result = analyze_export(args.export_path)
    else:
        result = compare_candidates(args.exports, args.run_name)
    print(result)


if __name__ == "__main__":
    main()
