"""CPU benchmark preflight contracts; no torch, Ultralytics or inference needed."""

import builtins
from collections import Counter
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model import benchmark_cpu as benchmark, compare_models


def records(per_country=12):
    return [{"sample_id": f"{country}_{index:03d}", "country": country, "split": "val", "assigned_split": "val",
             "is_mirror": False, "exclusion_reason": None, "exif_orientation": 1, "width": 600, "height": 600}
            for country in benchmark.COUNTRIES for index in range(per_country)]


def test_selection_is_original_val_country_balanced_and_manifest_order_independent():
    rows = records()
    # No image path/digest/dimension fields: these rows must be skipped before access.
    rows += [{"split": "test", "country": "Czech", "sample_id": "DO_NOT_OPEN_TEST"},
             {"split": "train", "country": "Japan", "sample_id": "DO_NOT_OPEN_TRAIN"}]
    selected = benchmark.select_inputs(rows)
    assert selected == benchmark.select_inputs(list(reversed(rows)))
    assert len(selected) == len({row["sample_id"] for row in selected}) == 40
    assert Counter(row["country"] for row in selected) == dict.fromkeys(benchmark.COUNTRIES, 10)
    assert [row["country"] for row in selected] == list(benchmark.COUNTRIES) * 10
    assert all(row["split"] == "val" and not row["is_mirror"] for row in selected)


@pytest.mark.parametrize("country", benchmark.COUNTRIES)
def test_missing_or_insufficient_country_fails(country):
    rows = [row for row in records(10) if row["country"] != country]
    with pytest.raises(ValueError, match="Insufficient"):
        benchmark.select_inputs(rows)


@pytest.mark.parametrize("change", [{"country": "Unknown"}, {"country": None}, {"country": "India"}, {"is_mirror": True},
                                  {"assigned_split": "test"}, {"exclusion_reason": "ambiguous"},
                                  {"exif_orientation": 6}, {"sample_id": "xmirror_Czech_000"},
                                  {"sample_id": "../test/escape"}, {"sample_id": None}])
def test_incorrect_validation_record_is_rejected(change):
    rows = records()
    rows[0].update(change)
    with pytest.raises(ValueError):
        benchmark.select_inputs(rows)


def test_checked_inputs_hashes_only_selected_val_images_without_test_file_access(tmp_path, monkeypatch):
    repo = tmp_path.resolve()
    val = repo / "Dataset/prepared/images/val"
    val.mkdir(parents=True)
    rows = records(10)
    for row in rows:
        image = val / f'{row["sample_id"]}.jpg'
        image.write_bytes(row["sample_id"].encode())
        row["image_sha256"] = benchmark.digest(image)
    rows += [{"split": "test", "country": "Czech", "sample_id": "ABSENT_TEST_FILE"},
             {"split": "train", "country": "Japan", "sample_id": "ABSENT_TRAIN_FILE"}]
    touched = []
    original_digest = benchmark.digest

    def guarded(path):
        assert Path(path).parent == val
        touched.append(Path(path))
        return original_digest(path)

    monkeypatch.setattr(benchmark, "digest", guarded)
    inputs = benchmark.checked_inputs(rows, repo)
    assert len(inputs) == len(touched) == 40
    assert all(item["image_path"].startswith("Dataset/prepared/images/val/") for item in inputs)
    touched[0].write_bytes(b"mutated image")
    with pytest.raises(ValueError, match="changed"):
        benchmark.checked_inputs(rows, repo)


@pytest.mark.parametrize("name", ["", "..", "../escape", "a/b", "a\\b", "C:\\outside"])
def test_output_name_cannot_escape_dataset(tmp_path, name):
    with pytest.raises(ValueError, match="run-name"):
        benchmark.output_directory(tmp_path.resolve(), name)


def test_output_has_fixed_containment_and_never_overwrites(tmp_path):
    repo = tmp_path.resolve()
    output = benchmark.output_directory(repo, "acceptance-v1")
    assert output == repo / "Dataset/compare30/cpu-latency/acceptance-v1"
    assert not output.exists()  # Pure preflight does not create output directories.
    output.mkdir(parents=True)
    sentinel = output / "latency.json"
    sentinel.write_bytes(b"existing evidence")
    with pytest.raises(ValueError, match="already exists"):
        benchmark.output_directory(repo, "acceptance-v1")
    assert sentinel.read_bytes() == b"existing evidence"


def test_unfinished_candidate_fails_before_vision_import_or_output(tmp_path, monkeypatch):
    plan = {"candidates": {"n": {"variant": "n"}, "s": {"variant": "s"}}}
    monkeypatch.setattr(compare_models, "load_plan", lambda *_: plan)
    checked = []

    def unfinished(row, *_):
        checked.append(row["variant"])
        raise ValueError("candidate has not completed training and validation")

    monkeypatch.setattr(compare_models, "verify_run", unfinished)
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"torch", "torchvision", "ultralytics"}:
            pytest.fail("Unfinished preflight imported a vision runtime")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(sys, "dont_write_bytecode", sys.dont_write_bytecode)
    with pytest.raises(ValueError, match="not completed"):
        benchmark.main(tmp_path, "unfinished")
    assert checked == ["n"]
    assert not (tmp_path / "Dataset/compare30/cpu-latency/unfinished").exists()


def test_missing_preregistration_fails_before_vision_import(tmp_path, monkeypatch):
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"torch", "torchvision", "ultralytics"}:
            pytest.fail("Missing-input preflight imported a vision runtime")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(sys, "dont_write_bytecode", sys.dont_write_bytecode)
    with pytest.raises(FileNotFoundError):
        benchmark.main(tmp_path, "missing-plan")
    assert not (tmp_path / "Dataset/compare30/cpu-latency/missing-plan").exists()


def test_latency_summary_uses_nearest_rank_p95_and_rejects_invalid_measurements():
    result = benchmark.summary(list(range(1, 121)))
    assert result["median_ms"] == 60.5 and result["p95_ms"] == 114 and result["timed_calls"] == 120
    for invalid in ([], [0], [float("nan")], [float("inf")], [-1]):
        with pytest.raises(ValueError, match="positive finite"):
            benchmark.summary(invalid)


def test_cache_locations_exist_before_runtime_import_so_ultralytics_cannot_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark.os, "environ", dict(benchmark.os.environ))
    output = tmp_path / "acceptance-v2"
    intended = benchmark.configure_runtime_environment(output)
    assert intended == output / "tool-cache/Ultralytics" and intended.is_dir()
    assert intended.parent.is_dir()
    assert benchmark.os.environ["YOLO_CONFIG_DIR"] == str(intended.parent)
    for key in ("MPLCONFIGDIR", "TORCH_HOME"):
        assert Path(benchmark.os.environ[key]).is_dir()
    assert benchmark.os.environ["CUDA_VISIBLE_DEVICES"] == ""
    assert benchmark.os.environ["OMP_NUM_THREADS"] == "4"


def cpu_predictor():
    args = SimpleNamespace(**benchmark.INFERENCE, max_det=100, device="cpu", quantize=None, save=False,
                           verbose=False, batch=1, rect=True, augment=False, agnostic_nms=False)
    parameter = SimpleNamespace(device=SimpleNamespace(type="cpu"), dtype="float32")
    backend = SimpleNamespace(fp16=False, model=SimpleNamespace(parameters=lambda: [parameter]))
    return SimpleNamespace(args=args, device=SimpleNamespace(type="cpu"), model=backend), parameter


def test_installed_precision_contract_accepts_args_without_deprecated_half():
    predictor, _ = cpu_predictor()
    assert not hasattr(predictor.args, "half")
    benchmark.verify_cpu_predictor(predictor, "float32")


@pytest.mark.parametrize("change", ["quantize", "fp16", "parameter_dtype", "parameter_device", "predictor_device", "no_parameters"])
def test_precision_check_rejects_quantization_or_non_cpu_float32_backend(change):
    predictor, parameter = cpu_predictor()
    if change == "quantize":
        predictor.args.quantize = 16
    elif change == "fp16":
        predictor.model.fp16 = True
    elif change == "parameter_dtype":
        parameter.dtype = "float16"
    elif change == "parameter_device":
        parameter.device.type = "cuda"
    elif change == "predictor_device":
        predictor.device.type = "cuda"
    else:
        predictor.model.model.parameters = lambda: []
    with pytest.raises(ValueError, match="arguments|CPU float32"):
        benchmark.verify_cpu_predictor(predictor, "float32")
