"""Matched experiment integrity and selection tests; no torch, data or GPU required."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model import compare_models as comparison
from model.checkpointing import fingerprint, sha256_file, write_json


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    dataset = tmp_path / "Dataset"
    prepared = dataset / "prepared"
    prepared.mkdir(parents=True)
    for split in ("train", "val", "test"):
        (prepared / "images" / split).mkdir(parents=True)
    names = comparison.source_names()
    (prepared / "data.yaml").write_text(f'path: {json.dumps(str(prepared))}\ntrain: images/train\nval: images/val\ntest: images/test\nnc: 8\nnames: {json.dumps(names)}\n')
    (prepared / "manifest.jsonl").write_text('{"split":"val","sample_id":"fixture"}\n')
    write_json(prepared / "audit.json", {"errors": []})
    write_json(prepared / "split_summary.json", {"seed": 42, "splits": {"val": {"images": 8}}})
    pretrained = dataset / "pretrained"
    pretrained.mkdir()
    sources = {}
    hashes = {}
    for variant in ("n", "s"):
        weight = pretrained / f"yolo11{variant}.pt"
        weight.write_bytes(f"fake COCO pretrained {variant}".encode())
        hashes[variant] = sha256_file(weight)
        sources[variant] = pretrained / f"{variant}-download.json"
        write_json(sources[variant], {"source_url": f"https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11{variant}.pt",
                   "architecture": f"YOLO11{variant}", "pretraining": "COCO", "size_bytes": weight.stat().st_size, "sha256": hashes[variant]})
    monkeypatch.setattr(comparison, "OFFICIAL_HASHES", hashes)
    baseline = json.loads(Path(comparison.__file__).with_name("training.example.json").read_text())
    baseline["train"].update(comparison.REQUIRED_TRAIN)
    baseline["train"].update(epochs=10, patience=10)
    baseline["run_name"] = "baseline10"
    path = dataset / "baseline10-config.json"
    write_json(path, baseline)
    return tmp_path, path, sources


def prepared_plan(experiment):
    root, baseline, sources = experiment
    return comparison.prepare(baseline, root / "Dataset" / "compare30", sources, root=root)


def completed_runs(experiment):
    root = experiment[0]
    plan_path = prepared_plan(experiment)
    plan = comparison.load_plan(plan_path, root)
    for variant, row in plan["candidates"].items():
        config = row["config"]
        run = root / "Dataset" / "runs" / config["run_name"]
        runtime = {"python": "3.12", "packages": {"ultralytics": "pinned"}, "source_file_sha256": {"train.py": "frozen-source"},
                   "git_commit": "same-revision", "git_dirty": True}
        identity = {"config_sha256": row["config_sha256"], "manifest_sha256": plan["inputs"]["manifest"]["sha256"],
                    "data_yaml_sha256": plan["inputs"]["data"]["sha256"], "pretrained_sha256": row["pretrained"]["sha256"],
                    "runtime": {"python": runtime["python"], "packages": runtime["packages"]}}
        write_json(run / "run_metadata.json", {"config": config, "identity": identity, "runtime": runtime, "status": "training", "resume_history": []})
        write_json(run / "run_status.json", {"status": "evaluated"})
        weights = run / "weights"
        weights.mkdir()
        for name in ("best.pt", "last.pt", "resume-latest.pt", "resume-previous.pt"):
            (weights / name).write_bytes(f"{variant}-{name}".encode())
        best_hash = sha256_file(weights / "best.pt")
        write_json(run / "recovery.json", {"completed_epochs": 30, "identity": identity, "checkpoint_sha256": sha256_file(weights / "resume-latest.pt")})
        (run / "results.csv").write_text("epoch,time\n" + "".join(f"{i},{i * 2}\n" for i in range(1, 31)))
        report = {"schema_version": "roadguard-evaluation-v1", "split": "val", "split_role": "validation", "numerical_validation_passed": True,
                  "weights_sha256": best_hash, "dataset_manifest_sha256": identity["manifest_sha256"], "model_version": config["model_version"],
                  "status": "experimental", "evaluation_conf": 0.001, "evaluation_iou": 0.7, "model_state_validation": {"checked": True},
                  "images": 8, "per_class": [{"class_id": i, "source_name": name, "instances": 1} for i, name in enumerate(comparison.source_names())],
                  "aggregate": {"map50_95": 0.3 if variant == "n" else 0.4, "map50": 0.5, "precision": 0.6, "recall": 0.7, "f1_macro_present_classes": 0.6}}
        write_json(run / "evaluation-val.json", report)
        # Presence of malformed test evidence must never influence validation selection.
        (run / "evaluation-test.json").write_text("DO NOT READ THIS FILE")
        write_json(run / "model_manifest.json", {"schema_version": "roadguard-model-v1", "weights_path": comparison.relative(weights / "best.pt", root),
                   "weights_sha256": best_hash, "model_version": config["model_version"], "source_class_names": comparison.source_names(),
                   "source_dataset": {"ref": "juusos/rdd2022es", "version": 1, "manifest_sha256": identity["manifest_sha256"]},
                   "inference": config["inference"], "status": "experimental", "evaluation_path": comparison.relative(run / "evaluation-val.json", root)})
        args = {**config["train"], "model": str(root / config["model"]), "data": str(root / config["data"]),
                "project": str(run.parent), "save_dir": str(run), "name": config["run_name"], "resume": False,
                "nbs": 64, "pretrained": True, "task": "detect", "mode": "train", "fraction": 1, "single_cls": False,
                "classes": None, "val": True, "split": "val"}
        (run / "args.yaml").write_text("".join(f"{key}: {json.dumps(value)}\n" for key, value in args.items()))
        write_json(run / "effective_training.json", {"schema_version": "roadguard-effective-training-v1", "configured_batch": 32, "actual_batch": 32,
                   "argument_batch": 32, "config_sha256": fingerprint(config), "event": "train_end",
                   "nbs": 64, "nominal_accumulate": 2, "effective_nominal_batch": 64, "batch_matches_configuration": True,
                   "epochs": 30, "epoch_1based": 30, "train_args_subset": config["train"]})
    return plan_path, root / "Dataset" / "runs" / plan["candidates"]["n"]["config"]["run_name"]


def test_prepare_freezes_independent_matched_runs_without_replacing_baseline(experiment):
    root, baseline_path, sources = experiment
    before = baseline_path.read_bytes()
    path = prepared_plan(experiment)
    plan = comparison.load_plan(path, root)
    assert baseline_path.read_bytes() == before
    assert plan["candidates"]["n"]["config"]["train"] == plan["candidates"]["s"]["config"]["train"]
    assert plan["candidates"]["s"]["config"]["train"]["epochs"] == 30
    assert plan["candidates"]["s"]["config"]["train"]["patience"] == 30
    assert plan["candidates"]["n"]["config"]["model"] != plan["candidates"]["s"]["config"]["model"]
    with pytest.raises(ValueError, match="already exists"):
        comparison.prepare(baseline_path, path.parent, sources, root=root)


def test_prepare_missing_small_weights_has_clear_error_and_no_outputs(experiment):
    root, baseline, sources = experiment
    (root / "Dataset/pretrained/yolo11s.pt").unlink()
    with pytest.raises(ValueError, match="Missing local YOLO11s"):
        comparison.prepare(baseline, root / "Dataset/compare30", sources, root=root)
    assert not (root / "Dataset/compare30").exists()


def test_comparison_is_portable_and_ignores_test_reports(experiment):
    path, _ = completed_runs(experiment)
    summary = comparison.compare(path, root=experiment[0])
    assert summary["selection"]["variant"] == "s"
    assert summary["selection"]["test_used"] is False
    assert "backend_environment_changed" in summary["selection"]
    assert str(experiment[0]) not in json.dumps(summary)
    assert summary["candidates"]["n"]["effective_nominal_batch"] == 64


@pytest.mark.parametrize("mutation", ["epochs", "identity", "checkpoint", "source_classes", "split", "runtime", "args_batch", "effective_batch", "effective_config", "effective_event", "results", "missing_run", "pretrained", "input", "config"])
def test_comparison_rejects_mismatched_missing_or_incomplete_evidence(experiment, mutation):
    path, run = completed_runs(experiment)
    def change(name, edit):
        value = comparison.read_json(run / name)
        edit(value)
        write_json(run / name, value)
    if mutation == "epochs":
        change("recovery.json", lambda value: value.update(completed_epochs=29))
    elif mutation == "identity":
        change("run_metadata.json", lambda value: value["identity"].update(pretrained_sha256="baseline10-checkpoint"))
    elif mutation == "checkpoint":
        (run / "weights/best.pt").write_bytes(b"changed")
    elif mutation == "source_classes":
        change("model_manifest.json", lambda value: value.update(source_class_names=["COCO class"] * 8))
    elif mutation == "split":
        change("evaluation-val.json", lambda value: value.update(split="test"))
    elif mutation == "runtime":
        change("run_metadata.json", lambda value: value["runtime"].update(git_commit="other-source"))
    elif mutation == "args_batch":
        args = run / "args.yaml"
        args.write_text(args.read_text().replace("batch: 32", "batch: 16"))
    elif mutation == "effective_batch":
        change("effective_training.json", lambda value: value.update(actual_batch=16))
    elif mutation == "effective_config":
        change("effective_training.json", lambda value: value.update(config_sha256="other-config"))
    elif mutation == "effective_event":
        change("effective_training.json", lambda value: value.update(event="epoch_start"))
    elif mutation == "results":
        (run / "results.csv").write_text("epoch,time\n30,60\n")
    elif mutation == "missing_run":
        (run / "run_status.json").unlink()
    elif mutation == "pretrained":
        (experiment[0] / "Dataset/pretrained/yolo11n.pt").write_bytes(b"another-model")
    elif mutation == "input":
        (experiment[0] / "Dataset/prepared/split_summary.json").write_text("{}")
    elif mutation == "config":
        config = path.parent / "n-config.json"
        value = comparison.read_json(config)
        value["train"]["epochs"] = 29
        write_json(config, value)
    with pytest.raises((ValueError, FileNotFoundError)):
        comparison.compare(path, root=experiment[0])


def test_selection_uses_ordered_exact_metrics_then_matched_cpu_latency():
    rows = {variant: {"validation": {"map50_95": 0.4, "map50": 0.5}, "checkpoints_sha256": {"best.pt": variant}} for variant in ("n", "s")}
    rows["n"]["validation"]["map50_95"] += 1e-12
    assert comparison.select(rows) == ("n", "higher_validation_map50_95")
    rows["n"]["validation"]["map50_95"] = 0.4
    rows["s"]["validation"]["map50"] = 0.6
    assert comparison.select(rows) == ("s", "higher_validation_map50")
    rows["s"]["validation"]["map50"] = 0.5
    with pytest.raises(ValueError, match="requires matched CPU"):
        comparison.select(rows)
    latency = {"schema_version": "roadguard-compare30-cpu-latency-v1", "device": "cpu", "test_used": False,
               "protocol": {"pipeline": "backend_real_single_image", "source_split": "val", "imgsz": 640, "conf": 0.25, "iou": 0.7,
                            "image_set_sha256": "a" * 64, "backend_source_sha256": "b" * 64, "cpu_threads": 4, "warmup": 2, "repeats": 5},
               "candidates": {"n": {"weights_sha256": "n", "median_ms": 80}, "s": {"weights_sha256": "s", "median_ms": 100}}}
    assert comparison.select(rows, latency)[0] == "n"
    latency["test_used"] = True
    with pytest.raises(ValueError, match="no test inputs"):
        comparison.select(rows, latency)


def test_plan_fingerprint_is_checked_and_outside_storage_refused(experiment):
    path = prepared_plan(experiment)
    value = comparison.read_json(path)
    value["policy"]["epochs"] = 29
    write_json(path, value)
    with pytest.raises(ValueError, match="preregistration"):
        comparison.load_plan(path, experiment[0])
    with pytest.raises(ValueError, match="Dataset"):
        comparison.asset(experiment[0] / "outside.json", experiment[0])
