"""Bounded YOLO training with epoch recovery, explicit local assets and reproducibility."""

from __future__ import annotations

import argparse
import copy
import importlib.metadata
import io
import json
import os
import platform
import random
import subprocess
from pathlib import Path

try:
    from .checkpointing import RecoveryStore, fingerprint, sha256_file, validate_resume, write_json
except ImportError:
    from checkpointing import RecoveryStore, fingerprint, sha256_file, validate_resume, write_json

REPO_ROOT = Path(__file__).resolve().parents[2]


class TrainingInterrupted(RuntimeError):
    """Intentional smoke interruption after a durable completed epoch."""


def local_path(value: str, root: Path = REPO_ROOT) -> Path:
    path = Path(value)
    return (root / path).resolve() if not path.is_absolute() else path.resolve()


def validate_dataset_yaml(path: Path, dataset_root: Path) -> None:
    """Read the pipeline's simple YAML subset without importing a YAML/vision runtime.

    Generated YAML uses one top-level key per line, JSON scalars/arrays, and bare
    local directory strings. More complex YAML is rejected, rather than guessed.
    """
    fields = {}
    allowed = {"path", "train", "val", "test", "nc", "names"}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line != line.lstrip() or ":" not in line:
            raise ValueError("Dataset YAML must use the preparation pipeline's flat JSON-compatible format")
        key, raw = line.split(":", 1)
        key, raw = key.strip(), raw.strip()
        if key == "download":
            raise ValueError("Dataset YAML download directives are forbidden")
        if key not in allowed or key in fields:
            raise ValueError(f"Unsupported or duplicate dataset YAML key: {key}")
        if not raw:
            raise ValueError(f"Missing dataset YAML value: {key}")
        if raw.startswith(('"', "[", "{")) or raw in {"null", "true", "false"} or key == "nc":
            try:
                fields[key] = json.loads(raw)
            except json.JSONDecodeError as error:
                raise ValueError(f"Dataset YAML value must be JSON-compatible: {key}") from error
        elif raw.startswith(("'", "!", "&", "*", "|", ">")):
            raise ValueError("Dataset YAML tags, aliases and complex scalar forms are unsupported")
        else:
            fields[key] = raw
    if not {"train", "val", "nc", "names"}.issubset(fields):
        raise ValueError("Dataset YAML requires train, val, nc and names")
    schema = json.loads(Path(__file__).with_name("label_schema.json").read_text(encoding="utf-8"))
    names = [row["source_name"] for row in schema["classes"]]
    if fields["nc"] != 8 or fields["names"] != names:
        raise ValueError("Dataset YAML must preserve the exact eight source class names")
    base_value = fields.get("path", str(path.resolve().parent))
    if not isinstance(base_value, str) or not Path(base_value).is_absolute():
        # Ultralytics resolves relative `path` against its global datasets setting,
        # so accepting it here would depend on unrelated machine configuration.
        raise ValueError("Dataset YAML path must be an absolute local directory (or omitted)")
    base = Path(base_value).resolve()
    if not base.is_relative_to(dataset_root) or not base.is_dir():
        raise ValueError("Dataset YAML path escapes dataset_root or is not an existing directory")
    for split in ("train", "val", "test"):
        if split not in fields:
            continue
        entries = fields[split] if isinstance(fields[split], list) else [fields[split]]
        if not entries:
            raise ValueError(f"Dataset YAML {split} cannot be empty")
        for entry in entries:
            if not isinstance(entry, str) or not entry:
                raise ValueError(f"Dataset YAML {split} must name local image directories")
            directory = (base / entry).resolve()
            if not directory.is_relative_to(dataset_root) or not directory.is_dir():
                raise ValueError(f"Dataset YAML {split} escapes dataset_root or is not an existing image directory")
            # Directory-only inputs avoid unvalidated image-list files redirecting
            # the loader to sources outside the dataset storage boundary.


def load_config(path: Path, root: Path = REPO_ROOT) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {"dataset_root", "data", "manifest", "model", "run_name", "model_version", "train", "inference"}
    if set(config) != required:
        raise ValueError(f"Configuration keys must be exactly {sorted(required)}")
    name = config["run_name"]
    if not isinstance(name, str) or not name or name in {".", ".."} or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in name):
        raise ValueError("run_name must contain only letters, digits, hyphens and underscores")
    train = config["train"]
    if not isinstance(train, dict) or train.get("cache") is not False or train.get("fliplr") != 0:
        raise ValueError("Training requires cache=false and fliplr=0 (source mirrors already exist)")
    if train.get("deterministic") is not True or not isinstance(train.get("seed"), int):
        raise ValueError("Reproducible training requires deterministic=true and an integer seed")
    if not isinstance(config["model_version"], str) or not config["model_version"].strip() or "demo" in config["model_version"].lower():
        raise ValueError("model_version must identify this real experimental model")
    for key, low, high in (("epochs", 1, 30), ("batch", 1, 64), ("imgsz", 32, 640), ("workers", 0, 4), ("patience", 1, 30)):
        if not isinstance(train.get(key), int) or not low <= train[key] <= high:
            raise ValueError(f"{key} must be an integer in [{low}, {high}]")
    forbidden = {"data", "model", "project", "name", "save_dir", "resume", "save", "save_period", "exist_ok", "fraction", "single_cls", "classes"}
    if forbidden.intersection(train):
        raise ValueError("Runner-owned training arguments cannot be overridden")
    dataset_root = local_path(config["dataset_root"], root)
    if not dataset_root.is_relative_to(root.resolve() / "Dataset"):
        raise ValueError("dataset_root must stay inside the repository Dataset subtree")
    for key in ("data", "manifest", "model"):
        asset = local_path(config[key], root)
        if not asset.is_relative_to(dataset_root) or not asset.is_file():
            raise ValueError(f"{key} must be an existing local file under dataset_root")
    validate_dataset_yaml(local_path(config["data"], root), dataset_root)
    inference = config["inference"]
    if set(inference) != {"conf", "iou", "imgsz"} or not 0 < inference["conf"] < 1 or not 0 < inference["iou"] < 1 or inference["imgsz"] != train["imgsz"]:
        raise ValueError("inference requires conf/iou in (0,1) and imgsz matching training")
    return config


def runtime_metadata() -> dict:
    versions = {name: importlib.metadata.version(name) for name in ("torch", "torchvision", "ultralytics", "numpy")}
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    try:
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        dirty = None
    files = ("train.py", "checkpointing.py", "evaluate.py", "data_pipeline.py", "requirements-vision.txt")
    hashes = {name: sha256_file(Path(__file__).with_name(name)) for name in files if Path(__file__).with_name(name).is_file()}
    return {"python": platform.python_version(), "platform": platform.platform(), "packages": versions,
            "git_commit": revision, "git_dirty": dirty, "source_file_sha256": hashes}


def configure_local_runtime(dataset_root: Path) -> None:
    """Set offline/cache policy before the first Ultralytics import."""
    config_dir = dataset_root / "tool-cache" / "ultralytics"
    config_dir.mkdir(parents=True, exist_ok=True)
    os.environ["YOLO_CONFIG_DIR"] = str(config_dir)
    os.environ["YOLO_OFFLINE"] = "true"
    os.environ["YOLO_AUTOINSTALL"] = "false"
    from ultralytics import settings

    integrations = ("sync", "clearml", "comet", "dvc", "hub", "mlflow", "neptune", "raytune", "tensorboard", "wandb")
    settings.update({key: False for key in integrations if key in settings})


def recovery_callback(identity: dict, store: RecoveryStore, stop_after_epoch: int | None = None):
    """Capture live model, exact optimizer/scaler/scheduler and RNG before final stripping."""
    def save(trainer):
        import numpy as np
        import torch

        checkpoint = torch.load(trainer.last, map_location="cpu", weights_only=False)
        live = trainer.model.module if hasattr(trainer.model, "module") else trainer.model
        checkpoint["optimizer"] = copy.deepcopy(trainer.optimizer.state_dict())
        checkpoint["scaler"] = trainer.scaler.state_dict()
        checkpoint["roadguard"] = {
            "identity": identity,
            "scheduler": trainer.scheduler.state_dict(),
            "live_model_state": {k: v.detach().cpu().clone() for k, v in live.state_dict().items()},
            "ema_state": {k: v.detach().cpu().clone() for k, v in trainer.ema.ema.state_dict().items()},
            "loader_generator": trainer.train_loader.generator.get_state() if trainer.train_loader.generator is not None else None,
            "stopper": {"best_fitness": trainer.stopper.best_fitness, "best_epoch": trainer.stopper.best_epoch},
            "rng": {"python": random.getstate(), "numpy": np.random.get_state(), "torch": torch.get_rng_state(),
                    "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []},
        }
        buffer = io.BytesIO()
        torch.save(checkpoint, buffer)
        store.publish(buffer.getvalue())
        write_json(store.latest.parent.parent / "recovery.json", {"completed_epochs": trainer.epoch + 1, "identity": identity,
                                                                "checkpoint_sha256": sha256_file(store.latest)})
        if stop_after_epoch is not None and trainer.epoch + 1 >= stop_after_epoch:
            raise TrainingInterrupted(f"Stopped after durable epoch {trainer.epoch + 1}")
    return save


def restore_callback(checkpoint: dict):
    def restore(trainer):
        import numpy as np
        import torch

        state = checkpoint["roadguard"]
        live = trainer.model.module if hasattr(trainer.model, "module") else trainer.model
        live.load_state_dict(state["live_model_state"], strict=True)
        trainer.ema.ema.load_state_dict(state["ema_state"], strict=True)
        if state["loader_generator"] is not None:
            trainer.train_loader.generator.set_state(state["loader_generator"].cpu())
        trainer.optimizer.load_state_dict(checkpoint["optimizer"])
        trainer.scaler.load_state_dict(checkpoint["scaler"])
        trainer.scheduler.load_state_dict(state["scheduler"])
        for key, value in state["stopper"].items():
            setattr(trainer.stopper, key, value)
        rng = state["rng"]
        random.setstate(rng["python"])
        np.random.set_state(rng["numpy"])
        torch.set_rng_state(rng["torch"].cpu())
        if rng["cuda"]:
            torch.cuda.set_rng_state_all([v.cpu() for v in rng["cuda"]])
        write_json(Path(trainer.save_dir) / "resume_verified.json", {"start_epoch": trainer.start_epoch,
                    "optimizer_state_entries": len(trainer.optimizer.state_dict()["state"]), "identity": state["identity"]})
    return restore


def run_training(config: dict, resume: Path | None = None, stop_after_epoch: int | None = None, *, model_factory=None, runtime=None) -> Path:
    runtime = runtime if runtime is not None else runtime_metadata()
    identity = {"config_sha256": fingerprint(config), "manifest_sha256": sha256_file(local_path(config["manifest"])),
                "data_yaml_sha256": sha256_file(local_path(config["data"])), "pretrained_sha256": sha256_file(local_path(config["model"])),
                "runtime": {"python": runtime["python"], "packages": runtime["packages"]}}
    run_dir = local_path(config["dataset_root"]) / "runs" / config["run_name"]
    checkpoint = None
    if resume is not None:
        import torch
        resume = resume.resolve()
        if not resume.is_file() or not resume.is_relative_to(run_dir.resolve() / "weights"):
            raise ValueError("Explicit resume checkpoint must exist inside this run's weights directory")
        checkpoint = torch.load(resume, map_location="cpu", weights_only=False)
        next_epoch = validate_resume(checkpoint, identity)
        if next_epoch >= config["train"]["epochs"]:
            raise ValueError("All configured epochs are completed; evaluate existing best.pt instead of restarting")
    elif run_dir.exists():
        raise ValueError("Run already exists; explicitly resume or use a new run_name")
    run_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = run_dir / "run_metadata.json"
    if checkpoint is not None and metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata.setdefault("resume_history", []).append({"runtime": runtime, "checkpoint": str(resume),
                                                         "checkpoint_sha256": sha256_file(resume), "next_epoch": next_epoch})
        metadata["status"] = "training"
    else:
        metadata = {"config": config, "identity": identity, "runtime": runtime, "status": "training", "resume_history": []}
    write_json(metadata_path, metadata)
    if model_factory is None:
        configure_local_runtime(local_path(config["dataset_root"]))
        from ultralytics import YOLO
        model_factory = YOLO
    model = model_factory(str(resume or local_path(config["model"])))
    model.add_callback("on_model_save", recovery_callback(identity, RecoveryStore(run_dir / "weights"), stop_after_epoch))
    if checkpoint is not None:
        model.add_callback("on_pretrain_routine_end", restore_callback(checkpoint))
    args = {**config["train"], "data": str(local_path(config["data"])), "project": str(run_dir.parent),
            "name": run_dir.name, "exist_ok": True, "save": True, "save_period": -1, "plots": True}
    if resume is not None:
        args["resume"] = str(resume)
    try:
        model.train(**args)
    except BaseException as error:
        write_json(run_dir / "run_status.json", {"status": "interrupted" if isinstance(error, (KeyboardInterrupt, TrainingInterrupted)) else "failed",
                                                "error_type": type(error).__name__, "error": str(error)})
        raise
    write_json(run_dir / "run_status.json", {"status": "training_completed_pending_evaluation"})
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("training.example.json"))
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--stop-after-epoch", type=int)
    args = parser.parse_args()
    try:
        result = run_training(load_config(args.config), args.resume, args.stop_after_epoch)
    except TrainingInterrupted as error:
        print(str(error))
        return 75
    print(f"Training finished; evaluate before cleanup: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
