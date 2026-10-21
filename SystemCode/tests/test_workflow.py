"""Persisted demo workflow boundaries, transactions, audit and request retries."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import io
import sqlite3

from PIL import Image
from pydantic import ValidationError
import pytest

from roadguard.config import REPOSITORY_ROOT
from roadguard.database import Database, DatabaseStateError, read_revision
from roadguard.errors import AppError
from roadguard.geography import JurongScope
from roadguard.images import ImageStore
from roadguard.inspections import WorkflowService
from roadguard.rules import RulePolicy, RuleService, load_rule_policy
from roadguard.schemas.workflow import ReviewRequest, TaskPatch, UploadMetadata
from roadguard.vision import DemoDetector, SCENARIOS


@pytest.fixture
def service(tmp_path):
    database = Database(tmp_path / "roadguard.sqlite3")
    database.initialize()
    rules = RuleService(load_rule_policy(REPOSITORY_ROOT / "SystemCode/config/demo_rules.example.json"))
    return WorkflowService(database, rules, DemoDetector(), JurongScope(), ImageStore(tmp_path / "images"))


@pytest.fixture
def image(service):
    output = io.BytesIO()
    Image.new("RGB", (80, 60), "white").save(output, format="PNG")
    return service.images.prepare(output.getvalue())


def metadata(scenario="high_confidence", **changes):
    data = dict(mode="demo", scenario_id=scenario, latitude=1.3405, longitude=103.706, road_type="public_motor_road")
    data.update(changes)
    return UploadMetadata.model_validate(data)


def create(service, image, scenario="high_confidence", key="upload-1"):
    return service.create(metadata(scenario), image, key)


def review_request(inspection, action="confirm", **changes):
    data = dict(request_id="review-1", expected_version=inspection.record_version, action=action)
    if action != "dismiss":
        data["detection_id"] = inspection.detections[0].detection_id
    if action == "correct":
        data["damage_label"] = "pothole_deep"
    data.update(changes)
    return ReviewRequest.model_validate(data)


@pytest.mark.parametrize("scenario,status,changed", [
    ("high_confidence", "accepted", True), ("low_confidence", "pending_review", False),
    ("no_detection", "no_detection", False), ("multiple_detections", "accepted", True),
    ("mixed_confidence", "pending_review", False), ("threshold_boundary", "accepted", True),
    ("below_threshold", "pending_review", False),
])
def test_all_seven_upload_scenarios_persist_provenance_and_scaled_boxes(service, image, scenario, status, changed):
    result = create(service, image, scenario)
    record = result.inspection
    assert record.status == status
    assert result.planning_input_changed is changed and result.replayed is False
    assert result.input_revision == int(changed)
    assert (record.image_width, record.image_height, record.model_version) == (80, 60, "demo-detector-v1")
    assert record.is_demo and record.mode == "demo" and record.demo_scenario_id == scenario
    assert record.road_type_source == "user_declared"
    assert record.scope_version == service.scope.scope_version
    assert record.created_at == record.updated_at and record.record_version == 1
    assert service.get_inspection(record.inspection_id) == record
    assert service.images.path(record.inspection_id).read_bytes() == image.content
    for item in record.detections:
        assert item.image_width == 80 and item.image_height == 60 and item.is_demo
        assert 0 <= item.bbox_xyxy[0] < item.bbox_xyxy[2] <= 80
    if changed:
        assert result.task is not None and result.task.is_demo and result.task.due_at is None
        assert result.task.inspection_id == record.inspection_id
        assert result.task.task_id == record.task_id and result.task.record_version == 1
        assert result.task.history[0].actor_source == "system_demo_rules"
    else:
        assert result.task is None and record.task_id is None
    if scenario == "multiple_detections":
        assert result.task.damage_label == "pothole_deep"
    if scenario == "no_detection":
        assert record.detections == []


@pytest.mark.parametrize("action,expected_status,expected_revision", [
    ("confirm", "accepted", 1), ("correct", "accepted", 1), ("dismiss", "rejected", 0),
])
def test_review_records_declared_fact_keeps_raw_detection_and_uses_explicit_mapping(service, image, action, expected_status, expected_revision):
    original = create(service, image, "low_confidence").inspection
    request = review_request(original, action, note="Demo review note.")
    result = service.review(original.inspection_id, request)
    assert result.inspection.status == expected_status and result.input_revision == expected_revision
    assert result.inspection.record_version == 2
    assert result.inspection.detections == original.detections
    assert result.inspection.detections[0].confidence == .42
    history = result.inspection.review_history[0]
    assert history.action == action and history.note == "Demo review note."
    assert history.actor_source == "user_declared_unverified"
    if action == "correct":
        assert history.original_damage_label == "pothole"
        assert history.corrected_damage_label == result.task.damage_label == "pothole_deep"
        assert result.task.priority == "P1"
    elif action == "confirm":
        assert result.task.damage_label == "pothole" and result.task.priority == "P2"
    else:
        assert result.task is None


def test_review_selection_must_belong_to_inspection(service, image):
    original = create(service, image, "low_confidence").inspection
    with pytest.raises(AppError) as error:
        service.review(original.inspection_id, review_request(original, detection_id="foreign-detection"))
    assert error.value.code == "invalid_detection_selection"
    assert service.get_inspection(original.inspection_id).record_version == 1


def test_mixed_review_can_select_uncertain_detection_without_erasing_other_facts(service, image):
    original = create(service, image, "mixed_confidence").inspection
    result = service.review(original.inspection_id, review_request(original, detection_id=original.detections[1].detection_id))
    assert result.task.damage_label == "pothole_deep"
    assert result.inspection.detections == original.detections


def test_upload_replay_returns_current_resource_and_revision_without_duplicate_image(service, image):
    first = create(service, image, "low_confidence")
    reviewed = service.review(first.inspection.inspection_id, review_request(first.inspection))
    replay = create(service, image, "low_confidence")
    assert replay.replayed is True and replay.planning_input_changed is False
    assert replay.inspection == reviewed.inspection and replay.task == reviewed.task
    assert replay.input_revision == 1
    assert len(list(service.images.root.glob("*.png"))) == 1


def test_upload_key_reuse_with_changed_metadata_or_source_is_conflict(service, image):
    create(service, image)
    with pytest.raises(AppError) as error:
        service.create(metadata("low_confidence"), image, "upload-1")
    assert error.value.code == "idempotency_conflict"
    raw = io.BytesIO()
    Image.new("RGB", (80, 60), "red").save(raw, format="PNG")
    with pytest.raises(AppError) as error:
        service.create(metadata(), service.images.prepare(raw.getvalue()), "upload-1")
    assert error.value.code == "idempotency_conflict"
    assert service.list_inspections().total == 1 and service.list_tasks().input_revision == 1


def test_review_replay_precedes_version_and_closed_state_validation(service, image):
    original = create(service, image, "low_confidence").inspection
    request = review_request(original)
    first = service.review(original.inspection_id, request)
    replay = service.review(original.inspection_id, request)
    assert replay.replayed and not replay.planning_input_changed and replay.input_revision == 1
    assert replay.inspection == first.inspection and replay.task == first.task
    with pytest.raises(AppError) as error:
        service.review(original.inspection_id, review_request(original, note="changed payload"))
    assert error.value.code == "idempotency_conflict"
    with pytest.raises(AppError) as error:
        service.review(original.inspection_id, review_request(first.inspection, request_id="other-review"))
    assert error.value.code == "invalid_state"
    assert service.list_tasks().total == 1


@pytest.mark.parametrize("scenario", ["high_confidence", "no_detection"])
def test_nonpending_inspection_cannot_be_reviewed(service, image, scenario):
    original = create(service, image, scenario).inspection
    with pytest.raises(AppError) as error:
        service.review(original.inspection_id, review_request(original, "dismiss"))
    assert error.value.code == "invalid_state"


def test_stale_review_version_has_no_business_change(service, image):
    original = create(service, image, "low_confidence").inspection
    with pytest.raises(AppError) as error:
        service.review(original.inspection_id, review_request(original, expected_version=2))
    assert error.value.code == "stale_record_version"
    assert service.list_tasks().total == 0 and service.list_tasks().input_revision == 0


def test_task_label_and_location_corrections_audit_changes_and_preserve_inspection(service, image):
    initial = create(service, image)
    patch = TaskPatch(request_id="patch-1", expected_version=1, damage_label="pothole_deep",
                      latitude=1.3410, longitude=103.706, road_type="public_motor_road")
    result = service.update_task(initial.task.task_id, patch)
    assert result.planning_input_changed and result.input_revision == 2
    assert result.task.record_version == 2 and result.task.priority == "P1" and result.task.service_minutes == 240
    assert result.task.latitude == 1.3410 and len(result.task.history) == 2
    assert result.task.history[-1].before.damage_label == "pothole"
    assert result.task.history[-1].after.damage_label == "pothole_deep"
    assert "damage_label" in result.task.history[-1].changed_fields
    assert result.task.history[-1].actor_source == "user_declared_unverified"
    assert service.get_inspection(initial.inspection.inspection_id) == initial.inspection


@pytest.mark.parametrize("status", ["completed", "cancelled"])
def test_terminal_task_preserves_history_and_cannot_change_again(service, image, status):
    initial = create(service, image)
    request = TaskPatch(request_id="finish", expected_version=1, status=status)
    result = service.update_task(initial.task.task_id, request)
    assert result.task.status == status and result.task.record_version == 2 and result.input_revision == 2
    assert service.list_tasks().total == 0
    assert service.list_tasks(status=status).total == 1
    replay = service.update_task(initial.task.task_id, request)
    assert replay.replayed and replay.task == result.task and not replay.planning_input_changed
    with pytest.raises(AppError) as error:
        service.update_task(initial.task.task_id, TaskPatch(request_id="late", expected_version=2, damage_label="pothole"))
    assert error.value.code == "invalid_state"


def test_noop_task_patch_has_no_record_or_input_revision_change(service, image):
    initial = create(service, image)
    request = TaskPatch(request_id="noop", expected_version=1, damage_label=initial.task.damage_label,
                        latitude=initial.task.latitude, longitude=initial.task.longitude, road_type="public_motor_road")
    result = service.update_task(initial.task.task_id, request)
    assert result.task == initial.task and result.input_revision == 1 and not result.planning_input_changed
    assert service.update_task(initial.task.task_id, request).replayed


def test_task_stale_write_and_key_payload_conflict(service, image):
    initial = create(service, image)
    request = TaskPatch(request_id="patch", expected_version=1, damage_label="pothole_deep")
    service.update_task(initial.task.task_id, request)
    with pytest.raises(AppError) as error:
        service.update_task(initial.task.task_id, TaskPatch(request_id="other", expected_version=1, status="completed"))
    assert error.value.code == "stale_record_version"
    with pytest.raises(AppError) as error:
        service.update_task(initial.task.task_id, TaskPatch(request_id="patch", expected_version=1, status="completed"))
    assert error.value.code == "idempotency_conflict"


def test_restart_keeps_frozen_inspection_policy_for_review_and_task_correction(service, image):
    original = create(service, image, "low_confidence").inspection
    source = service.rules.policy.model_dump()
    source["rule_version"] = "demo-new-policy-v2"
    source["rules"]["pothole"]["service_minutes"] = 999
    source["rules"]["pothole_deep"]["priority"] = "P3"
    fresh_database = Database(service.database.path)
    fresh_database.initialize()
    restarted = WorkflowService(fresh_database, RuleService(RulePolicy.model_validate(source)),
                                service.detector, service.scope, service.images)
    result = restarted.review(original.inspection_id, review_request(original))
    assert result.task.service_minutes == 120 and result.task.rule_version == "demo-rules-v2"
    patch = restarted.update_task(result.task.task_id, TaskPatch(request_id="correct", expected_version=1, damage_label="pothole_deep"))
    assert patch.task.priority == "P1" and patch.task.rule_version == "demo-rules-v2"
    assert restarted.get_inspection(original.inspection_id).detections == original.detections


def test_filtered_pagination_and_same_snapshot_task_revision(service, image):
    for index, scenario in enumerate(("high_confidence", "low_confidence", "no_detection", "high_confidence")):
        create(service, image, scenario, key=f"upload-{index}")
    all_records = service.list_inspections()
    assert all_records.total == 4 and len(all_records.items) == 4
    assert service.list_inspections(status="pending_review").total == 1
    page = service.list_inspections(limit=1, offset=1)
    assert page.total == 4 and page.items[0] == all_records.items[1]
    tasks = service.list_tasks(status=None, limit=1, offset=1)
    assert tasks.total == 2 and len(tasks.items) == 1 and tasks.input_revision == 2


def test_concurrent_duplicate_upload_has_one_file_one_task_and_one_revision(service, image):
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: create(service, image), range(4)))
    assert sum(not result.replayed for result in results) == 1
    assert len({result.inspection.inspection_id for result in results}) == 1
    assert service.list_tasks().total == 1 and service.list_tasks().input_revision == 1
    assert len(list(service.images.root.glob("*.png"))) == 1


def test_concurrent_review_requests_have_one_winner_and_one_task(service, image):
    original = create(service, image, "low_confidence").inspection
    def run(index):
        try:
            return service.review(original.inspection_id, review_request(original, request_id=f"review-{index}"))
        except AppError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(run, range(4)))
    assert sum(result == "stale_record_version" for result in results) == 3
    assert service.list_tasks().total == 1 and service.list_tasks().input_revision == 1


def test_concurrent_same_review_key_replays_without_duplicate_task(service, image):
    original = create(service, image, "low_confidence").inspection
    payload = review_request(original)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: service.review(original.inspection_id, payload), range(4)))
    assert sum(not item.replayed for item in results) == 1
    assert service.list_tasks().total == 1 and service.list_tasks().input_revision == 1


def test_concurrent_task_corrections_have_one_version_winner(service, image):
    initial = create(service, image)
    def run(index):
        try:
            return service.update_task(initial.task.task_id, TaskPatch(request_id=f"patch-{index}", expected_version=1,
                                                                      damage_label="pothole_deep"))
        except AppError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(run, range(4)))
    assert sum(result == "stale_record_version" for result in results) == 3
    assert service.get_task(initial.task.task_id).record_version == 2 and service.list_tasks().input_revision == 2


def test_database_commit_failure_rolls_back_upload_task_revision_and_new_image(service, image, monkeypatch):
    original_transaction = service.database.transaction
    @contextmanager
    def failing_transaction(*args, **kwargs):
        with original_transaction(*args, **kwargs) as connection:
            yield connection
            raise sqlite3.OperationalError("private-sql-secret")
    monkeypatch.setattr(service.database, "transaction", failing_transaction)
    with pytest.raises(AppError) as error:
        create(service, image)
    assert error.value.code == "database_unavailable" and "private-sql-secret" not in str(error.value)
    assert service.list_tasks().total == 0 and service.list_tasks().input_revision == 0
    assert service.list_inspections().total == 0 and list(service.images.root.glob("*.png")) == []


def test_review_failure_rolls_back_inspection_task_and_revision(service, image, monkeypatch):
    original = create(service, image, "low_confidence").inspection
    def fail(*args):
        raise sqlite3.OperationalError("secret SQL")
    monkeypatch.setattr(service, "_save_key", fail)
    with pytest.raises(AppError):
        service.review(original.inspection_id, review_request(original))
    assert service.get_inspection(original.inspection_id) == original
    assert service.list_tasks().total == 0 and service.list_tasks().input_revision == 0
    assert service.images.path(original.inspection_id).exists()


def test_task_failure_rolls_back_status_history_and_revision(service, image, monkeypatch):
    initial = create(service, image)
    def fail(*args):
        raise sqlite3.OperationalError("secret SQL")
    monkeypatch.setattr(service, "_save_key", fail)
    with pytest.raises(AppError):
        service.update_task(initial.task.task_id, TaskPatch(request_id="fail", expected_version=1, status="completed"))
    assert service.get_task(initial.task.task_id) == initial.task
    assert service.list_tasks().input_revision == 1


def test_old_task_request_replay_returns_latest_resource_after_later_change(service, image):
    initial = create(service, image)
    first_payload = TaskPatch(request_id="correct", expected_version=1, damage_label="pothole_deep")
    service.update_task(initial.task.task_id, first_payload)
    latest = service.update_task(initial.task.task_id, TaskPatch(request_id="finish", expected_version=2, status="completed"))
    replay = service.update_task(initial.task.task_id, first_payload)
    assert replay.task == latest.task and replay.input_revision == 3
    assert replay.replayed and not replay.planning_input_changed


def test_invalid_scope_or_scenario_never_persists(service, image):
    with pytest.raises(AppError):
        service.create(metadata(latitude=1.292149, longitude=103.776551), image, "outside")
    with pytest.raises(AppError) as error:
        service.create(metadata("missing-scenario"), image, "unknown")
    assert error.value.code == "demo_scenario_not_found"
    assert service.list_inspections().total == 0 and service.list_tasks().input_revision == 0


def test_active_task_outside_scope_patch_does_not_modify_history_or_revision(service, image):
    initial = create(service, image)
    with pytest.raises(AppError):
        service.update_task(initial.task.task_id, TaskPatch(request_id="outside", expected_version=1,
                            latitude=1.292149, longitude=103.776551, road_type="public_motor_road"))
    assert service.get_task(initial.task.task_id) == initial.task and service.list_tasks().input_revision == 1


def test_v1_migration_preserves_revision_and_repeated_v2_initialization_preserves_history(tmp_path, service, image):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE infra_metadata(singleton_id INTEGER PRIMARY KEY,schema_version INTEGER,input_revision INTEGER)")
        connection.execute("INSERT INTO infra_metadata VALUES (1,1,7)")
    database = Database(path)
    database.initialize()
    database.initialize()
    with database.connect() as connection:
        assert read_revision(connection) == 7
        assert connection.execute("SELECT schema_version FROM infra_metadata").fetchone()[0] == 5
    first = create(service, image)
    service.database.initialize()
    assert service.get_task(first.task.task_id) == first.task


def test_v2_missing_business_table_is_not_silently_recreated(service):
    with service.database.transaction() as connection:
        connection.execute("DROP TABLE tasks")
    with pytest.raises(DatabaseStateError):
        service.database.initialize()
    with service.database.connect() as connection:
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='tasks'").fetchone() is None


@pytest.mark.parametrize("damage", ["missing_table", "missing_singleton"])
def test_missing_metadata_never_resets_populated_v2_database(service, image, damage):
    original = create(service, image)
    service.update_task(original.task.task_id, TaskPatch(request_id="finish", expected_version=1, status="completed"))
    current = service.get_task(original.task.task_id)
    with service.database.transaction() as connection:
        if damage == "missing_table":
            connection.execute("DROP TABLE infra_metadata")
        else:
            connection.execute("DELETE FROM infra_metadata WHERE singleton_id=1")
    with pytest.raises(DatabaseStateError):
        service.database.initialize()
    with service.database.connect() as connection:
        if damage == "missing_table":
            assert connection.execute("SELECT name FROM sqlite_master WHERE name='infra_metadata'").fetchone() is None
        else:
            assert connection.execute("SELECT COUNT(*) FROM infra_metadata").fetchone()[0] == 0
        assert connection.execute("SELECT record_json FROM tasks WHERE task_id=?", (current.task_id,)).fetchone()[0] == current.model_dump_json()
        assert connection.execute("SELECT COUNT(*) FROM inspections").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM operation_keys").fetchone()[0] == 2


def test_v1_partial_workflow_state_is_not_adopted_or_revised(service, image):
    original = create(service, image)
    with service.database.transaction() as connection:
        connection.execute("UPDATE infra_metadata SET schema_version=1")
    with pytest.raises(DatabaseStateError):
        service.database.initialize()
    with service.database.connect() as connection:
        assert tuple(connection.execute("SELECT schema_version,input_revision FROM infra_metadata").fetchone()) == (1, 1)
    assert service.get_task(original.task.task_id) == original.task


def test_foreign_key_and_unique_inspection_task_constraints_are_real(service, image):
    first = create(service, image)
    with pytest.raises(sqlite3.IntegrityError), service.database.transaction() as connection:
        connection.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?)",
                           ("d" * 32, first.inspection.inspection_id, "active", 1, first.task.created_at.isoformat(), first.task.model_dump_json()))
    with pytest.raises(sqlite3.IntegrityError), service.database.transaction() as connection:
        connection.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?)", ("e" * 32, "f" * 32, "active", 1, "now", "{}"))


@pytest.mark.parametrize("fields", [
    {"action": "confirm"}, {"action": "correct", "detection_id": "d"},
    {"action": "confirm", "detection_id": "d", "damage_label": "pothole"},
    {"action": "dismiss", "detection_id": "d"}, {"action": "dismiss", "damage_label": "pothole"},
    {"action": "correct", "detection_id": "d", "damage_label": "unknown"},
    {"action": "dismiss", "note": "x" * 501}, {"action": "dismiss", "request_id": "non ascii \u4e2d\u6587"},
])
def test_review_request_rejects_invalid_action_fields(fields):
    data = dict(request_id="review", expected_version=1)
    data.update(fields)
    with pytest.raises(ValidationError):
        ReviewRequest.model_validate(data)


@pytest.mark.parametrize("changes", [
    {}, {"priority": "P1"}, {"service_minutes": 5}, {"due_at": None}, {"status": "active"},
    {"latitude": 1.3}, {"longitude": 103.7}, {"latitude": 1.3, "longitude": 103.7},
    {"damage_label": None}, {"status": None}, {"status": "completed", "expected_version": True},
])
def test_task_patch_only_accepts_explicit_editable_fields(changes):
    data = dict(request_id="patch", expected_version=1)
    data.update(changes)
    with pytest.raises(ValidationError):
        TaskPatch.model_validate(data)


def test_service_revalidates_mutated_request_snapshots(service, image):
    bad = metadata()
    bad.latitude = "private-input"
    with pytest.raises(AppError) as error:
        service.create(bad, image, "bad")
    assert error.value.code == "validation_error" and "private-input" not in str(error.value)
    original = create(service, image, "low_confidence").inspection
    review = review_request(original)
    review.action = "unknown"
    with pytest.raises(AppError):
        service.review(original.inspection_id, review)
    initial = create(service, image, key="high").task
    patch = TaskPatch(request_id="invalid", expected_version=1, status="completed")
    patch.status = "active"
    with pytest.raises(AppError):
        service.update_task(initial.task_id, patch)


@pytest.mark.parametrize("limit,offset,status", [(0, 0, None), (101, 0, None), (True, 0, None), (1, -1, None), (1, 0, "wrong"), (1, 0, [])])
def test_pagination_and_status_service_inputs_are_validated(service, limit, offset, status):
    with pytest.raises(AppError) as error:
        service.list_tasks(status=status, limit=limit, offset=offset)
    assert error.value.code == "validation_error"


def test_missing_resources_and_corrupt_snapshots_return_safe_errors(service, image):
    with pytest.raises(AppError) as error:
        service.get_task("f" * 32)
    assert error.value.status_code == 404
    with pytest.raises(AppError):
        service.get_inspection("../secret")
    first = create(service, image)
    with service.database.transaction() as connection:
        connection.execute("UPDATE tasks SET record_json='secret-invalid-json' WHERE task_id=?", (first.task.task_id,))
    with pytest.raises(AppError) as error:
        service.get_task(first.task.task_id)
    assert error.value.status_code == 503 and "secret-invalid-json" not in str(error.value)


def test_deleted_database_writes_fail_without_recreating_file(service, image):
    accepted = create(service, image)
    pending = create(service, image, "low_confidence", key="pending")
    original_images = set(service.images.root.glob("*.png"))
    service.database.path.unlink()
    operations = (
        lambda: create(service, image, key="after-deletion"),
        lambda: service.review(pending.inspection.inspection_id, review_request(pending.inspection)),
        lambda: service.update_task(accepted.task.task_id, TaskPatch(request_id="after-deletion", expected_version=1, status="completed")),
    )
    for operation in operations:
        with pytest.raises(AppError) as error:
            operation()
        assert error.value.status_code == 503 and error.value.code == "database_unavailable"
        assert not service.database.path.exists()
    assert set(service.images.root.glob("*.png")) == original_images


@pytest.mark.parametrize("width,height", [(1, 1), (80, 60), (1000, 120)])
def test_demo_dimensions_scale_all_scenarios_without_real_inference(width, height):
    detector = DemoDetector()
    for scenario in SCENARIOS:
        output = detector.detect(scenario, image_width=width, image_height=height)
        assert all(item.image_width == width and item.image_height == height for item in output)


@pytest.mark.parametrize("width,height", [(0, 1), (1, -1), (True, 1), (1.5, 1)])
def test_demo_scaling_rejects_invalid_dimensions(width, height):
    with pytest.raises(ValueError):
        DemoDetector().detect("high_confidence", image_width=width, image_height=height)
