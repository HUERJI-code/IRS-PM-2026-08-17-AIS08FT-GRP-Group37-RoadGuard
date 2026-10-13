"""Export honest split-specific metrics and prune only reproducible caches after validation."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

try:
    from .checkpointing import fingerprint, sha256_file, write_json
    from .train import REPO_ROOT, configure_local_runtime, load_config, local_path
except ImportError:
    from checkpointing import fingerprint, sha256_file, write_json
    from train import REPO_ROOT, configure_local_runtime, load_config, local_path


def source_names() -> list[str]:
    schema = json.loads(Path(__file__).with_name("label_schema.json").read_text(encoding="utf-8"))
    return [row["source_name"] for row in schema["classes"]]


def checked_metric(value) -> float:
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise ValueError(f"Metric outside finite [0,1]: {number}")
    return number


def metrics_report(metrics, validator, names: list[str]) -> dict:
    """Ultralytics P/R/F1 use the validation max-mean-F1 curve point, not inference.conf."""
    actual = metrics.names
    actual = [actual[i] for i in range(len(actual))] if isinstance(actual, dict) else list(actual)
    if actual != names:
        raise ValueError("Model/evaluation class names do not match the ordered source dictionary")
    box = metrics.box
    present = {int(class_id): index for index, class_id in enumerate(box.ap_class_index)}
    supports = list(metrics.nt_per_class)
    per_class = []
    for class_id, name in enumerate(names):
        values = {"precision": None, "recall": None, "f1": None, "map50": None, "map50_95": None}
        if class_id in present:
            index = present[class_id]
            values = {"precision": checked_metric(box.p[index]), "recall": checked_metric(box.r[index]),
                      "f1": checked_metric(box.f1[index]), "map50": checked_metric(box.ap50[index]),
                      "map50_95": checked_metric(box.ap[index])}
        per_class.append({"class_id": class_id, "source_name": name, "instances": int(supports[class_id]),
                          "evaluated": class_id in present, **values})
    if not present or sum(supports) == 0 or validator.seen <= 0:
        raise ValueError("Evaluation has no images or no annotated classes")
    matrix = validator.confusion_matrix.matrix.tolist()
    if len(matrix) != len(names) + 1 or any(len(row) != len(names) + 1 for row in matrix):
        raise ValueError("Confusion matrix dimensions do not match eight classes plus background")
    if any(not math.isfinite(float(v)) or v < 0 for row in matrix for v in row):
        raise ValueError("Confusion matrix contains invalid counts")
    labels = names + ["background"]
    confusions = sorted(({"predicted": labels[p], "actual": labels[t], "count": int(value)}
                         for p, row in enumerate(matrix) for t, value in enumerate(row) if p != t and value > 0),
                        key=lambda row: -row["count"])
    return {"images": int(validator.seen),
            "aggregate": {"precision": checked_metric(box.mp), "recall": checked_metric(box.mr),
                          "f1_macro_present_classes": sum(row["f1"] for row in per_class if row["evaluated"]) / len(present),
                          "map50": checked_metric(box.map50), "map50_95": checked_metric(box.map)},
            "per_class": per_class, "confusion_matrix": {"rows": "predicted", "columns": "actual", "labels": labels, "counts": matrix},
            "confusion_examples": confusions[:20],
            "precision_recall_operating_point": "Ultralytics max mean F1 on this split; descriptive only, not deployed threshold tuning",
            "numerical_validation_passed": True, "accuracy_acceptance": "not_defined_not_claimed",
            "limitations": ["Classes without ground truth have null metrics, not invented zeros.",
                            "Dataset labels are visual categories, not engineering severity measurements.",
                            "This evaluation does not calibrate the project's automatic acceptance gate."]}


def evaluate(config: dict, split: str = "val", *, model_factory=None) -> Path:
    if split not in {"val", "test"}:
        raise ValueError("Evaluation split must be val or held-out test")
    run_dir = local_path(config["dataset_root"]) / "runs" / config["run_name"]
    status_path = run_dir / "run_status.json"
    if not status_path.is_file() or json.loads(status_path.read_text())["status"] not in {"training_completed_pending_evaluation", "evaluated"}:
        raise ValueError("Evaluation requires a successfully completed training run")
    weights = run_dir / "weights" / "best.pt"
    if not weights.is_file():
        raise ValueError("No local best.pt; no model download is permitted")
    metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    if fingerprint(config) != metadata["identity"]["config_sha256"] or sha256_file(local_path(config["data"])) != metadata["identity"]["data_yaml_sha256"]:
        raise ValueError("Training config or dataset YAML changed since training")
    if sha256_file(local_path(config["manifest"])) != metadata["identity"]["manifest_sha256"]:
        raise ValueError("Dataset manifest changed since training")
    real_runtime = model_factory is None
    if real_runtime:
        configure_local_runtime(local_path(config["dataset_root"]))
        from ultralytics import YOLO
        model_factory = YOLO
    model = model_factory(str(weights))
    model_state = {"checked": False, "reason": "injected_test_model"}
    if real_runtime:
        import torch
        tensors = list(model.model.state_dict().values())
        if not tensors or any(not bool(torch.isfinite(tensor).all()) for tensor in tensors):
            raise ValueError("Model contains missing or non-finite parameter/buffer tensors")
        model_state = {"checked": True, "finite_tensors": len(tensors)}
    captured = {}
    model.add_callback("on_val_end", lambda validator: captured.update(validator=validator))
    # Low fixed confidence retains the PR curve. No inference threshold is selected using the test set.
    result = model.val(data=str(local_path(config["data"])), split=split, imgsz=config["train"]["imgsz"],
                       batch=config["train"]["batch"], device=config["train"]["device"], workers=config["train"]["workers"],
                       conf=0.001, iou=0.7, plots=True, save_json=True,
                       project=str(run_dir), name=f"evaluation-{split}", exist_ok=True)
    if "validator" not in captured:
        raise ValueError("Validator callback did not complete; no successful evaluation can be claimed")
    report = metrics_report(result, captured["validator"], source_names())
    report.update({"schema_version": "roadguard-evaluation-v1", "split": split,
                   "split_role": "validation" if split == "val" else "held_out_test_no_threshold_tuning",
                   "weights_sha256": sha256_file(weights), "dataset_manifest_sha256": metadata["identity"]["manifest_sha256"],
                   "model_version": config["model_version"], "status": "experimental",
                   "model_state_validation": model_state,
                   "evaluation_conf": 0.001, "evaluation_iou": 0.7,
                   "example_artifacts": [p.relative_to(REPO_ROOT).as_posix() for p in (run_dir / f"evaluation-{split}").glob("val_batch*.jpg")]})
    report_path = run_dir / f"evaluation-{split}.json"
    write_json(report_path, report)
    if split == "val":
        manifest = {"schema_version": "roadguard-model-v1", "weights_path": weights.relative_to(REPO_ROOT).as_posix(),
                    "weights_sha256": report["weights_sha256"], "model_version": config["model_version"],
                    "source_class_names": source_names(),
                    "source_dataset": {"ref": "juusos/rdd2022es", "version": 1, "manifest_sha256": report["dataset_manifest_sha256"]},
                    "inference": config["inference"], "status": "experimental", "evaluation_path": report_path.relative_to(REPO_ROOT).as_posix()}
        write_json(run_dir / "model_manifest.json", manifest)
        write_json(status_path, {"status": "evaluated", "numerical_validation_passed": True, "accuracy_acceptance": "not_defined_not_claimed"})
    return report_path


def cleanup_caches(dataset_root: Path, report_path: Path, *, apply: bool = False) -> dict:
    """Dry-run by default. Only prepared YOLO label caches and decoded image npy caches."""
    dataset_root = dataset_root.resolve()
    report_path = report_path.resolve()
    runs = dataset_root / "runs"
    if not report_path.is_relative_to(runs) or report_path.name != "evaluation-val.json":
        raise ValueError("Cleanup requires this dataset's validation report under runs")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    weights = report_path.parent / "weights" / "best.pt"
    if report.get("split") != "val" or report.get("numerical_validation_passed") is not True or not weights.is_file() or sha256_file(weights) != report.get("weights_sha256"):
        raise ValueError("Successful validation of current best weights is required before cleanup")
    status = json.loads((report_path.parent / "run_status.json").read_text(encoding="utf-8"))
    if status.get("status") != "evaluated":
        raise ValueError("Training and validation must both complete before cleanup")
    prepared = dataset_root / "prepared"
    if prepared.resolve() != prepared:
        raise ValueError("Prepared directory must not be a symlink or junction")
    if sha256_file(prepared / "manifest.jsonl") != report.get("dataset_manifest_sha256"):
        raise ValueError("Prepared dataset changed after evaluation")
    candidates = [prepared / "labels" / f"{split}.cache" for split in ("train", "val", "test")]
    for split in ("train", "val", "test"):
        candidates.extend((prepared / "images" / split).glob("*.npy"))
    selected = []
    for path in candidates:
        # Reject links/junction escapes even though the matching filename looks safe.
        if path.is_symlink() or path.resolve() != path or not path.resolve().is_relative_to(prepared):
            raise ValueError(f"Unsafe cache path: {path}")
        if path.is_file():
            selected.append({"path": str(path), "bytes": path.stat().st_size})
    output = {"dry_run": not apply, "files": selected, "bytes": sum(row["bytes"] for row in selected),
              "scope": "prepared/labels/{train,val,test}.cache and prepared/images/{train,val,test}/*.npy only"}
    if apply:
        for row in selected:
            Path(row["path"]).unlink()
    write_json(report_path.parent / ("cleanup-applied.json" if apply else "cleanup-dry-run.json"), output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("training.example.json"))
    parser.add_argument("--split", choices=("val", "test"), default="val")
    parser.add_argument("--cleanup", action="store_true", help="Audit caches; evaluates first unless --existing-report is set")
    parser.add_argument("--apply-cleanup", action="store_true")
    parser.add_argument("--existing-report", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    report = args.existing_report or evaluate(config, args.split)
    print(f"Evaluation report: {report}")
    if args.apply_cleanup and not args.cleanup:
        parser.error("--apply-cleanup requires --cleanup")
    if args.cleanup:
        print(json.dumps(cleanup_caches(local_path(config["dataset_root"]), report, apply=args.apply_cleanup), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
