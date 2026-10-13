"""Image-type accounting, main-subject selection and raw-evidence preservation."""

import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.single_damage import metrics, partition, select, selection_key
from model.predict_single_damage import load_selection, run
from model.checkpointing import sha256_file, write_json
from roadguard.schemas import Detection
from roadguard.schemas.common import LABELS_BY_ID
from roadguard.vision.primary import PrimaryPolicy, suggest_primary


def detection(index="a", class_id=6, confidence=0.8, box=(10, 10, 30, 30)):
    return Detection(detection_id=index, class_id=class_id, label=LABELS_BY_ID[class_id], confidence=confidence,
                     bbox_xyxy=box, image_width=100, image_height=100, model_version="test", is_demo=False)


def row(truth, predictions):
    return {"truth": [{"class_id": d.class_id, "bbox_xyxy": list(d.bbox_xyxy)} for d in truth], "detections": predictions}


def test_area_rank_can_select_main_subject_over_tiny_higher_score():
    tiny = detection("tiny", confidence=0.9, box=(0, 0, 5, 5))
    main = detection("main", confidence=0.7, box=(30, 30, 80, 80))
    original = copy.deepcopy([tiny, main])
    chosen, _ = select([tiny, main], PrimaryPolicy("area_quarter", 0.2), False)
    assert chosen == main and chosen.confidence == 0.7
    assert [tiny, main] == original
    assert select([tiny, main], PrimaryPolicy("confidence", 0.2), False)[0] == tiny


def test_ambiguous_classes_or_separate_regions_not_hidden():
    first = detection()
    for rival in (detection("b", class_id=7), detection("b", box=(60, 60, 80, 80))):
        proposal = suggest_primary([first, rival], PrimaryPolicy("confidence", 0.2))
        assert proposal["status"] == "ambiguous" and proposal["detection_id"] is None
        assert proposal["competing_detection_ids"] == ["a", "b"]
        assert select([first, rival], PrimaryPolicy("confidence", 0.2), True)[0] is None
        chosen, warning = select([first, rival], PrimaryPolicy("confidence", 0.2), False)
        assert chosen == first and warning == proposal


def test_same_class_overlapping_boxes_not_counted_as_competing_subjects():
    proposal = suggest_primary([detection(), detection("b", box=(11, 11, 31, 31))], PrimaryPolicy("confidence", 0.2))
    assert proposal["status"] == "suggested" and proposal["detection_id"] == "a"


@pytest.mark.parametrize("detections", [[], [detection(confidence=0.19)]])
def test_no_forced_output_below_filter(detections):
    assert select(detections, PrimaryPolicy("area_quarter", 0.2), False)[0] is None
    assert suggest_primary(detections, PrimaryPolicy("area_quarter", 0.2))["status"] == "no_suggestion"


def test_boundary_threshold_is_inclusive_and_score_ties_keep_input_order():
    first, second = detection(confidence=0.2), detection("b", confidence=0.2)
    assert select([first, second], PrimaryPolicy("area_quarter", 0.2), False)[0] == first


def test_wrong_class_counts_as_false_positive_and_false_negative_and_negatives_count():
    records = [row([detection()], [detection()]), row([detection()], [detection(class_id=7)]),
               row([detection()], []), row([], [detection()]), row([], [])]
    result = metrics(records, PrimaryPolicy("confidence", 0.2))
    assert (result["tp"], result["fp"], result["fn"]) == (1, 2, 2)
    assert result["precision"] == result["recall"] == 1 / 3
    assert result["presence_precision"] == result["presence_recall"] == 2 / 3
    assert result["negative_false_positive_rate"] == 0.5


def test_correct_type_at_wrong_location_does_not_pass_localization():
    result = metrics([row([detection()], [detection(box=(70, 70, 90, 90))])], PrimaryPolicy("confidence", 0.2))
    assert result["precision"] == result["recall"] == 1
    assert all(m["tp"] == 0 for m in result["typed_localization"].values())


def test_multi_object_ground_truth_cannot_silently_be_reduced():
    with pytest.raises(ValueError, match="Multi-object"):
        metrics([row([detection(), detection("b")], [detection()])], PrimaryPolicy("confidence", 0.2))


def test_confirmation_cannot_change_selection_ranking():
    item = {"calibration": {"precision": .6, "recall": .7, "macro_f1": .5}}
    assert selection_key(item) == selection_key({**item, "confirmation": {"precision": 1, "recall": 1}})
    assert partition("group-1") == partition("group-1")
    assert {partition(f"g{i}") for i in range(100)} == {"calibration", "confirmation"}


@pytest.mark.parametrize("threshold", [True, 0, -0.1, 1.1, float("nan"), float("inf"), "0.2"])
def test_invalid_threshold_rejected(threshold):
    with pytest.raises(ValueError):
        PrimaryPolicy("confidence", threshold)


def test_invalid_strategy_and_inconsistent_evidence_rejected():
    with pytest.raises(ValueError):
        PrimaryPolicy("largest", 0.2)
    for records in ([detection(), detection()], [detection(), detection("b").model_copy(update={"image_width": 101})]):
        with pytest.raises(ValueError):
            suggest_primary(records, PrimaryPolicy("confidence", 0.2))


@pytest.fixture
def selected_experiment(tmp_path):
    root = Path(__file__).resolve().parents[2]
    settings = {"recipe": "standard832", "strategy": "area_quarter", "threshold": 0.2, "gate": False}
    write_json(tmp_path / "selection.json", settings)
    write_json(tmp_path / "plan.json", {"source_sha256": {
        "single_damage.py": sha256_file(root / "SystemCode/model/single_damage.py"),
        "primary.py": sha256_file(root / "SystemCode/backend/roadguard/vision/primary.py")}})
    report = {"schema_version": "roadguard-single-damage-comparison-v1", "selected": settings,
              "plan_sha256": sha256_file(tmp_path / "plan.json"), "selection_sha256": sha256_file(tmp_path / "selection.json")}
    write_json(tmp_path / "comparison.json", report)
    write_json(tmp_path / "status.json", {"status": "complete", "comparison_sha256": sha256_file(tmp_path / "comparison.json")})
    return tmp_path


def test_runner_uses_verified_selected_policy(selected_experiment):
    settings, _, policy = load_selection(selected_experiment)
    assert policy.strategy == "area_quarter" and policy.threshold == 0.2 and settings["gate"] is False


@pytest.mark.parametrize("name", ["comparison.json", "plan.json", "selection.json"])
def test_runner_rejects_changed_evidence(selected_experiment, name):
    path = selected_experiment / name
    value = json.loads(path.read_text())
    value["unexpected_change"] = True
    write_json(path, value)
    with pytest.raises(ValueError):
        load_selection(selected_experiment)


def test_runner_refuses_output_outside_dataset_before_model_loading(tmp_path):
    with pytest.raises(ValueError, match="inside ignored Dataset"):
        run([], tmp_path / "missing", tmp_path / "missing.json", tmp_path / "output")
    assert not (tmp_path / "output").exists()
