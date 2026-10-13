"""Offline sweeps and injected export contracts; no GPU/torch import needed."""

import json
from pathlib import Path
import random
import sys
from types import SimpleNamespace

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model import balanced_metrics as balanced


def obj(class_id=0, confidence=None, box=(0, 0, 10, 10)):
    value = {"class_id": class_id, "bbox_xyxy": list(box)}
    if confidence is not None:
        value["confidence"] = confidence
    return value


def fixture_dataset(root):
    dataset = root / "Dataset"
    prepared = dataset / "prepared"
    for kind in ("images", "labels"):
        for split in ("train", "val", "test"):
            (prepared / kind / split).mkdir(parents=True)
    image = prepared / "images/val/Czech_01.jpg"
    Image.new("RGB", (10, 10), "gray").save(image)
    label = prepared / "labels/val/Czech_01.txt"
    label.write_text("0 0.5 0.5 1 1\n", encoding="utf-8")
    row = {"sample_id": "Czech_01", "split": "val", "assigned_split": "val", "is_mirror": False,
           "exclusion_reason": None, "country": "Czech", "width": 10, "height": 10, "exif_orientation": 1,
           "boxes": [[0, 0.5, 0.5, 1, 1]], "image_sha256": balanced.sha256_file(image), "label_sha256": balanced.sha256_file(label)}
    # No image/label files exist for these records: reading them would fail.
    others = [{"sample_id": "NEVER_READ_TEST", "split": "test"}, {"sample_id": "NEVER_READ_TRAIN", "split": "train"}]
    manifest = prepared / "manifest.jsonl"
    manifest.write_text("\n".join(json.dumps(record) for record in [row, *others]), encoding="utf-8")
    (prepared / "data.yaml").write_text(f'path: {json.dumps(prepared.as_posix())}\ntrain: images/train\nval: images/val\ntest: images/test\nnc: 8\nnames: {json.dumps(balanced.source_names())}\n', encoding="utf-8")
    weights = dataset / "best.pt"
    weights.write_bytes(b"FAKE UNIT TEST WEIGHTS")
    return dataset, manifest, row, weights


class FakeModel:
    names = dict(enumerate(balanced.source_names()))

    def __init__(self, predictions=None):
        self.predictions = [obj(confidence=0.8), obj(1, 0.2)] if predictions is None else predictions

    def predict(self, source, **settings):
        assert source.mode == "RGB" and source.size == (10, 10)
        assert settings["conf"] == 0.001 and settings["iou"] == 0.7 and settings["max_det"] == 100
        assert settings["batch"] == 1 and settings["quantize"] is None and "half" not in settings
        tensor = lambda values: SimpleNamespace(tolist=lambda: values)
        return [SimpleNamespace(orig_shape=(10, 10), boxes=SimpleNamespace(
            xyxy=tensor([p["bbox_xyxy"] for p in self.predictions]), cls=tensor([p["class_id"] for p in self.predictions]),
            conf=tensor([p["confidence"] for p in self.predictions])))]


def fake_export(tmp_path, monkeypatch, predictions=None):
    _, _, _, weights = fixture_dataset(tmp_path)
    monkeypatch.setattr(balanced, "configure_local_runtime", lambda _: pytest.fail("Fake export must not import torch or GPU runtime"))
    return balanced.export_predictions(weights, "fake-export", root=tmp_path, imgsz=832, expected_images=1,
                                       model_factory=lambda _: FakeModel(predictions))


def rewrite_raw_export(path, records):
    """Re-sign fixtures so tests reach schema validation beyond digest protection."""
    raw_path = path.parent / "predictions.jsonl"
    raw_path.write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
    metadata = json.loads(path.read_text())
    metadata["predictions_sha256"] = balanced.sha256_file(raw_path)
    metadata["predictions"] = sum(len(row["predictions"]) for row in records)
    path.write_text(json.dumps(metadata), encoding="utf-8")
    status = json.loads((path.parent / "status.json").read_text())
    status["export_sha256"] = balanced.sha256_file(path)
    (path.parent / "status.json").write_text(json.dumps(status), encoding="utf-8")


def test_prefix_curves_equal_brute_force_rematching_with_duplicates_confusions_and_ties():
    rng = random.Random(42)
    rows = []
    for index in range(12):
        truth = [obj(i % 8, box=(i * 12, 0, i * 12 + 10, 10)) for i in range(8)]
        predictions = [obj(rng.randrange(8), rng.choice([0.005, 0.1, 0.25, 0.5, 0.8]),
                           box=(i * 12, 0, i * 12 + rng.choice([4, 8, 10]), 10)) for i in range(8) for _ in range(2)]
        rows.append({"sample_id": str(index), "truth": truth, "predictions": predictions})
    for iou in (0.5, 0.3):
        curves = balanced.sweep_metrics(rows, iou=iou)
        for point in curves:
            expected = [{"tp": 0, "fp": 0, "fn": 0} for _ in range(8)]
            for row in rows:
                predictions = [p for p in row["predictions"] if p["confidence"] >= point["threshold"]]
                matches = balanced.match_detections(row["truth"], predictions, iou)
                for match in matches["matches"]:
                    expected[predictions[match["prediction_index"]]["class_id"]]["tp"] += 1
                for error in matches["false_positives"]:
                    expected[predictions[error["prediction_index"]]["class_id"]]["fp"] += 1
                for error in matches["false_negatives"]:
                    expected[row["truth"][error["truth_index"]]["class_id"]]["fn"] += 1
            assert [{key: row[key] for key in ("tp", "fp", "fn")} for row in point["per_class"]] == expected


def test_sweep_matches_once_per_image_not_per_confidence_threshold(monkeypatch):
    rows = [{"sample_id": str(i), "truth": [obj()], "predictions": [obj(confidence=(j + 1) / 100) for j in range(100)]}
            for i in range(20)]
    original = balanced.match_detections
    calls = []

    def tracked(*args):
        calls.append(args[2])
        return original(*args)

    monkeypatch.setattr(balanced, "match_detections", tracked)
    for iou in (0.5, 0.3):
        for mode in ("eight_class", "class_agnostic", "four_family_diagnostic"):
            balanced.sweep_metrics(rows, iou=iou, mode=mode)
    assert len(calls) == 20 * 2 * 3


def test_loose_iou_and_family_diagnostics_never_replace_eight_types():
    row = {"sample_id": "x", "truth": [obj()], "predictions": [obj(1, 0.8, (0, 0, 4, 10))]}
    primary = balanced.sweep_metrics([row], thresholds=[0.1])[0]
    loose = balanced.sweep_metrics([row], iou=0.3, thresholds=[0.1])[0]
    localized = balanced.sweep_metrics([row], iou=0.3, mode="class_agnostic", thresholds=[0.1])[0]
    family = balanced.sweep_metrics([row], iou=0.3, mode="four_family_diagnostic", thresholds=[0.1])[0]
    assert primary["micro"]["tp"] == loose["micro"]["tp"] == 0
    assert localized["micro"]["tp"] == family["micro"]["tp"] == 1
    assert localized["wrong_eight_type_among_localized"] == 1
    assert localized["localization_matched_subtype_matrix"]["counts"][1][0] == 1
    with pytest.raises(ValueError, match="primary"):
        balanced.choose_threshold([loose])
    with pytest.raises(ValueError, match="primary"):
        balanced.choose_threshold([family])


def test_global_selection_balances_precision_and_recall_then_macro_f1_and_recall():
    def point(threshold, precision, recall, macro):
        return {"mode": "eight_class", "iou": 0.5, "threshold": threshold,
                "micro": {"precision": precision, "recall": recall}, "macro": {"f1": macro}}
    high_precision_only = point(0.8, 0.95, 0.4, 0.8)
    balanced_point = point(0.3, 0.72, 0.72, 0.6)
    macro_winner = point(0.25, 0.72, 0.8, 0.7)
    assert balanced.choose_threshold([high_precision_only, balanced_point, macro_winner]) is macro_winner
    recall_winner = point(0.2, 0.72, 0.85, 0.7)
    assert balanced.choose_threshold([macro_winner, recall_winner]) is recall_winner


def test_empty_predictions_keep_null_per_class_and_zero_macro():
    curve = balanced.sweep_metrics([{"sample_id": "x", "truth": [obj()], "predictions": []}])
    assert curve[0]["micro"]["precision"] is None and curve[0]["micro"]["recall"] == 0
    assert curve[0]["macro"] == {"precision": 0, "recall": 0, "f1": 0}
    assert curve[0]["per_class"][7]["recall"] is None
    assert not curve[0]["target_met_micro"]


@pytest.mark.parametrize("thresholds", [[], [0.1, 0.1], [0.2, 0.1], [0.0001], [1.1], [float("nan")], [True]])
def test_invalid_thresholds_rejected(thresholds):
    with pytest.raises(ValueError, match="Thresholds"):
        balanced.sweep_metrics([], thresholds=thresholds)


def test_export_and_offline_analysis_no_test_access_or_runtime_import(tmp_path, monkeypatch):
    path = fake_export(tmp_path, monkeypatch)
    report_path = balanced.analyze_export(path, root=tmp_path, expected_images=1)
    metadata = json.loads(path.read_text())
    report = json.loads(report_path.read_text())
    assert metadata["images"] == 1 and metadata["inference"]["imgsz"] == 832
    assert metadata["execution"] == report["execution"] == "injected_test_model"
    assert report["thresholds"] == list(balanced.THRESHOLDS)
    assert report["primary_iou"] == 0.5 and report["secondary_iou"] == 0.3
    assert report["selected_primary"]["micro"]["tp"] == 1
    assert report["selected_primary"]["micro"]["fp"] == 0
    assert report["selected_primary"]["micro"]["recall"] == 1
    assert report["selected_threshold"] == 0.25  # First ascending exact tie above the .2 wrong-class prediction.
    assert set(metadata["source_file_sha256"]) == {"balanced_metrics.py", "analyze_errors.py", "evaluate.py", "train.py", "checkpointing.py"}
    assert len(report["selected_primary"]["per_class"]) == 8
    assert not report["selected_all_eight_classes_meet_target"]
    assert json.loads((report_path.parent / "status.json").read_text())["status"] == "complete"
    with pytest.raises(ValueError, match="already exists"):
        balanced.analyze_export(path, root=tmp_path, expected_images=1)
    with pytest.raises(ValueError, match="already exists"):
        balanced.export_predictions(tmp_path / "Dataset/best.pt", "fake-export", root=tmp_path, expected_images=1, model_factory=lambda _: FakeModel())


@pytest.mark.parametrize("kind", ["weights", "manifest", "predictions", "metadata"])
def test_changed_input_digests_reject_analysis(tmp_path, monkeypatch, kind):
    path = fake_export(tmp_path, monkeypatch)
    paths = {"weights": tmp_path / "Dataset/best.pt", "manifest": tmp_path / "Dataset/prepared/manifest.jsonl",
             "predictions": path.parent / "predictions.jsonl", "metadata": path}
    with paths[kind].open("ab") as stream:
        stream.write(b"\n")
    with pytest.raises(ValueError, match="hash"):
        balanced.analyze_export(path, root=tmp_path, expected_images=1)


@pytest.mark.parametrize("sample_ids", [["Czech_01", "Czech_01"], ["NEVER_READ_TEST"], []])
def test_duplicate_test_or_missing_raw_records_rejected(tmp_path, monkeypatch, sample_ids):
    path = fake_export(tmp_path, monkeypatch)
    rewrite_raw_export(path, [{"sample_id": sample_id, "predictions": []} for sample_id in sample_ids])
    with pytest.raises(ValueError, match="sample ID|every frozen"):
        balanced.analyze_export(path, root=tmp_path, expected_images=1)


@pytest.mark.parametrize("prediction", [obj(8, 0.5), obj(0, 0.0001), obj(0, 0.5, (-1, 0, 10, 10)), obj(0, float("nan"))])
def test_invalid_raw_prediction_rejected(tmp_path, monkeypatch, prediction):
    path = fake_export(tmp_path, monkeypatch)
    rewrite_raw_export(path, [{"sample_id": "Czech_01", "predictions": [prediction]}])
    with pytest.raises(ValueError):
        balanced.analyze_export(path, root=tmp_path, expected_images=1)


@pytest.mark.parametrize("run_name", ["../outside", "..", "x/y", ""])
def test_unsafe_output_name_rejected_before_loading(tmp_path, run_name):
    _, _, _, weights = fixture_dataset(tmp_path)
    with pytest.raises(ValueError, match="Output name"):
        balanced.export_predictions(weights, run_name, root=tmp_path, model_factory=lambda _: pytest.fail("Must not load"))


def test_export_failure_is_explicit_and_preserves_partial_directory(tmp_path):
    _, _, _, weights = fixture_dataset(tmp_path)
    model = SimpleNamespace(names=FakeModel.names, predict=lambda **kwargs: [SimpleNamespace(orig_shape=(10, 10), boxes=None)])
    with pytest.raises(ValueError, match="detection result"):
        balanced.export_predictions(weights, "failed", root=tmp_path, expected_images=1, model_factory=lambda _: model)
    directory = tmp_path / "Dataset/balanced-metrics/failed"
    assert json.loads((directory / "status.json").read_text())["status"] == "failed"
    assert not (directory / "export.json").exists()


def test_wrong_model_names_and_all_1921_required(tmp_path):
    _, _, _, weights = fixture_dataset(tmp_path)
    with pytest.raises(ValueError, match="Expected all 1921"):
        balanced.export_predictions(weights, "missing", root=tmp_path, model_factory=lambda _: FakeModel())
    with pytest.raises(ValueError, match="model.names"):
        balanced.export_predictions(weights, "wrongnames", root=tmp_path, expected_images=1,
                                    model_factory=lambda _: SimpleNamespace(names=["COCO"] * 8))


def test_duplicate_json_fields_are_rejected():
    with pytest.raises(ValueError, match="Duplicate JSON"):
        balanced._json('{"sample_id":"x", "sample_id":"y"}')


def test_offline_failure_does_not_publish_report(tmp_path, monkeypatch):
    path = fake_export(tmp_path, monkeypatch)

    def fail(*args, **kwargs):
        raise ValueError("Deliberate matcher failure")

    monkeypatch.setattr(balanced, "sweep_metrics", fail)
    with pytest.raises(ValueError, match="matcher failure"):
        balanced.analyze_export(path, root=tmp_path, expected_images=1)
    directory = path.parent / "analyses/sweep"
    assert json.loads((directory / "status.json").read_text())["status"] == "failed"
    assert not (directory / "report.json").exists()


def test_external_weights_and_export_paths_rejected(tmp_path):
    fixture_dataset(tmp_path)
    external = tmp_path / "outside.pt"
    external.write_bytes(b"unit test")
    with pytest.raises(ValueError, match="storage boundary"):
        balanced.export_predictions(external, "outside", root=tmp_path, model_factory=lambda _: pytest.fail("Must not load"))
    with pytest.raises(ValueError, match="storage boundary"):
        balanced.analyze_export(external, root=tmp_path)


def test_exact_objective_tie_keeps_first_ascending_grid_value():
    row = {"sample_id": "x", "truth": [obj()], "predictions": [obj(confidence=0.8)]}
    curve = balanced.sweep_metrics([row])
    assert balanced.choose_threshold(curve)["threshold"] == 0.001


def test_redirected_dataset_is_rejected_before_runtime(tmp_path, monkeypatch):
    original = Path.resolve
    expected = tmp_path / "Dataset"

    def redirected(path, *args, **kwargs):
        return tmp_path / "SystemCode" if path == expected else original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", redirected)
    with pytest.raises(ValueError, match="redirected"):
        balanced.export_predictions(expected / "best.pt", "bad-link", root=tmp_path, model_factory=lambda _: pytest.fail("Must not load"))
