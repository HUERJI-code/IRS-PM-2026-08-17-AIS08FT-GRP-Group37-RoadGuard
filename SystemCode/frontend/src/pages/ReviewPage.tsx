import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import labels from '../../../model/label_schema.json'
import { useApi } from '../api/context'
import { createOperation, type Operation } from '../api/client'
import type { Model } from '../api/contracts'
import { ApiError } from '../api/errors'
import { formatMinutes, formatSingaporeTime } from '../api/format'
import {
  EmptyState,
  ErrorState,
  LoadingState,
} from '../components/RequestState'
import InspectionImage from '../components/InspectionImage'

type ReviewPayload = Omit<Model<'ReviewRequest'>, 'request_id'>

function ReviewRecord({
  id,
  onReviewed,
  onLockChange,
  onReady,
}: {
  id: string
  onReviewed: () => void
  onLockChange: (locked: boolean) => void
  onReady: () => void
}) {
  const { api, mode } = useApi()
  const [attempt, setAttempt] = useState(0)
  const [inspection, setInspection] =
    useState<Model<'InspectionResponse'> | null>(null)
  const [loading, setLoading] = useState(true)
  const [readError, setReadError] = useState<unknown>(null)
  const [error, setError] = useState<unknown>(null)
  const [action, setAction] = useState<'confirm' | 'correct' | 'dismiss'>(
    'confirm',
  )
  const [label, setLabel] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [uncertain, setUncertain] = useState(false)
  const [conflict, setConflict] = useState(false)
  const [result, setResult] =
    useState<Model<'InspectionMutationResponse'> | null>(null)
  const operation = useRef<Operation<ReviewPayload> | null>(null)
  const inFlight = useRef(false)
  const active = useRef(true)
  const submission = useRef<AbortController | null>(null)

  useEffect(() => {
    onLockChange(busy || uncertain)
    return () => onLockChange(false)
  }, [busy, uncertain, onLockChange])
  useEffect(() => {
    active.current = true
    return () => {
      active.current = false
      submission.current?.abort()
    }
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    let current = true
    api
      .inspection(id, { signal: controller.signal })
      .then((value) => {
        if (current) setInspection(value)
      })
      .catch((err) => {
        if (current) setReadError(err)
      })
      .finally(() => {
        if (current) setLoading(false)
      })
    return () => {
      current = false
      controller.abort()
    }
  }, [api, id, attempt])
  useEffect(() => {
    if (!loading) onReady()
  }, [loading, onReady])
  useEffect(() => {
    if (!busy && !uncertain) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [busy, uncertain])

  function reload() {
    operation.current = null
    setInspection(null)
    setResult(null)
    setReadError(null)
    setError(null)
    setAction('confirm')
    setLabel('')
    setNote('')
    setConflict(false)
    setUncertain(false)
    setLoading(true)
    setAttempt((n) => n + 1)
  }
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (
      inFlight.current ||
      !inspection ||
      inspection.status !== 'pending_review' ||
      mode !== 'live' ||
      conflict
    )
      return
    inFlight.current = true
    setBusy(true)
    setError(null)
    try {
      if (!operation.current) {
        const payload: ReviewPayload = {
          expected_version: inspection.record_version,
          action,
        }
        if (action !== 'dismiss') {
          const detection = inspection.detections[0]
          if (!detection)
            throw new ApiError(
              'invalid_detection_selection',
              'No detection is available for review.',
              422,
              'http',
            )
          payload.detection_id = detection.detection_id
        }
        if (action === 'correct') {
          if (!labels.classes.some((item) => item.label_key === label))
            throw new ApiError(
              'validation_error',
              'Select the corrected label.',
              422,
              'http',
            )
          payload.damage_label = label
        }
        if (note.trim()) payload.note = note.trim()
        operation.current = createOperation(payload)
      }
      submission.current = new AbortController()
      const value = await api.review(id, operation.current, {
        signal: submission.current.signal,
      })
      if (!active.current) return
      setInspection(value.inspection)
      setResult(value)
      setUncertain(false)
      operation.current = null
      onReviewed()
    } catch (err) {
      if (!active.current) return
      setError(err)
      const unknown = err instanceof ApiError && err.outcomeUnknown
      setUncertain(unknown)
      if (!unknown) operation.current = null
      if (
        err instanceof ApiError &&
        [
          'stale_record_version',
          'invalid_state',
          'idempotency_conflict',
        ].includes(err.code)
      )
        setConflict(true)
    } finally {
      inFlight.current = false
      if (active.current) setBusy(false)
    }
  }
  if (loading) return <LoadingState />
  if (!inspection)
    return (
      <>
        <ErrorState error={readError} />
        <button className="button" onClick={reload}>
          Reload inspection
        </button>
      </>
    )
  const pending = inspection.status === 'pending_review'
  return (
    <section className="review-record" aria-label="Selected inspection">
      <div className="record-heading"><div><p className="eyebrow">#{inspection.inspection_id.slice(0, 8)} · {formatSingaporeTime(inspection.created_at)}</p><h2>Inspection details</h2></div><span className="status-badge">{pending ? 'Pending review' : 'Processed'}</span></div>
      <div className="review-body">
      <div className="review-evidence">
      <InspectionImage key={`${id}-${attempt}`} inspection={inspection} />
      <details className="review-provenance">
        <summary>Detection source and record</summary>
        <p>Inference source:{inspection.mode === 'real' ? 'Real image · Experimental model' : 'Fixed mock detection'}</p>
        <p>Model:{inspection.model_version}</p>
        <p className="record-id">{inspection.inspection_id} · Record version {inspection.record_version}</p>
      </details>
      <details>
        <summary>View rule evidence</summary>
        <ul>
          {inspection.decision_trace.map((trace, index) => (
            <li key={index}>
              {trace.message} ({trace.rule_version ?? 'Version not provided'})
            </li>
          ))}
        </ul>
      </details>
      {result && (
        <section className="notice" aria-label="Review result">
          <p>
            Image labels and confidence retain the original detection output. Corrected labels appear in the linked task and review history.
          </p>
          <h3>{result.replayed ? 'Original request result recovered' : 'Review saved'}</h3>
          <p>
            Inspection status:
            {result.inspection.status === 'rejected'
              ? 'Rejected'
              : result.inspection.status === 'accepted'
                ? 'Accepted'
                : result.inspection.status}{' '}
            · Input revision {result.input_revision}
          </p>
          {result.task ? (
            <>
              <p>Linked task:{result.task.task_id}</p>
              <p>
                Backend label:{result.task.damage_label} · {result.task.priority} ·
                Estimated repair {formatMinutes(result.task.service_minutes)}
              </p>
              <p>Rule version:{result.task.rule_version}</p>
              <Link to="/routes">Check crews and recalculate routes</Link>
              <Link to={`/tasks?task=${result.task.task_id}`}>
                View task workspace
              </Link>
            </>
          ) : (
            <p>No task is linked to this result.</p>
          )}
          {result.planning_input_changed ? (
            <p>Planning inputs have changed. Existing routes require replanning; this page has not recalculated them automatically.</p>
          ) : (
            <p>This response does not flag a planning-input change. The backend plan remains authoritative for route status.</p>
          )}
        </section>
      )}
      {!pending && (
        <p role="status" className="notice">
          This inspection has been processed ({inspection.status}), Read-only; it cannot be reviewed again.
        </p>
      )}
      {inspection.review_history.length > 0 && (
        <section>
          <h3>Review history</h3>
          <ul>
            {inspection.review_history.map((item) => (
              <li key={item.request_id}>
                {item.action} · {formatSingaporeTime(item.recorded_at)} · Original label{' '}
                {item.original_damage_label ?? 'None'} → Corrected label{' '}
                {item.corrected_damage_label ?? 'Not corrected'}
                {item.note && ` · Notes:${item.note}`}
              </li>
            ))}
          </ul>
        </section>
      )}
      </div>
      {pending && (
        <form
          onSubmit={(event) => void submit(event)}
          className="upload-form review-form"
        >
          {mode !== 'live' && (
            <p className="notice">This is a read-only mock snapshot. Reviews cannot be saved.</p>
          )}
          <fieldset disabled={busy || uncertain || conflict || mode !== 'live'}>
            <legend>Manual review decision</legend>
            <p className="review-instruction">Check the damage in the photo, then choose an action.</p>
            <label htmlFor="review-action">Action</label>
            <select
              id="review-action"
              value={action}
              onChange={(event) =>
                setAction(event.target.value as typeof action)
              }
            >
              <option value="confirm">Confirm current detection label</option>
              <option value="correct">Correct damage label and accept</option>
              <option value="dismiss">Reject without creating a task</option>
            </select>
            {action === 'correct' && (
              <>
                <label htmlFor="correct-label">Corrected label</label>
                <select
                  id="correct-label"
                  value={label}
                  required
                  onChange={(event) => setLabel(event.target.value)}
                >
                  <option value="">Select a label</option>
                  {labels.classes.map((item) => (
                    <option key={item.label_key} value={item.label_key}>
                      {item.display_name_zh} · {item.label_key}
                    </option>
                  ))}
                </select>
                <p className="field-note">
                  Labels come from the shared dictionary {labels.schema_version}
                  ; Severity, priority and repair duration are calculated by backend rules.
                </p>
              </>
            )}
            <label htmlFor="review-note">Review notes (optional, up to 500 characters)</label>
            <textarea
              id="review-note"
              rows={3}
              maxLength={500}
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
            <p className="field-note review-outcome">{action === 'dismiss' ? 'Rejection retains the inspection without creating a repair task.' : 'Acceptance creates a repair task and retains the original detection and review records.'}</p>
          </fieldset>
          {error !== null && <ErrorState error={error} />}
          {conflict && (
            <p className="notice">
              The record or request has changed. Reload and check before making a new review decision; the old decision is not replayed automatically.
            </p>
          )}
          {uncertain && (
            <p className="notice">
              The save outcome is uncertain. Stay here and retry the original request. Do not switch records or sources or submit another review. Refreshing loses the current retry ID.
            </p>
          )}
          <button
            className="button"
            type="submit"
            disabled={
              busy ||
              conflict ||
              mode !== 'live' ||
              (!uncertain &&
                action !== 'dismiss' &&
                !inspection.detections.length)
            }
          >
            {busy
              ? 'Saving review…'
              : uncertain
                ? 'Retry review with original request'
                : 'Save review decision'}
          </button>
          {busy && <p role="status">Saving. Stay on the current record.</p>}
        </form>
      )}
      </div>
      <div className="workflow-note">
        <button
          className="text-button"
          disabled={busy || uncertain}
          onClick={reload}
        >
          Reload and check
        </button>
        <Link to={`/inspections/${id}`}>View inspection result</Link>
      </div>
    </section>
  )
}

export default function ReviewPage() {
  const { api } = useApi()
  const [params, setParams] = useSearchParams()
  const selected = params.get('inspection') ?? ''
  const detailRef = useRef<HTMLDivElement>(null)
  const selectionToReveal = useRef(selected)
  useEffect(() => {
    selectionToReveal.current = selected
    if (selected && window.matchMedia?.('(max-width: 760px)').matches) {
      detailRef.current?.focus({ preventScroll: true })
    }
  }, [selected])
  const revealSelection = useCallback(() => {
    // The loaded record must exist before scrolling, including direct-link entry.
    // Do not interrupt an operator again after a save or explicit retry.
    if (!selected || selectionToReveal.current !== selected) return
    selectionToReveal.current = ''
    if (window.matchMedia?.('(max-width: 760px)').matches) {
      detailRef.current?.focus({ preventScroll: true })
      detailRef.current?.scrollIntoView?.({ block: 'start', behavior: 'instant' })
    }
  }, [selected])
  const [offset, setOffset] = useState(0)
  const [recordLocked, setRecordLocked] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [queue, setQueue] = useState<Model<'InspectionListResponse'> | null>(
    null,
  )
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => {
    const controller = new AbortController()
    let current = true
    api
      .inspections(
        { status: 'pending_review', limit: 20, offset },
        { signal: controller.signal },
      )
      .then((value) => {
        if (current) {
          setQueue(value)
          setError(null)
        }
      })
      .catch((err) => {
        if (current) setError(err)
      })
      .finally(() => {
        if (current) setLoading(false)
      })
    return () => {
      current = false
      controller.abort()
    }
  }, [api, offset, attempt])
  function refresh() {
    setLoading(true)
    setAttempt((n) => n + 1)
  }
  function page(next: number) {
    setLoading(true)
    setQueue(null)
    setError(null)
    setOffset(next)
  }
  return (
    <div className="review-workspace">
      <div className="page-heading">
        <div>
        <p className="eyebrow">INSPECTION REVIEW</p>
        <h1>Manual review</h1>
        <p className="description">
          Check damage photos and move confirmed repairs into the task queue.
        </p>
        </div>
        <Link className="button secondary" to="/tasks">View accepted tasks →</Link>
      </div>
      <div className="queue-workspace">
      <section className="review-queue" aria-label="Review queue">
        <div className="queue-heading"><h2>Inspections awaiting review</h2><span className="queue-count">{!loading && !error && queue ? queue.total : '—'}</span></div>
        <button className="text-button" disabled={loading} onClick={refresh}>
          Refresh review queue
        </button>
        {loading && <LoadingState />}
        {error !== null && (
          <>
            <ErrorState error={error} />
            {queue && <p>Previous list retained and may be stale. Opening a record reloads it.</p>}
          </>
        )}
        {queue && (
          <>
            <p className="queue-meta">Total {queue.total} pending records · Ordered by submission time</p>
            {!loading && !error && !queue.items.length && (
              <EmptyState
                message={
                  offset
                    ? 'No pending records remain on this page. Go to the previous page.'
                    : 'No inspections are awaiting review.'
                }
              />
            )}
            <ul className="review-list">
              {queue.items.map((item) => (
                <li key={item.inspection_id}>
                  <button
                    className="queue-item-button"
                    aria-label={`${labels.classes.find((label) => label.label_key === item.detections[0]?.label)?.display_name_zh ?? item.detections[0]?.label ?? 'No detection'}, Pending review, inspection ${item.inspection_id}`}
                    disabled={recordLocked}
                    aria-current={
                      selected === item.inspection_id ? 'true' : undefined
                    }
                    onClick={() =>
                      setParams({ inspection: item.inspection_id })
                    }
                  >
                    <span className="queue-item-title"><strong>{labels.classes.find((label) => label.label_key === item.detections[0]?.label)?.display_name_zh ?? item.detections[0]?.label ?? 'No detection'}</strong><span className="status-badge">Pending review</span></span>
                    <span className="queue-item-meta">{item.detections[0] ? `${(item.detections[0].confidence * 100).toFixed(1)}% Confidence` : 'No detection box'} · {item.mode === 'real' ? 'Real inference' : 'Mock detection'}</span>
                    <span className="queue-item-id" title={item.inspection_id}>#{item.inspection_id.slice(0, 8)} <span aria-hidden="true">↗</span></span>
                  </button>
                  <span>
                    {formatSingaporeTime(item.created_at)}
                  </span>
                </li>
              ))}
            </ul>
            <div className="pagination">
              <button
                disabled={loading || offset === 0}
                onClick={() => page(Math.max(0, offset - 20))}
              >
                Previous page
              </button>
              <span>Page {Math.floor(offset / 20) + 1}</span>
              <button
                disabled={loading || offset + 20 >= queue.total}
                onClick={() => page(offset + 20)}
              >
                Next page
              </button>
            </div>
          </>
        )}
      </section>
      <div className="record-pane" ref={detailRef} tabIndex={-1} aria-label="Review details workspace">
      {selected ? (
        <ReviewRecord
          key={selected}
          id={selected}
          onReviewed={refresh}
          onLockChange={setRecordLocked}
          onReady={revealSelection}
        />
      ) : (
        <div className="selection-empty"><span className="selection-icon" aria-hidden="true">{!loading && !error && queue?.total === 0 ? '✓' : '↖'}</span><h2>{!loading && !error && queue?.total === 0 ? 'Review queue cleared' : 'Select an inspection to review'}</h2><p>{!loading && !error && queue?.total === 0 ? 'New pending inspections appear here. View accepted inspections in repair tasks.' : 'Check the photo and model output, then confirm, correct or reject.'}</p><div className="selection-steps"><span><strong>Confirm</strong> Damage type is correct</span><span><strong>Correct</strong> Change the type and accept</span><span><strong>Reject</strong> Retain record without creating a task</span></div></div>
      )}
      </div>
      </div>
    </div>
  )
}
