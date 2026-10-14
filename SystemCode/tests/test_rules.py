"""Demo assumptions and gate/selection boundaries, without HTTP or persistence."""

from copy import deepcopy
from itertools import permutations
import json
from pathlib import Path

from pydantic import ValidationError
import pytest

from roadguard.config import ConfigurationError, REPOSITORY_ROOT
from roadguard.errors import AppError
from roadguard.rules import RulePolicy, RuleService, load_rule_policy
from roadguard.schemas import Detection, RuleAssessment, RuleCandidate
from roadguard.schemas.common import LABELS_BY_ID


POLICY_PATH = REPOSITORY_ROOT / "SystemCode/config/demo_rules.example.json"


def detection(class_id=0, confidence=0.90, detection_id="detection-01", **overrides):
    data = {
        "detection_id": detection_id, "class_id": class_id, "label": LABELS_BY_ID[class_id],
        "confidence": confidence, "bbox_xyxy": (10, 10, 50, 50),
        "image_width": 100, "image_height": 100, "model_version": "demo-detector-v1", "is_demo": True,
    }
    data.update(overrides)
    return Detection.model_validate(data)


@pytest.fixture
def source():
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def policy():
    return load_rule_policy(POLICY_PATH)


@pytest.fixture
def service(policy):
    return RuleService(policy)


@pytest.mark.parametrize("class_id,severity,priority,minutes", [
    (0, "low", "P3", 60), (1, "medium", "P2", 120),
    (2, "low", "P3", 60), (3, "medium", "P2", 120),
    (4, "medium", "P2", 120), (5, "high", "P1", 240),
    (6, "medium", "P2", 120), (7, "high", "P1", 240),
])
def test_eight_demo_labels_map_to_explicit_project_assumptions(service, class_id, severity, priority, minutes):
    result = service.evaluate([detection(class_id)])
    candidate = result.candidate
    assert result.status == "ready_for_task"
    assert candidate.damage_label == LABELS_BY_ID[class_id]
    assert (candidate.severity, candidate.priority, candidate.service_minutes) == (severity, priority, minutes)
    assert candidate.repair_recommendation == service.policy.rules[candidate.damage_label].recommendation
    assert result.rule_version == candidate.rule_version == "demo-rules-v2"
    assert result.is_demo is candidate.is_demo is True
    assert all(trace.is_demo and trace.rule_version == result.rule_version for trace in result.decision_trace)
    assert service.policy.rules[candidate.damage_label].reason in result.decision_trace[2].message
    assert result.decision_trace[0].code == "demo_assumptions"
    assert "not engineering measurements" in result.decision_trace[0].message
    assert "task_id" not in result.model_dump() and "due_at" not in candidate.model_dump()


@pytest.mark.parametrize("confidence,status", [
    (0, "pending_review"), (0.599999, "pending_review"),
    (0.60, "ready_for_task"), (0.600001, "ready_for_task"), (1, "ready_for_task"),
])
def test_confidence_threshold_boundary(service, confidence, status):
    result = service.evaluate([detection(confidence=confidence)])
    assert result.status == status
    if status == "pending_review":
        assert result.selected_detection_id is None and result.candidate is None
    else:
        assert result.candidate is not None


def test_no_detection_has_no_selection_or_candidate(service):
    result = service.evaluate([])
    assert result.status == "no_detection"
    assert result.detections == []
    assert result.selected_detection_id is None and result.candidate is None
    assert [trace.code for trace in result.decision_trace] == ["demo_assumptions", "no_detection"]


def test_any_uncertain_detection_blocks_mixed_batch_even_when_other_is_urgent(service):
    inputs = [detection(7, 0.99, "urgent"), detection(0, 0.59, "uncertain")]
    result = service.evaluate(inputs)
    assert result.status == "pending_review"
    assert result.selected_detection_id is None and result.candidate is None
    assert result.detections == inputs
    assert [trace.code for trace in result.decision_trace] == ["demo_assumptions", "confidence_review_required"]


def test_priority_takes_precedence_over_confidence(service):
    result = service.evaluate([detection(0, 1, "low"), detection(7, 0.6, "urgent")])
    assert result.selected_detection_id == "urgent"


def test_severity_takes_precedence_over_duration_when_priority_ties(source):
    source["rules"][LABELS_BY_ID[0]].update(priority="P1", severity="low", service_minutes=480)
    result = RuleService(RulePolicy.model_validate(source)).evaluate([
        detection(0, 1, "long-low"), detection(7, 0.6, "short-high"),
    ])
    assert result.selected_detection_id == "short-high"


def test_longest_known_duration_takes_precedence_over_confidence(source):
    source["rules"][LABELS_BY_ID[1]]["service_minutes"] = 60
    service = RuleService(RulePolicy.model_validate(source))
    result = service.evaluate([detection(1, 1, "short"), detection(6, 0.6, "long")])
    assert result.selected_detection_id == "long"


def test_unknown_duration_is_preserved_and_ranked_after_known(source):
    source["rules"][LABELS_BY_ID[1]]["service_minutes"] = None
    service = RuleService(RulePolicy.model_validate(source))
    alone = service.evaluate([detection(1)])
    assert alone.candidate.service_minutes is None
    result = service.evaluate([detection(1, 1, "unknown"), detection(3, 0.6, "known")])
    assert result.selected_detection_id == "known"


def test_confidence_breaks_equal_business_rule_tie(service):
    result = service.evaluate([detection(0, 0.61, "a"), detection(2, 0.9, "z")])
    assert result.selected_detection_id == "z"


def test_stable_id_breaks_complete_tie_for_all_input_permutations(service):
    inputs = [detection(0, 0.9, "c"), detection(2, 0.9, "a"), detection(0, 0.9, "b")]
    traces = []
    for ordered in permutations(inputs):
        result = service.evaluate(ordered)
        assert result.selected_detection_id == "a"
        assert [item.detection_id for item in result.detections] == [item.detection_id for item in ordered]
        traces.append([item.model_dump() for item in result.decision_trace])
    assert all(trace == traces[0] for trace in traces)


def test_unknown_duration_ties_still_use_confidence_then_id(source):
    for class_id in (0, 2):
        source["rules"][LABELS_BY_ID[class_id]]["service_minutes"] = None
    service = RuleService(RulePolicy.model_validate(source))
    assert service.evaluate([detection(0, .61, "a"), detection(2, .9, "z")]).selected_detection_id == "z"
    assert service.evaluate([detection(0, .9, "z"), detection(2, .9, "a")]).selected_detection_id == "a"


def test_corrected_label_uses_same_rule_engine(service):
    original = detection(0)
    initial = service.evaluate([original])
    corrected_data = original.model_dump()
    corrected_data.update(class_id=7, label=LABELS_BY_ID[7])
    corrected = service.evaluate([Detection.model_validate(corrected_data)])
    assert initial.candidate.priority == "P3"
    assert corrected.candidate.priority == "P1"
    assert corrected.candidate.service_minutes == 240
    assert corrected.rule_version == initial.rule_version


def test_configured_threshold_and_rule_values_are_not_hardcoded(source, tmp_path):
    source["rule_version"] = "demo-changed-rules-v2"
    source["confidence_threshold"] = 0.8
    source["rules"][LABELS_BY_ID[0]].update(
        priority="P1", severity="high", service_minutes=12.5,
        recommendation="Changed demo recommendation.", reason="Changed explicit demo assumption.",
    )
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    service = RuleService(load_rule_policy(path))
    assert service.evaluate([detection(confidence=.79)]).status == "pending_review"
    result = service.evaluate([detection(confidence=.8)])
    assert (result.candidate.priority, result.candidate.severity, result.candidate.service_minutes) == ("P1", "high", 12.5)
    assert result.candidate.repair_recommendation == "Changed demo recommendation."
    assert "Changed explicit demo assumption." in result.decision_trace[2].message
    assert result.rule_version == result.candidate.rule_version == "demo-changed-rules-v2"
    assert all(trace.rule_version == "demo-changed-rules-v2" for trace in result.decision_trace)


def test_policy_source_and_nested_rules_are_immutable(source):
    policy = RulePolicy.model_validate(source)
    source["confidence_threshold"] = 0
    source["rules"][LABELS_BY_ID[0]]["priority"] = "P1"
    assert policy.confidence_threshold == .6
    assert policy.rules[LABELS_BY_ID[0]].priority == "P3"
    with pytest.raises(ValidationError):
        policy.confidence_threshold = .1
    with pytest.raises(TypeError):
        policy.rules[LABELS_BY_ID[0]] = policy.rules[LABELS_BY_ID[1]]
    with pytest.raises(ValidationError):
        policy.rules[LABELS_BY_ID[0]].priority = "P1"
    service = RuleService(policy)
    with pytest.raises(AttributeError):
        service.policy = policy


def test_assessment_does_not_mutate_or_retain_caller_detections(service):
    original = detection()
    result = service.evaluate([original])
    assert result.detections[0] is not original
    original.confidence = .1
    assert result.detections[0].confidence == .9
    assert service.evaluate([original]).status == "pending_review"
    result.detections[0].confidence = .01
    assert service.evaluate([detection()]).status == "ready_for_task"


@pytest.mark.parametrize("mutation", [
    {"confidence": "secret-input"}, {"confidence": float("nan")},
    {"class_id": 7}, {"image_width": True}, {"bbox_xyxy": (0, 0, 999, 50)},
    {"is_demo": "true"},
])
def test_mutated_detector_objects_are_revalidated_without_echoing_input(service, mutation):
    item = detection()
    for key, value in mutation.items():
        setattr(item, key, value)
    with pytest.raises(AppError) as error:
        service.evaluate([item])
    assert error.value.code == "invalid_detections" and error.value.status_code == 422
    assert "secret-input" not in str(error.value)


@pytest.mark.parametrize("inputs", [
    [detection(detection_id="same"), detection(1, detection_id="same")],
    [detection(), detection(1, detection_id="different", image_width=101)],
    [detection(), detection(1, detection_id="different", image_height=101)],
    [{"class_id": 0}],
    None,
])
def test_invalid_detection_batches_rejected(service, inputs):
    with pytest.raises(AppError) as error:
        service.evaluate(inputs)
    assert error.value.code == "invalid_detections"


@pytest.mark.parametrize("key,value", [
    ("confidence_threshold", "0.6"), ("confidence_threshold", True),
    ("confidence_threshold", -0.1), ("confidence_threshold", 1.1),
    ("confidence_threshold", float("nan")), ("confidence_threshold", float("inf")),
    ("is_demo", False), ("is_demo", 1), ("is_demo", "true"),
    ("rule_version", " "), ("status", "validated"),
    ("selection_strategy", "highest_confidence"), ("unknown_field", "secret-input"),
])
def test_invalid_policy_root_fields_fail_safely(source, tmp_path, key, value):
    source[key] = value
    path = tmp_path / "secret-input.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ConfigurationError) as error:
        load_rule_policy(path)
    assert str(error.value) == "Demo rule policy could not be loaded or validated."
    assert "secret-input" not in str(error.value)
    assert str(path) not in str(error.value)


@pytest.mark.parametrize("key,value", [
    ("service_minutes", 0), ("service_minutes", -1), ("service_minutes", "20"),
    ("service_minutes", True), ("service_minutes", float("nan")),
    ("service_minutes", float("inf")), ("severity", "severe"), ("priority", "P0"),
    ("recommendation", " "), ("reason", ""), ("unknown_field", "secret-input"),
])
def test_invalid_policy_rule_fields_fail_safely(source, tmp_path, key, value):
    source["rules"][LABELS_BY_ID[0]][key] = value
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_rule_policy(path)


@pytest.mark.parametrize("mutation", ["missing_label", "extra_label", "missing_root", "missing_rule_field"])
def test_policy_requires_exact_label_set_and_complete_fields(source, tmp_path, mutation):
    if mutation == "missing_label":
        del source["rules"][LABELS_BY_ID[7]]
    elif mutation == "extra_label":
        source["rules"]["unknown_label"] = deepcopy(source["rules"][LABELS_BY_ID[0]])
    elif mutation == "missing_root":
        del source["is_demo"]
    else:
        del source["rules"][LABELS_BY_ID[0]]["service_minutes"]
    path = tmp_path / "incomplete.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_rule_policy(path)


@pytest.mark.parametrize("content", [
    b'{"rule_version":"a","rule_version":"b"}', b'{secret-input malformed}', b'[]', b'\xff',
    POLICY_PATH.read_bytes().replace(b'"confidence_threshold": 0.60', b'"confidence_threshold": 1e999'),
    POLICY_PATH.read_bytes().replace(b'"service_minutes": 60', b'"service_minutes": 1e999', 1),
    POLICY_PATH.read_bytes().replace(b'"severity": "low"', b'"severity": "low", "severity": "high"', 1),
])
def test_bad_json_and_encoding_rejected_without_path_or_content(tmp_path, content):
    path = tmp_path / "secret-input.json"
    path.write_bytes(content)
    with pytest.raises(ConfigurationError) as error:
        load_rule_policy(path)
    assert "secret-input" not in str(error.value)
    assert str(path) not in str(error.value)


def test_missing_policy_has_no_silent_fallback(tmp_path):
    with pytest.raises(ConfigurationError):
        load_rule_policy(tmp_path / "missing.json")


def test_unsafe_model_copy_policy_is_revalidated(source):
    policy = RulePolicy.model_validate(source)
    invalid = policy.model_copy(update={"confidence_threshold": "0.6"})
    with pytest.raises(ValidationError):
        RuleService(invalid)


@pytest.mark.parametrize("is_demo", [False, 1, "true"])
def test_result_contract_requires_strict_demo_true(service, is_demo):
    result = service.evaluate([detection()]).model_dump()
    result["is_demo"] = is_demo
    with pytest.raises(ValidationError):
        RuleAssessment.model_validate(result)
    candidate = service.evaluate([detection()]).candidate.model_dump()
    candidate["is_demo"] = is_demo
    with pytest.raises(ValidationError):
        RuleCandidate.model_validate(candidate)


@pytest.mark.parametrize("mutation", ["nonready_candidate", "wrong_selected", "wrong_candidate_label", "wrong_trace_version"])
def test_result_contract_rejects_inconsistent_linkage(service, mutation):
    data = service.evaluate([detection()]).model_dump()
    if mutation == "nonready_candidate":
        data["status"] = "pending_review"
    elif mutation == "wrong_selected":
        data["selected_detection_id"] = "missing"
    elif mutation == "wrong_candidate_label":
        data["candidate"]["damage_label"] = LABELS_BY_ID[7]
    else:
        data["decision_trace"][0]["rule_version"] = "wrong-version"
    with pytest.raises(ValidationError):
        RuleAssessment.model_validate(data)
