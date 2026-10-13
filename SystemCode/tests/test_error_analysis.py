"""Operational matcher and validation-only analysis, without GPU/torch imports."""

import json
from pathlib import Path
import sys
from types import SimpleNamespace

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model import analyze_errors as errors


def obj(class_id=0, box=(0, 0, 10, 10), confidence=None):
    result = {"class_id": class_id, "bbox_xyxy": list(box)}
    if confidence is not None:
        result["confidence"] = confidence
    return result


def test_confidence_order_one_to_one_and_duplicate():
    result = errors.match_detections([obj()], [obj(confidence=0.4), obj(confidence=0.9)])
    assert result["matches"] == [{"prediction_index": 1, "truth_index": 0, "iou": 1}]
    assert result["false_positives"][0]["category"] == "duplicate"
    assert result["false_negatives"] == []


def test_confidence_ties_and_iou_threshold_are_stable():
    # Half-overlapping box has IoU=0.5 and qualifies inclusively.
    result = errors.match_detections([obj()], [obj(box=(0, 0, 5, 10), confidence=0.7), obj(confidence=0.7)])
    assert result["matches"][0]["prediction_index"] == 0
    assert result["matches"][0]["iou"] == 0.5
    assert result["false_positives"][0]["category"] == "duplicate"


def test_class_confusion_is_fp_and_fn_not_tp():
    result = errors.match_detections([obj(2)], [obj(3, confidence=0.9)])
    assert not result["matches"]
    assert result["false_positives"][0]["category"] == "confusion"
    assert result["false_negatives"][0]["category"] == "confusion"


def test_localization_is_fp_and_fn_below_matching_iou():
    result = errors.match_detections([obj()], [obj(box=(0, 0, 3, 10), confidence=0.9)])
    assert not result["matches"]
    assert result["false_positives"][0]["category"] == "localization"
    assert result["false_negatives"][0]["category"] == "localization"


def test_background_miss_and_empty_cases():
    assert errors.match_detections([], []) == {"matches": [], "false_positives": [], "false_negatives": []}
    assert errors.match_detections([], [obj(confidence=0.9)])["false_positives"][0]["category"] == "background"
    assert errors.match_detections([obj()], [])["false_negatives"][0]["category"] == "missed"
    result = errors.match_detections([obj()], [obj(box=(20, 20, 30, 30), confidence=0.9)])
    assert result["false_positives"][0]["category"] == "background"
    assert result["false_negatives"][0]["category"] == "missed"


def test_two_predictions_cannot_claim_one_truth_or_leave_available_truth_unmatched():
    truth = [obj(), obj(box=(2, 0, 12, 10))]
    predictions = [obj(confidence=0.9), obj(confidence=0.8)]
    result = errors.match_detections(truth, predictions)
    assert [match["truth_index"] for match in result["matches"]] == [0, 1]
    assert not result["false_positives"] and not result["false_negatives"]


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
           "boxes": [[0, 0.5, 0.5, 1, 1]], "image_sha256": errors.sha256_file(image), "label_sha256": errors.sha256_file(label)}
    # These metadata rows have no files. A val-only reader must skip them before
    # attempting to access paths, digests, labels or image content.
    others = [{"sample_id": "MUST_NOT_OPEN_TEST", "split": "test"}, {"sample_id": "MUST_NOT_OPEN_TRAIN", "split": "train"}]
    manifest = prepared / "manifest.jsonl"
    manifest.write_text("\n".join(json.dumps(record) for record in [row, *others]), encoding="utf-8")
    (prepared / "data.yaml").write_text(f'path: {json.dumps(prepared.as_posix())}\ntrain: images/train\nval: images/val\ntest: images/test\nnc: 8\nnames: {json.dumps(errors.source_names())}\n', encoding="utf-8")
    weights = dataset / "best.pt"
    weights.write_bytes(b"FAKE UNIT TEST WEIGHTS")
    return dataset, manifest, row, weights


def test_manifest_reads_val_only_and_checks_all_hashes(tmp_path, monkeypatch):
    dataset, manifest, row, _ = fixture_dataset(tmp_path)
    original = errors.sha256_file
    touched = []

    def checked(path):
        touched.append(path)
        assert "test" not in path.parts and "train" not in path.parts
        return original(path)

    monkeypatch.setattr(errors, "sha256_file", checked)
    assert len(errors.validation_records(manifest, dataset, 1)) == 1
    assert len(touched) == 2
    (dataset / "prepared/labels/val/Czech_01.txt").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="digest changed"):
        errors.validation_records(manifest, dataset, 1)


@pytest.mark.parametrize("change", [{"is_mirror": True}, {"sample_id": "xmirror_Czech_01"}, {"sample_id": "../test/escape"}, {"assigned_split": "test"}])
def test_manifest_rejects_mirrors_and_path_escape(tmp_path, change):
    dataset, manifest, row, _ = fixture_dataset(tmp_path)
    row.update(change)
    manifest.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="original"):
        errors.validation_records(manifest, dataset, 1)


def test_requires_every_frozen_validation_image(tmp_path):
    dataset, manifest, _, _ = fixture_dataset(tmp_path)
    with pytest.raises(ValueError, match="Expected all 1921"):
        errors.validation_records(manifest, dataset)


def test_sample_selection_covers_categories_before_majority_classes():
    rows = []
    for index in range(100):
        truth = [obj(index % 8)]
        prediction = [obj(index % 8, confidence=0.9)]
        rows.append({"sample_id": f"val_{index}", "country": str(index % 5), "truth": truth, "predictions": prediction,
                     "false_positives": [], "false_negatives": [{"truth_index": 0, "category": "missed"}]})
    for index, category in enumerate(("background", "confusion", "localization", "duplicate")):
        rows.append({"sample_id": f"rare_{index}", "country": "India", "truth": [], "predictions": [obj(confidence=0.9)],
                     "false_positives": [{"prediction_index": 0, "category": category}], "false_negatives": []})
    selected = errors.select_samples(rows)
    assert len(selected) == len({row["sample_id"] for row in selected}) == 40
    assert {f"rare_{index}" for index in range(4)} <= {row["sample_id"] for row in selected}
    assert errors.select_samples(list(reversed(rows))) == selected


class FakeModel:
    names = dict(enumerate(errors.source_names()))

    def predict(self, source, **settings):
        assert isinstance(source, Image.Image) and source.mode == "RGB"
        assert settings["conf"] == 0.25 and settings["batch"] == 1 and settings["device"] == "cpu"
        assert not settings["save"] and not settings["half"]
        tensor = lambda values: SimpleNamespace(tolist=lambda: values)
        return [SimpleNamespace(orig_shape=(10, 10), boxes=SimpleNamespace(xyxy=tensor([[0, 0, 10, 10]]), cls=tensor([1]), conf=tensor([0.9])))]


def test_fake_integration_reports_actual_zero_based_confusion_and_artifacts(tmp_path):
    _, _, _, weights = fixture_dataset(tmp_path)
    path = errors.analyze(weights, "fake-run", root=tmp_path, expected_images=1, model_factory=lambda _: FakeModel())
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["images"] == 1 and report["execution"] == "injected_test_model"
    assert report["totals"] == {"tp": 0, "fp": 1, "fn": 1}
    assert report["per_class"][0]["fn"] == 1 and report["per_class"][1]["fp"] == 1
    assert report["diagnostic_categories"] == {"fp": {"confusion": 1}, "fn": {"confusion": 1}}
    for artifact in report["artifacts"]:
        assert (path.parent / artifact).is_file()
    with Image.open(path.parent / "contact-sheet-01.jpg") as sheet:
        assert sheet.size == (1800, 1200)
    assert json.loads((path.parent / "status.json").read_text())["status"] == "complete"
    with pytest.raises(ValueError, match="already exists"):
        errors.analyze(weights, "fake-run", root=tmp_path, expected_images=1, model_factory=lambda _: FakeModel())


@pytest.mark.parametrize("name", ["../outside", "..", "x/y", ""])
def test_output_path_escape_rejected(tmp_path, name):
    _, _, _, weights = fixture_dataset(tmp_path)
    with pytest.raises(ValueError, match="run_name"):
        errors.analyze(weights, name, root=tmp_path, model_factory=lambda _: FakeModel())


def test_wrong_model_class_names_fail_before_output_or_prediction(tmp_path):
    _, _, _, weights = fixture_dataset(tmp_path)
    with pytest.raises(ValueError, match="model.names"):
        errors.analyze(weights, "bad-names", root=tmp_path, expected_images=1,
                       model_factory=lambda _: SimpleNamespace(names={i: "COCO" for i in range(8)}))
    assert not (tmp_path / "Dataset/error-analysis/bad-names").exists()


@pytest.mark.parametrize("result,message", [(SimpleNamespace(orig_shape=(11, 10), boxes=None), "shape"),
                                             (SimpleNamespace(orig_shape=(10, 10), boxes=None), "missing detection boxes")])
def test_inference_failure_does_not_publish_success(tmp_path, result, message):
    _, _, _, weights = fixture_dataset(tmp_path)
    model = SimpleNamespace(names=FakeModel.names, predict=lambda **kwargs: [result])
    with pytest.raises(ValueError, match=message):
        errors.analyze(weights, "failed", root=tmp_path, expected_images=1, model_factory=lambda _: model)
    directory = tmp_path / "Dataset/error-analysis/failed"
    assert not (directory / "report.json").exists()
    assert json.loads((directory / "status.json").read_text())["status"] == "failed"


def test_empty_detection_tensors_are_a_valid_miss_and_never_import_gpu_runtime(tmp_path, monkeypatch):
    _, _, _, weights = fixture_dataset(tmp_path)
    monkeypatch.setattr(errors, "configure_local_runtime", lambda _: pytest.fail("Fake integration must not import vision runtime"))
    empty = SimpleNamespace(tolist=lambda: [])
    model = SimpleNamespace(names=FakeModel.names, predict=lambda **kwargs: [SimpleNamespace(orig_shape=(10, 10),
                            boxes=SimpleNamespace(xyxy=empty, cls=empty, conf=empty))])
    path = errors.analyze(weights, "empty", root=tmp_path, expected_images=1, model_factory=lambda _: model)
    report = json.loads(path.read_text())
    assert report["totals"] == {"tp": 0, "fp": 0, "fn": 1}
    assert report["per_class"][0]["precision"] is None and report["per_class"][0]["recall"] == 0
    assert report["per_class"][7]["recall"] is None


def test_outside_dataset_weights_fail_before_runtime(tmp_path):
    fixture_dataset(tmp_path)
    outside = tmp_path / "outside.pt"
    outside.write_bytes(b"unit test")
    with pytest.raises(ValueError, match="under Dataset"):
        errors.analyze(outside, "outside", root=tmp_path, model_factory=lambda _: pytest.fail("Must not load outside weights"))
