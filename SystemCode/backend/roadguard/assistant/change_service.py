"""Durable, owner-scoped availability requests with atomic confirmation and receipts."""
from datetime import datetime, timedelta, timezone
from functools import wraps
import hashlib
import json
import re
import sqlite3
import uuid

from pydantic import ValidationError
from roadguard.database import DatabaseStateError, assert_revision
from roadguard.errors import AppError
from roadguard.crews.schemas import CrewPatch
from roadguard.routing.service import RecalculateRequest
from .change_models import ChangePreview, ChangeRecord, ChangeList


def now():
    return datetime.now(timezone.utc)


def safe_db(method):
    @wraps(method)
    def call(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except (sqlite3.Error, DatabaseStateError, ValidationError):
            raise AppError('database_unavailable', 'The change request store is unavailable.', 503) from None
    return call


def parse_instruction(text: str):
    """A small exact grammar, not a permissive substring or a model execution tool."""
    text = text.strip()
    match = re.fullmatch(r'(enable|disable)\s+(crew-[0-9]{2})[.!]?', text, re.IGNORECASE)
    if match:
        return match[2], match[1].lower() == 'enable'
    match = re.fullmatch(r'set\s+(crew-[0-9]{2})\s+(available|unavailable)[.!]?', text, re.IGNORECASE)
    if match:
        return match[1], match[2].lower() == 'available'
    match = re.fullmatch(r'(?:\u8bf7)?(\u542f\u7528|\u505c\u7528)\s+(crew-[0-9]{2})[\u3002\uff01!]?', text)
    if match:
        return match[2], match[1] == '\u542f\u7528'
    match = re.fullmatch(r'(?:\u8bf7)?(?:\u5c06|\u628a)\s*(crew-[0-9]{2})\s*\u8bbe\u4e3a(\u53ef\u7528|\u4e0d\u53ef\u7528)[\u3002\uff01!]?', text)
    if match:
        return match[1], match[2] == '\u53ef\u7528'
    raise AppError('unsupported_change', 'Only an explicit single-crew availability change is supported.', 422)


class ChangeService:
    def __init__(self, database, crews, queries, planning):
        self.database, self.crews, self.queries, self.planning = database, crews, queries, planning

    def _read(self, connection, change_id, actor_id):
        row = connection.execute(
            'SELECT change_id,actor_id,client_key,record_json FROM assistant_changes WHERE change_id=? AND actor_id=?',
            (change_id, actor_id)).fetchone()
        if row is None:
            raise AppError('not_found', 'The requested change was not found.', 404)
        result = ChangeRecord.model_validate_json(row[3])
        if (result.change_id, result.actor_id, result.client_key) != tuple(row[:3]):
            raise DatabaseStateError('Stored request columns mismatch.')
        return result

    def _event(self, connection, record, action, details=None):
        connection.execute('INSERT INTO assistant_change_events VALUES (?,?,?,?,?,?)',
                           (uuid.uuid4().hex, record.change_id, record.actor_id, action, now().isoformat(),
                            json.dumps(details or {}, sort_keys=True)))

    def _save(self, connection, record, action, details=None):
        record.record_version += 1
        connection.execute('UPDATE assistant_changes SET record_json=? WHERE change_id=? AND actor_id=?',
                           (record.model_dump_json(), record.change_id, record.actor_id))
        self._event(connection, record, action, details)
        return record

    @staticmethod
    def _view(record):
        if record.status == 'pending' and record.expires_at <= now():
            return record.model_copy(update={'status': 'expired'})
        return record

    @safe_db
    def get(self, change_id, actor_id):
        with self.database.connect() as connection:
            return self._view(self._read(connection, change_id, actor_id))

    @safe_db
    def list(self, actor_id):
        with self.database.connect() as connection:
            ids = connection.execute('SELECT change_id FROM assistant_changes WHERE actor_id=? ORDER BY rowid DESC LIMIT 20',
                                     (actor_id,)).fetchall()
            return ChangeList(items=[self._view(self._read(connection, row[0], actor_id)) for row in ids])

    @safe_db
    def preview(self, payload: ChangePreview, actor_id: str):
        fingerprint = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
        crew_id, available = parse_instruction(payload.instruction)
        with self.database.transaction() as connection:
            existing = connection.execute(
                'SELECT change_id,payload_hash FROM assistant_changes WHERE actor_id=? AND client_key=?',
                (actor_id, payload.request_id)).fetchone()
            if existing:
                if existing[1] != fingerprint:
                    raise AppError('idempotency_conflict', 'The preview key was used for different input.', 409)
                return self._view(self._read(connection, existing[0], actor_id))
            plan = self.queries.get(payload.based_on_plan_id, connection=connection)
            assert_revision(connection, plan.input_revision)
            roster = self.crews.read_records(connection)
            crew = next((c for c in roster if c.crew_id == crew_id), None)
            if crew is None:
                raise AppError('not_found', 'The crew is not in the configured roster.', 404)
            created = now()
            record = ChangeRecord(change_id=f'change-{uuid.uuid4().hex}', actor_id=actor_id,
                                  client_key=payload.request_id, instruction=payload.instruction,
                                  based_on_plan_id=plan.plan_id, input_revision=plan.input_revision,
                                  crew_id=crew_id, crew_record_version=crew.record_version,
                                  before_available=crew.available, after_available=available,
                                  status='pending', record_version=1, created_at=created,
                                  expires_at=created + timedelta(minutes=15))
            connection.execute('INSERT INTO assistant_changes VALUES (?,?,?,?,?)',
                               (record.change_id, actor_id, payload.request_id, fingerprint, record.model_dump_json()))
            self._event(connection, record, 'previewed')
            return record

    @safe_db
    def confirm(self, change_id, actor_id, expected_version):
        with self.database.transaction() as connection:
            record = self._read(connection, change_id, actor_id)
            if record.status == 'confirmed':
                return record  # Immutable intent: replay never calls B again.
            if record.status != 'pending':
                raise AppError('change_not_pending', 'This request cannot be confirmed.', 409)
            if record.record_version != expected_version:
                raise AppError('stale_record_version', 'Reload the request before confirming.', 409)
            if record.expires_at <= now():
                record.status = 'expired'
                return self._save(connection, record, 'expired')
            # Only preconditions are caught; any B mutation failure rolls back all writes.
            try:
                assert_revision(connection, record.input_revision)
                crew = next(c for c in self.crews.read_records(connection) if c.crew_id == record.crew_id)
                if crew.record_version != record.crew_record_version or crew.available != record.before_available:
                    raise AppError('stale_record_version', 'The crew changed since preview.', 409)
            except AppError as exc:
                record.status, record.error_code = 'failed', exc.code
                return self._save(connection, record, 'confirmation_rejected', {'code': exc.code})
            except StopIteration:
                record.status, record.error_code = 'failed', 'crew_unavailable'
                return self._save(connection, record, 'confirmation_rejected', {'code': record.error_code})
            result = self.crews.update_in_transaction(
                connection, record.crew_id, CrewPatch(request_id=record.change_id,
                expected_version=record.crew_record_version, available=record.after_available))
            record.status, record.confirmed_at = 'confirmed', now()
            record.applied_revision = result.input_revision
            record.planning_input_changed = result.planning_input_changed
            return self._save(connection, record, 'confirmed', {
                'before': record.before_available, 'after': record.after_available,
                'input_revision': result.input_revision})

    @safe_db
    def cancel(self, change_id, actor_id, expected_version):
        with self.database.transaction() as connection:
            record = self._read(connection, change_id, actor_id)
            if record.status == 'cancelled':
                return record
            if record.status != 'pending':
                raise AppError('change_not_pending', 'A confirmed or closed request cannot be cancelled.', 409)
            if record.record_version != expected_version:
                raise AppError('stale_record_version', 'Reload the request before cancelling.', 409)
            record.status = 'cancelled'
            return self._save(connection, record, 'cancelled')

    @safe_db
    def replan(self, change_id, actor_id, attempt_id):
        with self.database.transaction() as connection:
            record = self._read(connection, change_id, actor_id)
            if record.status != 'confirmed':
                raise AppError('change_not_confirmed', 'Confirm the change before replanning.', 409)
            if record.replan_status == 'succeeded' or attempt_id in record.replan_attempts:
                return record  # A retry of the same attempt only reads its outcome.
            if record.replan_status == 'running' and record.replan_lease_until > now():
                raise AppError('change_replan_busy', 'A planning attempt is still running.', 409)
            if len(record.replan_attempts) >= 10:
                raise AppError('change_retry_limit', 'Use the route page to review and plan again.', 409)
            assert_revision(connection, record.applied_revision)
            record.replan_attempts.append(attempt_id)
            record.replan_attempt_id, record.replan_status = attempt_id, 'running'
            record.replan_lease_until = now() + timedelta(minutes=10)
            record.replan_error_code = None
            self._save(connection, record, 'replan_started', {'attempt_id': attempt_id})

        def saved(connection, result):
            current = self._read(connection, change_id, actor_id)
            # Fencing prevents a slow/crashed previous attempt from saving after recovery.
            if current.replan_status != 'running' or current.replan_attempt_id != attempt_id:
                raise AppError('change_attempt_superseded', 'This planning attempt has been superseded.', 409)
            current.replan_status, current.result = 'succeeded', result
            current.replan_lease_until = None
            self._save(connection, current, 'replan_succeeded', {'attempt_id': attempt_id})

        try:
            # Result receipt and B's two plans commit together. No DB lock during calculation.
            self.planning.recalculate(RecalculateRequest(expected_revision=record.applied_revision), on_saved=saved)
        except Exception as exc:
            # Failure after confirmation never rolls back availability. Unknown exceptions
            # are recorded with a constant code, never raw provider messages.
            code = exc.code if isinstance(exc, AppError) else 'planning_failed'
            with self.database.transaction() as connection:
                current = self._read(connection, change_id, actor_id)
                if current.replan_status == 'running' and current.replan_attempt_id == attempt_id:
                    current.replan_status, current.replan_error_code = 'failed', code
                    current.replan_lease_until = None
                    self._save(connection, current, 'replan_failed', {'attempt_id': attempt_id, 'code': code})
            return self.get(change_id, actor_id)
        return self.get(change_id, actor_id)
