"""Preregister and verify a matched YOLO11n/YOLO11s validation-only comparison.

Uses only the standard library; never imports a vision runtime, trains, downloads,
reads a test report, changes backend configuration, or cleans model artifacts.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import math
from pathlib import Path

try:
    from .checkpointing import fingerprint, sha256_file, write_json
    from .evaluate import source_names
    from .train import REPO_ROOT, load_config
except ImportError:
    from checkpointing import fingerprint, sha256_file, write_json
    from evaluate import source_names
    from train import REPO_ROOT, load_config


POLICY = {
    "selection_split": "val",
    "ranking": ["map50_95_desc", "map50_desc", "matched_cpu_backend_median_ms_asc_on_exact_tie"],
    "test_used_for_selection": False,
    "seed": 42,
    "epochs": 30,
    "initialization": "independent_official_COCO_pretrained_not_baseline10_resume",
    "limitation": "One seed; no estimate of training variance or statistical superiority.",
}
REQUIRED_TRAIN = {"epochs": 30, "patience": 30, "seed": 42, "imgsz": 640,
                  "batch": 32, "workers": 4, "amp": False, "cache": False,
                  "deterministic": True, "fliplr": 0, "optimizer": "AdamW",
                  "lr0": 0.001, "lrf": 0.01, "warmup_epochs": 1, "close_mosaic": 2}
OFFICIAL_HASHES = {"n": "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1",
                   "s": "85a76fe86dd8afe384648546b56a7a78580c7cb7b404fc595f97969322d502d5"}


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path.name}")
    return value


def asset(value: str | Path, root: Path) -> Path:
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve() / "Dataset"):
        raise ValueError("Comparison assets must stay under repository Dataset/")
    return path


def relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def expected_config(baseline: dict, variant: str) -> dict:
    value = copy.deepcopy(baseline)
    value["model"] = f"Dataset/pretrained/yolo11{variant}.pt"
    value["run_name"] = f"yolo11{variant}-rdd2022es-compare30-seed42"
    value["model_version"] = f"yolo11{variant}-rdd2022es-v1-compare30-seed42-experimental"
    value["train"].update(epochs=30, patience=30)
    if any(value["train"].get(key) != item for key, item in REQUIRED_TRAIN.items()):
        raise ValueError("Baseline hyperparameters do not match the authorized comparison")
    return value


def checked_pretrained(variant: str, config: dict, provenance_path: Path, root: Path) -> dict:
    weights = asset(config["model"], root)
    if not weights.is_file():
        raise ValueError(f"Missing local YOLO11{variant} official starting weights: {relative(weights, root)}; explicitly prepare them first")
    provenance = read_json(asset(provenance_path, root))
    url = f"https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11{variant}.pt"
    digest = sha256_file(weights)
    if (provenance.get("source_url") != url or provenance.get("architecture") != f"YOLO11{variant}"
            or "COCO" not in provenance.get("pretraining", "")
            or provenance.get("size_bytes") != weights.stat().st_size
            or provenance.get("sha256") != digest or digest != OFFICIAL_HASHES[variant]):
        raise ValueError(f"YOLO11{variant} official COCO pretrained provenance/hash mismatch")
    return {"source_url": url, "architecture": f"YOLO11{variant}", "pretraining": "COCO",
            "sha256": digest, "size_bytes": weights.stat().st_size,
            "provenance_path": relative(provenance_path, root), "provenance_sha256": sha256_file(provenance_path)}


def prepare(baseline_path: Path, output: Path, provenance_paths: dict[str, Path], *, root: Path = REPO_ROOT) -> Path:
    root = root.resolve()
    baseline_path, output = asset(baseline_path, root), asset(output, root)
    baseline = load_config(baseline_path, root)
    if baseline["train"]["epochs"] != 10 or baseline["train"]["patience"] != 10 or baseline["model"] != "Dataset/pretrained/yolo11n.pt":
        raise ValueError("Preparation requires the original ten-epoch YOLO11n baseline config")
    if output.exists():
        raise ValueError("Comparison output already exists; refusing to replace a preregistration")
    candidates = {}
    for variant in ("n", "s"):
        config = expected_config(baseline, variant)
        provenance = asset(provenance_paths[variant], root)
        candidates[variant] = {"config": config, "config_path": relative(output / f"{variant}-config.json", root),
                               "config_sha256": fingerprint(config),
                               "pretrained": checked_pretrained(variant, config, provenance, root)}
        if asset(config["dataset_root"], root).joinpath("runs", config["run_name"]).exists():
            raise ValueError("A comparison run already exists; preregistration must precede training")
    inputs = {key: {"path": baseline[key], "sha256": sha256_file(asset(baseline[key], root))}
              for key in ("data", "manifest")}
    for name in ("audit.json", "split_summary.json"):
        path = asset(baseline["manifest"], root).parent / name
        inputs[name] = {"path": relative(path, root), "sha256": sha256_file(path)}
    plan = {"schema_version": "roadguard-compare30-plan-v1", "policy": POLICY,
            "baseline_config_path": relative(baseline_path, root), "baseline_config_sha256": fingerprint(baseline),
            "source_class_names": source_names(), "inputs": inputs, "candidates": candidates}
    plan["plan_sha256"] = fingerprint(plan)
    # No output is published until all local pretrained and input checks pass.
    for variant, row in candidates.items():
        write_json(output / f"{variant}-config.json", row["config"])
        load_config(output / f"{variant}-config.json", root)
    path = output / "plan.json"
    write_json(path, plan)
    return path


def load_plan(path: Path, root: Path) -> dict:
    plan = read_json(asset(path, root))
    content = {key: value for key, value in plan.items() if key != "plan_sha256"}
    if (plan.get("schema_version") != "roadguard-compare30-plan-v1" or plan.get("policy") != POLICY
            or plan.get("plan_sha256") != fingerprint(content) or plan.get("source_class_names") != source_names()
            or set(plan.get("candidates", {})) != {"n", "s"}):
        raise ValueError("Invalid or changed comparison preregistration")
    baseline = load_config(asset(plan["baseline_config_path"], root), root)
    if fingerprint(baseline) != plan["baseline_config_sha256"]:
        raise ValueError("Frozen baseline config changed")
    if set(plan.get("inputs", {})) != {"data", "manifest", "audit.json", "split_summary.json"}:
        raise ValueError("Missing frozen comparison inputs")
    if any(plan["inputs"][key]["path"] != baseline[key] for key in ("data", "manifest")):
        raise ValueError("Frozen input path does not match baseline")
    for item in plan["inputs"].values():
        if sha256_file(asset(item["path"], root)) != item["sha256"]:
            raise ValueError("Frozen data/manifest/split/audit input changed")
    for variant, row in plan["candidates"].items():
        config = load_config(asset(row["config_path"], root), root)
        if config != row["config"] or config != expected_config(baseline, variant) or fingerprint(config) != row["config_sha256"]:
            raise ValueError("Candidate config changed or mismatched")
        verified = checked_pretrained(variant, config, asset(row["pretrained"]["provenance_path"], root), root)
        if verified != row["pretrained"]:
            raise ValueError("Frozen pretrained provenance changed")
    return plan


def actual_training_args(run: Path, config: dict, metadata: dict, root: Path) -> dict:
    """Parse Ultralytics' flat args YAML without requiring PyYAML in ordinary CI."""
    args = {}
    for line in (run / "args.yaml").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        if line != line.lstrip() or ":" not in line:
            raise ValueError("Unsupported actual training args YAML format")
        key, raw = line.split(":", 1)
        raw = raw.strip()
        if key in args:
            raise ValueError("Duplicate actual training argument")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw[1:-1] if len(raw) > 1 and raw[0] == raw[-1] == "'" else raw
        args[key] = value
    if any(args.get(key) != value for key, value in config["train"].items()):
        raise ValueError("Actual training args differ from configuration (including batch)")
    fixed = {"nbs": 64, "pretrained": True, "task": "detect", "mode": "train", "fraction": 1,
             "single_cls": False, "classes": None, "val": True, "split": "val"}
    if any(args.get(key) != value for key, value in fixed.items()):
        raise ValueError("Actual training objective/pretraining/batch defaults changed")
    for key, value in (("data", config["data"]), ("project", relative(run.parent, root)), ("save_dir", relative(run, root))):
        if asset(args[key], root) != asset(value, root):
            raise ValueError("Actual training path does not match candidate run/data")
    if args.get("name") != config["run_name"]:
        raise ValueError("Actual training run name mismatch")
    model_path = asset(args["model"], root)
    resumed = bool(metadata.get("resume_history"))
    if model_path != asset(config["model"], root) and not (resumed and model_path.is_relative_to(run / "weights")):
        raise ValueError("Actual model initialization is foreign to this candidate")
    if args.get("resume") is not False and not (resumed and asset(args["resume"], root).is_relative_to(run / "weights")):
        raise ValueError("Undocumented or foreign resume")
    effective = read_json(run / "effective_training.json")
    expected = {"schema_version": "roadguard-effective-training-v1", "configured_batch": 32, "actual_batch": 32,
                "argument_batch": 32, "config_sha256": fingerprint(config), "event": "train_end",
                "nbs": 64, "nominal_accumulate": 2, "effective_nominal_batch": 64,
                "batch_matches_configuration": True, "epochs": 30, "epoch_1based": 30}
    if any(effective.get(key) != value for key, value in expected.items()):
        raise ValueError("Effective training evidence lacks matched full-epoch batch protocol")
    if any(effective.get("train_args_subset", {}).get(key) != value for key, value in config["train"].items()):
        raise ValueError("Effective training arguments differ from configuration")
    return {key: value for key, value in args.items() if key not in {"model", "data", "project", "name", "save_dir", "resume"}}


def verify_run(row: dict, plan: dict, root: Path) -> dict:
    config = row["config"]
    run = asset(config["dataset_root"], root) / "runs" / config["run_name"]
    metadata = read_json(run / "run_metadata.json")
    identity = metadata.get("identity", {})
    if (metadata.get("config") != config or identity.get("config_sha256") != row["config_sha256"]
            or identity.get("manifest_sha256") != plan["inputs"]["manifest"]["sha256"]
            or identity.get("data_yaml_sha256") != plan["inputs"]["data"]["sha256"]
            or identity.get("pretrained_sha256") != row["pretrained"]["sha256"]):
        raise ValueError("Run identity/config does not match preregistration")
    if metadata.get("status") != "training" or read_json(run / "run_status.json").get("status") != "evaluated":
        # train.py keeps initial metadata.status=training; final state lives in run_status.json.
        raise ValueError("Run lacks successful training and validation state")
    recovery = read_json(run / "recovery.json")
    if recovery.get("completed_epochs") != 30 or recovery.get("identity") != identity:
        raise ValueError("Comparison requires exactly 30 durable completed epochs with matching identity")
    checkpoints = {name: sha256_file(run / "weights" / name) for name in
                   ("best.pt", "last.pt", "resume-latest.pt", "resume-previous.pt")}
    if checkpoints["resume-latest.pt"] != recovery.get("checkpoint_sha256"):
        raise ValueError("Latest recovery checkpoint changed")
    with (run / "results.csv").open(encoding="utf-8", newline="") as stream:
        records = [{key.strip(): value for key, value in record.items()} for record in csv.DictReader(stream)]
    if [float(record["epoch"]) for record in records] != list(range(1, 31)):
        raise ValueError("Training log must contain all 30 consecutive epochs")
    report = read_json(run / "evaluation-val.json")  # Deliberately never inspect test.
    manifest = read_json(run / "model_manifest.json")
    expected_manifest = {"schema_version": "roadguard-model-v1", "weights_path": relative(run / "weights" / "best.pt", root),
                         "weights_sha256": checkpoints["best.pt"], "model_version": config["model_version"],
                         "source_class_names": source_names(), "source_dataset": {"ref": "juusos/rdd2022es", "version": 1,
                         "manifest_sha256": identity["manifest_sha256"]}, "inference": config["inference"],
                         "status": "experimental", "evaluation_path": relative(run / "evaluation-val.json", root)}
    if manifest != expected_manifest:
        raise ValueError("Model manifest/source classes/provenance mismatch")
    if (report.get("schema_version") != "roadguard-evaluation-v1" or report.get("split") != "val"
            or report.get("split_role") != "validation" or report.get("numerical_validation_passed") is not True
            or report.get("weights_sha256") != checkpoints["best.pt"] or report.get("dataset_manifest_sha256") != identity["manifest_sha256"]
            or report.get("model_version") != config["model_version"] or report.get("status") != "experimental"
            or report.get("evaluation_conf") != 0.001 or report.get("evaluation_iou") != 0.7
            or report.get("model_state_validation", {}).get("checked") is not True
            or report.get("images", 0) <= 0
            or [item.get("source_name") for item in report.get("per_class", [])] != source_names()
            or [item.get("class_id") for item in report.get("per_class", [])] != list(range(8))):
        raise ValueError("Validation metrics/provenance/source classes do not match expected evidence")
    split_summary = read_json(asset(plan["inputs"]["split_summary.json"]["path"], root))
    if report["images"] != split_summary["splits"]["val"]["images"]:
        raise ValueError("Validation image count does not match frozen validation split")
    supports = [item.get("instances") for item in report["per_class"]]
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in supports) or sum(supports) <= 0:
        raise ValueError("Invalid validation per-class annotation counts")
    metrics = {}
    for name in ("map50_95", "map50", "precision", "recall", "f1_macro_present_classes"):
        value = report.get("aggregate", {}).get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Validation aggregate metric is missing or invalid")
        metrics[name] = value
    for resume in metadata.get("resume_history", []):
        if not asset(resume["checkpoint"], root).is_relative_to(run / "weights") or resume.get("next_epoch", -1) not in range(1, 30):
            raise ValueError("Resume history contains foreign/invalid initialization")
    runtime = metadata.get("runtime", {})
    if identity.get("runtime") != {"python": runtime.get("python"), "packages": runtime.get("packages")} or not runtime.get("source_file_sha256"):
        raise ValueError("Missing or inconsistent runtime/source provenance")
    actual_args = actual_training_args(run, config, metadata, root)
    return {"run_name": config["run_name"], "model_version": config["model_version"], "completed_epochs": 30,
            "config_sha256": row["config_sha256"], "pretrained": {key: row["pretrained"][key] for key in
            ("source_url", "architecture", "pretraining", "sha256", "size_bytes")},
            "checkpoints_sha256": checkpoints, "validation": metrics, "validation_images": report["images"],
            "validation_class_instances": supports,
            "model_manifest_path": relative(run / "model_manifest.json", root),
            "actual_training_args_sha256": fingerprint(actual_args), "effective_nominal_batch": 64,
            "runtime": {key: runtime.get(key) for key in ("python", "packages", "source_file_sha256", "git_commit", "git_dirty")}}


def select(candidates: dict, latency: dict | None = None) -> tuple[str, str]:
    n, s = candidates["n"]["validation"], candidates["s"]["validation"]
    for metric in ("map50_95", "map50"):
        if n[metric] != s[metric]:
            return ("n" if n[metric] > s[metric] else "s"), f"higher_validation_{metric}"
    if latency is None:
        raise ValueError("Exact validation tie requires matched CPU backend latency evidence; no arbitrary winner")
    if latency.get("schema_version") != "roadguard-compare30-cpu-latency-v1" or latency.get("device") != "cpu" or latency.get("test_used") is not False:
        raise ValueError("CPU latency must use the documented matched protocol with no test inputs")
    protocol = latency.get("protocol", {})
    fixed = {"pipeline": "backend_real_single_image", "source_split": "val", "imgsz": 640, "conf": 0.25, "iou": 0.7}
    if (not isinstance(protocol, dict) or any(protocol.get(key) != value for key, value in fixed.items())
            or any(not isinstance(protocol.get(key), int) or isinstance(protocol[key], bool) or protocol[key] < minimum
                   for key, minimum in (("warmup", 1), ("repeats", 3), ("cpu_threads", 1)))
            or any(not isinstance(protocol.get(key), str) or len(protocol[key]) != 64
                   or any(character not in "0123456789abcdef" for character in protocol[key])
                   for key in ("image_set_sha256", "backend_source_sha256"))):
        raise ValueError("Missing matched CPU backend/validation/input/runtime latency protocol")
    values = []
    for variant in ("n", "s"):
        item = latency.get("candidates", {}).get(variant, {})
        if item.get("weights_sha256") != candidates[variant]["checkpoints_sha256"]["best.pt"]:
            raise ValueError("Latency weights do not match candidate checkpoints")
        number = item.get("median_ms")
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or number <= 0:
            raise ValueError("Invalid CPU latency")
        values.append(number)
    if values[0] == values[1]:
        raise ValueError("Missing matched latency protocol or unresolved exact tie")
    return ("n" if values[0] < values[1] else "s"), "lower_matched_cpu_backend_median_ms_exact_validation_tie"


def compare(plan_path: Path, *, root: Path = REPO_ROOT, latency_path: Path | None = None) -> dict:
    root = root.resolve()
    plan = load_plan(plan_path, root)
    candidates = {variant: verify_run(row, plan, root) for variant, row in plan["candidates"].items()}
    if (candidates["n"]["runtime"] != candidates["s"]["runtime"]
            or candidates["n"]["actual_training_args_sha256"] != candidates["s"]["actual_training_args_sha256"]
            or candidates["n"]["validation_class_instances"] != candidates["s"]["validation_class_instances"]
            or candidates["n"]["validation_images"] != candidates["s"]["validation_images"]):
        raise ValueError("Candidate runtime/source revision or validation image counts differ")
    latency = read_json(asset(latency_path, root)) if latency_path else None
    winner, reason = select(candidates, latency)
    return {"schema_version": "roadguard-compare30-summary-v1", "plan_sha256": plan["plan_sha256"],
            "policy": POLICY, "source_class_names": plan["source_class_names"],
            "frozen_input_sha256": {key: value["sha256"] for key, value in plan["inputs"].items()},
            "matched_train": plan["candidates"]["n"]["config"]["train"], "candidates": candidates,
            "selection": {"variant": winner, "reason": reason, "split": "val", "test_used": False,
                          "recommended_manifest_path": candidates[winner]["model_manifest_path"],
                          "backend_environment_changed": False},
            "latency_evidence_sha256": sha256_file(asset(latency_path, root)) if latency_path else None,
            "status": "experimental", "accuracy_acceptance": "not_defined_not_claimed"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--baseline", type=Path, default=Path("Dataset/baseline10-config.json"))
    prepare_parser.add_argument("--output", type=Path, default=Path("Dataset/compare30"))
    prepare_parser.add_argument("--n-provenance", type=Path, default=Path("Dataset/pretrained/download.json"))
    prepare_parser.add_argument("--s-provenance", type=Path, default=Path("Dataset/pretrained/download-yolo11s.json"))
    compare_parser = commands.add_parser("compare")
    compare_parser.add_argument("--plan", type=Path, default=Path("Dataset/compare30/plan.json"))
    compare_parser.add_argument("--output", type=Path, default=Path("Dataset/compare30/summary.json"))
    compare_parser.add_argument("--cpu-latency", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        print(prepare(args.baseline, args.output, {"n": args.n_provenance, "s": args.s_provenance}))
    else:
        output = asset(args.output, REPO_ROOT)
        if output.exists():
            raise ValueError("Summary exists; choose a new output rather than replacing experiment evidence")
        summary = compare(args.plan, latency_path=args.cpu_latency)
        write_json(output, summary)
        print(json.dumps(summary["selection"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
