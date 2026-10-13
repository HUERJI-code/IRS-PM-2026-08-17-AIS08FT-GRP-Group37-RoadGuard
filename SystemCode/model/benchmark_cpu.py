"""Measure the actual RoadGuard CPU prepare+detect path after both compare30 runs finish.

Run with the repository Python, --repo REPOSITORY and an unused --run-name.
No model or dependency download, GPU use, training, test-image access, or backend
configuration change. --self-test exercises only dependency-free helpers.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time

COUNTRIES = ("Czech", "India", "Japan", "United_States")
THREADS, WARMUP, REPEATS = 4, 2, 3
IMAGE_COUNT, TIMED_CALLS = 10 * len(COUNTRIES), 10 * len(COUNTRIES) * REPEATS
INFERENCE = {"imgsz": 640, "conf": 0.25, "iou": 0.7}


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def select_inputs(rows):
    groups = {country: [] for country in COUNTRIES}
    for row in rows:
        if row.get("split") != "val":
            continue
        if row.get("country") not in groups:
            raise ValueError("Validation record has an unsupported or missing country")
        sample = row.get("sample_id")
        if (row.get("assigned_split") != "val" or row.get("is_mirror") is not False
                or row.get("exclusion_reason") is not None or row.get("exif_orientation") != 1
                or not isinstance(sample, str) or not sample or sample.lower().startswith("xmirror_")
                or not sample.startswith(row["country"] + "_")
                or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in sample)):
            raise ValueError("Selected val country contains a non-original or unsafe record")
        groups[row["country"]].append(row)
    for country, values in groups.items():
        if len(values) < 10:
            raise ValueError(f"Insufficient frozen validation originals for {country}")
        values.sort(key=lambda row: (hashlib.sha256(f'42:{row["sample_id"]}'.encode()).hexdigest(), row["sample_id"]))
    selected = [groups[country][index] for index in range(10) for country in COUNTRIES]
    if len({row["sample_id"] for row in selected}) != IMAGE_COUNT:
        raise ValueError("Duplicate validation sample IDs")
    return selected


def checked_inputs(rows, repo: Path):
    """Open only the selected original val images, never train/test image bytes."""
    inputs = []
    for row in select_inputs(rows):
        image = (repo / "Dataset" / "prepared" / "images" / "val" / f'{row["sample_id"]}.jpg').resolve(strict=True)
        if not image.is_relative_to(repo / "Dataset" / "prepared" / "images" / "val") or digest(image) != row["image_sha256"]:
            raise ValueError("Selected original val image changed or escaped its directory")
        inputs.append({"sample_id": row["sample_id"], "country": row["country"], "image_sha256": row["image_sha256"],
                       "width": row["width"], "height": row["height"], "image_path": image.relative_to(repo).as_posix()})
    return inputs


def output_directory(repo: Path, run_name: str):
    if not run_name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in run_name):
        raise ValueError("run-name must contain only letters, digits, hyphens and underscores")
    base = repo / "Dataset" / "compare30" / "cpu-latency"
    output = (base / run_name).resolve()
    if base.resolve() != base or not output.is_relative_to(base) or output.exists():
        raise ValueError("Latency output already exists or escaped its boundary; choose an unused run-name")
    return output


def configure_runtime_environment(output: Path):
    """Create cache parents before libraries inspect whether their location is writable."""
    cache = output / "tool-cache"
    for directory in (cache / "Ultralytics", cache / "matplotlib", cache / "torch"):
        directory.mkdir(parents=True, exist_ok=True)
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[name] = str(THREADS)
    os.environ.update({"CUDA_VISIBLE_DEVICES": "", "YOLO_OFFLINE": "true", "YOLO_AUTOINSTALL": "false",
                       "YOLO_CONFIG_DIR": str(cache), "MPLCONFIGDIR": str(cache / "matplotlib"),
                       "TORCH_HOME": str(cache / "torch")})
    return cache / "Ultralytics"


def verify_cpu_predictor(predictor, float32):
    """8.4.176 uses quantize; verify the actual fused backend precision as well."""
    expected = {**INFERENCE, "max_det": 100, "device": "cpu", "quantize": None, "save": False,
                "verbose": False, "batch": 1, "rect": True, "augment": False, "agnostic_nms": False}
    if any(getattr(predictor.args, key, object()) != value for key, value in expected.items()):
        raise ValueError("Actual predictor arguments differ from the measured protocol")
    parameters = list(predictor.model.model.parameters())
    if (predictor.device.type != "cpu" or predictor.model.fp16 or not parameters
            or any(parameter.device.type != "cpu" or parameter.dtype != float32 for parameter in parameters)):
        raise ValueError("Actual predictor backend is not CPU float32")


def summary(values):
    if not values or any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError("Timings must be positive finite measurements")
    ordered = sorted(values)
    return {"median_ms": statistics.median(values), "p95_ms": ordered[math.ceil(0.95 * len(values)) - 1],
            "min_ms": ordered[0], "max_ms": ordered[-1], "timed_calls": len(values)}


def self_test():
    rows = [{"sample_id": f"{country}_{i:02d}", "country": country, "split": "val", "assigned_split": "val",
             "is_mirror": False, "exclusion_reason": None, "exif_orientation": 1}
            for country in COUNTRIES for i in range(12)]
    selected = select_inputs(rows + [{"split": "test", "country": "Czech", "sample_id": "MUST_NOT_READ"}])
    assert selected == select_inputs(list(reversed(rows)))
    assert Counter(row["country"] for row in selected) == dict.fromkeys(COUNTRIES, 10)
    assert summary(list(range(1, 101)))["p95_ms"] == 95
    assert summary([1, 2, 3])["median_ms"] == 2
    print("Dependency-free selection/statistics smoke passed; no inference executed.")


def main(repo: Path, run_name: str):
    started = time.perf_counter()
    repo = repo.resolve(strict=True)
    output = output_directory(repo, run_name)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(repo / "SystemCode"))
    from model.compare_models import load_plan, verify_run
    from model.checkpointing import write_json

    plan_path = repo / "Dataset" / "compare30" / "plan.json"
    plan = load_plan(plan_path, repo)
    verified = {variant: verify_run(plan["candidates"][variant], plan, repo) for variant in ("n", "s")}
    manifest_path = repo / "Dataset" / "prepared" / "manifest.jsonl"
    if digest(manifest_path) != plan["inputs"]["manifest"]["sha256"]:
        raise ValueError("Prepared manifest differs from the frozen comparison")
    inputs = checked_inputs([json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines()], repo)
    source_paths = [repo / "SystemCode/backend/roadguard" / name for name in
                    ("images.py", "vision/real.py", "schemas/vision.py", "schemas/common.py")]
    # Include every backend schema source: DTO validation is part of this boundary.
    source_paths = sorted(set(source_paths + list((repo / "SystemCode/backend/roadguard/schemas").glob("*.py"))))
    sources = {path.relative_to(repo).as_posix(): digest(path) for path in source_paths if path.is_file()}
    helper_sha = digest(Path(__file__))
    protocol = {"pipeline": "backend_real_single_image", "source_split": "val", "test_used": False,
                "image_set_sha256": fingerprint(inputs), "backend_source_sha256": fingerprint(sources),
                **INFERENCE, "cpu_threads": THREADS, "interop_threads": 1, "warmup": WARMUP, "repeats": REPEATS,
                "max_det": 100, "images": IMAGE_COUNT, "seed": 42, "country_counts": dict.fromkeys(COUNTRIES, 10),
                "selection": "Per country sort by SHA256('42:'+sample_id), take first10; interleave Czech/India/Japan/United_States.",
                "warmup_definition": "Two untimed fresh prepare+detect calls per candidate on the first two fixed inputs.",
                "repeat_definition": "Three complete passes over the same ordered40images;120timedcalls per candidate.",
                "candidate_execution_order": [["n", "s"], ["s", "n"], ["n", "s"]],
                "timing_boundary": "perf_counter_ns immediately before ImageStore.prepare(bytes) until LocalVisionDetector.detect returns Detection DTO list",
                "includes": ["upload byte hash", "image verify/decode", "EXIF/RGB/PNG normalization", "prepared PNG decode",
                             "YOLO preprocessing", "CPU inference", "NMS/postprocessing", "Detection DTO construction/validation"],
                "excludes": ["disk image read and SHA assertion", "model/manifest/checkpoint load", "warmup", "result serialization",
                             "runtime assertions", "persistent image storage", "HTTP/database/rules/review/task processing"],
                "p95_definition": "nearest rank ceil(0.95*N), on120single-image pipeline measurements",
                "cache_policy": "Models/predictors warmed and retained; image bytes re-read every call, fresh prepare/detect, no image/result memoization."}
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "status.json", {"status": "running", "protocol": protocol})
    try:
        # Before importing torch/numpy/Ultralytics: avoid CPU library thread surprises.
        expected_config_directory = configure_runtime_environment(output)
        import torch
        torch.set_num_threads(THREADS)
        torch.set_num_interop_threads(1)
        torch.manual_seed(42)
        import ultralytics.utils as ultra_utils
        import ultralytics.utils.torch_utils as torch_utils
        if Path(ultra_utils.USER_CONFIG_DIR).resolve() != expected_config_directory.resolve():
            raise ValueError("Ultralytics fell back outside the intended latency cache directory")
        # select_device(cpu) resets torch threads to this imported constant in8.4.176.
        ultra_utils.NUM_THREADS = torch_utils.NUM_THREADS = THREADS
        from ultralytics import YOLO, settings
        settings.update({key: False for key in ("sync", "clearml", "comet", "dvc", "hub", "mlflow", "neptune",
                         "raytune", "tensorboard", "wandb") if key in settings})
        sys.path.insert(0, str(repo / "SystemCode" / "backend"))
        from roadguard.images import ImageStore
        from roadguard.vision.real import LocalVisionDetector
        store = ImageStore(output / "unused-image-storage")  # prepare() never stores a file.
        detectors, candidates = {}, {}
        for variant in ("n", "s"):
            manifest = repo / verified[variant]["model_manifest_path"]
            detector = LocalVisionDetector(manifest, model_loader=YOLO)
            detector._load()  # Exclude trusted-manifest hash and weight loading from measured latency.
            if detector._inference != INFERENCE or detector.weights_sha256 != verified[variant]["checkpoints_sha256"]["best.pt"]:
                raise ValueError("Candidate backend inference settings/weights differ")
            parameters = list(detector._model.model.parameters())
            if not parameters or any(p.device.type != "cpu" or p.dtype != torch.float32 or not bool(torch.isfinite(p).all()) for p in parameters):
                raise ValueError("Candidate weights are not finite CPU float32 parameters")
            candidates[variant] = {"weights_sha256": detector.weights_sha256, "manifest_sha256": digest(manifest),
                                   "model_version": detector.model_version, "parameter_count_before_fusion": sum(p.numel() for p in parameters),
                                   "timings": [], "warmup_timings_ms": []}
            detectors[variant] = detector
            del parameters
        if not 0 < candidates["n"]["parameter_count_before_fusion"] < candidates["s"]["parameter_count_before_fusion"]:
            raise ValueError("Actual n/s parameter counts do not identify the expected smaller/larger pair")

        def invoke(variant, item):
            data = (repo / item["image_path"]).read_bytes()  # Excluded; bytes are never retained across calls.
            if hashlib.sha256(data).hexdigest() != item["image_sha256"]:
                raise ValueError("Input changed between repeated calls")
            if torch.get_num_threads() != THREADS or torch.get_num_interop_threads() != 1:
                raise ValueError("CPU threads differ before timed invocation")
            detector = detectors[variant]
            begin = time.perf_counter_ns()
            prepared = store.prepare(data)
            detections = detector.detect(prepared)
            elapsed = (time.perf_counter_ns() - begin) / 1_000_000
            predictor = detector._model.predictor
            verify_cpu_predictor(predictor, torch.float32)
            if (torch.get_num_threads() != THREADS or torch.get_num_interop_threads() != 1
                    or (prepared.width, prepared.height) != (item["width"], item["height"])
                    or any(dto.is_demo or dto.model_version != detector.model_version for dto in detections)):
                raise ValueError("Actual CPU/device/image/DTO contract differs")
            count = len(detections)
            # Ultralytics retains the most recent batch/result; clear those references,
            # outside timing, so neither image nor prediction is cached between calls.
            for name in ("results", "batch", "dataset", "plotted_img"):
                if hasattr(predictor, name):
                    setattr(predictor, name, None)
            del data, prepared, detections
            return elapsed, count

        for variant in ("n", "s"):
            for item in inputs[:WARMUP]:
                elapsed, _ = invoke(variant, item)
                candidates[variant]["warmup_timings_ms"].append(elapsed)
        measure_started = time.perf_counter()
        for repeat, order in enumerate(protocol["candidate_execution_order"], 1):
            for variant in order:
                for item in inputs:
                    elapsed, count = invoke(variant, item)
                    candidates[variant]["timings"].append({"repeat": repeat, "sample_id": item["sample_id"],
                                                           "country": item["country"], "elapsed_ms": elapsed, "detections": count})
                print(f"CPU latency repeat{repeat}/{REPEATS} candidate{variant}: {IMAGE_COUNT} images complete", flush=True)
        measured_wall = time.perf_counter() - measure_started
        for variant, candidate in candidates.items():
            if len(candidate["timings"]) != TIMED_CALLS or candidates[variant]["weights_sha256"] != digest(repo / "Dataset/runs" / plan["candidates"][variant]["config"]["run_name"] / "weights/best.pt"):
                raise ValueError("Incomplete timings or changed candidate weights")
            candidate.update(summary([row["elapsed_ms"] for row in candidate["timings"]]))
            candidate["total_timed_pipeline_seconds"] = sum(row["elapsed_ms"] for row in candidate["timings"]) / 1000
        if (digest(manifest_path) != plan["inputs"]["manifest"]["sha256"]
                or sources != {path: digest(repo / path) for path in sources} or digest(Path(__file__)) != helper_sha):
            raise ValueError("Frozen inputs or measured source changed during execution")
        report = {"schema_version": "roadguard-compare30-cpu-latency-v1", "status": "complete", "device": "cpu", "test_used": False,
                  "protocol": protocol, "inputs": inputs, "candidates": candidates, "backend_source_files_sha256": sources,
                  "helper_source_sha256": helper_sha, "plan_sha256": plan["plan_sha256"],
                  "prepared_manifest_sha256": plan["inputs"]["manifest"]["sha256"],
                  "runtime": {"python": platform.python_version(), "platform": platform.platform(), "cpu": platform.processor(),
                              "packages": {name: importlib.metadata.version(name) for name in ("torch", "torchvision", "ultralytics", "Pillow", "numpy", "pydantic")},
                              "actual_torch_num_threads": torch.get_num_threads(), "actual_torch_interop_threads": torch.get_num_interop_threads()},
                  "measured_passes_wall_seconds": measured_wall, "total_wall_seconds": time.perf_counter() - started,
                  "limitations": ["40 country-balanced validation originals are a fixed latency sample, not production traffic.",
                                  "Median/p95 summarize 120 calls per candidate; no statistical superiority claim.",
                                  "Warm loaded-model latency; excludes cold start, disk read, HTTP, database and task processing.",
                                  "OS filesystem cache and CPU scheduling/thermal state are not controlled.",
                                  "Alternating candidate blocks reduces but does not eliminate order/thermal effects.",
                                  "Ultralytics NUM_THREADS is set to4 in this process only; repository source is unchanged."]}
        write_json(output / "latency.json", report)
        write_json(output / "status.json", {"status": "complete", "latency_sha256": digest(output / "latency.json")})
        print(output / "latency.json")
    except BaseException as error:
        write_json(output / "status.json", {"status": "failed", "error_type": type(error).__name__, "error": str(error)})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--run-name", default="acceptance-v1")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        main(args.repo, args.run_name)
