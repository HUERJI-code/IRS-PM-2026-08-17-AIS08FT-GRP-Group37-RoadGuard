"""Geometry, eight-class inference/recovery and heuristic fusion tests; no GPU."""

import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model import balanced_metrics as balanced
from model import inference_experiments as experiments
from model.checkpointing import sha256_file, write_json


def obj(class_id=0, score=0.8, box=(0, 0, 10, 10)):
    return {"class_id": class_id, "confidence": score, "bbox_xyxy": list(box)}


@pytest.fixture
def dataset(tmp_path, monkeypatch):
    prepared = tmp_path / "Dataset/prepared"
    for kind in ("images", "labels"):
        for split in ("train", "val", "test"):
            (prepared / kind / split).mkdir(parents=True)
    records = []
    for index in range(2):
        image = prepared / f"images/val/Czech_{index}.jpg"
        Image.new("RGB", (16, 12), "gray").save(image)
        label = prepared / f"labels/val/Czech_{index}.txt"
        label.write_text("0 0.5 0.5 1 1\n")
        records.append({"sample_id": f"Czech_{index}", "split": "val", "assigned_split": "val", "is_mirror": False,
                        "exclusion_reason": None, "country": "Czech", "width": 16, "height": 12, "exif_orientation": 1,
                        "boxes": [[0, 0.5, 0.5, 1, 1]], "image_sha256": sha256_file(image), "label_sha256": sha256_file(label)})
    (prepared / "manifest.jsonl").write_text("\n".join(json.dumps(row) for row in [*records, {"sample_id": "NEVER_READ_TEST", "split": "test"},
                                                                                         {"sample_id": "NEVER_READ_TRAIN", "split": "train"}]))
    (prepared / "data.yaml").write_text(f'path: {json.dumps(str(prepared))}\ntrain: images/train\nval: images/val\ntest: images/test\nnc: 8\nnames: {json.dumps(balanced.source_names())}\n')
    weights = tmp_path / "Dataset/best.pt"
    weights.write_bytes(b"test model checkpoint")
    monkeypatch.setattr(experiments, "configure_local_runtime", lambda _: pytest.fail("Injected models must not enter real runtime"))
    return tmp_path, weights


class FakeModel:
    names = dict(enumerate(balanced.source_names()))

    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def predict(self, source, **settings):
        self.calls.append((source.size, copy.deepcopy(settings)))
        if len(self.calls) == self.fail_on:
            raise RuntimeError("injected interruption")
        assert source.mode == "RGB"
        assert settings["conf"] == 0.001 and settings["iou"] == 0.7 and settings["max_det"] == 100
        assert settings["quantize"] is None and settings["batch"] == 1 and settings["agnostic_nms"] is False
        tensor = lambda value: SimpleNamespace(tolist=lambda: value)
        # Descending model order is intentionally preserved, including score ties.
        predictions = [obj(0, 0.8, (0, 0, source.width, source.height)), obj(1, 0.8, (0, 0, source.width, source.height))]
        return [SimpleNamespace(orig_shape=(source.height, source.width), boxes=SimpleNamespace(
            xyxy=tensor([prediction["bbox_xyxy"] for prediction in predictions]), cls=tensor([prediction["class_id"] for prediction in predictions]),
            conf=tensor([prediction["confidence"] for prediction in predictions])))]


def export(dataset, name="unit-export", model=None, **kwargs):
    root, weights = dataset
    model = model or FakeModel()
    path = experiments.export_predictions(weights, name, root=root, expected_images=2, model_factory=lambda _: model, **kwargs)
    return path, model


def test_flip_and_native_crop_offsets_are_inverted_exactly():
    view = {"crop": [0, 0, 100, 80], "flip": True}
    assert experiments.project_box([10, 15, 30, 40], view, 100, 80) == [70, 15, 90, 40]
    view = {"crop": [40, 30, 100, 80], "flip": True}
    assert experiments.project_box([5, 2, 20, 10], view, 100, 80) == [80, 32, 95, 40]
    view["flip"] = False
    assert experiments.project_box([5, 2, 20, 10], view, 100, 80) == [45, 32, 60, 40]
    for bad in ([float("nan"), 0, 10, 10], [-1, 0, 10, 10], [0, 0, 100, 60], [0, 0, 0, 10], [False, 0, 10, 10]):
        with pytest.raises(ValueError):
            experiments.project_box(bad, view, 100, 80)


@pytest.mark.parametrize("width,height", [(101, 77), (16, 12), (1, 1)])
def test_tiles_cover_every_pixel_with_ceil_sizes_and_full_image_retained(width, height):
    regions = experiments.tile_regions(width, height)
    assert len(regions) == (1 if (width, height) == (1, 1) else 4)
    expected_width = __import__("math").ceil(width * 0.625)
    expected_height = __import__("math").ceil(height * 0.625)
    for left, top, right, bottom in regions:
        assert right - left == expected_width and bottom - top == expected_height
    assert all(any(left <= x < right and top <= y < bottom for left, top, right, bottom in regions)
               for x in range(width) for y in range(height))
    assert experiments.views("tiles", width, height)[0] == {"crop": [0, 0, width, height], "flip": False}


def test_class_aware_nms_retains_cross_class_duplicates_and_stable_ties():
    predictions = [obj(0, 0.8), obj(1, 0.8), obj(0, 0.8), obj(2, 0.7)]
    before = copy.deepcopy(predictions)
    assert experiments.class_aware_nms(predictions) == [predictions[0], predictions[1], predictions[3]]
    assert predictions == before
    # IoU exactly .5 is retained: NMS suppresses >, unlike matching's >=.
    assert len(experiments.class_aware_nms([obj(), obj(box=(0, 0, 5, 10))], 0.5)) == 2
    assert len(experiments.class_aware_nms([obj(class_id=index % 8, box=(index * 20, 0, index * 20 + 10, 10)) for index in range(150)], 0.7)) == 100


def test_paired_score_has_one_vote_per_model_and_singleton_penalty():
    models = [[obj(0, 0.9), obj(0, 0.8)], [obj(0, 0.7, box=(1, 0, 11, 10))]]
    result = experiments.paired_score_fusion(models)
    assert len(result) == 2
    assert result[0]["confidence"] == pytest.approx(0.8)
    assert result[1]["confidence"] == pytest.approx(0.4)
    assert result[0]["bbox_xyxy"] == pytest.approx([0.7 / 1.6, 0, (9 + 7.7) / 1.6, 10])
    assert result[1]["bbox_xyxy"] == models[0][1]["bbox_xyxy"]
    assert experiments.paired_score_fusion(models) == result
    assert all(0 <= prediction["bbox_xyxy"][0] < prediction["bbox_xyxy"][2] <= 11 for prediction in result)


def test_pairing_is_same_class_nontransitive_and_drops_subfloor_singletons():
    assert len(experiments.paired_score_fusion([[obj(0)], [obj(1)]])) == 2
    assert experiments.paired_score_fusion([[obj(score=0.001)], []]) == []
    assert experiments.paired_score_fusion([[obj(score=0.002)], []])[0]["confidence"] == 0.001
    with pytest.raises(ValueError, match="exactly two"):
        experiments.paired_score_fusion([[obj()]])
    # Equal-IoU opposite boxes choose confidence then the original source index.
    result = experiments.paired_score_fusion([[obj(0, 0.9)], [obj(0, 0.6), obj(0, 0.8)]])
    assert result[0]["confidence"] == pytest.approx(0.85)
    assert result[1]["confidence"] == pytest.approx(0.3)


def test_equal_fused_score_final_nms_ties_follow_original_source_not_raw_seed_order():
    a, b = (0, 0, 10, 10), (2.5, 0, 12.5, 10)
    parent = [obj(0, 0.8, b), obj(0, 0.1, a)]
    current = [obj(0, 0.9, a), obj(0, 0.2, b)]
    # A seeds first using current .9, yet B contributes parent original index0.
    result = experiments.paired_score_fusion([parent, current])
    assert [prediction["confidence"] for prediction in result] == [0.5, 0.5]
    assert result[0]["bbox_xyxy"] == pytest.approx(b)
    assert experiments.class_aware_nms(result, 0.5)[0]["bbox_xyxy"] == pytest.approx(b)


def test_standard_export_preserves_original_model_order_and_marks_fake_execution(dataset):
    path, model = export(dataset)
    metadata, rows = experiments.load_export(path, root=dataset[0], expected_images=2)
    assert [prediction["class_id"] for prediction in rows[0]["predictions"]] == [0, 1]
    assert metadata["identity"]["execution"] == "injected_test_model" and not experiments._genuine(metadata)
    assert len(model.calls) == 2
    metrics_path = experiments.analyze_export(path, root=dataset[0], expected_images=2)
    report = experiments._read(metrics_path)
    assert report["execution"] == "injected_test_model" and report["test_used"] is False
    assert report["thresholds"] == list(balanced.THRESHOLDS) and len(report["thresholds"]) == 25
    assert len(report["selected_primary"]["per_class"]) == 8
    assert report["primary_iou"] == 0.5 and report["secondary_iou"] == 0.3
    with pytest.raises(ValueError, match="real validated"):
        experiments.fuse_exports([path], "must-not-fuse-fake", root=dataset[0], expected_images=2)
    with pytest.raises(ValueError, match="preregistered"):
        experiments.compare_candidates([path, *[dataset[0] / f"Dataset/inference-followup/missing{i}/export.json" for i in range(7)]],
                                       "must-not-select-fake", root=dataset[0], expected_images=2)


@pytest.mark.parametrize("method,expected_calls", [("flip", 4), ("tiles", 10)])
def test_multiview_exports_record_realized_native_transforms_and_common_nms(dataset, method, expected_calls):
    path, model = export(dataset, method=method, nms_iou=0.5)
    metadata, rows = experiments.load_export(path, root=dataset[0], expected_images=2)
    assert len(model.calls) == expected_calls
    image = experiments._read(path.parent / "images/Czech_0.json")
    assert image["realized_views"] == experiments.views(method, 16, 12)
    assert metadata["identity"]["config"]["settings"]["iou"] == 0.7
    assert metadata["identity"]["config"]["global_nms_iou"] == 0.5
    assert len(rows[0]["predictions"]) <= 100
    assert all(0 <= prediction["bbox_xyxy"][0] < prediction["bbox_xyxy"][2] <= 16 for prediction in rows[0]["predictions"])


def test_interrupted_export_resumes_only_missing_atomic_images(dataset):
    model = FakeModel(fail_on=2)
    with pytest.raises(RuntimeError, match="interruption"):
        export(dataset, model=model)
    output = dataset[0] / "Dataset/inference-followup/unit-export"
    completed = output / "images/Czech_0.json"
    before = completed.read_bytes()
    assert completed.is_file() and not (output / "export.json").exists()
    model = FakeModel()
    path, _ = export(dataset, model=model, resume=True)
    assert len(model.calls) == 1 and completed.read_bytes() == before
    assert experiments._read(path.parent / "status.json")["status"] == "complete"
    model = FakeModel()
    same, _ = export(dataset, model=model, resume=True)
    assert same == path and not model.calls


def test_interrupted_resume_rejects_mutated_completed_payload_before_it_can_be_resigned(dataset):
    with pytest.raises(RuntimeError, match="interruption"):
        export(dataset, model=FakeModel(fail_on=2))
    path = dataset[0] / "Dataset/inference-followup/unit-export/images/Czech_0.json"
    value = experiments._read(path)
    value["predictions"][0]["confidence"] = 0.7
    write_json(path, value)
    model = FakeModel()
    with pytest.raises(ValueError, match="payload changed"):
        export(dataset, model=model, resume=True)
    assert not model.calls
    assert not (path.parent.parent / "export.json").exists()


@pytest.mark.parametrize("mutation", ["config", "weights", "image", "manifest", "code", "runtime", "image_result"])
def test_resume_rejects_changed_config_input_code_runtime_and_predictions(dataset, monkeypatch, mutation):
    path, _ = export(dataset)
    kwargs = {"resume": True}
    root, weights = dataset
    if mutation == "config":
        kwargs["imgsz"] = 960
    elif mutation == "weights":
        weights.write_bytes(b"changed weights")
    elif mutation == "image":
        (root / "Dataset/prepared/images/val/Czech_0.jpg").write_bytes(b"changed image")
    elif mutation == "manifest":
        manifest = root / "Dataset/prepared/manifest.jsonl"
        manifest.write_text(manifest.read_text() + "\n")
    elif mutation == "code":
        monkeypatch.setattr(experiments, "_source_hashes", lambda: {"inference_experiments.py": "changed"})
    elif mutation == "runtime":
        monkeypatch.setattr(experiments, "_runtime", lambda: {"python": "other version"})
    elif mutation == "image_result":
        image_path = path.parent / "images/Czech_0.json"
        value = experiments._read(image_path)
        value["predictions"][0]["confidence"] = 0.2
        write_json(image_path, value)
    with pytest.raises(ValueError):
        export(dataset, **kwargs)


def test_incomplete_image_set_cannot_be_loaded_as_complete_export(dataset):
    path, _ = export(dataset)
    (path.parent / "images/Czech_1.json").unlink()
    with pytest.raises(ValueError, match="Incomplete"):
        experiments.load_export(path, root=dataset[0], expected_images=2)
    with pytest.raises(ValueError, match="exactly eight"):
        experiments.compare_candidates([path], "incomplete-comparison", root=dataset[0], expected_images=2)


def test_original_export_loader_is_reused_without_relaxing_frozen_contract(dataset, monkeypatch):
    root = dataset[0]
    path = root / "Dataset/balanced-metrics/old/export.json"
    calls = []
    monkeypatch.setattr(balanced, "_load_export", lambda export_path, export_root, count: calls.append((export_path, export_root, count)) or ({"old": True}, []))
    assert experiments.load_export(path, root=root, expected_images=2) == ({"old": True}, [])
    assert calls == [(path, root, 2)]


def test_selection_uses_fixed_primary_not_secondary_or_confusion_family():
    rows = [{"sample_id": "x", "truth": [{"class_id": 0, "bbox_xyxy": [0, 0, 10, 10]}],
             "predictions": [obj(0, 0.8, (0, 0, 4, 10)), obj(1, 0.9)]}]
    report = experiments.metrics({"execution": "injected_test_model"}, rows)
    assert report["selected_primary"]["micro"]["tp"] == 0
    assert report["selected_secondary_diagnostic"]["micro"]["tp"] == 1
    assert report["selected_primary"]["mode"] == "eight_class" and report["target_met_micro"] is False
    assert len(report["selected_primary"]["per_class"]) == 8


def signed_genuine_source_fixture(dataset, name, weights=None):
    """Resign synthetic artifacts to test source loader/derived metadata contracts.

    Only isolated test directories contain these deliberately synthetic fixtures.
    No real model inference or accuracy claim is made.
    """
    root, default_weights = dataset
    path = balanced.export_predictions(weights or default_weights, name, root=root, expected_images=2,
                                       model_factory=lambda _: FakeModel())
    metadata = experiments._read(path)
    metadata.update(execution="real_local_weights", model_state_validation={"checked": True, "finite_tensors": 1},
                    precision_validation={"checked": True, "floating_tensor_dtype": "torch.float32", "fp16": False, "quantize": None})
    write_json(path, metadata)
    status = experiments._read(path.parent / "status.json")
    status["export_sha256"] = sha256_file(path)
    write_json(path.parent / "status.json", status)
    return path


def test_cached_post_nms_and_two_model_fusion_metadata_load_and_resume(dataset):
    parent = signed_genuine_source_fixture(dataset, "parent640")
    weights = dataset[0] / "Dataset/other.pt"
    weights.write_bytes(b"distinct current model")
    current = signed_genuine_source_fixture(dataset, "current832", weights)
    renms = experiments.fuse_exports([current], "cached-renms", root=dataset[0], expected_images=2)
    metadata, _ = experiments.load_export(renms, root=dataset[0], expected_images=2)
    assert metadata["identity"]["config"]["method"] == "cached_post_nms"
    for strategy in ("union_nms", "paired_score"):
        path = experiments.fuse_exports([parent, current], strategy, strategy=strategy, root=dataset[0], expected_images=2)
        metadata, rows = experiments.load_export(path, root=dataset[0], expected_images=2)
        assert metadata["identity"]["config"]["exports"] == [parent.relative_to(dataset[0]).as_posix(), current.relative_to(dataset[0]).as_posix()]
        assert len(rows[0]["predictions"]) == 2
        assert experiments._genuine(metadata)
        assert experiments.fuse_exports([parent, current], strategy, strategy=strategy, root=dataset[0], expected_images=2, resume=True) == path
    with pytest.raises(ValueError, match="distinct model"):
        experiments.fuse_exports([parent, parent], "duplicate-votes", strategy="paired_score", root=dataset[0], expected_images=2)


def test_derived_export_rejects_changed_underlying_predictions_even_if_source_metadata_unchanged(dataset):
    source = signed_genuine_source_fixture(dataset, "source")
    path = experiments.fuse_exports([source], "renms", root=dataset[0], expected_images=2)
    raw = source.parent / "predictions.jsonl"
    raw.write_text(raw.read_text().replace('"confidence": 0.8', '"confidence": 0.7'))
    with pytest.raises(ValueError, match="Raw predictions hash"):
        experiments.load_export(path, root=dataset[0], expected_images=2)


def test_global_winner_and_both_metrics_recommendation_can_differ():
    def candidate(name, p, r, f1):
        return {"id": name, "selected_primary": {"mode": "eight_class", "iou": 0.5, "threshold": 0.3,
                "micro": {"precision": p, "recall": r}, "macro": {"f1": f1}}}
    baseline = candidate("baseline", 0.6, 0.7, 0.6)
    global_winner = candidate("global", 0.75, 0.69, 0.8)
    improves_both = candidate("both", 0.65, 0.72, 0.6)
    selected = experiments.select_methods([baseline, global_winner, improves_both])
    assert selected["global_winner"] is global_winner
    assert selected["recommendation"] is improves_both and selected["recommendation_improves_both"]
    selected = experiments.select_methods([baseline, global_winner])
    assert selected["recommendation"] is baseline and not selected["recommendation_improves_both"]
    equal = candidate("equal-baseline", 0.6, 0.75, 0.8)
    assert experiments.select_methods([baseline, equal])["recommendation"] is baseline


def test_resumed_genuine_process_rechecks_actual_backend_even_with_saved_precision_state(dataset, monkeypatch):
    root, weights = dataset
    tensor = SimpleNamespace(dtype="fp32", is_floating_point=lambda: True)
    torch = SimpleNamespace(float32="fp32", manual_seed=lambda _: None, get_float32_matmul_precision=lambda: "highest",
                            isfinite=lambda _: SimpleNamespace(all=lambda: True),
                            cuda=SimpleNamespace(is_available=lambda: False),
                            backends=SimpleNamespace(cudnn=SimpleNamespace(benchmark=False, deterministic=True, allow_tf32=True),
                                                     cuda=SimpleNamespace(matmul=SimpleNamespace(allow_tf32=True))))

    class BackendModel(FakeModel):
        def __init__(self, fail_on=None, device_type="cpu"):
            super().__init__(fail_on)
            state = SimpleNamespace(state_dict=lambda: {"weight": tensor})
            self.model = state
            self.predictor = SimpleNamespace(model=SimpleNamespace(model=state, fp16=False), args=SimpleNamespace(quantize=None),
                                             device=SimpleNamespace(type=device_type, index=None))
    active = [BackendModel(fail_on=2)]
    monkeypatch.setattr(experiments, "configure_local_runtime", lambda _: None)
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=lambda _: active[0]))
    with pytest.raises(RuntimeError, match="interruption"):
        experiments.export_predictions(weights, "genuine-process", root=root, expected_images=2)
    state = experiments._read(root / "Dataset/inference-followup/genuine-process/validation.json")
    assert state["precision_validation"]["checked"] is True
    active[0] = BackendModel(device_type="cuda")
    with pytest.raises(ValueError, match="requested device"):
        experiments.export_predictions(weights, "genuine-process", root=root, expected_images=2, resume=True)


def test_preregistration_validates_original_hashes_not_only_plan_linkage(dataset):
    root, weights = dataset
    directory = root / "Dataset/inference-followup"
    directory.mkdir()
    plan = {"schema_version": "roadguard-inference-followup-plan-v1", "budget": {"candidate_count": 8},
            "common": {"threshold_grid": list(balanced.THRESHOLDS)},
            "inputs": {"fixture_weight": {"path": "Dataset/best.pt", "sha256": sha256_file(weights)}}}
    write_json(directory / "plan.json", plan)
    write_json(directory / "protocol-clarifications.json", {"schema_version": "roadguard-inference-followup-clarifications-v1",
               "base_plan_sha256": sha256_file(directory / "plan.json")})
    hashes = experiments._protocol(root)
    assert hashes["plan.json"] == sha256_file(directory / "plan.json")
    weights.write_bytes(b"changed but locally consistent replacement model")
    with pytest.raises(ValueError, match="original input hash"):
        experiments._protocol(root)


def test_geometry_helpers_reject_invalid_classes_scores_and_nonfinite_boxes():
    for prediction in (obj(8), obj(score=float("nan")), obj(box=(-1, 0, 10, 10)), obj(box=(0, 0, 10, float("inf")))):
        with pytest.raises(ValueError):
            experiments.class_aware_nms([prediction])
        with pytest.raises(ValueError):
            experiments.paired_score_fusion([[prediction], []])
