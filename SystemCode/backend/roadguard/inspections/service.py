"""Transactional demo workflow. Detected facts and frozen policies are retained."""

from datetime import datetime, timezone
from contextlib import contextmanager
from functools import wraps
import hashlib
import json
import logging
import re
import sqlite3
from threading import Lock
from uuid import uuid4

from pydantic import TypeAdapter

from roadguard.database import Database, DatabaseStateError, increment_revision, read_revision
from roadguard.errors import AppError
from roadguard.geography import JurongScope
from roadguard.images import ImageStore, PreparedImage
from roadguard.rules import RulePolicy, RuleService
from roadguard.schemas import DecisionTrace, Detection, RuleAssessment
from roadguard.schemas.workflow import (
    InspectionList, InspectionMutation, InspectionRecord, RequestId, ReviewHistoryEntry,
    ReviewRequest, TaskAuditValues, TaskHistoryEntry, TaskList, TaskMutation, TaskPatch, TaskRecord,
    UploadMetadata,
)
from roadguard.vision import DemoDetector, DemoScenarioNotFound


logger = logging.getLogger(__name__)


def _db_operation(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except (sqlite3.Error, DatabaseStateError):
            raise AppError("database_unavailable", "The workflow database is unavailable.", 503) from None
    return wrapped


def _validated(model, payload, *, patch=False):
    try:
        return model.model_validate(payload.model_dump(warnings=False, exclude_unset=patch,
                                                     exclude_none=model is UploadMetadata))
    except (AttributeError, TypeError, ValueError):
        raise AppError("validation_error", "Workflow request validation failed.", 422) from None


def _hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _now():
    return datetime.now(timezone.utc)


class WorkflowService:
    def __init__(self, database: Database, rules: RuleService, detector: DemoDetector,
                 scope: JurongScope, images: ImageStore, *, real_detector=None) -> None:
        self.database, self.rules, self.detector = database, rules, detector
        self.scope, self.images = scope, images
        self.real_detector = real_detector
        self._key_guard, self._create_locks = Lock(), {}

    @contextmanager
    def _create_key_lock(self, key):
        # Single-flight per key in this process. Cross-process writes still recheck
        # the durable key under SQLite's write lock before saving any resources.
        with self._key_guard:
            entry = self._create_locks.setdefault(key, [Lock(), 0])
            entry[1] += 1
        try:
            with entry[0]:
                yield
        finally:
            with self._key_guard:
                entry[1] -= 1
                if entry[1] == 0:
                    del self._create_locks[key]

    def _detect(self, metadata, image):
        if metadata.mode == "demo":
            try:
                detections = self.detector.detect(metadata.scenario_id, image_width=image.width, image_height=image.height)
            except DemoScenarioNotFound:
                raise AppError("demo_scenario_not_found", "The requested demo scenario is not available.", 404) from None
            return self.rules.evaluate(detections), self.detector.model_version, None, None
        if self.real_detector is None:
            raise AppError("detector_unavailable", "The local real detector is unavailable.", 503)
        try:
            detections = [Detection.model_validate(item.model_dump(warnings=False))
                          for item in self.real_detector.detect(image)]
            if (len(detections) > 100 or not isinstance(self.real_detector.model_version, str)
                    or not self.real_detector.model_version.strip()
                    or self.real_detector.model_version.strip().startswith("demo")
                    or not isinstance(self.real_detector.weights_sha256, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", self.real_detector.weights_sha256)
                    or self.real_detector.manifest_version != "roadguard-model-v1"):
                raise ValueError("invalid real detector provenance")
            if any(item.is_demo or (item.image_width, item.image_height, item.model_version) !=
                   (image.width, image.height, self.real_detector.model_version) for item in detections):
                raise ValueError("inconsistent real detection provenance")
            trace = [DecisionTrace(code="demo_business_assumptions", rule_version=self.rules.policy.rule_version,
                                   is_demo=True, message="Detection uses real image pixels. Inspection and any reviewed task remain demo business objects: severity, priority, service time and road eligibility are unvalidated assumptions.")]
            trace.append(DecisionTrace(
                code="real_uncalibrated_review_required" if detections else "no_detection",
                message="Every nonempty real detection requires human review; no calibrated acceptance threshold exists. The demo confidence threshold is not applied." if detections else "No real detections survived the model inference filter; no task is produced. This does not prove the image is damage-free.",
                rule_version=self.rules.policy.rule_version, is_demo=True,
            ))
            assessment = RuleAssessment(status="pending_review" if detections else "no_detection", detections=detections,
                                        selected_detection_id=None, candidate=None, decision_trace=trace,
                                        rule_version=self.rules.policy.rule_version, is_demo=True)
            return assessment, self.real_detector.model_version, self.real_detector.weights_sha256, self.real_detector.manifest_version
        except AppError:
            raise
        except Exception:
            raise AppError("detector_inference_failed", "Real image inference failed; no inspection was created.", 502) from None

    @staticmethod
    def _resource_id(value):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{32}", value):
            raise AppError("not_found", "The requested resource was not found.", 404)
        return value

    @staticmethod
    def _decode(model, value):
        try:
            return model.model_validate_json(value)
        except (ValueError, TypeError):
            raise AppError("database_unavailable", "Stored workflow data is unavailable.", 503) from None

    def _inspection(self, connection, inspection_id):
        row = connection.execute("SELECT status,record_version,record_json FROM inspections WHERE inspection_id=?", (inspection_id,)).fetchone()
        if row is None:
            raise AppError("not_found", "The requested inspection was not found.", 404)
        record = self._decode(InspectionRecord, row[2])
        if (record.inspection_id, record.status, record.record_version) != (inspection_id, row[0], row[1]):
            raise AppError("database_unavailable", "Stored inspection data is inconsistent.", 503)
        return record

    def _task(self, connection, task_id):
        row = connection.execute("SELECT status,record_version,inspection_id,record_json FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise AppError("not_found", "The requested task was not found.", 404)
        record = self._decode(TaskRecord, row[3])
        if (record.task_id, record.status, record.record_version, record.inspection_id) != (task_id, row[0], row[1], row[2]):
            raise AppError("database_unavailable", "Stored task data is inconsistent.", 503)
        return record

    def _frozen_rules(self, connection, inspection_id):
        row = connection.execute("SELECT policy_json FROM inspections WHERE inspection_id=?", (inspection_id,)).fetchone()
        return RuleService(self._decode(RulePolicy, row[0]))

    @staticmethod
    def _lookup_key(connection, scope, request_key, payload_hash):
        row = connection.execute("SELECT payload_hash,resource_id FROM operation_keys WHERE scope=? AND request_key=?",
                                 (scope, request_key)).fetchone()
        if row is not None and row[0] != payload_hash:
            raise AppError("idempotency_conflict", "The request key was already used for different input.", 409)
        return row[1] if row is not None else None

    @staticmethod
    def _save_key(connection, scope, request_key, payload_hash, resource_id):
        connection.execute("INSERT INTO operation_keys VALUES (?,?,?,?,?)",
                           (scope, request_key, payload_hash, resource_id, _now().isoformat()))

    def _inspection_result(self, connection, inspection_id, *, changed=False, replayed=False):
        inspection = self._inspection(connection, inspection_id)
        task = self._task(connection, inspection.task_id) if inspection.task_id else None
        return InspectionMutation(inspection=inspection, task=task, input_revision=read_revision(connection),
                                  planning_input_changed=changed, replayed=replayed)

    def _task_result(self, connection, task_id, *, changed=False, replayed=False):
        return TaskMutation(task=self._task(connection, task_id), input_revision=read_revision(connection),
                            planning_input_changed=changed, replayed=replayed)

    @staticmethod
    def _audit(task):
        return TaskAuditValues.model_validate({key: getattr(task, key) for key in TaskAuditValues.model_fields})

    def _make_task(self, inspection, candidate, request_id, actor_source, now):
        data = dict(task_id=inspection.task_id, inspection_id=inspection.inspection_id,
                    latitude=inspection.latitude, longitude=inspection.longitude,
                    damage_label=candidate.damage_label, severity=candidate.severity, priority=candidate.priority,
                    service_minutes=candidate.service_minutes, created_at=now, updated_at=now, due_at=None,
                    status="active", rule_version=candidate.rule_version, record_version=1,
                    repair_recommendation=candidate.repair_recommendation, is_demo=True)
        after = TaskAuditValues.model_validate({key: data[key] for key in TaskAuditValues.model_fields})
        data["history"] = [TaskHistoryEntry(request_id=request_id, action="created", recorded_at=now,
                                           changed_fields=list(TaskAuditValues.model_fields), before=None,
                                           after=after, actor_source=actor_source)]
        return TaskRecord.model_validate(data)

    @staticmethod
    def _insert_task(connection, task):
        connection.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?)",
                           (task.task_id, task.inspection_id, task.status, task.record_version,
                            task.created_at.isoformat(), task.model_dump_json()))

    @staticmethod
    def _write_inspection(connection, inspection):
        connection.execute("UPDATE inspections SET status=?,record_version=?,record_json=? WHERE inspection_id=?",
                           (inspection.status, inspection.record_version, inspection.model_dump_json(), inspection.inspection_id))

    @_db_operation
    def create(self, metadata: UploadMetadata, image: PreparedImage, idempotency_key: str) -> InspectionMutation:
        metadata = _validated(UploadMetadata, metadata)
        try:
            key = TypeAdapter(RequestId).validate_python(idempotency_key)
            if not isinstance(image, PreparedImage) or type(image.content) is not bytes or not image.content:
                raise ValueError("invalid prepared image")
            if type(image.width) is not int or type(image.height) is not int or min(image.width, image.height) <= 0:
                raise ValueError("invalid image dimensions")
            if not re.fullmatch(r"[0-9a-f]{64}", image.source_sha256):
                raise ValueError("invalid source hash")
        except (TypeError, ValueError):
            raise AppError("validation_error", "Upload request validation failed.", 422) from None
        fingerprint = _hash({"metadata": metadata.model_dump(mode="json"), "source_sha256": image.source_sha256})
        with self._create_key_lock(key):
            return self._create_prepared(metadata, image, key, fingerprint)

    def _create_prepared(self, metadata, image, key, fingerprint):
        # Replay is independent of model availability and never invokes inference.
        with self.database.connect() as connection:
            replay_id = self._lookup_key(connection, "create", key, fingerprint)
            if replay_id:
                return self._inspection_result(connection, replay_id, replayed=True)
        self.scope.validate(metadata.latitude, metadata.longitude, metadata.road_type)
        # CPU/GPU work happens before BEGIN IMMEDIATE; other domain writes proceed.
        assessment, model_version, weights_sha256, manifest_version = self._detect(metadata, image)
        saved_image_id = None
        try:
            with self.database.transaction() as connection:
                replay_id = self._lookup_key(connection, "create", key, fingerprint)
                if replay_id:
                    return self._inspection_result(connection, replay_id, replayed=True)
                now, inspection_id = _now(), uuid4().hex
                candidate = assessment.candidate
                task_id = uuid4().hex if candidate is not None else None
                inspection = InspectionRecord(
                    inspection_id=inspection_id, image_url=f"/api/v1/inspections/{inspection_id}/image",
                    annotated_image_url=None, latitude=metadata.latitude, longitude=metadata.longitude,
                    detections=assessment.detections, selected_detection_id=assessment.selected_detection_id,
                    status="accepted" if candidate else assessment.status, task_id=task_id,
                    decision_trace=assessment.decision_trace, is_demo=True, created_at=now, updated_at=now,
                    record_version=1, mode=metadata.mode, demo_scenario_id=metadata.scenario_id,
                    model_version=model_version, model_weights_sha256=weights_sha256,
                    model_manifest_version=manifest_version, image_width=image.width, image_height=image.height,
                    scope_version=self.scope.scope_version, road_type=metadata.road_type, review_history=[],
                )
                if candidate is not None:
                    inspection.decision_trace.append(DecisionTrace(
                        code="demo_task_created", message="The validated demo candidate was accepted and a single task "
                        "was created after declared-road and Jurong boundary validation. No route plan was calculated.",
                        rule_version=candidate.rule_version, is_demo=True,
                    ))
                self.images.save(inspection_id, image)
                saved_image_id = inspection_id
                connection.execute("INSERT INTO inspections VALUES (?,?,?,?,?,?)",
                                   (inspection_id, inspection.status, 1, now.isoformat(), inspection.model_dump_json(),
                                    self.rules.policy.model_dump_json()))
                if candidate is not None:
                    task = self._make_task(inspection, candidate, key, "system_demo_rules", now)
                    self._insert_task(connection, task)
                    increment_revision(connection)
                self._save_key(connection, "create", key, fingerprint, inspection_id)
                result = self._inspection_result(connection, inspection_id, changed=candidate is not None)
            return result
        except BaseException:
            if saved_image_id is not None:
                try:
                    self.images.delete(saved_image_id)
                except Exception as cleanup_error:
                    # A crash/failed cleanup can leave an orphan file; never remove broad paths.
                    logger.error("New image cleanup failed: %s", type(cleanup_error).__name__)
            raise

    @_db_operation
    def get_inspection(self, inspection_id: str) -> InspectionRecord:
        inspection_id = self._resource_id(inspection_id)
        with self.database.connect() as connection:
            return self._inspection(connection, inspection_id)

    @_db_operation
    def get_task(self, task_id: str) -> TaskRecord:
        task_id = self._resource_id(task_id)
        with self.database.connect() as connection:
            return self._task(connection, task_id)

    @_db_operation
    def review(self, inspection_id: str, payload: ReviewRequest) -> InspectionMutation:
        inspection_id = self._resource_id(inspection_id)
        payload = _validated(ReviewRequest, payload)
        key_scope, fingerprint = "review:" + inspection_id, _hash(payload.model_dump(mode="json"))
        with self.database.transaction() as connection:
            replay_id = self._lookup_key(connection, key_scope, payload.request_id, fingerprint)
            if replay_id:
                return self._inspection_result(connection, replay_id, replayed=True)
            inspection = self._inspection(connection, inspection_id)
            if inspection.record_version != payload.expected_version:
                raise AppError("stale_record_version", "The inspection has changed. Reload it before retrying.", 409)
            if inspection.status != "pending_review":
                raise AppError("invalid_state", "Only pending inspections can be reviewed.", 409)
            selected = next((item for item in inspection.detections if item.detection_id == payload.detection_id), None)
            if payload.action != "dismiss" and selected is None:
                raise AppError("invalid_detection_selection", "The selected detection does not belong to this inspection.", 422)
            rules, now = self._frozen_rules(connection, inspection_id), _now()
            candidate = None if payload.action == "dismiss" else rules.reviewed_candidate(selected, payload.damage_label)
            data = inspection.model_dump()
            data.update(status="rejected" if candidate is None else "accepted", task_id=uuid4().hex if candidate else None,
                        selected_detection_id=selected.detection_id if candidate else None,
                        updated_at=now, record_version=inspection.record_version + 1)
            data["review_history"].append(ReviewHistoryEntry(
                request_id=payload.request_id, action=payload.action, recorded_at=now,
                detection_id=payload.detection_id, original_damage_label=selected.label if selected else None,
                corrected_damage_label=payload.damage_label, note=payload.note,
                rule_version=rules.policy.rule_version,
            ))
            reason = "No task is created after the declared dismissal." if candidate is None else rules.policy.rules[candidate.damage_label].reason
            data["decision_trace"].append(DecisionTrace(
                code="review_dismissed" if candidate is None else "reviewed_rule_mapping",
                message="User-declared review (identity is unverified). " + reason,
                rule_version=rules.policy.rule_version, is_demo=True,
            ))
            inspection = InspectionRecord.model_validate(data)
            self._write_inspection(connection, inspection)
            if candidate is not None:
                self._insert_task(connection, self._make_task(inspection, candidate, payload.request_id, "user_declared_unverified", now))
                increment_revision(connection)
            self._save_key(connection, key_scope, payload.request_id, fingerprint, inspection_id)
            return self._inspection_result(connection, inspection_id, changed=candidate is not None)

    @_db_operation
    def update_task(self, task_id: str, payload: TaskPatch) -> TaskMutation:
        task_id = self._resource_id(task_id)
        payload = _validated(TaskPatch, payload, patch=True)
        key_scope, fingerprint = "task:" + task_id, _hash(payload.model_dump(mode="json", exclude_unset=True))
        with self.database.transaction() as connection:
            replay_id = self._lookup_key(connection, key_scope, payload.request_id, fingerprint)
            if replay_id:
                return self._task_result(connection, replay_id, replayed=True)
            task = self._task(connection, task_id)
            if task.record_version != payload.expected_version:
                raise AppError("stale_record_version", "The task has changed. Reload it before retrying.", 409)
            if task.status != "active":
                raise AppError("invalid_state", "Only active tasks can be changed.", 409)
            data = task.model_dump()
            if payload.latitude is not None:
                self.scope.validate(payload.latitude, payload.longitude, payload.road_type)
                data.update(latitude=payload.latitude, longitude=payload.longitude)
            if payload.damage_label is not None:
                inspection = self._inspection(connection, task.inspection_id)
                original = next(item for item in inspection.detections if item.detection_id == inspection.selected_detection_id)
                candidate = self._frozen_rules(connection, task.inspection_id).reviewed_candidate(original, payload.damage_label)
                for key in ("damage_label", "severity", "priority", "service_minutes", "rule_version", "repair_recommendation"):
                    data[key] = getattr(candidate, key)
            if payload.status is not None:
                data["status"] = payload.status
            changed_fields = [key for key in TaskAuditValues.model_fields if data[key] != getattr(task, key)]
            changed = bool(changed_fields) or data["repair_recommendation"] != task.repair_recommendation
            if changed:
                now = _now()
                after = TaskAuditValues.model_validate({key: data[key] for key in TaskAuditValues.model_fields})
                data.update(updated_at=now, record_version=task.record_version + 1)
                data["history"].append(TaskHistoryEntry(
                    request_id=payload.request_id, action="updated", recorded_at=now, changed_fields=changed_fields,
                    before=self._audit(task), after=after, actor_source="user_declared_unverified",
                ))
                task = TaskRecord.model_validate(data)
                connection.execute("UPDATE tasks SET status=?,record_version=?,record_json=? WHERE task_id=?",
                                   (task.status, task.record_version, task.model_dump_json(), task_id))
                increment_revision(connection)
            self._save_key(connection, key_scope, payload.request_id, fingerprint, task_id)
            return self._task_result(connection, task_id, changed=changed)

    def _list(self, table, model, status, limit, offset):
        allowed = {"no_detection", "pending_review", "accepted", "rejected"} if table == "inspections" else {"active", "completed", "cancelled"}
        if (status is not None and (not isinstance(status, str) or status not in allowed)
                or type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0):
            raise AppError("validation_error", "List filter or pagination is invalid.", 422)
        where, parameters = ("", ()) if status is None else (" WHERE status=?", (status,))
        id_column = "inspection_id" if table == "inspections" else "task_id"
        with self.database.connect() as connection:
            total = connection.execute(f"SELECT COUNT(*) FROM {table}" + where, parameters).fetchone()[0]
            rows = connection.execute(f"SELECT {id_column} FROM {table}" + where + f" ORDER BY created_at,{id_column} LIMIT ? OFFSET ?",
                                      parameters + (limit, offset)).fetchall()
            loader = self._inspection if table == "inspections" else self._task
            result = dict(items=[loader(connection, row[0]) for row in rows], total=total, limit=limit, offset=offset)
            if table == "tasks":
                result["input_revision"] = read_revision(connection)
                return TaskList(**result)
            return InspectionList(**result)

    @_db_operation
    def list_inspections(self, status=None, limit=50, offset=0) -> InspectionList:
        return self._list("inspections", InspectionRecord, status, limit, offset)

    @_db_operation
    def list_tasks(self, status="active", limit=50, offset=0) -> TaskList:
        return self._list("tasks", TaskRecord, status, limit, offset)
