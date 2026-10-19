"""The demo adapter's reproducible inputs and provenance, without image inference."""

import pytest

from roadguard.schemas import Detection
from roadguard.schemas.common import LABELS_BY_ID
from roadguard.vision import DemoDetector, DemoScenarioNotFound, SCENARIOS


EXPECTED_DETECTIONS = {
    "high_confidence": [(6, 0.96)],
    "low_confidence": [(6, 0.42)],
    "no_detection": [],
    "multiple_detections": [(0, 0.98), (7, 0.90)],
    "mixed_confidence": [(6, 0.96), (7, 0.42)],
    "threshold_boundary": [(6, 0.60)],
    "below_threshold": [(6, 0.5999)],
}


def test_scenario_catalog_is_complete_descriptive_and_read_only():
    assert set(SCENARIOS) == set(EXPECTED_DETECTIONS)
    assert all(description.startswith("Demo:") for description in SCENARIOS.values())
    with pytest.raises(TypeError):
        SCENARIOS["high_confidence"] = "Changed by a caller"


@pytest.mark.parametrize("scenario_id,expected", EXPECTED_DETECTIONS.items())
def test_scenarios_emit_exact_validated_detections_and_original_pixel_metadata(scenario_id, expected):
    detector = DemoDetector()
    detections = detector.detect(scenario_id)
    assert [(d.class_id, d.confidence) for d in detections] == expected
    assert detector.model_version == "demo-detector-v1"
    assert detector.is_demo is True
    assert (detector.image_width, detector.image_height) == (640, 480)
    for detection in detections:
        assert Detection.model_validate_json(detection.model_dump_json()) == detection
        assert detection.label == LABELS_BY_ID[detection.class_id]
        assert detection.is_demo is True
        assert detection.model_version == "demo-detector-v1"
        assert (detection.image_width, detection.image_height) == (640, 480)
        left, top, right, bottom = detection.bbox_xyxy
        assert 0 <= left < right <= 640
        assert 0 <= top < bottom <= 480
        assert right > 1 and bottom > 1  # Original pixels, not normalized YOLO coordinates.


@pytest.mark.parametrize("scenario_id", EXPECTED_DETECTIONS)
def test_repeated_calls_and_new_instances_are_stable_but_return_fresh_objects(scenario_id):
    detector = DemoDetector()
    first = detector.detect(scenario_id)
    second = detector.detect(scenario_id)
    other_instance = DemoDetector().detect(scenario_id)
    assert first == second == other_instance
    assert first is not second
    assert first is not other_instance
    for first_item, second_item in zip(first, second):
        assert first_item is not second_item


def test_detection_ids_are_unique_within_and_between_named_scenarios():
    detector = DemoDetector()
    identifiers = [d.detection_id for scenario in SCENARIOS for d in detector.detect(scenario)]
    assert len(identifiers) == len(set(identifiers))
    assert identifiers


def test_caller_mutation_does_not_change_future_results():
    detector = DemoDetector()
    first = detector.detect("multiple_detections")
    before = [d.model_dump(mode="json") for d in first]
    first[0].confidence = 0.01
    first[0].detection_id = "caller-replaced"
    first[0].bbox_xyxy = (0, 0, 0, 0)
    first.pop()
    fresh = detector.detect("multiple_detections")
    assert [d.model_dump(mode="json") for d in fresh] == before
    empty = detector.detect("no_detection")
    empty.append(fresh[0])
    assert detector.detect("no_detection") == []


@pytest.mark.parametrize("scenario_id", [
    "unknown-private-token", "", "HIGH_CONFIDENCE", " high_confidence ",
    None, 1, True, [], {},
])
def test_unsupported_scenarios_raise_generic_domain_error(scenario_id):
    with pytest.raises(DemoScenarioNotFound) as raised:
        DemoDetector().detect(scenario_id)
    assert isinstance(raised.value, ValueError)
    assert str(raised.value) == "The requested demo scenario is not available."


def test_boundary_and_selection_fixtures_expose_the_intended_rule_inputs():
    detector = DemoDetector()
    assert detector.detect("below_threshold")[0].confidence < 0.60
    assert detector.detect("threshold_boundary")[0].confidence == 0.60
    multiple = detector.detect("multiple_detections")
    assert multiple[0].confidence > multiple[1].confidence
    assert multiple[1].class_id == 7
    mixed = detector.detect("mixed_confidence")
    assert mixed[0].confidence >= 0.60 > mixed[1].confidence
